"""Exception hierarchy for lumen_protocol.

Every error raised on purpose by the SDK derives from :class:`LEDError`.
"""
from __future__ import annotations

from typing import Any, Optional


class LEDError(Exception):
    """Base class of all lumen_protocol errors."""


class ValidationError(LEDError, ValueError):
    """A caller supplied an argument that the reference SDK rejects or cannot encode."""


class TransportError(LEDError):
    """Socket-level failure (connect refused, reset, write failed...)."""


class ConnectError(TransportError):
    """The TCP connection could not be established."""


class LEDTimeoutError(TransportError):
    """No (complete) reply arrived before the deadline.

    ``result`` carries what is known: e.g. that the request bytes were written.
    A timeout means the *outcome is unknown*, not that nothing was displayed.
    """

    def __init__(self, message: str, result: Optional[Any] = None) -> None:
        super().__init__(message)
        self.result = result


class ReceiveTimeoutError(LEDTimeoutError):
    """The request was written but no reply arrived in time."""


class ProtocolError(LEDError):
    """A reply could not be decoded (too short, wrong packet type, bad checksum...)."""


class NegativeAcknowledgmentError(ProtocolError):
    """The controller answered, but the reply does not meet the reference success criterion."""

    def __init__(self, message: str, result: Optional[Any] = None) -> None:
        super().__init__(message)
        self.result = result


class UnsupportedProtocolError(LEDError):
    """The controller advertises a protocol generation this SDK does not implement."""


class NotSupportedError(LEDError, NotImplementedError):
    """A reference SDK feature that has not been recovered/implemented (never faked)."""
