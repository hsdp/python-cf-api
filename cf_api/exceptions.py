from requests_factory import APIException
from requests_factory import ResponseException
from requests_factory import InvalidStateException


class CFException(APIException):
    """Base class of all exceptions used in this library
    """
    pass


class UnavailableException(CFException):
    """Indicates that the requested Cloud Foundry component is unavailable
    """
    pass


class InvalidArgsException(CFException):
    """Indicates that invalid arguments have been provided to the function
    """
    pass


class NotFoundException(CFException):
    """Indicates that the requested object cannot be found
    """
    pass


class TimeoutException(CFException):
    """Indicates that an operation has timed out
    """
    pass
