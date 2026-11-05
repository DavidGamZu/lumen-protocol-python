"""Client configuration (no global state, no hardcoded targets)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

#: Java: ExtSendUtil/ExternalNetworkSendProtocol literal ``"255.255.255.255"`` (controller ID code).
BROADCAST_ID_CODE = "255.255.255.255"
#: Java: ExternalNetworkSendProtocol.timeout field, used by Socket.connect (500 ms).
JAVA_CONNECT_TIMEOUT_S = 0.5
#: Java: ExternalNetworkSendProtocolPojo.receiveTimeOut default (5000 ms), used by Receive().
JAVA_RECEIVE_TIMEOUT_S = 5.0
#: Java: UdpProtocol.getCardProtocol DatagramSocket.setSoTimeout(3000) and port 57274.
JAVA_PROBE_TIMEOUT_S = 3.0
UDP_PROBE_PORT = 57274


@dataclass(frozen=True)
class ClientConfig:
    """Tunable behaviour of :class:`lumen_protocol.LEDClient`.

    Defaults reproduce the timeouts observed in the Java SDK 1.4.7 bytecode.
    """

    connect_timeout: float = JAVA_CONNECT_TIMEOUT_S
    receive_timeout: float = JAVA_RECEIVE_TIMEOUT_S
    #: Java sends an unconditional UDP probe ("CPower~?" -> port 57274) before every TCP connect
    #: when ``protocolModel == 0``; a probe timeout silently falls back to the "old" protocol.
    probe_protocol: bool = True
    probe_timeout: float = JAVA_PROBE_TIMEOUT_S
    #: Dotted-quad controller ID code placed in the 4-byte frame prefix.
    id_code: str = BROADCAST_ID_CODE
    #: Extra connect attempts (connect is idempotent). Display commands are NEVER retried.
    connect_retries: int = 0
    #: Force a protocol generation (1 or 2) instead of using the probe result. Needed for offline
    #: frame building and for ``probe_protocol=False``; generation 2 also needs ``mac``.
    protocol_generation: Optional[int] = None
    #: 12-hex-digit controller MAC (generation 2 frame prefix). Normally learned from the probe.
    mac: Optional[str] = None
    #: Log request/reply bytes at DEBUG level. Off by default: payloads may be confidential.
    trace_bytes: bool = False
