import string
import pprint

from dissect.cstruct.types.instance import Instance
from dissect.cstruct.types.structure import Structure

COLOR_RED = '\033[1;31m'
COLOR_GREEN = '\033[1;32m'
COLOR_YELLOW = '\033[1;33m'
COLOR_BLUE = '\033[1;34m'
COLOR_PURPLE = '\033[1;35m'
COLOR_CYAN = '\033[1;36m'
COLOR_WHITE = '\033[1;37m'
COLOR_NORMAL = '\033[1;0m'

COLOR_BG_RED = '\033[1;41m\033[1;37m'
COLOR_BG_GREEN = '\033[1;42m\033[1;37m'
COLOR_BG_YELLOW = '\033[1;43m\033[1;37m'
COLOR_BG_BLUE = '\033[1;44m\033[1;37m'
COLOR_BG_PURPLE = '\033[1;45m\033[1;37m'
COLOR_BG_CYAN = '\033[1;46m\033[1;37m'
COLOR_BG_WHITE = '\033[1;47m\033[1;30m'

PRINTABLE = string.digits + string.ascii_letters + string.punctuation + " "


def _hexdump(bytes_hex, offset=0, prefix="", palette=None):
    """Hexdump some data.

    Args:
        bytes_hex: Bytes to hexdump.
        offset: Byte offset of the hexdump.
        prefix: Optional prefix.
        palette: Colorize the hexdump using this color pattern.
    """
    if palette:
        palette = palette[::-1]

    remaining = 0
    active = None

    for i in range(0, len(bytes_hex), 16):
        values = ""
        chars = []

        for j in range(16):
            if not active and palette:
                remaining, active = palette.pop()
                values += active
            elif active and j == 0:
                values += active

            if i + j >= len(bytes_hex):
                values += "  "
            else:
                char = bytes_hex[i + j]
                char = chr(char)

                print_char = char if char in PRINTABLE else "."

                if active:
                    values += "{:02x}".format(ord(char))
                    chars.append(active + print_char + COLOR_NORMAL)
                else:
                    values += "{:02x}".format(ord(char))
                    chars.append(print_char)

                remaining -= 1
                if remaining == 0:
                    active = None

                    if palette is not None:
                        values += COLOR_NORMAL

                if j == 15:
                    if palette is not None:
                        values += COLOR_NORMAL

            values += " "
            if j == 7:
                values += " "

        chars = "".join(chars)
        yield "{}{:08x}  {:48s}  {}".format(prefix, offset + i, values, chars)


def hexdump(bytes_hex, palette=None, offset=0, prefix="", output='print'):
    """Hexdump some data.

    Args:
        bytes_hex: Bytes to hexdump.
        palette: Colorize the hexdump using this color pattern.
        offset: Byte offset of the hexdump.
        prefix: Optional prefix.
        output: Output format, can be 'print', 'generator' or 'string'.
    """
    generator = _hexdump(bytes_hex, offset=offset, prefix=prefix, palette=palette)
    if output == 'print':
        print("\n".join(generator))
    elif output == 'generator':
        return generator
    elif output == 'string':
        return '\n'.join(list(generator))
    else:
        raise ValueError("Invalid output argument: '{:s}' (should be 'print', 'generator' or 'string').".format(output))


def _dumpstruct(generic_obj, obj_dump, color, data, output, offset):
    palette = []
    colors = [
        (COLOR_RED, COLOR_BG_RED),
        (COLOR_GREEN, COLOR_BG_GREEN),
        (COLOR_YELLOW, COLOR_BG_YELLOW),
        (COLOR_BLUE, COLOR_BG_BLUE),
        (COLOR_PURPLE, COLOR_BG_PURPLE),
        (COLOR_CYAN, COLOR_BG_CYAN),
        (COLOR_WHITE, COLOR_BG_WHITE),
    ]
    ci = 0
    out = ["struct {}:".format(obj_dump.name)]
    foreground, background = None, None
    for field in generic_obj._type.fields:
        if color:
            foreground, background = colors[ci % len(colors)]
            palette.append((generic_obj._size(field.name), background))
        ci += 1

        value = getattr(generic_obj, field.name)
        if isinstance(value, str):
            value = repr(value)
        elif isinstance(value, int):
            value = hex(value)
        elif isinstance(value, list):
            value = pprint.pformat(value)
            if '\n' in value:
                value = value.replace('\n', '\n{}'.format(' ' * (len(field.name) + 4)))

        if color:
            out.append("- {}{}{}: {}".format(foreground, field.name, COLOR_NORMAL, value))
        else:
            out.append("- {}: {}".format(field.name, value))

    out = '\n'.join(out)

    if output == 'print':
        print()
        hexdump(data, palette, offset=offset)
        print()
        print(out)
    elif output == 'string':
        return '\n'.join(['', hexdump(data, palette, offset=offset, output='string'), '', out])


def dumpstruct(obj_dump, data=None, offset=0, color=True, output='print'):
    """Dump a structure or parsed structure instance.

    Prints a colorized hexdump and parsed structure output.

    Args:
        obj_dump: Structure or Instance to dump.
        data: Bytes to parse the Structure on, if t is not a parsed Instance.
        offset: Byte offset of the hexdump.
        output: Output format, can be 'print' or 'string'.
    """
    if output not in ('print', 'string'):
        raise ValueError(
            "Invalid output argument: '{:s}' (should be 'print' or 'string').".format(output)
        )

    if isinstance(obj_dump, Instance):
        return _dumpstruct(obj_dump, obj_dump._type, color, obj_dump.dumps(), output, offset)
    elif isinstance(obj_dump, Structure) and data:
        return _dumpstruct(obj_dump(data), obj_dump, color, data, output, offset)
    else:
        raise ValueError("Invalid arguments")
