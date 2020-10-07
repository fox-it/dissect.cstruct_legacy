import os
import pytest
from io import BytesIO

from dissect import cstruct
from dissect.cstruct.types.bytesinteger import BytesInteger
from dissect.cstruct.utils import dumpstruct, hexdump


def test_simple_types():
    c = cstruct.cstruct()
    assert c.uint32(b'\x01\x00\x00\x00') == 1
    assert c.uint32[10](b"A" * 20 + b"B" * 20) == [0x41414141] * 5 + [0x42424242] * 5
    assert c.uint32[None](b"A" * 20 + b"\x00" * 4) == [0x41414141] * 5

    with pytest.raises(EOFError):
        c.char[None](b'aaa')

    with pytest.raises(EOFError):
        c.wchar[None](b'a\x00a\x00a')


@pytest.mark.parametrize('compiled', [True, False])
def test_simple_struct(compiled):
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
    c.load(d, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_simple_struct_be(compiled):
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
    c.load(d, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_bytes_integer_struct_signed(compiled):
    d = """
    struct test {
        int24   a;
        int24   b[2];
        int24   len;
        int24   dync[len];
        int24   c;
        int24   d[3];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    a = c.test(b'AAABBBCCC\x02\x00\x00DDDEEE\xff\xff\xff\x01\xff\xff\x02\xff\xff\x03\xff\xff')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == -1
    assert a.d == [-255, -254, -253]


@pytest.mark.parametrize('compiled', [True, False])
def test_bytes_integer_struct_unsigned(compiled):
    d = """
    struct test {
        uint24  a;
        uint24  b[2];
        uint24  len;
        uint24  dync[len];
        uint24  c;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    a = c.test(b'AAABBBCCC\x02\x00\x00DDDEEE\xff\xff\xff')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == 0xffffff


@pytest.mark.parametrize('compiled', [True, False])
def test_bytes_integer_struct_signed_be(compiled):
    d = """
    struct test {
        int24   a;
        int24   b[2];
        int24   len;
        int24   dync[len];
        int24   c;
        int24   d[3];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)
    c.endian = '>'

    a = c.test(b'AAABBBCCC\x00\x00\x02DDDEEE\xff\xff\xff\xff\xff\x01\xff\xff\x02\xff\xff\x03')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == -1
    assert a.d == [-255, -254, -253]


@pytest.mark.parametrize('compiled', [True, False])
def test_bytes_integer_struct_unsigned_be(compiled):
    d = """
    struct test {
        uint24  a;
        uint24  b[2];
        uint24  len;
        uint24  dync[len];
        uint24  c;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)
    c.endian = '>'

    a = c.test(b'AAABBBCCC\x00\x00\x02DDDEEE\xff\xff\xff')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == 0xffffff


@pytest.mark.parametrize('compiled', [True, False])
def test_enum(compiled):
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

    struct test_expr {
        uint16  size;
        Test16  expr[size * 2];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

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

    assert c.test_expr(b'\x01\x00\x01\x00\x02\x00').expr == [c.Test16.A, c.Test16.B]
    assert c.test_expr(size=1, expr=[c.Test16.A, c.Test16.B]).dumps() == b'\x01\x00\x01\x00\x02\x00'

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


@pytest.mark.parametrize('compiled', [True, False])
def test_enum_comments(compiled):
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
    c.load(d, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_flag(compiled):
    d = """
    flag Test {
        a,
        b,
        c,
        d
    };

    flag Odd {
        a = 2,
        b,
        c,
        d = 32, e, f,
        g
    };
    """

    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    assert c.Test.a == 1
    assert c.Test.b == 2
    assert c.Test.c == 4
    assert c.Test.d == 8

    assert c.Odd.a == 2
    assert c.Odd.b == 4
    assert c.Odd.c == 8
    assert c.Odd.d == 32
    assert c.Odd.e == 64
    assert c.Odd.f == 128
    assert c.Odd.g == 256

    assert c.Test.a == c.Test.a
    assert c.Test.a != c.Test.b
    assert bool(c.Test(0)) is False
    assert bool(c.Test(1)) is True

    assert c.Test.a | c.Test.b == 3
    assert str(c.Test.c | c.Test.d) == 'Test.d|c'
    assert repr(c.Test.a | c.Test.b) == '<Test.b|a: 3>'
    assert c.Test(2) == c.Test.b
    assert c.Test(3) == c.Test.a | c.Test.b
    assert c.Test.c & 12 == c.Test.c
    assert c.Test.b & 12 == 0
    assert c.Test.b ^ c.Test.a == c.Test.a | c.Test.b

    assert ~c.Test.a == -2
    assert str(~c.Test.a) == 'Test.d|c|b'


@pytest.mark.parametrize('compiled', [True, False])
def test_flag_read(compiled):
    d = """
    flag Test16 : uint16 {
        A = 0x1,
        B = 0x2
    };

    flag Test24 : uint24 {
        A = 0x1,
        B = 0x2
    };

    flag Test32 : uint32 {
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
        Test16  l[2];
        Test16  c16;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    a = c.test(b'\x01\x00\x02\x00\x01\x00\x00\x02\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x02\x00\x03\x00')
    assert a.a16.enum == c.Test16 and a.a16.value == c.Test16.A
    assert a.b16.enum == c.Test16 and a.b16.value == c.Test16.B
    assert a.a24.enum == c.Test24 and a.a24.value == c.Test24.A
    assert a.b24.enum == c.Test24 and a.b24.value == c.Test24.B
    assert a.a32.enum == c.Test32 and a.a32.value == c.Test32.A
    assert a.b32.enum == c.Test32 and a.b32.value == c.Test32.B

    assert len(a.l) == 2
    assert a.l[0].enum == c.Test16 and a.l[0].value == c.Test16.A
    assert a.l[1].enum == c.Test16 and a.l[1].value == c.Test16.B

    assert a.c16 == c.Test16.A | c.Test16.B
    assert a.c16 & c.Test16.A
    assert str(a.c16) == 'Test16.B|A'


@pytest.mark.parametrize('compiled', [True, False])
def test_bitfield(compiled):
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
    c.load(d, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_bitfield_be(compiled):
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
    c.load(d, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_write_struct(compiled):
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
    c.load(d, compiled=compiled)
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
    assert c.test(magic=b'test', wmagic=u'test', a=0x01, b=0x0302, c=0x07060504, string=b'lalala',
                  wstring=u'test').dumps() == d


@pytest.mark.parametrize('compiled', [True, False])
def test_write_struct_be(compiled):
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
    c.load(d, compiled=compiled)

    a = c.test()
    a.magic = 'test'
    a.wmagic = 'test'
    a.a = 0x01
    a.b = 0x0203
    a.c = 0x04050607
    a.string = b'lalala'
    a.wstring = 'test'

    assert a.dumps() == b'test\x00t\x00e\x00s\x00t\x01\x02\x03\x04\x05\x06\x07lalala\x00\x00t\x00e\x00s\x00t\x00\x00'


@pytest.mark.parametrize('compiled', [True, False])
def test_write_bitfield(compiled):
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


@pytest.mark.parametrize('compiled', [True, False])
def test_write_bitfield_be(compiled):
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
    c.load(d, compiled=compiled)

    a = c.test()
    a.a = 0b1
    a.b = 0b1
    a.c = 0xff
    a.d = 0b11
    a.e = 0b111

    assert a.dumps() == b'\xc0\x00\x00\x00\x00\xff\xf8\x00'


@pytest.mark.parametrize('compiled', [True, False])
def test_write_enum(compiled):
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
    c.load(d, compiled=compiled)

    a = c.test()
    a.a16 = c.Test16.A
    a.b16 = c.Test16.B
    a.a24 = c.Test24.A
    a.b24 = c.Test24.B
    a.a32 = c.Test32.A
    a.b32 = c.Test32.B
    a.list = [c.Test16.A, c.Test16.B]

    assert a.dumps() == b'\x01\x00\x02\x00\x01\x00\x00\x02\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x02\x00'


@pytest.mark.parametrize('compiled', [True, False])
def test_enum_name(compiled):
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
    c.load(d, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_pointers(compiled):
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
    c.load(d, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_duplicate_type(compiled):
    d = """
    struct test {
        uint32  a;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    with pytest.raises(ValueError):
        c.load(d)


@pytest.mark.parametrize('compiled', [True, False])
def test_load_file(compiled):
    path = os.path.join(os.path.dirname(__file__), 'data/testdef.txt')

    c = cstruct.cstruct()
    c.loadfile(path, compiled=compiled)
    assert 'test' in c.typedefs


def test_read_type_name():
    c = cstruct.cstruct()
    c.read('uint32', b'\x01\x00\x00\x00') == 1


def test_type_resolve():
    c = cstruct.cstruct()

    assert c.resolve('BYTE') == c.int8

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
    #define d 1 << 1
    """
    c = cstruct.cstruct()
    c.load(d)

    assert c.a == 1
    assert c.b == 2
    assert c.c == "test"
    assert c.d == 2


@pytest.mark.parametrize('compiled', [True, False])
def test_struct_definitions(compiled):
    c = cstruct.cstruct()
    c.load("""
    struct _test {
        uint32  a;
        // uint32 comment
        uint32  b;
    } test, test1;
    """, compiled=compiled)

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

    assert c.test == c.uint32
    assert c.resolve('test') == c.uint32


@pytest.mark.parametrize('compiled', [True, False])
def test_lookups(compiled):
    c = cstruct.cstruct()
    c.load("""
    #define test_1 1
    #define test_2 2
    $a = {'test_1': 3, 'test_2': 4}
    """, compiled=compiled)
    assert c.lookups['a'] == {1: 3, 2: 4}


@pytest.mark.parametrize('compiled', [True, False])
def test_expressions(compiled):
    c = cstruct.cstruct()
    c.load("""
    #define const 1
    struct test {
        uint8   flag;
        uint8   data_1[flag & 1 * 4];
        uint8   data_2[flag & (1 << 2)];
        uint8   data_3[const];
    };
    """, compiled=compiled)

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


@pytest.mark.parametrize('compiled', [True, False])
def test_struct_sizes(compiled):
    c = cstruct.cstruct()
    c.load("""
    struct static {
        uint32  test;
    };

    struct dynamic {
        uint32  test[];
    };
    """, compiled=compiled)

    assert len(c.static) == 4

    if not compiled:
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
    else:
        with pytest.raises(NotImplementedError) as excinfo:
            c.static.add_field("another", c.uint32)
        assert str(excinfo.value) == "Can't add fields to a compiled structure"


@pytest.mark.parametrize('compiled', [True, False])
def test_default_constructors(compiled):
    c = cstruct.cstruct()
    c.load("""
    enum Enum {
        a = 0,
        b = 1
    };

    flag Flag {
        a = 0,
        b = 1
    };

    struct test {
        uint32  t_int;
        uint32  t_int_array[2];
        uint24  t_bytesint;
        uint24  t_bytesint_array[2];
        char    t_char;
        char    t_char_array[2];
        wchar   t_wchar;
        wchar   t_wchar_array[2];
        Enum    t_enum;
        Enum    t_enum_array[2];
        Flag    t_flag;
        Flag    t_flag_array[2];
    };
    """, compiled=compiled)

    testobj = c.test()
    assert testobj.t_int == 0
    assert testobj.t_int_array == [0, 0]
    assert testobj.t_bytesint == 0
    assert testobj.t_bytesint_array == [0, 0]
    assert testobj.t_char == b'\x00'
    assert testobj.t_char_array == b'\x00\x00'
    assert testobj.t_wchar == u'\x00'
    assert testobj.t_wchar_array == u'\x00\x00'
    assert testobj.t_enum == c.Enum(0)
    assert testobj.t_enum_array == [c.Enum(0), c.Enum(0)]
    assert testobj.t_flag == c.Flag(0)
    assert testobj.t_flag_array == [c.Flag(0), c.Flag(0)]

    assert testobj.dumps() == b'\x00' * 54


@pytest.mark.parametrize('compiled', [True, False])
def test_union(compiled):
    d = """
    union test {
        uint32 a;
        char   b[8];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    assert len(c.test) == 8

    a = c.test(b'zomgbeef')
    assert a.a == 0x676d6f7a
    assert a.b == b'zomgbeef'

    assert a.dumps() == b'zomgbeef'
    assert c.test().dumps() == b'\x00\x00\x00\x00\x00\x00\x00\x00'


@pytest.mark.parametrize('compiled', [True, False])
def test_nested_struct(compiled):
    c = cstruct.cstruct()
    c.load("""
    struct test_named {
        char magic[4];
        struct {
            uint32 a;
            uint32 b;
        } a;
        struct {
            char   c[8];
        } b;
    };

    struct test_anonymous {
        char magic[4];
        struct {
            uint32 a;
            uint32 b;
        };
        struct {
            char   c[8];
        };
    };
    """, compiled=compiled)

    assert len(c.test_named) == len(c.test_anonymous) == 20

    a = c.test_named(b'zomg\x39\x05\x00\x00\x28\x23\x00\x00deadbeef')
    assert a.magic == b'zomg'
    assert a.a.a == 1337
    assert a.a.b == 9000
    assert a.b.c == b'deadbeef'

    b = c.test_anonymous(b'zomg\x39\x05\x00\x00\x28\x23\x00\x00deadbeef')
    assert b.magic == b'zomg'
    assert b.a == 1337
    assert b.b == 9000
    assert b.c == b'deadbeef'


@pytest.mark.parametrize('compiled', [True, False])
def test_nested_union(compiled):
    d = """
    struct test {
        char magic[4];
        union {
            struct {
                uint32 a;
                uint32 b;
            } a;
            struct {
                char   b[8];
            } b;
        } c;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=False)

    assert len(c.test) == 12

    a = c.test(b'zomgholybeef')
    assert a.magic == b'zomg'
    assert a.c.a.a == 0x796c6f68
    assert a.c.a.b == 0x66656562
    assert a.c.b.b == b'holybeef'

    assert a.dumps() == b'zomgholybeef'


@pytest.mark.parametrize('compiled', [True, False])
def test_anonymous_union_struct(compiled):
    d = """
    typedef struct test
    {
        union
        {
            uint32 a;
            struct
            {
                char b[3];
                char c;
            };
        };
        uint32 d;
    }
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    b = b'\x01\x01\x02\x02\x03\x03\x04\x04'
    a = c.test(b)

    assert a.a == 0x02020101
    assert a.b == b'\x01\x01\x02'
    assert a.c == b'\x02'
    assert a.d == 0x04040303

    assert a.dumps() == b


@pytest.mark.parametrize('compiled', [True, False])
def test_config_flag_nocompile(compiled):
    d = """
    struct compiled_global
    {
        uint32  a;
    };

    #[nocompile]
    struct never_compiled
    {
        uint32  a;
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=compiled)

    if compiled:
        assert '+compiled' in repr(c.compiled_global)

    assert '+compiled' not in repr(c.never_compiled)


def test_hexdump(capsys):
    hexdump(b'\x00' * 16)
    captured = capsys.readouterr()
    assert captured.out == "00000000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ................\n"

    out = hexdump(b'\x00' * 16, output='string')
    assert out == "00000000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ................"

    out = hexdump(b'\x00' * 16, output='generator')
    assert next(out) == "00000000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ................"

    with pytest.raises(ValueError) as excinfo:
        hexdump('b\x00', output='str')
    assert str(excinfo.value) == "Invalid output argument: 'str' (should be 'print', 'generator' or 'string')."


@pytest.mark.parametrize('compiled', [True, False])
def test_dumpstruct(capsys, compiled):
    c = cstruct.cstruct()
    c.load("""
    struct test {
        uint32 testval;
    };
    """, compiled=compiled)

    data = b'\x39\x05\x00\x00'
    a = c.test(data)

    dumpstruct(c.test, data)
    captured_1 = capsys.readouterr()

    dumpstruct(a)
    captured_2 = capsys.readouterr()

    assert captured_1.out == captured_2.out

    out_1 = dumpstruct(c.test, data, output='string')
    out_2 = dumpstruct(a, output='string')

    assert out_1 == out_2

    with pytest.raises(ValueError) as excinfo:
        dumpstruct(a, output='generator')
    assert str(excinfo.value) == "Invalid output argument: 'generator' (should be 'print' or 'string')."


@pytest.mark.parametrize('compiled', [True, False])
def test_compiler_slicing_multiple(compiled):
    c = cstruct.cstruct()
    c.load("""
    struct compile_slicing {
        char single;
        char multiple[2];
    };
    """, compiled=compiled)
    a = c.compile_slicing(b'\x01\x02\x03')
    assert a.single == b'\x01'
    assert a.multiple == b'\x02\x03'


@pytest.mark.parametrize('compiled', [True, False])
def test_underscores_attribute(compiled):
    c = cstruct.cstruct()
    c.load("""
    struct __test {
        uint32 test_val;
    };
    """, compiled=compiled)

    data = b'\x39\x05\x00\x00'
    a = c.__test(data)
    assert a.test_val == 1337


def test_half_compiled_struct():
    from dissect.cstruct import RawType

    class OffByOne(RawType):
        def __init__(self, cstruct_obj):
            self._t = cstruct_obj.uint64
            super().__init__(cstruct_obj, 'OffByOne', 8)

        def _read(self, stream):
            return self._t._read(stream) + 1

        def _write(self, stream, data):
            return self._t._write(stream, data - 1)

    c = cstruct.cstruct()
    # Add an unsupported type for the cstruct compiler
    # so that it returns the original struct,
    # only partially compiling the struct.
    c.addtype("offbyone", OffByOne(c))
    c.load("""
    struct uncompiled {
        uint32      a;
        offbyone    b;
        uint16      c;
    };

    struct compiled {
        char        a[4];
        uncompiled  b;
        uint16      c;
    };
    """, compiled=True)

    assert '+compiled' not in repr(c.uncompiled)
    assert '+compiled' in repr(c.compiled)

    buf = b'zomg\x01\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03\x00\x04\x00'
    obj = c.compiled(buf)
    assert obj.a == b'zomg'
    assert obj.b.a == 1
    assert obj.b.b == 3
    assert obj.b.c == 3
    assert obj.c == 4

    assert obj.dumps() == buf
