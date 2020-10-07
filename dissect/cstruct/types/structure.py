from collections import OrderedDict
from io import BytesIO
from dissect.cstruct.bitbuffer import BitBuffer
from dissect.cstruct.types.base import Array, BaseType
from dissect.cstruct.types.instance import Instance
from dissect.cstruct.types.pointer import Pointer


class Field(object):
    """Holds a structure field."""

    def __init__(self, name, type_, bits=None, offset=None):
        self.name = name
        self.type = type_
        self.bits = bits
        self.offset = offset

    def __repr__(self):
        return '<Field {} {}>'.format(self.name, self.type)


class Structure(BaseType):
    """Type class for structures."""

    def __init__(self, cstruct, name, fields=None, anonymous=False):
        super().__init__(cstruct)
        self.name = name
        self.size = None
        self.lookup = OrderedDict()
        self.fields = fields
        self.anonymous = anonymous

        for field in self.fields:
            self.lookup[field.name] = field

        self._calc_offsets()

    def __len__(self):
        if self.size is None:
            self.size = self._calc_size()

        return self.size

    def __repr__(self):
        return '<Structure {}>'.format(self.name)

    def _calc_offsets(self):
        offset = 0
        bits_type = None
        bits_remaining = 0

        for field in self.fields:
            if field.bits:
                if bits_remaining == 0 or field.type != bits_type:
                    bits_type = field.type
                    bits_remaining = bits_type.size * 8

                    if offset is not None:
                        field.offset = offset
                        offset += bits_type.size
                else:
                    field.offset = None

                bits_remaining -= field.bits
                continue

            field.offset = offset
            if offset is not None:
                try:
                    offset += len(field.type)
                except TypeError:
                    offset = None

    def _calc_size(self):
        size = 0
        bits_type = None
        bits_remaining = 0

        for field in self.fields:
            if field.bits:
                if bits_remaining == 0 or field.type != bits_type:
                    bits_type = field.type
                    bits_remaining = bits_type.size * 8
                    size += bits_type.size

                bits_remaining -= field.bits
                continue

            field_len = len(field.type)
            size += field_len

            if field.offset is not None:
                size = max(size, field.offset + field_len)

        return size

    def _read(self, stream, *args, **kwargs):
        bit_buffer = BitBuffer(stream, self.cstruct.endian)
        struct_start = stream.tell()

        result = OrderedDict()
        sizes = {}
        for field in self.fields:
            start = stream.tell()
            field_type = self.cstruct.resolve(field.type)

            if field.offset:
                if start != struct_start + field.offset:
                    stream.seek(struct_start + field.offset)
                    start = struct_start + field.offset

            if field.bits:
                result[field.name] = bit_buffer.read(field_type, field.bits)
                continue
            else:
                bit_buffer.reset()

            if isinstance(field_type, (Array, Pointer)):
                v = field_type._read(stream, result)
            else:
                v = field_type._read(stream)

            if isinstance(field_type, Structure) and field_type.anonymous:
                sizes.update(v._sizes)
                result.update(v._values)
            else:
                sizes[field.name] = stream.tell() - start
                result[field.name] = v

        return Instance(self, result, sizes)

    def _write(self, stream, data):
        bit_buffer = BitBuffer(stream, self.cstruct.endian)
        num = 0

        for field in self.fields:
            offset = stream.tell()

            if field.bits:
                bit_buffer.write(field.type, getattr(data, field.name), field.bits)
                continue

            if bit_buffer._type:
                bit_buffer.flush()

            if isinstance(field.type, Structure) and field.type.anonymous:
                field.type._write(stream, data)
            else:
                field.type._write(stream, getattr(data, field.name))
            num += stream.tell() - offset

        if bit_buffer._type:
            bit_buffer.flush()

        return num

    def add_field(self, name, type_, offset=None):
        """Add a field to this structure.

        Args:
            name: The field name.
            type_: The field type.
            offset: The field offset.
        """
        field = Field(name, type_, offset=offset)
        self.fields.append(field)
        self.lookup[name] = field
        self.size = None

    def default(self):
        """Create and return an empty Instance from this structure.

        Returns:
            An empty Instance from this structure.
        """
        result = OrderedDict()
        for field in self.fields:
            result[field.name] = field.type.default()

        return Instance(self, result)

    def show(self, indent=0):
        """Pretty print this structure."""
        if indent == 0:
            print("struct {}".format(self.name))

        for field in self.fields:
            if field.offset is None:
                offset = '0x??'
            else:
                offset = '0x{:02x}'.format(field.offset)

            print("{}+{} {} {}".format(' ' * indent, offset, field.name, field.type))

            if isinstance(field.type, Structure):
                field.type.show(indent + 1)


class Union(Structure):
    """Type class for unions"""

    def __repr__(self):
        return '<Union {}>'.format(self.name)

    def _calc_offsets(self):
        """Overridden because we don't use this for unions"""
        pass

    def _calc_size(self):
        return max(len(field.type) for field in self.fields)

    def _read(self, stream):
        buf = BytesIO(memoryview(stream.read(len(self))))
        result = OrderedDict()
        sizes = {}

        for field in self.fields:
            start = 0
            buf.seek(0)
            field_type = self.cstruct.resolve(field.type)

            if field.offset:
                buf.seek(field.offset)
                start = field.offset

            if isinstance(field_type, (Array, Pointer)):
                v = field_type._read(buf, result)
            else:
                v = field_type._read(buf)

            if isinstance(field_type, Structure) and field_type.anonymous:
                sizes.update(v._sizes)
                result.update(v._values)
            else:
                sizes[field.name] = buf.tell() - start
                result[field.name] = v

        return Instance(self, result, sizes)

    def _write(self, stream, data):
        offset = stream.tell()

        # Find the largest field
        field = max(self.fields, key=lambda e: len(e.type))

        # Write the value to the stream using the largest file's field type
        field.type._write(stream, getattr(data, field.name))

        return stream.tell() - offset

    def show(self, indent=0):
        # TODO: Implement

        raise NotImplementedError()
