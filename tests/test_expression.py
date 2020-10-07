import pytest

from dissect.cstruct.expression import Expression


testdata = [
    ('1 * 0', 0),
    ('1 * 1', 1),
    ('7 * 8', 56),
    ('7*8', 56),
    ('7 *8', 56),
    ('   7  *     8  ', 56),
    ('0 / 1', 0),
    ('1 / 1', 1),
    ('2 / 2', 1),
    ('3 / 2', 1),
    ('4 / 2', 2),
    ('1 % 1', 0),
    ('1 % 2', 1),
    ('5 % 3', 2),
    ('0 + 0', 0),
    ('1 + 0', 1),
    ('1 + 3', 4),
    ('0 - 0', 0),
    ('1 - 0', 1),
    ('0 - 1', -1),
    ('1 - 3', -2),
    ('3 - 1', 2),
    ('0x0 >> 0', 0x0),
    ('0x1 >> 0', 0x1),
    ('0x1 >> 1', 0x0),
    ('0xf0 >> 4', 0xf),
    ('0x0 << 4', 0),
    ('0x1 << 0', 1),
    ('0xf << 4', 0xf0),
    ('0 & 0', 0),
    ('1 & 0', 0),
    ('1 & 1', 1),
    ('1 & 2', 0),
    ('1 ^ 1', 0),
    ('1 ^ 0', 1),
    ('1 ^ 3', 2),
    ('0 | 0', 0),
    ('0 | 1', 1),
    ('1 | 1', 1),
    ('1 | 2', 3),
    # This type of expression is not supported by the parser and will fail.
    # ('4 * 1 + 1', 5),
    ('-42', -42),
    ('42 + (-42)', 0),
    ('A + 5', 13),
    ('21 - B', 8),
    ('A + B', 21),
]


class Consts(object):
    consts = {
        'A': 8,
        'B': 13,
    }


def id_fn(val):
    if isinstance(val, (str,)):
        return val


@pytest.mark.parametrize('expression, answer',
                         testdata,
                         ids=id_fn)
def test_expression(expression, answer):
    parser = Expression(Consts(), expression)
    assert parser.evaluate() == answer
