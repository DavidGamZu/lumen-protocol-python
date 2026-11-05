"""Typed models: enums for protocol values and result objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Tuple

from ..exceptions import NegativeAcknowledgmentError


class Color(IntEnum):
    """Text colour index (Java ``crColor`` 1..7).

    Names: C-Power5200 SDK API Manual, "Rich3 Text" ("red green yellow blue purple cyan white").
    The Java sample comment lists "blue" twice; the manual says the 6th is cyan.
    """

    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    PURPLE = 5
    CYAN = 6
    WHITE = 7


class FontSize(IntEnum):
    """Font size index (Java ``nFontSize`` 0..7) -> point size in :data:`FONT_POINTS`."""

    PT8 = 0
    PT12 = 1
    PT16 = 2
    PT24 = 3
    PT32 = 4
    PT40 = 5
    PT48 = 6
    PT56 = 7


#: Java sample comment. The manual confirms 0,2..7; index 1 (12pt) is from the Java comment only.
FONT_POINTS = {0: 8, 1: 12, 2: 16, 3: 24, 4: 32, 5: 40, 6: 48, 7: 56}


class HAlign(IntEnum):
    LEFT = 0
    CENTER = 1
    RIGHT = 2


class VAlign(IntEnum):
    TOP = 0
    MIDDLE = 1
    BOTTOM = 2


class DeliveryStage(IntEnum):
    """How far a command is *known* to have progressed. Higher never implies display."""

    NOT_SENT = 0
    WRITE_SENT = 1        # bytes handed to the OS socket (no peer confirmation)
    REPLY_RECEIVED = 2    # a reply frame arrived
    DEVICE_ACK = 3        # reply satisfies the reference SDK's success rule


@dataclass(frozen=True)
class ReplyFrame:
    """Decoded "old" (TCP) reply frame. See docs/PROTOCOL.md."""

    raw: bytes
    id_code: Tuple[int, int, int, int]
    declared_length: int
    packet_type: int
    card_type: int
    card_id: int
    command: int
    body: bytes           # bytes between the command code and the 2-byte checksum
    checksum_ok: Optional[bool]  # None when the frame is truncated
    generation: int = 1          # 1 = "old" TCP frame, 2 = MAC-addressed A5..AE frame
    mac: Optional[str] = None    # generation 2 only


@dataclass(frozen=True)
class SendResult:
    """Outcome of one command. ``display_confirmed`` is never observable from the wire."""

    stage: DeliveryStage
    request: bytes
    reply: Optional[ReplyFrame] = None
    acknowledged: Optional[bool] = None   # None: no ack criterion applies / no reply
    display_confirmed: Optional[bool] = None
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def write_sent(self) -> bool:
        return self.stage >= DeliveryStage.WRITE_SENT

    @property
    def reply_received(self) -> bool:
        return self.stage >= DeliveryStage.REPLY_RECEIVED

    @property
    def ok(self) -> bool:
        """True only when the reference success rule was met (still NOT display confirmation)."""
        return self.stage == DeliveryStage.DEVICE_ACK

    def require_ack(self) -> "SendResult":
        """Raise :class:`NegativeAcknowledgmentError` unless the reference success rule was met."""
        if not self.ok:
            raise NegativeAcknowledgmentError(
                f"controller reply did not meet the success rule (stage={self.stage.name})", self)
        return self


@dataclass(frozen=True)
class TextOptions:
    """Parameters of ``send_text`` with the defaults of the demonstrated Java call."""

    color: int = 1
    font_size: int = 2
    speed: int = 1
    effect: int = 1
    stay_time: int = 3
    horizontal_alignment: int = 1
    vertical_alignment: int = 1


@dataclass(frozen=True)
class ProbeResult:
    """Parsed answer to the UDP ``CPower~?`` probe (see transport/udp.py)."""

    protocol: int         # 1 old, 2 new, 3 old+new, 8002 encrypted (Java UdpProtocol mapping)
    fields: Tuple[str, ...]
    mac: Optional[str]
