from dissect import cstruct


def test_compiled_struct():
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
    c.load(d, compiled=True)

    d = b'testt\x00e\x00s\x00t\x00\x01\x02\x03\x04\x05\x06\x07lalala\x00t\x00e\x00s\x00t\x00\x00\x00'
    a = c.test(d)

    assert a.magic == b'test'
    assert a.wmagic == 'test'
    assert a.a == 0x01
    assert a.b == 0x0302
    assert a.c == 0x07060504
    assert a.string == b'lalala'
    assert a.wstring == 'test'
    assert d == a.dumps()


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
    c = cstruct.cstruct()
    c.load(d, compiled=True)
    c.endian = '>'

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


def test_compiled_int24():
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
    c.load(d, compiled=True)

    a = c.test(b'AAABBBCCC\x02\x00\x00DDDEEE\xff\xff\xff\x01\xff\xff\x02\xff\xff\x03\xff\xff')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == -1
    assert a.d == [-255, -254, -253]


def test_compiled_uint24():
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
    c.load(d, compiled=True)

    a = c.test(b'AAABBBCCC\x02\x00\x00DDDEEE\xff\xff\xff')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == 0xffffff


def test_compiled_int24_be():
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
    c.load(d, compiled=True)
    c.endian = '>'

    a = c.test(b'AAABBBCCC\x00\x00\x02DDDEEE\xff\xff\xff\xff\xff\x01\xff\xff\x02\xff\xff\x03')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == -1
    assert a.d == [-255, -254, -253]


def test_compiled_uint24_be():
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
    c.load(d, compiled=True)
    c.endian = '>'

    a = c.test(b'AAABBBCCC\x00\x00\x02DDDEEE\xff\xff\xff')
    assert a.a == 0x414141
    assert a.b == [0x424242, 0x434343]
    assert a.len == 0x02
    assert a.dync == [0x444444, 0x454545]
    assert a.c == 0xffffff


def test_compiled_enum():
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
        Test16  l[2];
    };
    """
    c = cstruct.cstruct()
    c.load(d, compiled=True)

    a = c.test(b'\x01\x00\x02\x00\x01\x00\x00\x02\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x02\x00')
    assert a.a16.enum == c.Test16 and a.a16.value == c.Test16.A
    assert a.b16.enum == c.Test16 and a.b16.value == c.Test16.B
    assert a.a24.enum == c.Test24 and a.a24.value == c.Test24.A
    assert a.b24.enum == c.Test24 and a.b24.value == c.Test24.B
    assert a.a32.enum == c.Test32 and a.a32.value == c.Test32.A
    assert a.b32.enum == c.Test32 and a.b32.value == c.Test32.B

    assert len(a.l) == 2
    assert a.l[0].enum == c.Test16 and a.l[0].value == c.Test16.A
    assert a.l[1].enum == c.Test16 and a.l[1].value == c.Test16.B


def test_compiled_bitfield():
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
    c.load(d, compiled=True)

    a = c.test(b'\x03\x00\xff\x00\x00\x00\x1f\x00')
    assert a.a == 0b1
    assert a.b == 0b1
    assert a.c == 0xff
    assert a.d == 0b11
    assert a.e == 0b111


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
    c.load(d, compiled=True)

    d = b'\x02\x00testt\x00e\x00s\x00t\x00\x01\x02\x03\x04\x05\x06\x07lalala\x00t\x00e\x00s\x00t\x00\x00\x00'
    p = c.ptrtest(d)
    a = p.ptr

    assert a.magic == b'test'
    assert a.wmagic == 'test'
    assert a.a == 0x01
    assert a.b == 0x0302
    assert a.c == 0x07060504
    assert a.string == b'lalala'
    assert a.wstring == 'test'
