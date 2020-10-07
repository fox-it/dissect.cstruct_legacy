from dissect.cstruct.types.base import RawType


class BytesInteger(RawType):
    """Implements an integer type that can span an arbitrary amount of bytes."""

    def __init__(self, cstruct, name, size, signed):
        self.signed = signed
        super().__init__(cstruct, name, size)

    @staticmethod
    def parse(buf, size, count, signed, endian):
        nums = []

        for c in range(count):
            num = 0
            data = buf[c * size:(c + 1) * size]
            if endian == '<':  # little-endian (LE)
                data = b''.join(data[i:i + 1] for i in reversed(range(len(data))))

            ints = list(data)
            for i in ints:
                num = (num << 8) | i

            if signed and (num & (1 << (size * 8 - 1))):
                bias = 1 << (size * 8 - 1)
                num -= bias * 2

            nums.append(num)

        return nums

    @staticmethod
    def pack(data, size, endian):
        buf = []
        for i in data:
            num = int(i)
            if num < 0:
                num += 1 << (size * 8)

            d = [b'\x00'] * size
            i = size - 1

            while i >= 0:
                b = num & 255
                d[i] = bytes((b,))
                num >>= 8
                i -= 1

            if endian == '<':
                d = b''.join(d[i:i + 1][0] for i in reversed(range(len(d))))
            else:
                d = b''.join(d)

            buf.append(d)

        return b''.join(buf)

    def _read(self, stream):
        return self.parse(stream.read(self.size * 1), self.size, 1, self.signed, self.cstruct.endian)[0]

    def _read_array(self, stream, count):
        return self.parse(stream.read(self.size * count), self.size, count, self.signed, self.cstruct.endian)

    def _read_0(self, stream):
        result = []

        while True:
            v = self._read(stream)
            if v == 0:
                break

            result.append(v)

        return result

    def _write(self, stream, data):
        return stream.write(self.pack([data], self.size, self.cstruct.endian))

    def _write_array(self, stream, data):
        return stream.write(self.pack(data, self.size, self.cstruct.endian))

    def _write_0(self, stream, data):
        return self._write_array(stream, data + [0])

    def default(self):
        return 0

    def default_array(self, count):
        return [0] * count
