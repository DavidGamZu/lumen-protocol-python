"""High-level client. Maps the Java ``ExtSendUtil`` operations onto explicit Python methods.

Outcome vocabulary (never conflated):
  * write sent        - bytes handed to the OS socket
  * reply received    - a decodable reply frame arrived
  * device acknowledged - reply meets the Java SDK's success rule (``reply[12] == 0`` for the
                          foreign-data commands). Whether that rule means "accepted" is
                          UNVERIFIED without hardware.
  * display confirmed - never observable over this protocol; always ``None``.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import replace
from typing import Callable, Optional, Sequence, Tuple

from .config import ClientConfig
from .exceptions import (
    ConnectError,
    LEDTimeoutError,
    NegativeAcknowledgmentError,
    NotSupportedError,
    ReceiveTimeoutError,
    TransportError,
    UnsupportedProtocolError,
)
from .models import DeliveryStage, ProbeResult, SendResult
from .protocol import commands as cmd
from .protocol.decoder import (
    brightness_from_reply,
    decode_reply,
    decode_serial_reply,
    java_foreign_ack,
)
from .transport.base import Transport
from .transport.tcp import TcpTransport
from .transport.udp import probe_protocol

log = logging.getLogger("lumen_protocol.client")

ProbeFn = Callable[[str, float], Optional[ProbeResult]]


class LEDClient:
    """One controller. Not a global: create one per target, close it (or use ``with``).

    ``timeout`` (seconds) sets both connect and receive timeouts unless ``config`` is given.
    Calls are serialised with a lock; display-changing commands are never retried.
    """

    def __init__(self, host: str, port: int, timeout: Optional[float] = None, *,
                 config: Optional[ClientConfig] = None,
                 transport: Optional[Transport] = None,
                 probe: Optional[ProbeFn] = None) -> None:
        cfg = config or ClientConfig()
        if timeout is not None:
            cfg = replace(cfg, connect_timeout=timeout, receive_timeout=timeout)
        self.host, self.port, self.config = host, port, cfg
        self._transport = transport or TcpTransport(host, port, cfg.connect_timeout,
                                                    cfg.trace_bytes)
        self._probe: ProbeFn = probe or (lambda h, t: probe_protocol(h, t))
        self._lock = threading.RLock()
        self._probed = False
        self._generation = 1
        self._mac: Optional[str] = None

    @property
    def protocol_generation(self) -> int:
        """Generation in use (valid after :meth:`connect`; 1 until then)."""
        return self._generation

    def _select_protocol(self) -> None:
        """Pick the generation like Java ``initSocket``: probe, else assume "old" (1)."""
        cfg = self.config
        if cfg.protocol_generation in (1, 2):
            self._generation, self._mac = cfg.protocol_generation, cfg.mac
            if self._generation == 2:
                cmd.validate_mac(self._mac)
            return
        if cfg.protocol_generation is not None:
            raise UnsupportedProtocolError(
                f"protocol generation {cfg.protocol_generation!r} is not implemented (1 or 2)")
        if not cfg.probe_protocol:
            return
        result = self._probe(self.host, cfg.probe_timeout)
        if result is None:                      # Java: probe failure -> "old" protocol
            return
        if result.protocol == 1:
            return
        if result.protocol == 2:
            self._generation, self._mac = 2, cmd.validate_mac(result.mac)
            log.info("controller reports generation 2 (MAC %s)", self._mac)
            return
        raise UnsupportedProtocolError(
            f"controller reports protocol generation {result.protocol}; only generations 1 and 2 "
            "are implemented (3 = mixed, 8002 = AES-encrypted). Fields: " + repr(result.fields))

    def _build(self, builder: Callable[[int, Optional[str]], object]) -> object:
        """Validate with a throw-away generation-1 build (no I/O), connect, then build for real."""
        builder(1, None)
        self.connect()
        return builder(self._generation, self._mac)

    # ------------------------------------------------------------------ lifecycle
    def __enter__(self) -> "LEDClient":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def connected(self) -> bool:
        return self._transport.is_open

    def connect(self) -> None:
        """Open the TCP link. Optionally probes the protocol generation first (see config)."""
        with self._lock:
            if self._transport.is_open:
                return
            if not self._probed:
                self._select_protocol()
                self._probed = True
            last: Optional[ConnectError] = None
            for _ in range(self.config.connect_retries + 1):
                try:
                    self._transport.open()
                    return
                except ConnectError as exc:
                    last = exc
            assert last is not None
            raise last

    def close(self) -> None:
        with self._lock:
            self._transport.close()

    # ------------------------------------------------------------------ plumbing
    def _execute(self, request: bytes, *, java_ack: bool,
                 warnings: Tuple[str, ...] = ()) -> Tuple[SendResult, Optional[bytes]]:
        with self._lock:
            self.connect()
            if self.config.trace_bytes:
                log.debug("request %s", request.hex(" "))
            self._transport.send(request)
            sent = SendResult(DeliveryStage.WRITE_SENT, request, warnings=warnings)
            try:
                if self._generation == 2:
                    raw = self._transport.receive_serial_frame(self.config.receive_timeout)
                else:
                    raw = self._transport.receive_frame(self.config.receive_timeout)
            except ReceiveTimeoutError as exc:
                exc.result = sent
                raise
            except LEDTimeoutError as exc:  # pragma: no cover - other timeout subclasses
                exc.result = sent
                raise
            frame = decode_serial_reply(raw) if self._generation == 2 else decode_reply(raw)
            if java_ack:
                ack = java_foreign_ack(frame)
                stage = DeliveryStage.DEVICE_ACK if ack else DeliveryStage.REPLY_RECEIVED
                return SendResult(stage, request, frame, ack, None, warnings), raw
            return SendResult(DeliveryStage.REPLY_RECEIVED, request, frame, None, None,
                              warnings), raw

    # ------------------------------------------------------------------ commands
    def send_text(self, window: int, text: str, color: int = 1, font_size: int = 2,
                  speed: int = 1, effect: int = 1, stay_time: int = 3,
                  horizontal_alignment: int = 1, vertical_alignment: int = 1) -> SendResult:
        """Java ``ExtSendUtil.sendText(nWndNo, content, crColor, nFontSize, nSpeed, nEffect,
        nStayTime, nAlignmentHori, nAlignmentVert)``. Defaults = the demonstrated Java call.

        Raises ``ReceiveTimeoutError`` if no reply arrives (outcome unknown). Returns a result
        whose ``ok`` is True only when the Java success rule was met.
        """
        idc = self.config.id_code
        with self._lock:
            request, warnings = self._build(lambda g, m: cmd.build_text_request(  # type: ignore
                window, text, color, font_size, speed, effect, stay_time,
                horizontal_alignment, vertical_alignment, idc, g, m))
            for w in warnings:
                log.warning(w)
            result, _ = self._execute(request, java_ack=True, warnings=warnings)
            return result

    def _foreign_command(self, builder: Callable[..., bytes]) -> SendResult:
        idc = self.config.id_code
        with self._lock:
            request = self._build(lambda g, m: builder(idc, g, m))
            return self._execute(request, java_ack=True)[0]  # type: ignore[arg-type]

    def save_sent_data_to_flash(self) -> SendResult:
        """Java ``saveSentDataToFlash`` (bytecode-only evidence)."""
        return self._foreign_command(cmd.build_save_to_flash)

    def clear_saved_data_from_flash(self) -> SendResult:
        """Java ``clearSavedDataFromFlash`` (bytecode-only evidence). Destructive on the device."""
        return self._foreign_command(cmd.build_clear_saved_flash)

    def quit_external_screen(self) -> SendResult:
        """Java ``quitExternalScreen`` (bytecode-only evidence)."""
        return self._foreign_command(cmd.build_quit_external)

    def _require_gen1(self, method: str) -> None:
        if self._generation != 1:
            raise NotSupportedError(
                f"{method}: only supported on protocol generation 1 controllers (see docs/API_COVERAGE.md)")

    def get_brightness(self) -> Tuple[int, ...]:
        """Java ``getBrightness``: 24 hourly values (>31 = sensor auto, per manual). Gen 1 only."""
        with self._lock:
            self.connect()
            self._require_gen1("get_brightness")
            _, raw = self._execute(cmd.build_get_brightness(self.config.id_code), java_ack=False)
            assert raw is not None
            return brightness_from_reply(decode_reply(raw))

    def set_brightness(self, hourly: Sequence[int]) -> SendResult:
        """Java ``setBrightness(int[24])`` (``-1`` = automatic). Java only checks "a reply came";
        so ``acknowledged`` stays ``None`` here. Gen 1 only."""
        request = cmd.build_set_brightness(hourly, self.config.id_code)   # validate before I/O
        with self._lock:
            self.connect()
            self._require_gen1("set_brightness")
            return self._execute(request, java_ack=False)[0]

    def set_screen_switch(self, on: bool) -> SendResult:
        """Java ``setScreenSwitch(boolean)``. Same reply caveat as :meth:`set_brightness`. Gen 1 only."""
        request = cmd.build_screen_switch(on, self.config.id_code)
        with self._lock:
            self.connect()
            self._require_gen1("set_screen_switch")
            return self._execute(request, java_ack=False)[0]

    # ------------------------------------------------------------------ not implemented
    def _unsupported(self, method: str, why: str) -> None:
        raise NotSupportedError(f"{method}: {why} (see docs/API_COVERAGE.md)")

    def send_picture(self, *args: object, **kw: object) -> SendResult:
        """Java ``sendPicture``: image encoding + chunked upload not recovered."""
        self._unsupported("send_picture", "not supported")
        raise AssertionError  # pragma: no cover

    def send_video(self, *args: object, **kw: object) -> SendResult:
        self._unsupported("send_video", "not supported")
        raise AssertionError  # pragma: no cover

    def split_screen(self, *args: object, **kw: object) -> SendResult:
        self._unsupported("split_screen", "not supported")
        raise AssertionError  # pragma: no cover

    def send_multi(self, *args: object, **kw: object) -> SendResult:
        self._unsupported("send_multi", "not supported")
        raise AssertionError  # pragma: no cover

    def restart_app(self) -> SendResult:
        self._unsupported("restart_app", "not supported")
        raise AssertionError  # pragma: no cover

    def restart_hard(self) -> SendResult:
        self._unsupported("restart_hard", "not supported")
        raise AssertionError  # pragma: no cover

    def set_screen_on_off_time(self, *args: object) -> SendResult:
        self._unsupported("set_screen_on_off_time", "not supported")
        raise AssertionError  # pragma: no cover

    def get_screen_size(self) -> Tuple[int, int]:
        self._unsupported("get_screen_size", "not supported")
        raise AssertionError  # pragma: no cover
