class Error(Exception):
    """Base class for exceptions for this module.
    It is used to recognize errors specific to this module"""
    pass


class ParserError(Error):
    pass


class ResolveError(Error):
    pass


class NullPointerDereference(Error):
    pass
