"""Reply decoding for the "old" (TCP) frame. Pure functions.

Java ``ExternalNetworkSendProtocol.Receive`` returns the raw bytes as ints and the callers index
them directly (``reply[12]``, ``reply[14..]``). We decode the same layout into a
:class:`ReplyFrame` and expose the *same* success rules as named functions so the rule is explicit.
"""
from __future__ import annotations

from typing import Optional, Tuple

from ..exceptions import ProtocolError
from ..models import ReplyFrame
from .encoder import END, PACKET_RETURN, START, checksum16, unescape_serial

#: id(4) + length(2) + reserved(2) + 68/E8 + card + id + cmd
HEADER_LEN = 12
CHECKSUM_LEN = 2


def expected_total_length(prefix: bytes) -> Optional[int]:
    """Total frame size implied by the 2-byte length at offset 4 (``8 + LEN``), or None."""
    if len(prefix) < 6:
        return None
    return 8 + (prefix[4] | (prefix[5] << 8))


def decode_reply(raw: bytes) -> ReplyFrame:
    """Decode an old-format reply. Raises :class:`ProtocolError` if it cannot be framed."""
    if len(raw) < HEADER_LEN:
        raise ProtocolError(f"reply too short ({len(raw)} bytes, need >= {HEADER_LEN})")
    length = raw[4] | (raw[5] << 8)
    total = 8 + length
    checksum_ok: Optional[bool] = None
    body_end = len(raw)
    if len(raw) >= total and total >= HEADER_LEN + CHECKSUM_LEN:
        body_end = total - CHECKSUM_LEN
        got = raw[body_end] | (raw[body_end + 1] << 8)
        checksum_ok = got == checksum16(raw[8:body_end])
    ptype = raw[8]
    if ptype != PACKET_RETURN:
        raise ProtocolError(f"unexpected packet type 0x{ptype:02X} (expected 0xE8 return packet)")
    return ReplyFrame(
        raw=bytes(raw),
        id_code=(raw[0], raw[1], raw[2], raw[3]),
        declared_length=length,
        packet_type=ptype,
        card_type=raw[9],
        card_id=raw[10],
        command=raw[11],
        body=bytes(raw[HEADER_LEN:body_end]),
        checksum_ok=checksum_ok,
    )


#: Java ``Receive`` hands generation-2 replies on only if they are at least this long.
MIN_SERIAL_REPLY = 20


def decode_serial_reply(raw: bytes) -> ReplyFrame:
    """Decode a generation-2 reply: ``A5 | MAC(12) | 00 | escaped(E8 32 FF cmd body chk(2)) | AE``.

    Java ``Receive`` (packageDataType != 1): skips the first 14 bytes, un-escapes ``AA x`` ->
    ``A0|x`` up to (excluding) the final byte, then reports ``reply[11]=cmd`` and
    ``reply[12]=first body byte``. We decode the same layout and also verify the checksum.
    """
    if len(raw) < MIN_SERIAL_REPLY:
        raise ProtocolError(f"generation-2 reply too short ({len(raw)} bytes, need >= "
                            f"{MIN_SERIAL_REPLY})")
    if raw[0] != START or raw[-1] != END:
        raise ProtocolError("generation-2 reply is not delimited by A5 .. AE")
    inner = unescape_serial(raw[14:-1])
    if len(inner) < 6:
        raise ProtocolError("generation-2 reply payload too short after un-escaping")
    if inner[0] != PACKET_RETURN:
        raise ProtocolError(f"unexpected packet type 0x{inner[0]:02X} (expected 0xE8)")
    got = inner[-2] | (inner[-1] << 8)
    return ReplyFrame(
        raw=bytes(raw),
        id_code=(0, 0, 0, 0),
        declared_length=len(inner),
        packet_type=inner[0],
        card_type=inner[1],
        card_id=inner[2],
        command=inner[3],
        body=bytes(inner[4:-2]),
        checksum_ok=got == checksum16(inner[:-2]),
        generation=2,
        mac=raw[1:13].decode("latin-1"),
    )


def java_foreign_ack(frame: ReplyFrame) -> bool:
    """Java ``sendDataMulti`` success rule: first body byte (``reply[12]``) is ``0``.

    Same rule for both generations (Java indexes the un-escaped frame identically). It is only what
    the Java SDK checks; the 0x7B reply layout is undocumented, so whether this byte really means
    "accepted" is UNVERIFIED on hardware.
    """
    return len(frame.body) > 0 and frame.body[0] == 0


def brightness_from_reply(frame: ReplyFrame) -> Tuple[int, ...]:
    """Java ``getBrightness``: ``reply[14:38]`` (24 hourly values; manual CMD 0x46)."""
    raw = frame.raw
    if len(raw) < 14 + 24:
        raise ProtocolError(f"brightness reply too short ({len(raw)} bytes)")
    return tuple(raw[14:38])
