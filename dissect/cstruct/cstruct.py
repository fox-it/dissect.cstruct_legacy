# TODO:
# - Rework definition parsing, maybe pycparser?
# - Change expression implementation
# - Lazy reading?
from __future__ import print_function
import ctypes as _ctypes
import sys

from io import BytesIO
from dissect.cstruct.exceptions import ResolveError
from dissect.cstruct.types.base import Array
from dissect.cstruct.types.bytesinteger import BytesInteger
from dissect.cstruct.types.chartype import CharType
from dissect.cstruct.types.packedtype import PackedType
from dissect.cstruct.types.pointer import Pointer
from dissect.cstruct.types.voidtype import VoidType
from dissect.cstruct.types.wchartype import WcharType
from dissect.cstruct.parser import CStyleParser, TokenParser


class cstruct(object):
    """Main class of cstruct. All types are registered in here.

    Args:
        endian: The endianness to use when parsing.
        pointer: The pointer type to use for Pointers.
    """

    DEF_CSTYLE = 1
    DEF_LEGACY = 2

    def __init__(self, endian='<', pointer=None, align=None):
        self.endian = endian

        self.consts = {}
        self.lookups = {}
        self.typedefs = {
            'BYTE': 'int8',
            'UBYTE': 'uint8',
            'UCHAR': 'uint8',
            'uchar': 'uint8',
            'SHORT': 'int16',
            'short': 'int16',
            'USHORT': 'uint16',
            'ushort': 'uint16',
            'LONG': 'int32',
            'long': 'int32',
            'ULONG': 'uint32',
            'ulong': 'uint32',
            'ULONG64': 'uint64',

            'u1': 'uint8',
            'u2': 'uint16',
            'u4': 'uint32',
            'u8': 'uint64',

            'WORD': 'uint16',
            'DWORD': 'uint32',
            'QWORD': 'uint64',

            'LONGLONG': 'int64',
            'ULONGLONG': 'uint64',

            'int': 'int32',
            'unsigned int': 'uint32',

            'int8': PackedType(self, 'int8', 1, 'b'),
            'uint8': PackedType(self, 'uint8', 1, 'B'),
            'int16': PackedType(self, 'int16', 2, 'h'),
            'uint16': PackedType(self, 'uint16', 2, 'H'),
            'int32': PackedType(self, 'int32', 4, 'i'),
            'uint32': PackedType(self, 'uint32', 4, 'I'),
            'int64': PackedType(self, 'int64', 8, 'q'),
            'uint64': PackedType(self, 'uint64', 8, 'Q'),
            'float': PackedType(self, 'float', 4, 'f'),
            'double': PackedType(self, 'double', 8, 'd'),
            'char': CharType(self),
            'wchar': WcharType(self),

            'int24': BytesInteger(self, 'int24', 3, True),
            'uint24': BytesInteger(self, 'uint24', 3, False),
            'int48': BytesInteger(self, 'int48', 6, True),
            'uint48': BytesInteger(self, 'uint48', 6, False),

            'void': VoidType(),
        }

        pointer = pointer or 'uint64' if sys.maxsize > 2 ** 32 else 'uint32'
        self.pointer = self.resolve(pointer)
        self.align = align
        self._anonymous_count = 0

    def __getattr__(self, attr):
        try:
            return self.typedefs[attr]
        except KeyError:
            pass

        try:
            return self.consts[attr]
        except KeyError:
            pass

        raise AttributeError("Invalid attribute: %s" % attr)

    def _next_anonymous(self):
        name = 'anonymous_{:d}'.format(self._anonymous_count)
        self._anonymous_count += 1
        return name

    def addtype(self, name, type_, replace=False):
        """Add a type or type reference.

        Args:
            name: Name of the type to be added.
            type_: The type to be added. Can be a str reference to another type
                or a compatible type class.

        Raises:
            ValueError: If the type already exists.
        """
        if not replace and name in self.typedefs:
            raise ValueError("Duplicate type: %s" % name)

        self.typedefs[name] = type_

    def load(self, definition, deftype=None, **kwargs):
        """Parse structures from the given definitions using the given definition type.

        Definitions can be parsed using different parsers. Currently, there's
        only one supported parser - DEF_CSTYLE. Parsers can add types and
        modify this cstruct instance. Arguments can be passed to parsers
        using kwargs.

        The CSTYLE parser was recently replaced with token based parser,
        instead of a strictly regex based one. The old parser is still available
        by using DEF_LEGACY.

        Args:
            definition: The definition to parse.
            deftype: The definition type to parse the definitions with.
            **kwargs: Keyword arguments for parsers.
        """
        deftype = deftype or cstruct.DEF_CSTYLE

        if deftype == cstruct.DEF_CSTYLE:
            TokenParser(self, **kwargs).parse(definition)
        elif deftype == cstruct.DEF_LEGACY:
            CStyleParser(self, **kwargs).parse(definition)

    def loadfile(self, path, deftype=None, **kwargs):
        """Load structure definitions from a file.

        The given path will be read and parsed using the .load() function.

        Args:
            path: The path to load definitions from.
            deftype: The definition type to parse the definitions with.
            **kwargs: Keyword arguments for parsers.
        """
        with open(path) as fh:
            self.load(fh.read(), deftype, **kwargs)

    def read(self, name, s):
        """Parse data using a given type.

        Args:
            name: Type name to read.
            s: File-like object or byte string to parse.

        Returns:
            The parsed data.
        """
        return self.resolve(name).read(s)

    def resolve(self, name):
        """Resolve a type name to get the actual type object.

        Types can be referenced using different names. When we want
        the actual type object, we need to resolve these references.

        Args:
            name: Type name to resolve.

        Returns:
            The resolved type object.

        Raises:
            ResolveError: If the type can't be resolved.
        """
        type_name = name
        if not isinstance(type_name, str):
            return type_name

        for _ in range(10):
            if type_name not in self.typedefs:
                raise ResolveError("Unknown type %s" % name)

            type_name = self.typedefs[type_name]

            if not isinstance(type_name, str):
                return type_name

        raise ResolveError("Recursion limit exceeded while resolving type %s" % name)


class Instance(object):
    """Holds parsed structure data."""
    __slots__ = ('_type', '_values', '_sizes')

    def __init__(self, type_, values, sizes=None):
        object.__setattr__(self, '_type', type_)
        object.__setattr__(self, '_values', values)
        object.__setattr__(self, '_sizes', sizes)

    def __getattr__(self, attr):
        try:
            return self._values[attr]
        except KeyError:
            raise AttributeError("Invalid attribute: %r" % attr)

    def __setattr__(self, attr, value):
        if attr not in self._type.lookup:
            raise AttributeError("Invalid attribute: %r" % attr)

        self._values[attr] = value

    def __getitem__(self, item):
        return self._values[item]

    def __contains__(self, attr):
        return attr in self._values

    def __repr__(self):
        return '<%s %s>' % (
            self._type.name,
            ', '.join(
                [
                    '%s=%s' % (k, hex(v) if isinstance(v, (int, int)) else repr(v))
                    for k, v in self._values.items()
                ]
            ),
        )

    def __len__(self):
        return len(self.dumps())

    def _size(self, field):
        return self._sizes[field]

    def write(self, fh):
        """Write this structure to a writable file-like object.

        Args:
            fh: File-like objects that supports writing.

        Returns:
            The amount of bytes written.
        """
        return self._type.write(fh, self)

    def dumps(self):
        """Dump this structure to a byte string.

        Returns:
            The raw bytes of this structure.
        """
        s = BytesIO()
        self.write(s)
        return s.getvalue()


def ctypes(structure):
    """Create ctypes structures from cstruct structures."""
    fields = []
    for field in structure.fields:
        t = ctypes_type(field.type)
        fields.append((field.name, t))

    tt = type(structure.name, (_ctypes.Structure,), {'_fields_': fields})
    return tt


def ctypes_type(t):
    mapping = {
        'I': _ctypes.c_ulong,
        'i': _ctypes.c_long,
        'b': _ctypes.c_int8,
    }

    if isinstance(t, PackedType):
        return mapping[t.packchar]

    if isinstance(t, CharType):
        return _ctypes.c_char

    if isinstance(t, Array):
        subtype = ctypes_type(t._type)
        return subtype * t.count

    if isinstance(t, Pointer):
        subtype = ctypes_type(t._target)
        return ctypes.POINTER(subtype)

    raise NotImplementedError("Type not implemented: %s" % t.__class__.__name__)
