from io import BytesIO
from dissect.cstruct.expression import Expression


class BaseType(object):
    """Base class for cstruct type classes."""

    def __init__(self, cstruct):
        self.cstruct = cstruct

    def __getitem__(self, count):
        return Array(self.cstruct, self, count)

    def __call__(self, *args, **kwargs):
        if len(args) > 0:
            return self.read(*args, **kwargs)

        result = self.default()
        if kwargs:
            for k, v in kwargs.items():
                setattr(result, k, v)

        return result

    def reads(self, data):
        """Parse the given data according to the type that implements this class.

        Args:
            data: Byte string to parse.

        Returns:
            The parsed value of this type.
        """

        return self._read(BytesIO(data))

    def dumps(self, data):
        """Dump the given data according to the type that implements this class.

        Args:
            data: Data to dump.

        Returns:
            The resulting bytes.
        """
        out = BytesIO()
        self._write(out, data)
        return out.getvalue()

    def read(self, obj, *args, **kwargs):
        """Parse the given data according to the type that implements this class.

        Args:
            obj: Data to parse. Can be a (byte) string or a file-like object.

        Returns:
            The parsed value of this type.
        """
        if isinstance(obj, (str, bytes, memoryview)):
            return self.reads(obj)

        return self._read(obj)

    def write(self, stream, data):
        """Write the given data to a writable file-like object according to the
        type that implements this class.

        Args:
            stream: Writable file-like object to write to.
            data: Data to write.

        Returns:
            The amount of bytes written.
        """
        return self._write(stream, data)

    def _read(self, stream):
        raise NotImplementedError()

    def _read_array(self, stream, count):
        return [self._read(stream) for _ in range(count)]

    def _read_0(self, stream):
        raise NotImplementedError()

    def _write(self, stream, data):
        raise NotImplementedError()

    def _write_array(self, stream, data):
        num = 0
        for i in data:
            num += self._write(stream, i)

        return num

    def _write_0(self, stream, data):
        raise NotImplementedError()

    def default(self):
        """Return a default value of this type."""
        raise NotImplementedError()

    def default_array(self, count):
        """Return a default array of this type."""
        return [self.default() for _ in range(count)]


class Array(BaseType):
    """Implements a fixed or dynamically sized array type.

    Example:
        When using the default C-style parser, the following syntax is supported:

            x[3] -> 3 -> static length.
            x[] -> None -> null-terminated.
            x[expr] -> expr -> dynamic length.
    """

    def __init__(self, cstruct, type_, count):
        self.type = type_
        self.count = count
        self.null_terminated = self.count is None
        self.dynamic = isinstance(self.count, Expression)
        super().__init__(cstruct)

    def __repr__(self):
        if self.null_terminated:
            return '{0!r}[]'.format(self.type)

        return '{0!r}[{1}]'.format(self.type, self.count)

    def __len__(self):
        if self.dynamic or self.null_terminated:
            raise TypeError("Dynamic size")

        return len(self.type) * self.count

    def _read(self, stream, context=None):
        if self.null_terminated:
            return self.type._read_0(stream)

        if self.dynamic:
            count = self.count.evaluate(context)
        else:
            count = self.count

        return self.type._read_array(stream, max(0, count))

    def _write(self, f, data):
        if self.null_terminated:
            return self.type._write_0(f, data)

        return self.type._write_array(f, data)

    def default(self):
        if self.dynamic or self.null_terminated:
            return []

        return self.type.default_array(self.count)


class RawType(BaseType):
    """Base class for raw types that have a name and size."""

    def __init__(self, cstruct, name=None, size=0):
        self.name = name
        self.size = size
        super().__init__(cstruct)

    def __len__(self):
        return self.size

    def __repr__(self):
        if self.name:
            return self.name

        return BaseType.__repr__(self)

    def _read(self, stream):
        raise NotImplementedError()

    def _read_0(self, stream):
        raise NotImplementedError()

    def _write(self, stream, data):
        raise NotImplementedError()

    def _write_0(self, stream, data):
        raise NotImplementedError()

    def default(self):
        raise NotImplementedError()
