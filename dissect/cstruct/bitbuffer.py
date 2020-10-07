class BitBuffer(object):
    """Implements a bit buffer that can read and write bit fields."""

    def __init__(self, stream, endian):
        self.stream = stream
        self.endian = endian

        self._type = None
        self._buffer = 0
        self._remaining = 0

    def read(self, field_type, bits):
        if self._remaining < 1 or self._type.size != field_type.size:
            self._type = field_type
            self._remaining = field_type.size * 8
            self._buffer = field_type._read(self.stream)

        if self.endian != '>':
            v = self._buffer & ((1 << bits) - 1)
            self._buffer >>= bits
            self._remaining -= bits
        else:
            v = self._buffer & (((1 << (self._remaining - bits)) - 1) ^ ((1 << self._remaining) - 1))
            v >>= self._remaining - bits
            self._remaining -= bits

        return v

    def write(self, field_type, data, bits):
        if self._remaining == 0:
            self._remaining = field_type.size * 8
            self._type = field_type

        if self.endian != '>':
            self._buffer |= data << (self._type.size * 8 - self._remaining)
        else:
            self._buffer |= data << (self._remaining - bits)

        self._remaining -= bits

    def flush(self):
        self._type._write(self.stream, self._buffer)
        self._type = None
        self._remaining = 0
        self._buffer = 0

    def reset(self):
        self._type = None
        self._buffer = 0
        self._remaining = 0
