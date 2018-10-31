import os
import pytest
from io import BytesIO
from dissect import cstruct
from dissect.cstruct.cstruct import BytesInteger


def test_simple_types():
    c = cstruct.cstruct()
    assert c.uint32(b'\x01\x00\x00\x00') == 1
    assert c.uint32[10](b"A" * 20 + b"B" * 20) == [0x41414141] * 5 + [0x42424242] * 5
    assert c.uint32[None](b"A" * 20 + b"\x00" * 4) == [0x41414141] * 5

    with pytest.raises(EOFError):
        c.char[None](b'aaa')

    with pytest.raises(EOFError):
        c.wchar[None](b'a\x00a\x00a')


def test_simple_struct():
    d = """
    struct test {
        char    magic[4];
        wchar   wmagic[4];
        uint8   a;
        uint16  b;
        uint32  c;
        char    string[];
        wchar   wstring[];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    d = b'testt\x00e\x00s\x00t\x00\x01\x02\x03\x04\x05\x06\x07lalala\x00t\x00e\x00s\x00t\x00\x00\x00'
    a = c.test(d)

    assert 'magic' in a
    assert a.magic == b'test'
    assert a['magic'] == a.magic
    assert a.wmagic == 'test'
    assert a.a == 0x01
    assert a.b == 0x0302
    assert a.c == 0x07060504
    assert a.string == b'lalala'
    assert a.wstring == 'test'

    with pytest.raises(AttributeError):
        a.nope

    assert a._size('magic') == 4
    assert len(a) == len(d)
    assert d == a.dumps()

    assert repr(a)

    f = BytesIO()
    size = a.write(f)
    assert size == len(d) == len(f.getvalue())


def test_simple_struct_be():
    d = """
    struct test {
        char    magic[4];
        wchar   wmagic[4];
        uint8   a;
        uint16  b;
        uint32  c;
        char    string[];
        wchar   wstring[];
    };
    """
    c = cstruct.cstruct(endian='>')
    c.load(d, compiled=False)

    d = b'test\x00t\x00e\x00s\x00t\x01\x02\x03\x04\x05\x06\x07lalala\x00\x00t\x00e\x00s\x00t\x00\x00'
    a = c.test(d)

    assert a.magic == b'test'
    assert a.wmagic == 'test'
    assert a.a == 0x01
    assert a.b == 0x0203
    assert a.c == 0x04050607
    assert a.string == b'lalala'
    assert a.wstring == 'test'
    assert d == a.dumps()


def test_bytes_integer_unsigned():
    c = cstruct.cstruct()

    assert c.uint24(b'AAA') == 0x414141
    assert c.uint24(b'\xff\xff\xff') == 0xffffff
    assert c.uint24[4](b'AAABBBCCCDDD') == [0x414141, 0x424242, 0x434343, 0x444444]
    assert c.uint48(b'AAAAAA') == 0x414141414141
    assert c.uint48(b'\xff\xff\xff\xff\xff\xff') == 0xffffffffffff
    assert c.uint48[4](b'AAAAAABBBBBBCCCCCCDDDDDD') == [
        0x414141414141, 0x424242424242, 0x434343434343, 0x444444444444
    ]

    uint40 = BytesInteger(c, 'uint40', 5, signed=False)
    assert uint40(b'AAAAA') == 0x4141414141
    assert uint40(b'\xff\xff\xff\xff\xff') == 0xffffffffff
    assert uint40[2](b'AAAAABBBBB') == [0x4141414141, 0x4242424242]
    assert uint40[None](b'AAAAA\x00') == [0x4141414141]


def test_bytes_integer_signed():
    c = cstruct.cstruct()

    assert c.int24(b'\xff\x00\x00') == 255
    assert c.int24(b'\xff\xff\xff') == -1
    assert c.int24[4](b'\xff\xff\xff\xfe\xff\xff\xfd\xff\xff\xfc\xff\xff') == [-1, -2, -3, -4]

    int40 = BytesInteger(c, 'int40', 5, signed=True)
    assert int40(b'AAAAA') == 0x4141414141
    assert int40(b'\xff\xff\xff\xff\xff') == -1
    assert int40[2](b'\xff\xff\xff\xff\xff\xfe\xff\xff\xff\xff') == [-1, -2]


def test_bytes_integer_unsigned_be():
    c = cstruct.cstruct()
    c.endian = '>'

    assert c.uint24(b'\x00\x00\xff') == 255
    assert c.uint24(b'\xff\xff\xff') == 0xffffff
    assert c.uint24[3](b'\x00\x00\xff\x00\x00\xfe\x00\x00\xfd') == [255, 254, 253]

    uint40 = BytesInteger(c, 'uint40', 5, signed=False)
    assert uint40(b'\x00\x00\x00\x00\xff') == 255
    assert uint40(b'\xff\xff\xff\xff\xff') == 0xffffffffff
    assert uint40[2](b'\x00\x00\x00\x00A\x00\x00\x00\x00B') == [0x41, 0x42]


def test_bytes_integer_signed_be():
    c = cstruct.cstruct()
    c.endian = '>'

    assert c.int24(b'\x00\x00\xff') == 255
    assert c.int24(b'\xff\xff\x01') == -255
    assert c.int24[3](b'\xff\xff\x01\xff\xff\x02\xff\xff\x03') == [-255, -254, -253]

    int40 = BytesInteger(c, 'int40', 5, signed=True)
    assert int40(b'\x00\x00\x00\x00\xff') == 255
    assert int40(b'\xff\xff\xff\xff\xff') == -1
    assert int40(b'\xff\xff\xff\xff\x01') == -255
    assert int40[2](b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfe') == [-1, -2]


def test_enum():
    d = """
    enum Test16 : uint16 {
        A = 0x1,
        B = 0x2
    };

    enum Test24 : uint24 {
        A = 0x1,    // comment, best one
        B = 0x2
    };

    enum Test32 : uint32 {
        A = 0x1,
        B = 0x2     // comment
    };

    struct test {
        Test16  a16;
        Test16  b16;
        Test24  a24;
        Test24  b24;
        Test32  a32;
        Test32  b32;        // this is a comment, awesome
        Test16  l[2];
    };

    struct test_term {
        Test16  null[];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    d = b'\x01\x00\x02\x00\x01\x00\x00\x02\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x02\x00'
    a = c.test(d)

    assert a.a16.enum == c.Test16 and a.a16 == c.Test16.A
    assert a.b16.enum == c.Test16 and a.b16 == c.Test16.B
    assert a.a24.enum == c.Test24 and a.a24 == c.Test24.A
    assert a.b24.enum == c.Test24 and a.b24 == c.Test24.B
    assert a.a32.enum == c.Test32 and a.a32 == c.Test32.A
    assert a.b32.enum == c.Test32 and a.b32 == c.Test32.B

    assert len(a.l) == 2
    assert a.l[0].enum == c.Test16 and a.l[0] == c.Test16.A
    assert a.l[1].enum == c.Test16 and a.l[1] == c.Test16.B

    assert 'A' in c.Test16
    assert 'Foo' not in c.Test16
    assert c.Test16(1) == c.Test16['A']
    assert c.Test24(2) == c.Test24.B
    assert c.Test16.A != c.Test24.A

    with pytest.raises(KeyError):
        c.Test16['C']

    with pytest.raises(AttributeError):
        c.Test16.C

    assert a.dumps() == d

    assert c.test_term(b'\x01\x00\x02\x00\x00\x00').null == [c.Test16.A, c.Test16.B]
    assert c.test_term(null=[c.Test16.A, c.Test16.B]).dumps() == b'\x01\x00\x02\x00\x00\x00'

    x = {
        c.Test16.A: 'Test16.A',
        c.Test16.B: 'Test16.B',
        c.Test24.A: 'Test24.A',
        c.Test24.B: 'Test24.B'
    }

    assert x[c.Test16.A] == 'Test16.A'
    assert x[c.Test16(2)] == 'Test16.B'
    assert x[c.Test24(1)] == 'Test24.A'
    assert x[c.Test24.B] == 'Test24.B'

    with pytest.raises(KeyError):
        x[c.Test32.A]


def test_enum_comments():
    d = """
    enum Inline { hello=7, world, foo, bar }; // inline enum

    enum Test {
        a = 2,  // comment, 2
        b,      // comment, 3
        c       // comment, 4
    };

    enum Odd {
        a = 0,          // hello, world
        b,              // next
        c,              // next
        d = 5, e, f     // inline, from 5
        g               // next
    };
    """

    c = cstruct.cstruct()
    c.load(d, compiled=False)

    assert c.Inline.hello == 7
    assert c.Inline.world == 8
    assert c.Inline.foo == 9
    assert c.Inline.bar == 10

    assert c.Test.a == 2
    assert c.Test.b == 3
    assert c.Test.c == 4

    assert c.Odd.a == 0
    assert c.Odd.b == 1
    assert c.Odd.c == 2

    assert c.Odd.d == 5
    assert c.Odd.e == 6
    assert c.Odd.f == 7
    assert c.Odd.g == 8

    assert c.Test.a == c.Test.a
    assert c.Test.a != c.Test.b


def test_bitfield():
    d = """
    struct test {
        uint16  a:4;
        uint16  b:4;
        uint16  c:4;
        uint16  d:4;
        uint32  e;
        uint16  f:2;
        uint16  g:3;
        uint32  h;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    d = b'\x12\x34\xff\x00\x00\x00\x1f\x00\x01\x00\x00\x00'
    a = c.test(d)

    assert a.a == 0b10
    assert a.b == 0b01
    assert a.c == 0b100
    assert a.d == 0b011
    assert a.e == 0xff
    assert a.f == 0b11
    assert a.g == 0b111
    assert a.h == 1
    assert a.dumps() == d


def test_bitfield_be():
    d = """
    struct test {
        uint16  a:4;
        uint16  b:4;
        uint16  c:4;
        uint16  d:4;
        uint32  e;
        uint16  f:2;
        uint16  g:3;
        uint16  h:4;
        uint32  i;
    };
    """
    c = cstruct.cstruct(endian='>')
    c.load(d, compiled=False)

    d = b'\x12\x34\x00\x00\x00\xff\x1f\x00\x00\x00\x00\x01'
    a = c.test(d)

    assert a.a == 0b01
    assert a.b == 0b10
    assert a.c == 0b011
    assert a.d == 0b100
    assert a.e == 0xff
    assert a.f == 0
    assert a.g == 0b11
    assert a.h == 0b1110
    assert a.i == 1
    assert a.dumps() == d


def test_write():
    c = cstruct.cstruct()

    assert c.uint32.dumps(1) == b'\x01\x00\x00\x00'
    assert c.uint16.dumps(255) == b'\xff\x00'
    assert c.int8.dumps(-10) == b'\xf6'
    assert c.uint8[4].dumps([1, 2, 3, 4]) == b'\x01\x02\x03\x04'
    assert c.uint24.dumps(300) == b'\x2c\x01\x00'
    assert c.int24.dumps(-1337) == b'\xc7\xfa\xff'
    assert c.uint24[4].dumps([1, 2, 3, 4]) == b'\x01\x00\x00\x02\x00\x00\x03\x00\x00\x04\x00\x00'
    assert c.uint24[None].dumps([1, 2]) == b'\x01\x00\x00\x02\x00\x00\x00\x00\x00'
    assert c.char.dumps(0x61) == b'a'
    assert c.wchar.dumps('lala') == b'l\x00a\x00l\x00a\x00'
    assert c.uint32[None].dumps([1]) == b'\x01\x00\x00\x00\x00\x00\x00\x00'


def test_write_be():
    c = cstruct.cstruct(endian='>')

    assert c.uint32.dumps(1) == b'\x00\x00\x00\x01'
    assert c.uint16.dumps(255) == b'\x00\xff'
    assert c.int8.dumps(-10) == b'\xf6'
    assert c.uint8[4].dumps([1, 2, 3, 4]) == b'\x01\x02\x03\x04'
    assert c.uint24.dumps(300) == b'\x00\x01\x2c'
    assert c.int24.dumps(-1337) == b'\xff\xfa\xc7'
    assert c.uint24[4].dumps([1, 2, 3, 4]) == b'\x00\x00\x01\x00\x00\x02\x00\x00\x03\x00\x00\x04'
    assert c.char.dumps(0x61) == b'a'
    assert c.wchar.dumps('lala') == b'\x00l\x00a\x00l\x00a'


def test_write_struct():
    d = """
    struct test {
        char    magic[4];
        wchar   wmagic[4];
        uint8   a;
        uint16  b;
        uint32  c;
        char    string[];
        wchar   wstring[];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)
    d = b'testt\x00e\x00s\x00t\x00\x01\x02\x03\x04\x05\x06\x07lalala\x00t\x00e\x00s\x00t\x00\x00\x00'

    a = c.test()
    a.magic = 'test'
    a.wmagic = 'test'
    a.a = 0x01
    a.b = 0x0302
    a.c = 0x07060504
    a.string = b'lalala'
    a.wstring = 'test'

    with pytest.raises(AttributeError):
        a.nope = 1

    assert a.dumps() == d
    assert c.test(magic=b'test', wmagic=u'test', a=0x01, b=0x0302, c=0x07060504, string=b'lalala', wstring=u'test').dumps() == d


def test_write_struct_be():
    d = """
    struct test {
        char    magic[4];
        wchar   wmagic[4];
        uint8   a;
        uint16  b;
        uint32  c;
        char    string[];
        wchar   wstring[];
    };
    """
    c = cstruct.cstruct(endian='>')
    c.load(d, compiled=False)

    a = c.test()
    a.magic = 'test'
    a.wmagic = 'test'
    a.a = 0x01
    a.b = 0x0203
    a.c = 0x04050607
    a.string = b'lalala'
    a.wstring = 'test'

    assert a.dumps() == b'test\x00t\x00e\x00s\x00t\x01\x02\x03\x04\x05\x06\x07lalala\x00\x00t\x00e\x00s\x00t\x00\x00'


def test_write_bitfield():
    d = """
    struct test {
        uint16  a:1;
        uint16  b:1;
        uint32  c;
        uint16  d:2;
        uint16  e:3;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    a = c.test()
    a.a = 0b1
    a.b = 0b1
    a.c = 0xff
    a.d = 0b11
    a.e = 0b111

    assert a.dumps() == b'\x03\x00\xff\x00\x00\x00\x1f\x00'


def test_write_bitfield_be():
    d = """
    struct test {
        uint16  a:1;
        uint16  b:1;
        uint32  c;
        uint16  d:2;
        uint16  e:3;
    };
    """
    c = cstruct.cstruct(endian='>')
    c.load(d, compiled=False)

    a = c.test()
    a.a = 0b1
    a.b = 0b1
    a.c = 0xff
    a.d = 0b11
    a.e = 0b111

    assert a.dumps() == b'\xc0\x00\x00\x00\x00\xff\xf8\x00'


def test_write_enum():
    d = """
    enum Test16 : uint16 {
        A = 0x1,
        B = 0x2
    };

    enum Test24 : uint24 {
        A = 0x1,
        B = 0x2
    };

    enum Test32 : uint32 {
        A = 0x1,
        B = 0x2
    };

    struct test {
        Test16  a16;
        Test16  b16;
        Test24  a24;
        Test24  b24;
        Test32  a32;
        Test32  b32;
        Test16  list[2];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    a = c.test()
    a.a16 = c.Test16.A
    a.b16 = c.Test16.B
    a.a24 = c.Test24.A
    a.b24 = c.Test24.B
    a.a32 = c.Test32.A
    a.b32 = c.Test32.B
    a.list = [c.Test16.A, c.Test16.B]

    assert a.dumps() == b'\x01\x00\x02\x00\x01\x00\x00\x02\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x02\x00'


def test_enum_name():
    d = """
    enum Color: uint16 {
          RED = 1,
          GREEN = 2,
          BLUE = 3,
    };
    struct Pixel {
        uint8 x;
        uint8 y;
        Color color;
        uint32 hue;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    Color = c.Color
    Pixel = c.Pixel

    pixel = Pixel(b'\xFF\x0A\x01\x00\xAA\xBB\xCC\xDD')
    assert pixel.x == 255
    assert pixel.y == 10
    assert pixel.color.name == 'RED'
    assert pixel.color.value == Color.RED
    assert pixel.color.value == 1
    assert pixel.hue == 0xDDCCBBAA

    # unknown enum values default to <enum name>_<value>
    pixel = Pixel(b'\x00\x00\xFF\x00\xAA\xBB\xCC\xDD')
    assert pixel.color.name == 'Color_255'
    assert pixel.color.value == 0xFF


def test_pointers():
    d = """
    struct test {
        char    magic[4];
        wchar   wmagic[4];
        uint8   a;
        uint16  b;
        uint32  c;
        char    string[];
        wchar   wstring[];
    };

    struct ptrtest {
        test    *ptr;
    };
    """
    c = cstruct.cstruct(pointer='uint16')
    c.load(d, compiled=False)

    d = b'\x02\x00testt\x00e\x00s\x00t\x00\x01\x02\x03\x04\x05\x06\x07lalala\x00t\x00e\x00s\x00t\x00\x00\x00'
    p = c.ptrtest(d)

    assert p != 0

    a = p.ptr

    assert a.magic == b'test'
    assert a.wmagic == 'test'
    assert a.a == 0x01
    assert a.b == 0x0302
    assert a.c == 0x07060504
    assert a.string == b'lalala'
    assert a.wstring == 'test'

    with pytest.raises(cstruct.NullPointerDereference):
        c.ptrtest(b'\x00\x00').ptr.magic


def test_duplicate_type():
    d = """
    struct test {
        uint32  a;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    with pytest.raises(ValueError):
        c.load(d)


def test_load_file():
    path = os.path.join(os.path.dirname(__file__), 'data/testdef.txt')

    c = cstruct.cstruct()
    c.loadfile(path, compiled=False)
    assert 'test' in c.typedefs


def test_read_type_name():
    c = cstruct.cstruct()
    c.read('uint32', b'\x01\x00\x00\x00') == 1


def test_type_resolve():
    c = cstruct.cstruct()

    assert c.resolve('byte') == c.int8

    with pytest.raises(cstruct.ResolveError) as excinfo:
        c.resolve('fake')
    assert "Unknown type" in str(excinfo.value)

    c.addtype('ref0', 'uint32')
    for i in range(1, 15):  # Recursion limit is currently 10
        c.addtype('ref{}'.format(i), 'ref{}'.format(i - 1))

    with pytest.raises(cstruct.ResolveError) as excinfo:
        c.resolve('ref14')
    assert "Recursion limit exceeded" in str(excinfo.value)


def test_constants():
    d = """
    #define a 1
    #define b 0x2
    #define c "test"
    """
    c = cstruct.cstruct()
    c.load(d)

    assert c.a == 1
    assert c.b == 2
    assert c.c == "test"

    with pytest.raises(AttributeError):
        c.d

    c.load("""#define d = 1 << 1""")  # Expressions in constants are currently not supported
    with pytest.raises(AttributeError):
        c.d


def test_struct_definitions():
    c = cstruct.cstruct()
    c.load("""
    struct _test {
        uint32  a;
        // uint32 comment
        uint32  b;
    } test, test1;
    """, compiled=False)

    assert c._test == c.test == c.test1
    assert c.test.name == '_test'
    assert c._test.name == '_test'

    assert 'a' in c.test.lookup
    assert 'b' in c.test.lookup

    with pytest.raises(cstruct.ParserError):
        c.load("""
        struct {
            uint32  a;
        };
        """)


def test_typedef():
    c = cstruct.cstruct()
    c.load("""typedef uint32 test;""")

    assert c.test == 'uint32'
    assert c.resolve('test') == c.uint32


def test_lookups():
    c = cstruct.cstruct()
    c.load("""
    #define test_1 1
    #define test_2 2
    $a = {'test_1': 3, 'test_2': 4}
    """, compiled=False)
    assert c.lookups['a'] == {1: 3, 2: 4}


def test_expressions():
    c = cstruct.cstruct()
    c.load("""
    #define const 1
    struct test {
        uint8   flag;
        uint8   data_1[flag & 1 * 4];
        uint8   data_2[flag & (1 << 2)];
        uint8   data_3[const];
    };
    """, compiled=False)

    a = c.test(b'\x01\x00\x01\x02\x03\xff')
    assert a.flag == 1
    assert a.data_1 == [0, 1, 2, 3]
    assert a.data_2 == []
    assert a.data_3 == [255]

    a = c.test(b'\x04\x04\x05\x06\x07\xff')
    assert a.flag == 4
    assert a.data_1 == []
    assert a.data_2 == [4, 5, 6, 7]
    assert a.data_3 == [255]


def test_struct_sizes():
    c = cstruct.cstruct()
    c.load("""
    struct static {
        uint32  test;
    };

    struct dynamic {
        uint32  test[];
    };
    """, compiled=False)

    assert len(c.static) == 4
    c.static.add_field("another", c.uint32)
    assert len(c.static) == 8
    c.static.add_field("atoffset", c.uint32, 12)
    assert len(c.static) == 16

    a = c.static(b'\x01\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00')
    assert a.test == 1
    assert a.another == 2
    assert a.atoffset == 3

    with pytest.raises(TypeError) as excinfo:
        len(c.dynamic)
    assert str(excinfo.value) == "Dynamic size"


def test_hexdump(capsys):
    cstruct.hexdump(b'\x00' * 16)
    captured = capsys.readouterr()
    assert captured.out == "00000000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ................\n"


def test_dumpstruct(capsys):
    c = cstruct.cstruct()
    c.load("""
    struct test {
        uint32 testval;
    };
    """, compiled=False)

    data = b'\x39\x05\x00\x00'
    a = c.test(data)

    cstruct.dumpstruct(c.test, data)
    captured_1 = capsys.readouterr()

    cstruct.dumpstruct(a)
    captured_2 = capsys.readouterr()

    assert captured_1.out == captured_2.out
