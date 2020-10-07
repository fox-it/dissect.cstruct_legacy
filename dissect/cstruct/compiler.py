import struct
from collections import OrderedDict
from dissect.cstruct.bitbuffer import BitBuffer
from dissect.cstruct.expression import Expression
from dissect.cstruct.types.base import Array
from dissect.cstruct.types.chartype import CharType
from dissect.cstruct.types.instance import Instance
from dissect.cstruct.types.structure import Structure, Union
from dissect.cstruct.types.wchartype import WcharType
from dissect.cstruct.types.packedtype import PackedType
from dissect.cstruct.types.flag import Flag, FlagInstance
from dissect.cstruct.types.enum import Enum, EnumInstance
from dissect.cstruct.types.bytesinteger import BytesInteger
from dissect.cstruct.types.pointer import Pointer, PointerInstance


class Compiler(object):
    """Compiler for cstruct structures. Creates somewhat optimized parsing code."""

    TYPES = (
        Structure,
        Pointer,
        Enum,
        Flag,
        Array,
        PackedType,
        CharType,
        WcharType,
        BytesInteger,
    )

    COMPILE_TEMPLATE = """
class {name}(Structure):
    def __init__(self, cstruct, structure, source=None):
        self.structure = structure
        self.source = source
        super().__init__(cstruct, structure.name, structure.fields, anonymous=structure.anonymous)

    def _read(self, stream):
        r = OrderedDict()
        sizes = {{}}
        bitreader = BitBuffer(stream, self.cstruct.endian)

{read_code}

        return Instance(self, r, sizes)

    def add_field(self, name, type_, offset=None):
        raise NotImplementedError("Can't add fields to a compiled structure")

    def __repr__(self):
        return '<Structure {name} +compiled>'
"""

    def __init__(self, cstruct):
        self.cstruct = cstruct

    def compile(self, structure):
        if isinstance(structure, Union):
            # TODO: Compiling unions should be supported
            return structure

        structure_name = structure.name

        try:
            # Generate struct class based on provided structure type
            source = self.gen_struct_class(structure_name, structure)
        except TypeError:
            return structure

        # Create code object that can be executed later on
        code_object = compile(
            source,
            f'<compiled {structure_name}>',
            'exec',
        )

        env = {
            'OrderedDict': OrderedDict,
            'Structure': Structure,
            'Instance': Instance,
            'Expression': Expression,
            'EnumInstance': EnumInstance,
            'FlagInstance': FlagInstance,
            'PointerInstance': PointerInstance,
            'BytesInteger': BytesInteger,
            'BitBuffer': BitBuffer,
            'struct': struct,
            'range': range,
        }

        exec(code_object, env)
        return env[structure_name](self.cstruct, structure, source)

    def gen_struct_class(self, name, structure):
        blocks = []
        classes = []
        cur_block = []
        read_size = 0
        prev_was_bits = False

        for field in structure.fields:
            field_type = self.cstruct.resolve(field.type)

            if not isinstance(field_type, self.TYPES):
                raise TypeError(f"Unsupported type for compiler: {field_type}")

            if isinstance(field_type, Structure) \
                    or (isinstance(field_type, Array) and isinstance(field_type.type, Structure)):

                blocks.append(self.gen_read_block(read_size, cur_block))

                struct_read = 's = stream.tell()\n'
                if isinstance(field_type, Array):
                    num = field_type.count

                    if isinstance(num, Expression):
                        num = 'max(0, Expression(self.cstruct, "{expr}").evaluate(r))'.format(expr=num.expression)

                    struct_read += (
                        'r["{name}"] = []\n'
                        'for _ in range({num}):\n'
                        '    r["{name}"].append(self.lookup["{name}"].type.type._read(stream))\n'.format(
                            name=field.name,
                            num=num,
                        )
                    )
                    struct_read += 'sizes["{name}"] = stream.tell() - s'.format(name=field.name)
                elif isinstance(field_type, Structure) and field_type.anonymous:
                    struct_read += 'v = self.lookup["{name}"].type._read(stream)\n'.format(name=field.name)
                    struct_read += 'r.update(v._values)\n'
                    struct_read += 'sizes.update(v._sizes)'
                else:
                    struct_read += 'r["{name}"] = self.lookup["{name}"].type._read(stream)\n'.format(name=field.name)
                    struct_read += 'sizes["{name}"] = stream.tell() - s'.format(name=field.name)

                blocks.append(struct_read)
                read_size = 0
                cur_block = []
                continue

            if field.bits:
                blocks.append(self.gen_read_block(read_size, cur_block))
                blocks.append(
                    'r["{name}"] = bitreader.read(self.cstruct.{type_name}, {bits})'.format(
                        name=field.name,
                        type_name=field.type.name,
                        bits=field.bits
                    )
                )

                read_size = 0
                cur_block = []
                prev_was_bits = True
                continue

            if prev_was_bits:
                blocks.append('bitreader.reset()')
                prev_was_bits = False

            try:
                count = len(field_type)
                read_size += count
                cur_block.append(field)
            except TypeError:
                if cur_block:
                    blocks.append(self.gen_read_block(read_size, cur_block))

                blocks.append(self.gen_dynamic_block(field))
                read_size = 0
                cur_block = []

        if len(cur_block):
            blocks.append(self.gen_read_block(read_size, cur_block))

        read_code = '\n\n'.join(blocks)
        read_code = '\n'.join(['    ' * 2 + line for line in read_code.split('\n')])

        classes.append(
            self.COMPILE_TEMPLATE.format(
                name=name,
                read_code=read_code
            )
        )
        return '\n\n'.join(classes)

    def gen_read_block(self, size, block):
        template = (
            'buf = stream.read({size})\n'
            'if len(buf) != {size}: raise EOFError()\n'
            'data = struct.unpack(self.cstruct.endian + "{{}}", buf)\n'
            '{{}}'.format(size=size)
        )

        read_code = []
        fmt = []

        cur_type = None
        cur_count = 0

        buf_offset = 0
        data_offset = 0

        for field in block:
            field_type = self.cstruct.resolve(field.type)
            read_type = field_type

            count = 1
            data_count = 1

            if isinstance(read_type, (Enum, Flag)):
                read_type = read_type.type
            elif isinstance(read_type, Pointer):
                read_type = self.cstruct.pointer

            if isinstance(field_type, Array):
                count = read_type.count
                data_count = count
                read_type = read_type.type

                if isinstance(read_type, (Enum, Flag)):
                    read_type = read_type.type
                elif isinstance(read_type, Pointer):
                    read_type = self.cstruct.pointer

                if isinstance(read_type, (CharType, WcharType, BytesInteger)):
                    read_slice = '{}:{}'.format(
                        buf_offset, buf_offset + (count * read_type.size)
                    )
                else:
                    read_slice = '{}:{}'.format(data_offset, data_offset + count)
            elif isinstance(read_type, CharType):
                read_slice = f'{buf_offset}:{buf_offset + 1}'
            elif isinstance(read_type, (WcharType, BytesInteger)):
                read_slice = '{}:{}'.format(buf_offset, buf_offset + read_type.size)
            else:
                read_slice = str(data_offset)

            if not cur_type:
                if isinstance(read_type, PackedType):
                    cur_type = read_type.packchar
                else:
                    cur_type = 'x'

            if isinstance(read_type, (PackedType, CharType, WcharType, BytesInteger, Enum, Flag)):
                char_count = count

                if isinstance(read_type, (CharType, WcharType, BytesInteger)):
                    data_count = 0
                    pack_char = 'x'
                    char_count *= read_type.size
                else:
                    pack_char = read_type.packchar

                if cur_type != pack_char:
                    fmt.append('{}{}'.format(cur_count, cur_type))
                    cur_count = 0

                cur_count += char_count
                cur_type = pack_char

            if isinstance(read_type, BytesInteger):
                getter = 'BytesInteger.parse(buf[{slice}], {size}, {count}, {signed}, self.cstruct.endian){data_slice}'

                getter = getter.format(
                    slice=read_slice,
                    size=read_type.size,
                    count=count,
                    signed=read_type.signed,
                    data_slice='[0]' if count == 1 else '',
                )
            elif isinstance(read_type, (CharType, WcharType)):
                getter = 'buf[{}]'.format(read_slice)

                if isinstance(read_type, WcharType):
                    getter += ".decode('utf-16-le' if self.cstruct.endian == '<' else 'utf-16-be')"
            else:
                getter = 'data[{}]'.format(read_slice)

            if isinstance(field_type, (Enum, Flag)):
                getter = '{enum_type}Instance(self.cstruct.{type_name}, {getter})'.format(
                    enum_type=field_type.__class__.__name__,
                    type_name=field_type.name,
                    getter=getter
                )
            elif isinstance(field_type, Array) and isinstance(field_type.type, (Enum, Flag)):
                getter = '[{enum_type}Instance(self.cstruct.{type_name}, d) for d in {getter}]'.format(
                    enum_type=field_type.type.__class__.__name__,
                    type_name=field_type.type.name,
                    getter=getter
                )
            elif isinstance(field_type, Pointer):
                getter = 'PointerInstance(self.cstruct.{type_name}, stream, {getter}, r)'.format(
                    type_name=field_type.type.name,
                    getter=getter
                )
            elif isinstance(field_type, Array) and isinstance(field_type.type, Pointer):
                getter = '[PointerInstance(self.cstruct.{type_name}, stream, d, r) for d in {getter}]'.format(
                    type_name=field_type.type.name,
                    getter=getter
                )
            elif isinstance(field_type, Array) and isinstance(read_type, PackedType):
                getter = 'list({})'.format(getter)

            read_code.append(
                'r["{name}"] = {getter}'.format(name=field.name, getter=getter)
            )
            read_code.append(
                'sizes["{name}"] = {size}'.format(name=field.name, size=count * read_type.size)
            )

            data_offset += data_count
            buf_offset += count * read_type.size

        if cur_count:
            fmt.append('{}{}'.format(cur_count, cur_type))

        return template.format(''.join(fmt), '\n'.join(read_code))

    def gen_dynamic_block(self, field):
        if not isinstance(field.type, Array):
            raise TypeError(f"Only Array can be dynamic, got {field.type!r}")

        field_type = self.cstruct.resolve(field.type.type)
        reader = None

        if isinstance(field_type, (Enum, Flag)):
            field_type = field_type.type

        if not field.type.count:  # Null terminated
            if isinstance(field_type, PackedType):
                reader = (
                    't = []\n'
                    'while True:\n'
                    '    d = stream.read({size})\n'
                    '    if len(d) != {size}: raise EOFError()\n'
                    '    v = struct.unpack(self.cstruct.endian + "{packchar}", d)[0]\n'
                    '    if v == 0: break\n'
                    '    t.append(v)'.format(size=field_type.size, packchar=field_type.packchar)
                )

            elif isinstance(field_type, (CharType, WcharType)):
                reader = (
                    't = []\n'
                    'while True:\n'
                    '    c = stream.read({size})\n'
                    '    if len(c) != {size}: raise EOFError()\n'
                    '    if c == b"{null}": break\n'
                    '    t.append(c)\n'
                    't = b"".join(t)'.format(size=field_type.size, null='\\x00' * field_type.size)
                )

                if isinstance(field_type, WcharType):
                    reader += ".decode('utf-16-le' if self.cstruct.endian == '<' else 'utf-16-be')"
            elif isinstance(field_type, BytesInteger):
                reader = (
                    't = []\n'
                    'while True:\n'
                    '    d = stream.read({size})\n'
                    '    if len(d) != {size}: raise EOFError()\n'
                    '    v = BytesInteger.parse(d, {size}, 1, {signed}, self.cstruct.endian)\n'
                    '    if v == 0: break\n'
                    '    t.append(v)'.format(size=field_type.size, signed=field_type.signed)
                )

            if isinstance(field_type, (Enum, Flag)):
                reader += '\nt = [{enum_type}Instance(self.cstruct.{type_name}, d) for d in t]'.format(
                    enum_type=field_type.__class__.__name__,
                    type_name=field_type.name
                )

            if not reader:
                raise TypeError(f"Couldn't compile a reader for array {field!r}, {field_type!r}.")

            return 's = stream.tell()\n{reader}\nr["{name}"]' \
                   ' = t\nsizes["{name}"] = stream.tell() - s'.format(reader=reader, name=field.name)

        expr = field.type.count.expression
        expr_read = (
            'dynsize = max(0, Expression(self.cstruct, "{expr}").evaluate(r))\n'
            'buf = stream.read(dynsize * {type_size})\n'
            'if len(buf) != dynsize * {type_size}: raise EOFError()\n'
            'r["{name}"] = {{reader}}\n'
            'sizes["{name}"] = dynsize * {type_size}'.format(expr=expr, name=field.name, type_size=field_type.size)
        )

        if isinstance(field_type, PackedType):
            reader = 'list(struct.unpack(self.cstruct.endian + "{{:d}}{packchar}".format(dynsize), buf))'.format(
                packchar=field_type.packchar,
            )
        elif isinstance(field_type, (CharType, WcharType)):
            reader = 'buf'
            if isinstance(field_type, WcharType):
                reader += ".decode('utf-16-le' if self.cstruct.endian == '<' else 'utf-16-be')"
        elif isinstance(field_type, BytesInteger):
            reader = 'BytesInteger.parse(buf, {size}, dynsize, {signed}, self.cstruct.endian)'.format(
                size=field_type.size,
                signed=field_type.signed
            )

        if isinstance(field_type, (Enum, Flag)):
            reader += '[{enum_type}Instance(self.cstruct.{type_name}, d) for d in {reader}]'.format(
                enum_type=field_type.__class__.__name__,
                type_name=field_type.name,
                reader=reader
            )

        return expr_read.format(reader=reader, size=None)
