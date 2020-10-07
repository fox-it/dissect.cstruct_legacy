from dissect.cstruct.exceptions import NullPointerDereference
from dissect.cstruct.types.base import Array, RawType


class Pointer(RawType):
    """Implements a pointer to some other type."""

    def __init__(self, cstruct, target):
        self.cstruct = cstruct
        self.type = target
        super().__init__(cstruct)

    def __len__(self):
        return len(self.cstruct.pointer)

    def __repr__(self):
        return '<Pointer {!r}>'.format(self.type)

    def _read(self, stream, ctx):
        addr = self.cstruct.pointer(stream)
        return PointerInstance(self.type, stream, addr, ctx)


class PointerInstance(object):
    """Like the Instance class, but for structures referenced by a pointer."""

    def __init__(self, type_name, stream, addr, ctx):
        self._stream = stream
        self._type = type_name
        self._addr = addr
        self._ctx = ctx
        self._value = None

    def __getattr__(self, attr):
        return getattr(self._get(), attr)

    def __str__(self):
        return str(self._get())

    def __nonzero__(self):
        return self._addr != 0

    def __repr__(self):
        return "<Pointer {!r} @ 0x{:x}>".format(self._type, self._addr)

    def _get(self):
        if self._addr == 0:
            raise NullPointerDereference()

        if self._value is None:
            # Read current position of file read/write pointer
            position = self._stream.tell()
            # Reposition the file read/write pointer
            self._stream.seek(self._addr)

            if isinstance(self._type, Array):
                value = self._type._read(self._stream, self._ctx)
            else:
                value = self._type._read(self._stream, )

            self._stream.seek(position)
            self._value = value

        return self._value
