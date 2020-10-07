from dissect.cstruct.types.base import RawType


class WcharType(RawType):
    """Implements a wide-character type."""

    def __init__(self, cstruct):
        super().__init__(cstruct, 'wchar', 2)

    @property
    def encoding(self):
        if self.cstruct.endian == '<':  # little-endian (LE)
            return 'utf-16-le'
        elif self.cstruct.endian == '>':  # big-endian (BE)
            return 'utf-16-be'

    def _read(self, stream):
        return stream.read(2).decode(self.encoding)

    def _read_array(self, stream, count):
        if count == 0:
            return u''

        data = stream.read(2 * count)
        return data.decode(self.encoding)

    def _read_0(self, stream):
        byte_string = b''
        while True:
            bytes_stream = stream.read(2)

            if len(bytes_stream) != 2:
                raise EOFError()

            if bytes_stream == b'\x00\x00':
                break

            byte_string += bytes_stream

        return byte_string.decode(self.encoding)

    def _write(self, stream, data):
        return stream.write(data.encode(self.encoding))

    def _write_array(self, stream, data):
        return self._write(stream, data)

    def _write_0(self, stream, data):
        return self._write(stream, data + u'\x00')

    def default(self):
        return u'\x00'

    def default_array(self, count):
        return u'\x00' * count
