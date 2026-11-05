"""Command builders: validated arguments -> complete request frames (bytes). Pure functions.

Each builder lists its evidence. "bytecode" = Java SDK 1.4.7 disassembly; "manual" = the
local C-Power5200 SDK API Manual / Basic Protocol .doc text extraction (see docs/EVIDENCE_LEDGER.md).
"""
from __future__ import annotations

import re
from typing import Optional, Sequence, Tuple

from ..config import BROADCAST_ID_CODE
from ..exceptions import ValidationError
from .encoder import (
    PROTOCOL_FOREIGN,
    build_text_body,
    frame_old,
    frame_old_foreign,
    frame_unified,
    pack_foreign_data,
    text_payload,
)

# Foreign-data command codes (first payload byte). Source: bytecode ExtSendUtil.
CC_TEXT = 0x02            # also manual CC=0x02
CC_QUIT_EXTERNAL = 0x06   # bytecode only
CC_FLASH = 0x07           # bytecode only: [7, 0, 0, 0] save / [7, 1, 0, 0] clear

# Direct protocol codes (frame_old). Source: bytecode + manual (0x46 brightness, 0x76 power).
PC_BRIGHTNESS = 0x46      # 70
PC_SCREEN_SWITCH = 0x76   # 118


def _check_range(name: str, value: int, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an int, got {type(value).__name__}")
    if not lo <= value <= hi:
        raise ValidationError(f"{name} must be {lo} ~ {hi}, got {value}")
    return value


_MAC = re.compile(r"[0-9A-Fa-f]{12}")


def validate_mac(mac: Optional[str]) -> str:
    """12 hex digits, as reported by the controller probe (e.g. ``00606edfd2c5``)."""
    if not isinstance(mac, str) or not _MAC.fullmatch(mac):
        raise ValidationError(f"generation 2 needs a 12-hex-digit MAC, got {mac!r}")
    return mac


def wrap_foreign(foreign: bytes, id_code: str = BROADCAST_ID_CODE, generation: int = 1,
                 mac: Optional[str] = None) -> bytes:
    """Frame a ``packForeignData`` payload for the chosen protocol generation.

    1: ``package_control_old_forein`` (ID-code prefix, no escaping).
    2: ``package_unified(123, ..., mac)`` (``A5 MAC 00 escaped(...) AE``, no cipher).
    """
    if generation == 1:
        return frame_old_foreign(foreign, id_code)
    if generation == 2:
        return frame_unified(PROTOCOL_FOREIGN, foreign, validate_mac(mac))
    raise ValidationError(f"unsupported protocol generation {generation!r} (1 or 2)")


def build_text_request(window: int, text: str, color: int = 1, font_size: int = 2,
                       speed: int = 1, effect: int = 1, stay_time: int = 3,
                       horizontal_alignment: int = 1, vertical_alignment: int = 1,
                       id_code: str = BROADCAST_ID_CODE, generation: int = 1,
                       mac: Optional[str] = None) -> Tuple[bytes, Tuple[str, ...]]:
    """Equivalent of Java ``ExtSendUtil.sendText(9 args)`` -> (frame, warnings).

    Validation that exists in Java (bytecode): window 0~32, color 1~7, font_size 0~7.
    Extra Python validation (documented ranges, stricter than Java which truncates silently):
    speed 1~100, effect 0~255, stay_time 0~65535, alignments 0~2.
    """
    _check_range("window (nWndNo)", window, 0, 32)
    _check_range("color (crColor)", color, 1, 7)
    _check_range("font_size (nFontSize)", font_size, 0, 7)
    _check_range("speed (nSpeed)", speed, 1, 100)
    _check_range("effect (nEffect)", effect, 0, 255)
    _check_range("stay_time (nStayTime)", stay_time, 0, 0xFFFF)
    _check_range("horizontal_alignment", horizontal_alignment, 0, 2)
    _check_range("vertical_alignment", vertical_alignment, 0, 2)
    if not isinstance(text, str):
        raise ValidationError("text must be str")
    body, warnings = build_text_body(text, color, font_size)
    payload = text_payload(window, body, effect, speed, stay_time,
                           horizontal_alignment, vertical_alignment)
    return wrap_foreign(pack_foreign_data(payload), id_code, generation, mac), warnings


def build_save_to_flash(id_code: str = BROADCAST_ID_CODE, generation: int = 1,
                        mac: Optional[str] = None) -> bytes:
    """Java ``saveSentDataToFlash``: foreign payload ``07 00 00 00`` (bytecode only)."""
    return wrap_foreign(pack_foreign_data(bytes((CC_FLASH, 0, 0, 0))), id_code, generation, mac)


def build_clear_saved_flash(id_code: str = BROADCAST_ID_CODE, generation: int = 1,
                            mac: Optional[str] = None) -> bytes:
    """Java ``clearSavedDataFromFlash``: foreign payload ``07 01 00 00`` (bytecode only)."""
    return wrap_foreign(pack_foreign_data(bytes((CC_FLASH, 1, 0, 0))), id_code, generation, mac)


def build_quit_external(id_code: str = BROADCAST_ID_CODE, generation: int = 1,
                        mac: Optional[str] = None) -> bytes:
    """Java ``quitExternalScreen``: foreign payload ``06`` (bytecode only)."""
    return wrap_foreign(pack_foreign_data(bytes((CC_QUIT_EXTERNAL,))), id_code, generation, mac)


def build_get_brightness(id_code: str = BROADCAST_ID_CODE) -> bytes:
    """Java ``getBrightness`` request: protocol 0x46, data ``01`` (manual: 0x01 query)."""
    return frame_old(PC_BRIGHTNESS, b"\x01", id_code)


def build_set_brightness(values: Sequence[int], id_code: str = BROADCAST_ID_CODE) -> bytes:
    """Java ``setBrightness(int[])``: protocol 0x46, data ``00`` + 24 bytes (``-1`` -> 32 = auto).

    Manual: valid values 0~31, "larger than 31 means auto detect by sensor".
    """
    if len(values) != 24:
        raise ValidationError(f"brightness needs 24 hourly values, got {len(values)}")
    data = bytearray(b"\x00")
    for i, v in enumerate(values):
        if v == -1:
            data.append(32)
        else:
            data.append(_check_range(f"brightness[{i}]", v, 0, 31))
    return frame_old(PC_BRIGHTNESS, bytes(data), id_code)


def build_screen_switch(on: bool, id_code: str = BROADCAST_ID_CODE) -> bytes:
    """Java ``setScreenSwitch(boolean)``: protocol 0x76, data ``00 <on> 00*8`` (10 bytes).

    NOTE: the manual's example shows 9 data bytes (``00 01 00*7``); Java sends 10. We follow Java.
    """
    data = bytes((0, 1 if on else 0)) + bytes(8)
    return frame_old(PC_SCREEN_SWITCH, data, id_code)
