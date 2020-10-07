from dissect.cstruct.types.base import RawType


class Enum(RawType):
    """Implements an Enum type.

    Enums can be made using any type. The API for accessing enums and their
    values is very similar to Python 3 native enums.

    Example:
        When using the default C-style parser, the following syntax is supported:

            enum <name> [: <type>] {
                <values>
            };

        For example, an enum that has A=1, B=5 and C=6 could be written like so:

            enum Test : uint16 {
                A, B=5, C
            };
    """

    def __init__(self, cstruct, name, type_, values):
        self.type = type_
        self.values = values
        self.reverse = {}

        for k, v in values.items():
            self.reverse[v] = k

        super().__init__(cstruct, name, len(self.type))

    def __call__(self, value):
        if isinstance(value, int):
            return EnumInstance(self, value)
        return super(Enum, self).__call__(value)

    def __getitem__(self, attr):
        return self(self.values[attr])

    def __getattr__(self, attr):
        try:
            return self(self.values[attr])
        except KeyError:
            raise AttributeError(attr)

    def __contains__(self, attr):
        return attr in self.values

    def _read(self, stream):
        v = self.type._read(stream, )
        return self(v)

    def _read_array(self, stream, count):
        return list(map(self, self.type._read_array(stream, count)))

    def _read_0(self, stream):
        return list(map(self, self.type._read_0(stream)))

    def _write(self, stream, data):
        data = data.value if isinstance(data, EnumInstance) else data
        return self.type._write(stream, data)

    def _write_array(self, stream, data):
        data = [d.value if isinstance(d, EnumInstance) else d for d in data]
        return self.type._write_array(stream, data)

    def _write_0(self, stream, data):
        data = [d.value if isinstance(d, EnumInstance) else d for d in data]
        return self.type._write_0(stream, data)

    def default(self):
        return self(0)

    def default_array(self, count):
        return [self.default() for _ in range(count)]


class EnumInstance(object):
    """Implements a value instance of an Enum"""

    def __init__(self, enum, value):
        self.enum = enum
        self.value = value

    def __eq__(self, value):
        if isinstance(value, EnumInstance) and value.enum is not self.enum:
            return False

        if hasattr(value, 'value'):
            value = value.value

        return self.value == value

    def __ne__(self, value):
        return self.__eq__(value) is False

    def __hash__(self):
        return hash((self.enum, self.value))

    def __str__(self):
        return '{}.{}'.format(self.enum.name, self.name)

    def __repr__(self):
        return '<{}.{}: {}>'.format(self.enum.name, self.name, self.value)

    @property
    def name(self):
        if self.value not in self.enum.reverse:
            return '{}_{}'.format(self.enum.name, self.value)

        return self.enum.reverse[self.value]
