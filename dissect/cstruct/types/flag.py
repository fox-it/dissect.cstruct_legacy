from dissect.cstruct.types.enum import Enum, EnumInstance


class Flag(Enum):
    """Implements a Flag type.

    Flags can be made using any type. The API for accessing flags and their
    values is very similar to Python 3 native flags.

    Example:
        When using the default C-style parser, the following syntax is supported:

            flag <name> [: <type>] {
                <values>
            };

        For example, a flag that has A=1, B=4 and C=8 could be written like so:

            flag Test : uint16 {
                A, B=4, C
            };
    """

    def __call__(self, value):
        if isinstance(value, int):
            return FlagInstance(self, value)

        return super(Enum, self).__call__(value)


class FlagInstance(EnumInstance):
    """Implements a value instance of a Flag"""

    def __bool__(self):
        return bool(self.value)

    __nonzero__ = __bool__

    def __or__(self, other):
        if hasattr(other, 'value'):
            other = other.value

        return self.__class__(self.enum, self.value | other)

    def __and__(self, other):
        if hasattr(other, 'value'):
            other = other.value

        return self.__class__(self.enum, self.value & other)

    def __xor__(self, other):
        if hasattr(other, 'value'):
            other = other.value

        return self.__class__(self.enum, self.value ^ other)

    __ror__ = __or__
    __rand__ = __and__
    __rxor__ = __xor__

    def __invert__(self):
        return self.__class__(self.enum, ~self.value)

    def __str__(self):
        if self.name is not None:
            return '{}.{}'.format(self.enum.name, self.name)

        members, _ = self.decompose()
        return '{}.{}'.format(
            self.enum.name,
            '|'.join([str(name or value) for name, value in members]),
        )

    def __repr__(self):
        if self.name is not None:
            return '<{}.{}: {}>'.format(self.enum.name, self.name, self.value)

        members, _ = self.decompose()
        return '<{}.{}: {}>'.format(
            self.enum.name,
            '|'.join([str(name or value) for name, value in members]),
            self.value
        )

    @property
    def name(self):
        return self.enum.reverse.get(self.value, None)

    def decompose(self):
        members = []
        not_covered = self.value

        for name, value in self.enum.values.items():
            if value and ((value & self.value) == value):
                members.append((name, value))
                not_covered &= ~value

        if not members:
            members.append((None, self.value))

        members.sort(key=lambda m: m[0], reverse=True)
        if len(members) > 1 and members[0][1] == self.value:
            members.pop(0)

        return members, not_covered
