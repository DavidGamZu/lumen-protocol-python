"""lumen_protocol - native Python client for Lumen / C-Power LED controllers (offline-verified only).

Behaviour is derived from the Java SDK 1.4.7 bytecode and cross-checked against the local
C-Power5200 SDK API Manual. It has NOT been verified against a physical controller.

    from lumen_protocol import LEDClient
    with LEDClient("192.168.1.100", 5000, timeout=5) as c:
        result = c.send_text(0, "Hello")
"""
import logging as _logging

from .client import LEDClient
from .config import ClientConfig
from .exceptions import (
    ConnectError,
    LEDError,
    LEDTimeoutError,
    NegativeAcknowledgmentError,
    NotSupportedError,
    ProtocolError,
    ReceiveTimeoutError,
    TransportError,
    UnsupportedProtocolError,
    ValidationError,
)
from .models import (
    Color,
    DeliveryStage,
    FontSize,
    HAlign,
    ProbeResult,
    ReplyFrame,
    SendResult,
    TextOptions,
    VAlign,
)
from .protocol import build_text_request

_logging.getLogger("lumen_protocol").addHandler(_logging.NullHandler())

__version__ = "0.1.0"

__all__ = [
    "LEDClient", "ClientConfig", "build_text_request", "Color", "FontSize", "HAlign", "VAlign",
    "DeliveryStage", "ProbeResult", "ReplyFrame", "SendResult", "TextOptions",
    "LEDError", "ValidationError", "TransportError", "ConnectError", "LEDTimeoutError",
    "ReceiveTimeoutError", "ProtocolError", "NegativeAcknowledgmentError",
    "UnsupportedProtocolError", "NotSupportedError", "__version__",
]
