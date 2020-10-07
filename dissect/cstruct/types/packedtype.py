import struct

from dissect.cstruct.types.base import RawType


class PackedType(RawType):
    """Implements a packed type that uses Python struct packing characters."""

    def __init__(self, cstruct, name, size, packchar):
        super().__init__(cstruct, name, size)
        self.packchar = packchar

    def _read(self, stream):
        return self._read_array(stream, 1)[0]

    def _read_array(self, stream, count):
        length = self.size * count
        data = stream.read(length)
        fmt = self.cstruct.endian + str(count) + self.packchar

        if len(data) != length:
            raise EOFError("Read %d bytes, but expected %d" % (len(data), length))

        return list(struct.unpack(fmt, data))

    def _read_0(self, stream):
        byte_array = []
        while True:
            bytes_stream = stream.read(self.size)
            unpacked_struct = struct.unpack(self.cstruct.endian + self.packchar, bytes_stream)[0]

            if unpacked_struct == 0:
                break

            byte_array.append(unpacked_struct)

        return byte_array

    def _write(self, stream, data):
        return self._write_array(stream, [data])

    def _write_array(self, stream, data):
        fmt = self.cstruct.endian + str(len(data)) + self.packchar
        return stream.write(struct.pack(fmt, *data))

    def _write_0(self, stream, data):
        return self._write_array(stream, data + [0])

    def default(self):
        return 0

    def default_array(self, count):
        return [0] * count
