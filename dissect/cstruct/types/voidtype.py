from dissect.cstruct.types.base import RawType


class VoidType(RawType):
    """Implements a void type."""

    def __init__(self):
        super().__init__(None, 'void')

    def _read(self, stream):
        return None
