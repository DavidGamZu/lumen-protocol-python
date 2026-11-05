"""Pure byte-level encoders. No I/O, no global state.

Every function cites the Java member it re-implements (read from bytecode with ``javap`` -
no Java source is included) and, where one exists, the independent manual section.
Java ``byte`` arithmetic is reproduced explicitly with ``& 0xFF``.
"""
from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from ..config import BROADCAST_ID_CODE
from ..exceptions import ValidationError

CARD_TYPE = 0x32        # fixed "card type" code (manual 2.1.1 / bytecode: bipush 50)
PACKET_SEND = 0x68      # "send packet" (manual: 0x68 send / 0xE8 return)
PACKET_RETURN = 0xE8
CARD_ID_GROUP = 0xFF    # "0xFF: group address" (bytecode: iconst_m1)
PROTOCOL_FOREIGN = 0x7B  # 123: "external call" data protocol code
DEFAULT_ADDITIONAL_INFO = 0x11  # package_control_old default (bipush 17)

START = 0xA5
END = 0xAE
ESC = 0xAA


def checksum16(data: bytes) -> int:
    """Sum of bytes, 16-bit (manual: "cumulative each byte... 16bit unsigned")."""
    return sum(data) & 0xFFFF


def _le16(value: int) -> bytes:
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


def parse_id_code(id_code: str) -> bytes:
    """Dotted quad -> 4 bytes (Java: ``split("\\\\.")`` + ``Integer.parseInt`` + ``(byte)``)."""
    parts = id_code.split(".")
    if len(parts) != 4:
        raise ValidationError(f"id_code must be a dotted quad, got {id_code!r}")
    try:
        nums = [int(p) for p in parts]
    except ValueError as exc:
        raise ValidationError(f"id_code must be numeric, got {id_code!r}") from exc
    if any(n < 0 or n > 255 for n in nums):
        raise ValidationError(f"id_code octets must be 0..255, got {id_code!r}")
    return bytes(nums)


# --------------------------------------------------------------------------- framing
def pack_foreign_data(data: bytes, index: int = 0, count: int = 1,
                      flag_a: bool = True, flag_b: bool = False) -> bytes:
    """Java ``ControlGetProtocol.packForeignData(byte[], int, int, boolean, boolean)``.

    Layout: ``flags, len_lo, len_hi, packet_no, last_packet_no, data``.
    ``flags`` = 1, +2 if not ``flag_a``, +4 if ``flag_b``. Manual 2.2.1 calls these fields
    "additional information", "packed data length LL LH", "PO" and "TP" (= total packets - 1).
    """
    n = len(data)
    if n > 0xFFFF:
        raise ValidationError("foreign data longer than 65535 bytes needs multi-packet send")
    flags = 1
    if not flag_a:
        flags += 2
    if flag_b:
        flags += 4
    return bytes((flags, n & 0xFF, (n >> 8) & 0xFF, index & 0xFF, (count - 1) & 0xFF)) + data


def frame_old_foreign(foreign: bytes, id_code: str = BROADCAST_ID_CODE) -> bytes:
    """Java ``ControlGetProtocol.package_control_old_forein(byte[], String)`` (default TCP frame).

    ``ID(4) | LEN(2,LE) | 00 00 | 68 32 FF 7B | foreign | CHK(2,LE)`` where
    ``LEN = 6 + len(foreign)`` and CHK sums bytes from ``68`` to the last foreign byte.
    Cross-check: C-Power5200 SDK API Manual 2.2.1 (network frame, no transcoding).
    """
    prefix = parse_id_code(id_code)
    inner = bytes((PACKET_SEND, CARD_TYPE, CARD_ID_GROUP, PROTOCOL_FOREIGN)) + foreign
    length = 6 + len(foreign)
    return prefix + _le16(length) + b"\x00\x00" + inner + _le16(checksum16(inner))


def frame_old(code: int, data: bytes, id_code: str = BROADCAST_ID_CODE,
              additional: int = DEFAULT_ADDITIONAL_INFO) -> bytes:
    """Java ``package_control_old(byte, byte[], String[, int])`` (non-foreign commands).

    ``ID(4) | LEN(2,LE) | 00 00 | 68 32 FF code additional | data | CHK(2,LE)``,
    ``LEN = 7 + len(data)``; CHK sums ``68`` .. last data byte.
    """
    prefix = parse_id_code(id_code)
    inner = bytes((PACKET_SEND, CARD_TYPE, CARD_ID_GROUP, code & 0xFF, additional & 0xFF)) + data
    return prefix + _le16(7 + len(data)) + b"\x00\x00" + inner + _le16(checksum16(inner))


def escape_serial(data: bytes) -> bytes:
    """Manual 2.1.3 / bytecode: A5, AA, AE -> AA, (b & 0x0F)."""
    out = bytearray()
    for b in data:
        if b in (START, ESC, END):
            out += bytes((ESC, b & 0x0F))
        else:
            out.append(b)
    return bytes(out)


def unescape_serial(data: bytes) -> bytes:
    """Inverse of :func:`escape_serial` (Java ``Receive``: ``0xA0 | next``)."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == ESC and i + 1 < len(data):
            out.append(0xA0 | data[i + 1])
            i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def frame_unified(code: int, data: bytes, mac: Optional[str]) -> bytes:
    """Java ``package_unified`` for ``code == 123`` (packageDataWithAESExternal), no cipher.

    NOT used by the client (protocol generation 2/3 is unsupported); provided for the offline
    oracle test only. Reproduces Java's fixed-size buffer: when ``mac`` is not exactly 12
    characters the array keeps trailing zero bytes, because Java sizes it for a 12-char MAC.
    """
    buf = bytearray((PACKET_SEND, CARD_TYPE, CARD_ID_GROUP, code & 0xFF)) + data
    buf += _le16(checksum16(bytes(buf)))
    escaped = escape_serial(bytes(buf))
    mac_bytes = bytes((ord(c) & 0xFF) for c in mac) if mac else b""
    out = bytearray(14 + len(escaped) + 1)
    out[0] = START
    out[1:1 + len(mac_bytes)] = mac_bytes
    pos = 1 + len(mac_bytes) + 1  # zero separator after the MAC
    out[pos:pos + len(escaped)] = escaped
    out[pos + len(escaped)] = END
    return bytes(out)


# --------------------------------------------------------------------------- text body
def java_parse_int(text: str, radix: int = 10) -> int:
    """Strict ``Integer.parseInt`` (no whitespace, no underscores)."""
    pattern = r"[+-]?[0-9]+" if radix == 10 else r"[+-]?[0-9a-fA-F]+"
    if not re.fullmatch(pattern, text):
        raise ValidationError(f"not a valid number: {text!r}")
    return int(text, radix)


class TextSegment(NamedTuple):
    size: int
    color: int
    text: str


class ParsedText(NamedTuple):
    segments: Tuple[TextSegment, ...]
    font: int
    ext_bkcolor: bool
    bkcolor: bytes
    text_length: int


_TAG = re.compile(r"<[^>]+>")
_BK_MAP = {1: 0x30, 2: 0x0C, 3: 0x3C, 4: 0x03, 5: 0x33, 6: 0x0F, 7: 0x3F}


def parse_text_labels(content: str, color: int, font_size: int) -> ParsedText:
    """Java ``Utils.analysisContentLabel``: handles ``<font=N> <size=N> <color=HEX> <bkcolor=N>``.

    Any other ``<...>`` token is silently dropped (as Java does). Plain text yields one segment.
    NOTE: a literal ``<...>`` in user text is therefore consumed as markup.
    """
    size, col, font, bk, ext = font_size, color, 0, -1, False
    segments: List[TextSegment] = []
    prev_end = 0
    for m in _TAG.finditer(content):
        tag = m.group()
        if m.start() != prev_end:
            segments.append(TextSegment(size, col, content[prev_end:m.start()]))
        gt = tag.index(">")
        if "<font=" in tag:
            font = java_parse_int(tag[6:gt])
            if not 0 <= font <= 7:
                raise ValidationError("font must be 0 ~ 7")
        if "<size=" in tag:
            size = java_parse_int(tag[6:gt])
        if "<color=" in tag:
            col = java_parse_int(tag[7:gt].replace("#", ""), 16)
        if "<bkcolor=" in tag:
            bk = java_parse_int(tag.split("=")[1][:1])
            ext = True
            if not 1 <= bk <= 7:
                raise ValidationError("bkcolor must be 1 ~ 7")
        prev_end = m.end()
    if prev_end < len(content):
        segments.append(TextSegment(size, col, content[prev_end:]))
    total = sum(len(utf16_units(s.text)) for s in segments)
    return ParsedText(tuple(segments), font, ext, bytes((_BK_MAP.get(bk, 0), 0, 0x11)), total)


def utf16_units(text: str) -> List[str]:
    """Split like Java ``String.substring(i, i+1)``: one UTF-16 code unit per element."""
    data = text.encode("utf-16-le", "surrogatepass")
    return [data[i:i + 2].decode("utf-16-le", "surrogatepass") for i in range(0, len(data), 2)]


def _roundtrips(ch: str, codec: str) -> bool:
    try:
        return ch.encode(codec).decode(codec) == ch
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False


#: What the SDK emits for a unit its GBK table cannot map: ``3F`` ('?') followed by ``BA``.
#: ``BA`` is the first byte of a two-byte padding literal the SDK appends and then fails to strip
#: completely (observed in the oracle for every Hebrew/Arabic/emoji unit; bug-compatible).
UNMAPPABLE_PAIR = bytes((0x3F, 0xBA))
#: Lone UTF-16 surrogates become a plain '?' padded to two bytes.
SURROGATE_PAIR = bytes((0x00, 0x3F))


def _stock_pair(ch: str) -> bytes:
    """Stock-Python approximation of ``getStringCode``; the oracle table corrects its misses."""
    if 0xD800 <= ord(ch) <= 0xDFFF:
        return SURROGATE_PAIR
    if _roundtrips(ch, "gb2312"):
        try:
            raw = ch.encode("gbk")
        except UnicodeEncodeError:
            raw = ch.encode("gb2312")
    elif _roundtrips(ch, "latin-1"):
        raw = ch.encode("latin-1")
    else:
        try:
            raw = ch.encode("gbk")
        except UnicodeEncodeError:
            return UNMAPPABLE_PAIR
    return b"\x00" + raw[:1] if len(raw) == 1 else raw[:2]


def _overrides() -> Dict[int, bytes]:
    global _OVERRIDES
    if _OVERRIDES is None:
        try:
            from ._java_gbk_overrides import OVERRIDES
        except ImportError:  # only while the table is being generated
            OVERRIDES = {}
        _OVERRIDES = OVERRIDES
    return _OVERRIDES


_OVERRIDES: Optional[Dict[int, bytes]] = None


def encode_char(ch: str) -> Tuple[bytes, bool]:
    """Java ``StringUtil.getStringCode(String)`` for one UTF-16 unit -> (2 bytes, lossy).

    Verified exhaustively: all 65,536 UTF-16 units match the real SDK output (see
    tests/test_char_table.py and tests/fixtures/java_char_table.tsv). Java chooses an encoding by
    round-trip (GB2312, ISO-8859-1, UTF-8, GBK); GB2312 chars use GBK bytes, Latin-1 chars one
    byte padded as ``00 xx``, everything else GBK bytes or, if the JDK GBK table has no entry,
    :data:`UNMAPPABLE_PAIR` (``3F BA``) - so Hebrew/Arabic/emoji are NOT displayable.
    ``lossy`` is True when the character could not be represented.
    """
    pair = _overrides().get(ord(ch))
    if pair is None:
        pair = _stock_pair(ch)
    # SURROGATE_PAIR is also the plain encoding of '?' itself, which is not a loss.
    lossy = pair == UNMAPPABLE_PAIR or (pair == SURROGATE_PAIR and ch != "?")
    return pair, lossy


def build_text_body(content: str, color: int, font_size: int) -> Tuple[bytes, Tuple[str, ...]]:
    """Java ``ControlGetProtocol.textProgramMatDataPack(content, color, size, 2, 0, 0, false)``.

    ``[font*16, 00, 1C]`` (only if ``<font=N>`` N>0) ``+ bkcolor(3)`` (only if ``<bkcolor>``)
    ``+ per character (color*16+size, hi, lo) + 00 00 00`` terminator.
    Manual CC=0x02: "Every 3 bytes represent a character, end with 3 bytes of 0".
    Returns the body and human-readable warnings (lossy characters).
    """
    parsed = parse_text_labels(content, color, font_size)
    out = bytearray()
    if parsed.font > 0:
        out += bytes(((parsed.font * 16) & 0xFF, 0, 0x1C))
    if parsed.ext_bkcolor:
        out += parsed.bkcolor
    lossy_chars: List[str] = []
    for seg in parsed.segments:
        tag = (seg.color * 16 + seg.size) & 0xFF
        for ch in utf16_units(seg.text):
            pair, lossy = encode_char(ch)
            if lossy:
                lossy_chars.append(ch)
            out += bytes((tag,)) + pair
    out += b"\x00\x00\x00"
    warnings: Tuple[str, ...] = ()
    if lossy_chars:
        shown = ascii("".join(dict.fromkeys(lossy_chars)))  # ascii(): safe on any console
        warnings = (f"{len(lossy_chars)} character(s) not representable in GBK were sent as "
                    f"'?' (the controller protocol cannot represent them): {shown}",)
    return bytes(out), warnings


def correct_effect_value(effect: int) -> int:
    """Java ``ExtSendUtil.getCorrectEffectValue`` (private): effect index -> wire byte."""
    if effect == 0:
        return 255
    e = effect - 1
    if e == 12:
        v = 14
    elif e == 13:
        v = 12
    elif e == 14:
        v = 15
    elif e == 15:
        v = 13
    elif e in (55, 56):
        v = e + 2
    elif 57 <= e <= 64:
        v = e + 3
    elif e >= 65:
        v = e + 4
    else:
        v = e
    return v & 0xFF


def text_payload(window: int, body: bytes, effect: int, speed: int, stay_time: int,
                 horizontal: int, vertical: int) -> bytes:
    """Java ``ExtSendUtil.sendText`` header + body (command code 0x02 first).

    ``02 | window | effect' | h + 4*v | speed | stay_hi | stay_lo | body``
    Manual CC=0x02: window, effect, alignment, speed, stay time (high byte first), string.
    """
    return bytes((
        0x02, window & 0xFF, correct_effect_value(effect),
        (horizontal + vertical * 4) & 0xFF, speed & 0xFF,
        (stay_time & 0xFF00) >> 8, stay_time & 0xFF,
    )) + body
