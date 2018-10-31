# dissect.cstruct
Structure parsing in Python made easy. With cstruct, you can write C-like structures and use them to parse binary data, either as file-like objects or bytestrings.

Parsing binary data with cstruct feels familiar and easy. No need to learn a new syntax or the quirks of a new parsing library before you can start parsing data. The syntax isn't strict C but it's compatible with most common structure definitions. You can often use structure definitions from open-source C projects and use them out of the box with little to no changes. Need to parse an EXT4 super block? Just copy the structure definition from the Linux kernel source code. Need to parse some custom file format? Write up a simple structure and immediately start parsing data, tweaking the structure as you go.

By design cstruct is incredibly simple. No complex syntax, filters, pre- or postprocessing steps. Just structure parsing.

## Installation
```
pip install dissect.cstruct
```

## Usage
All you need to do is instantiate a new cstruct instance and load some structure definitions in there. After that you can start using them from your Python code.

```python
from dissect import cstruct

# Default endianness is LE, but can be configured using a kwarg or setting the 'endian' attribute
# e.g. cstruct.cstruct(endian='>') or cparser.endian = '>'
cparser = cstruct.cstruct()
cparser.load("""
#define SOME_CONSTANT   5

enum Example : uint16 {
    A, B = 0x5, C
};

struct some_struct {
    uint8   field_1;
    char    field_2[SOME_CONSTANT];
    char    field_3[field_1 & 1 * 5];  // Some random expression to calculate array length
    Example field_4[2];
};
""")

data = b'\x01helloworld\x00\x00\x06\x00'
result = cparser.some_struct(data)  # Also accepts file-like objects
assert result.field_1 == 0x01
assert result.field_2 == b'hello'
assert result.field_3 == b'world'
assert result.field_4 == [cparser.Example.A, cparser.Example.C]

assert cparser.Example.A == 0
assert cparser.Example.C == 6
assert cparser.Example(5) == cparser.Example.B

assert result.dumps() == data

# You can also instantiate structures from Python by using kwargs
# Note that array sizes are not enforced
instance = cparser.some_struct(field_1=5, field_2='lorem', field_3='ipsum', field_4=[cparser.Example.B, cparser.Example.A])
assert instance.dumps() == b'\x05loremipsum\x05\x00\x00\x00'
```

By default, all structures are compiled into classes that provide optimised performance. You can disable this by passing a `compiled=False` keyword argument to the `.load()` call. You can also inspect the resulting source code by accessing the source attribute of the structure: `print(cparser.some_struct.source)`.

More examples can be found in the `examples` directory.

## Features
### Structure parsing
Write simple C-like structures and use them to parse binary data, as can be seen in the examples.

### Type parsing
Aside from loading structure definitions, any of the supported types can be used individually for parsing data. For example, the following is all supported:

```python
from dissect import cstruct
cs = cstruct.cstruct()
# Default endianness is LE, but can be configured using a kwarg or setting the attribute
# e.g. cstruct.cstruct(endian='>') or cs.endian = '>'
assert cs.uint32(b'\x05\x00\x00\x00') == 5
assert cs.uint24[2](b'\x01\x00\x00\x02\x00\x00') == [1, 2]  # You can also parse arrays using list indexing
assert cs.char[None](b'hello world!\x00') == b'hello world!'  # A list index of None means null terminated
```

### Parse bit fields
Bit fields are supported as part of structures. They are properly aligned to their boundaries.

```python
bitdef = """
struct test {
    uint16  a:1;
    uint16  b:1;  # Read 2 bits from an uint16
    uint32  c;    # The next field is properly aligned
    uint16  d:2;
    uint16  e:3;
};
"""
bitfields = cstruct.cstruct()
bitfields.load(bitdef)

d = b'\x03\x00\xff\x00\x00\x00\x1f\x00'
a = bitfields.test(d)

assert a.a == 0b1
assert a.b == 0b1
assert a.c == 0xff
assert a.d == 0b11
assert a.e == 0b111
assert a.dumps() == d
```

### Enums
The API to access enum members and their values is similar to that of the native Enum type in Python 3. Functionally, it's best comparable to the IntEnum type.

### Custom types
You can implement your own types by subclassing `BaseType` or `RawType`, and adding them to your cstruct instance with `addtype(name, type)`

### Custom definition parsers
Don't like the C-like definition syntax? Write your own syntax parser!

## Todo
- Nested structure definitions
- Unions
