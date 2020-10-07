from io import BytesIO


class Instance(object):
    """Holds parsed structure data."""
    __slots__ = ('_type', '_values', '_sizes')

    def __init__(self, type_, values, sizes=None):
        # Done in this manner to check if the attr is in the lookup
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
