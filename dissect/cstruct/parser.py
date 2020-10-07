import re
import ast
from dissect.cstruct.compiler import Compiler
from dissect.cstruct.exceptions import ParserError
from dissect.cstruct.expression import Expression
from dissect.cstruct.types.base import Array
from dissect.cstruct.types.structure import Structure, Field, Union
from dissect.cstruct.types.flag import Flag
from dissect.cstruct.types.enum import Enum
from dissect.cstruct.types.pointer import Pointer


class Parser(object):
    """Base class for definition parsers.

    Args:
        cs: An instance of cstruct.
    """

    def __init__(self, cs):
        self.cstruct = cs

    def parse(self, data):
        """This function should parse definitions to cstruct types.

        Args:
            data: Data to parse definitions from, usually a string.
        """
        raise NotImplementedError()


class TokenParser(Parser):
    """
    Args:
        cs: An instance of cstruct.
        compiled: Whether structs should be compiled or not.
    """

    def __init__(self, cs, compiled=True):
        super().__init__(cs)

        self.compiler = Compiler(self.cstruct) if compiled else None
        self.TOK = self._tokencollection()

    @staticmethod
    def _tokencollection():
        TOK = TokenCollection()
        TOK.add(r'#\[(?P<values>[^\]]+)\](?=\s*)', 'CONFIG_FLAG')
        TOK.add(r'#define\s+(?P<name>[^\s]+)\s+(?P<value>[^\r\n]+)\s*', 'DEFINE')
        TOK.add(r'typedef(?=\s)', 'TYPEDEF')
        TOK.add(r'(?:struct|union)(?=\s|{)', 'STRUCT')
        TOK.add(r'(?P<enumtype>enum|flag)\s+(?P<name>[^\s:{]+)\s*(:\s'
                r'*(?P<type>[^\s]+)\s*)?\{(?P<values>[^}]+)\}\s*(?=;)', 'ENUM')
        TOK.add(r'(?<=})\s*(?P<defs>(?:[a-zA-Z0-9_]+\s*,\s*)+[a-zA-Z0-9_]+)\s*(?=;)', 'DEFS')
        TOK.add(r'(?P<name>\*?[a-zA-Z0-9_]+)(?:\s*:\s*(?P<bits>\d+))?(?:\[(?P<count>[^;\n]*)\])?\s*(?=;)', 'NAME')
        TOK.add(r'[a-zA-Z_][a-zA-Z0-9_]*', 'IDENTIFIER')
        TOK.add(r'[{}]', 'BLOCK')
        TOK.add(r'\$(?P<name>[^\s]+) = (?P<value>{[^}]+})\w*[\r\n]+', 'LOOKUP')
        TOK.add(r';', 'EOL')
        TOK.add(r'\s+', None)
        TOK.add(r'.', None)

        return TOK

    def _constant(self, tokens):
        const = tokens.consume()
        pattern = self.TOK.patterns[self.TOK.DEFINE]
        match = pattern.match(const.value).groupdict()

        value = match['value']
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass

        try:
            value = Expression(self.cstruct, value).evaluate()
        except Exception:
            pass

        self.cstruct.consts[match['name']] = value

    def _enum(self, tokens):
        # We cheat with enums because the entire enum is in the token
        etok = tokens.consume()

        pattern = self.TOK.patterns[self.TOK.ENUM]
        # Dirty trick because the regex expects a ; but we don't want it to be part of the value
        # TODO: do we?
        d = pattern.match(etok.value + ';').groupdict()
        enumtype = d['enumtype']

        nextval = 0
        if enumtype == 'flag':
            nextval = 1

        values = {}
        for line in d['values'].splitlines():
            for v in line.split(','):
                key, sep, val = v.partition('=')
                key = key.strip()
                val = val.strip()
                if not key:
                    continue
                if not val:
                    val = nextval
                else:
                    val = Expression(self.cstruct, val).evaluate()

                if enumtype == 'flag':
                    high_bit = val.bit_length() - 1
                    nextval = 2 ** (high_bit + 1)
                else:
                    nextval = val + 1

                values[key] = val

        if not d['type']:
            d['type'] = 'uint32'

        enumcls = Enum
        if enumtype == 'flag':
            enumcls = Flag

        enum = enumcls(
            self.cstruct, d['name'], self.cstruct.resolve(d['type']), values
        )
        self.cstruct.addtype(enum.name, enum)

        tokens.eol()

    def _typedef(self, tokens):
        tokens.consume()
        type_ = None

        if tokens.next == self.TOK.IDENTIFIER:
            ident = tokens.consume()
            type_ = self.cstruct.resolve(ident.value)
        elif tokens.next == self.TOK.STRUCT:
            # The register thing is a bit dirty
            # Basically consumes all NAME tokens and
            # registers the struct
            type_ = self._struct(tokens, register=True)

        names = self._names(tokens)
        for name in names:
            self.cstruct.addtype(name, type_)

    def _struct(self, tokens, register=False):
        stype = tokens.consume()

        names = []
        if tokens.next == self.TOK.IDENTIFIER:
            ident = tokens.consume()
            names.append(ident.value)

        if tokens.next == self.TOK.NAME:
            if not len(names):
                raise ParserError("line {:d}: unexpected anonymous struct".format(
                    self._lineno(tokens.next)
                ))
            return self.cstruct.resolve(names[0])

        if tokens.next != self.TOK.BLOCK:
            raise ParserError(f"line {self._lineno(tokens.next):d}: expected start of block '{tokens.next}'")

        fields = []
        tokens.consume()
        while len(tokens):
            if tokens.next == self.TOK.BLOCK and tokens.next.value == '}':
                tokens.consume()
                break

            field = self._parse_field(tokens)
            fields.append(field)

        # Parsing names consumes the EOL token
        names.extend(self._names(tokens))
        name = names[0] if names else None

        if stype.value.startswith('union'):
            class_ = Union
        else:
            class_ = Structure
        is_anonymous = False
        if not name:
            is_anonymous = True
            name = self.cstruct._next_anonymous()

        st = class_(self.cstruct, name, fields, anonymous=is_anonymous)
        if self.compiler and 'nocompile' not in tokens.flags:
            st = self.compiler.compile(st)

        # This is pretty dirty
        if register:
            if not names:
                raise ParserError("line {:d}: struct has no name".format(
                    self._lineno(stype)
                ))

            for name in names:
                self.cstruct.addtype(name, st)
        tokens.reset_flags()
        return st

    def _lookup(self, tokens):
        # Just like enums, we cheat and have the entire lookup in the token
        ltok = tokens.consume()

        pattern = self.TOK.patterns[self.TOK.LOOKUP]
        # Dirty trick because the regex expects a ; but we don't want it to be part of the value
        # TODO: do we?
        m = pattern.match(ltok.value + ';')
        d = ast.literal_eval(m.group(2))
        self.cstruct.lookups[m.group(1)] = dict(
            [(self.cstruct.consts[k], v) for k, v in d.items()]
        )

    def _parse_field(self, tokens):
        type_ = None
        if tokens.next == self.TOK.IDENTIFIER:
            ident = tokens.consume()
            type_ = self.cstruct.resolve(ident.value)
        elif tokens.next == self.TOK.STRUCT:
            type_ = self._struct(tokens)
            if tokens.next != self.TOK.NAME:
                return Field(type_.name, type_)

        if tokens.next != self.TOK.NAME:
            raise ParserError("line {:d}: expected name".format(self._lineno(tokens.next)))
        nametok = tokens.consume()

        pattern = self.TOK.patterns[self.TOK.NAME]
        # Dirty trick because the regex expects a ; but we don't want it to be part of the value
        d = pattern.match(nametok.value + ';').groupdict()

        name = d['name']
        count = d['count']
        if count is not None:
            if count == '':
                count = None
            else:
                count = Expression(self.cstruct, count)
                try:
                    count = count.evaluate()
                except Exception:
                    pass

            type_ = Array(self.cstruct, type_, count)

        if name.startswith('*'):
            name = name[1:]
            type_ = Pointer(self.cstruct, type_)

        tokens.eol()
        return Field(name, type_, int(d['bits']) if d['bits'] else None)

    def _names(self, tokens):
        names = []
        while True:
            if tokens.next == self.TOK.EOL:
                tokens.eol()
                break

            if tokens.next not in (self.TOK.NAME, self.TOK.DEFS):
                break

            ntoken = tokens.consume()
            if ntoken == self.TOK.NAME:
                names.append(ntoken.value)
            elif ntoken == self.TOK.DEFS:
                for name in ntoken.value.strip().split(','):
                    names.append(name.strip())

        return names

    @staticmethod
    def _remove_comments(string):
        # https://stackoverflow.com/a/18381470
        pattern = r"(\".*?\"|\'.*?\')|(/\*.*?\*/|//[^\r\n]*$)"
        # first group captures quoted strings (double or single)
        # second group captures comments (//single-line or /* multi-line */)
        regex = re.compile(pattern, re.MULTILINE | re.DOTALL)

        def _replacer(match):
            # if the 2nd group (capturing comments) is not None,
            # it means we have captured a non-quoted (real) comment string.
            if match.group(2) is not None:
                return ""  # so we will return empty to remove the comment
            else:  # otherwise, we will return the 1st group
                return match.group(1)  # captured quoted-string

        return regex.sub(_replacer, string)

    @staticmethod
    def _lineno(tok):
        """Quick and dirty line number calculator"""

        match = tok.match
        return match.string.count('\n', 0, match.start())

    def _config_flag(self, tokens):
        flag_token = tokens.consume()
        pattern = self.TOK.patterns[self.TOK.CONFIG_FLAG]
        tok_dict = pattern.match(flag_token.value).groupdict()
        tokens.flags.extend(tok_dict['values'].split(','))

    def parse(self, data):
        scanner = re.Scanner(self.TOK.tokens)
        data = self._remove_comments(data)
        tokens, remaining = scanner.scan(data)

        if len(remaining):
            raise ParserError("line {:d}: invalid syntax in definition".format(
                data.count('\n', 0, len(data) - len(remaining))
            ))

        tokens = TokenConsumer(tokens)
        while True:
            token = tokens.next
            if token is None:
                break

            if token == self.TOK.CONFIG_FLAG:
                self._config_flag(tokens)
            elif token == self.TOK.DEFINE:
                self._constant(tokens)
            elif token == self.TOK.TYPEDEF:
                self._typedef(tokens)
            elif token == self.TOK.STRUCT:
                self._struct(tokens, register=True)
            elif token == self.TOK.ENUM:
                self._enum(tokens)
            elif token == self.TOK.LOOKUP:
                self._lookup(tokens)
            else:
                raise ParserError(f"line {self._lineno(token):d}: unexpected token {token!r}")


class CStyleParser(Parser):
    """Definition parser for C-like structure syntax.

    Args:
        cs: An instance of cstruct
        compiled: Whether structs should be compiled or not.
    """

    def __init__(self, cs, compiled=True):
        self.compiled = compiled
        super().__init__(cs)

    def _constants(self, data):
        r = re.finditer(r'#define\s+(?P<name>[^\s]+)\s+(?P<value>[^\r\n]+)\s*\n', data)
        for t in r:
            d = t.groupdict()
            v = d['value'].rsplit('//')[0]

            try:
                v = ast.literal_eval(v)
            except (ValueError, SyntaxError):
                pass

            self.cstruct.consts[d['name']] = v

    def _enums(self, data):
        r = re.finditer(
            r'(?P<enumtype>enum|flag)\s+(?P<name>[^\s:{]+)\s*(:\s*(?P<type>[^\s]+)\s*)?\{(?P<values>[^}]+)\}\s*;',
            data,
        )
        for t in r:
            d = t.groupdict()
            enumtype = d['enumtype']

            nextval = 0
            if enumtype == 'flag':
                nextval = 1

            values = {}
            for line in d['values'].split('\n'):
                line, sep, comment = line.partition("//")
                for v in line.split(","):
                    key, sep, val = v.partition("=")
                    key = key.strip()
                    val = val.strip()
                    if not key:
                        continue
                    if not val:
                        val = nextval
                    else:
                        val = Expression(self.cstruct, val).evaluate()

                    if enumtype == 'flag':
                        high_bit = val.bit_length() - 1
                        nextval = 2 ** (high_bit + 1)
                    else:
                        nextval = val + 1

                    values[key] = val

            if not d['type']:
                d['type'] = 'uint32'

            enumcls = Enum
            if enumtype == 'flag':
                enumcls = Flag

            enum = enumcls(
                self.cstruct, d['name'], self.cstruct.resolve(d['type']), values
            )
            self.cstruct.addtype(enum.name, enum)

    def _structs(self, data):
        compiler = Compiler(self.cstruct)
        r = re.finditer(
            r'(#(?P<flags>(?:compile))\s+)?'
            r'((?P<typedef>typedef)\s+)?'
            r'(?P<type>[^\s]+)\s+'
            r'(?P<name>[^\s]+)?'
            r'(?P<fields>'
            r'\s*{[^}]+\}(?P<defs>\s+[^;\n]+)?'
            r')?\s*;',
            data,
        )
        for t in r:
            d = t.groupdict()

            if d['name']:
                name = d['name']
            elif d['defs']:
                name = d['defs'].strip().split(',')[0].strip()
            else:
                raise ParserError("No name for struct")

            if d['type'] == 'struct':
                data = self._parse_fields(d['fields'][1:-1].strip())
                st = Structure(self.cstruct, name, data)
                if d['flags'] == 'compile' or self.compiled:
                    st = compiler.compile(st)
            elif d['typedef'] == 'typedef':
                st = d['type']
            else:
                continue

            if d['name']:
                self.cstruct.addtype(d['name'], st)

            if d['defs']:
                for td in d['defs'].strip().split(','):
                    td = td.strip()
                    self.cstruct.addtype(td, st)

    def _parse_fields(self, s):
        fields = re.finditer(
            r'(?P<type>[^\s]+)\s+(?P<name>[^\s\[:]+)(:(?P<bits>\d+))?(\[(?P<count>[^;\n]*)\])?;',
            s,
        )

        result = []
        for f in fields:
            d = f.groupdict()
            if d['type'].startswith('//'):
                continue

            type_ = self.cstruct.resolve(d['type'])

            d['name'] = d['name'].replace('(', '').replace(')', '')

            # Maybe reimplement lazy type references later
            # _type = TypeReference(self, d['type'])
            if d['count'] is not None:
                if d['count'] == '':
                    count = None
                else:
                    count = Expression(self.cstruct, d['count'])
                    try:
                        count = count.evaluate()
                    except Exception:
                        pass

                type_ = Array(self.cstruct, type_, count)

            if d['name'].startswith('*'):
                d['name'] = d['name'][1:]
                type_ = Pointer(self.cstruct, type_)

            field = Field(d['name'], type_, int(d['bits']) if d['bits'] else None)
            result.append(field)

        return result

    def _lookups(self, data, consts):
        r = re.finditer(r'\$(?P<name>[^\s]+) = ({[^}]+})\w*\n', data)

        for t in r:
            d = ast.literal_eval(t.group(2))
            self.cstruct.lookups[t.group(1)] = dict(
                [(self.cstruct.consts[k], v) for k, v in d.items()]
            )

    # TODO: Implement proper parsing
    def parse(self, data):
        self._constants(data)
        self._enums(data)
        self._structs(data)
        self._lookups(data, self.cstruct.consts)


class Token(object):
    __slots__ = ('token', 'value', 'match')

    def __init__(self, token, value, match):
        self.token = token
        self.value = value
        self.match = match

    def __eq__(self, other):
        if isinstance(other, Token):
            other = other.token

        return self.token == other

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return "<Token.{} value={!r}>".format(self.token, self.value)


class TokenCollection(object):
    def __init__(self):
        self.tokens = []
        self.lookup = {}
        self.patterns = {}

    def __getattr__(self, attr):
        try:
            return self.lookup[attr]
        except AttributeError:
            pass

        return object.__getattribute__(self, attr)

    def add(self, regex, name):
        if name is None:
            self.tokens.append((regex, None))
        else:
            self.lookup[name] = name
            self.patterns[name] = re.compile(regex)
            self.tokens.append((regex, lambda s, t: Token(name, t, s.match)))


class TokenConsumer(object):
    def __init__(self, tokens):
        self.tokens = tokens
        self.flags = []

    def __contains__(self, token):
        return token in self.tokens

    def __len__(self):
        return len(self.tokens)

    def __repr__(self):
        return '<TokenConsumer next={!r}>'.format(self.next)

    @property
    def next(self):
        try:
            return self.tokens[0]
        except IndexError:
            return None

    def consume(self):
        return self.tokens.pop(0)

    def reset_flags(self):
        self.flags = []

    def eol(self):
        token = self.consume()
        if token.token != 'EOL':
            raise ParserError("line {:d}: expected EOL".format(self._lineno(token)))
