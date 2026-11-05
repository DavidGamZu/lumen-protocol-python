"""TCP transport. Evidence: Java ``ExternalNetworkSendProtocol.initSocket`` uses ``java.net.Socket``
``connect(ip:port, 500ms)`` and plain stream reads/writes (bytecode)."""
from __future__ import annotations

import logging
import socket
import time
from typing import Optional

from ..exceptions import ConnectError, ReceiveTimeoutError, TransportError
from ..protocol.decoder import expected_total_length
from .base import Transport

log = logging.getLogger("lumen_protocol.transport.tcp")


class TcpTransport(Transport):
    def __init__(self, host: str, port: int, connect_timeout: float = 0.5,
                 trace_bytes: bool = False) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.trace_bytes = trace_bytes
        self._sock: Optional[socket.socket] = None

    @property
    def is_open(self) -> bool:
        return self._sock is not None

    def open(self) -> None:
        self.close()
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as exc:
            raise ConnectError(f"cannot connect to {self.host}:{self.port}: {exc}") from exc
        sock.settimeout(None)
        self._sock = sock
        log.debug("connected to %s:%s", self.host, self.port)

    def close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:  # pragma: no cover - close never needs to propagate
                pass

    def send(self, data: bytes) -> None:
        if self._sock is None:
            raise TransportError("transport is not open")
        try:
            self._sock.sendall(data)
        except OSError as exc:
            self.close()
            raise TransportError(f"write failed: {exc}") from exc
        if self.trace_bytes:
            log.debug("TX %d bytes: %s", len(data), data.hex(" "))

    def receive_frame(self, timeout: float) -> bytes:
        return self._receive(timeout, serial=False)

    def receive_serial_frame(self, timeout: float) -> bytes:
        return self._receive(timeout, serial=True)

    @staticmethod
    def _serial_complete(buf: bytearray) -> bool:
        start = buf.find(b"\xa5")
        return start >= 0 and buf.find(b"\xae", start + 1) >= 0

    def _receive(self, timeout: float, serial: bool) -> bytes:
        if self._sock is None:
            raise TransportError("transport is not open")
        deadline = time.monotonic() + timeout
        buf = bytearray()
        total: Optional[int] = None
        while (not self._serial_complete(buf)) if serial else (total is None or len(buf) < total):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._sock.settimeout(remaining)
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                break
            except OSError as exc:
                self.close()
                raise TransportError(f"read failed: {exc}") from exc
            if not chunk:  # peer closed
                self.close()
                if buf:
                    break
                raise TransportError("connection closed by peer before any reply")
            buf += chunk
            if not serial:
                total = expected_total_length(bytes(buf[:6]))
        if serial and self._serial_complete(buf):
            start = buf.find(b"\xa5")
            buf = buf[start:buf.find(b"\xae", start + 1) + 1]
        if not buf:
            raise ReceiveTimeoutError(f"Receive timed out after {timeout:g}s (no reply bytes)")
        if self.trace_bytes:
            log.debug("RX %d bytes: %s", len(buf), bytes(buf).hex(" "))
        return bytes(buf)
