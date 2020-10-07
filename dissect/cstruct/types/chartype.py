from dissect.cstruct.types.base import RawType


class CharType(RawType):
    """Implements a character type that can properly handle strings."""

    def __init__(self, cstruct):
        super().__init__(cstruct, 'char', 1)

    def _read(self, stream):
        return stream.read(1)

    def _read_array(self, stream, count):
        if count == 0:
            return b''

        return stream.read(count)

    def _read_0(self, stream):
        byte_array = []
        while True:
            bytes_stream = stream.read(1)
            if bytes_stream == b'':
                raise EOFError()

            if bytes_stream == b'\x00':
                break

            byte_array.append(bytes_stream)

        return b''.join(byte_array)

    def _write(self, stream, data):
        if isinstance(data, int):
            data = chr(data)

        if isinstance(data, str):
            data = data.encode('latin-1')

        return stream.write(data)

    def _write_array(self, stream, data):
        return self._write(stream, data)

    def _write_0(self, stream, data):
        return self._write(stream, data + b'\x00')

    def default(self):
        return b'\x00'

    def default_array(self, count):
        return b'\x00' * count
