"""UDP protocol-generation probe.

Evidence: Java ``UdpProtocol.getCardProtocol`` (bytecode) sends the 9-byte datagram
``"CPower~?"`` (GBK) + ``00`` to ``<ip>:57274`` with a 3000 ms receive timeout, decodes the reply
as GB2312, drops 4 leading characters, splits on TAB and maps fields[3]/fields[4] to a protocol
generation. Any failure (including "Receive timed out") yields generation 1 ("old").

This module only talks to the host you pass in; nothing is broadcast and nothing runs on import.
"""
from __future__ import annotations

import logging
import socket
from typing import Optional

from ..config import JAVA_PROBE_TIMEOUT_S, UDP_PROBE_PORT
from ..models import ProbeResult

log = logging.getLogger("lumen_protocol.transport.udp")

PROBE_PAYLOAD = b"CPower~?\x00"


def parse_probe_reply(data: bytes) -> ProbeResult:
    """Pure decoder of the probe answer (mapping copied from the Java bytecode)."""
    text = data.split(b"\x00", 1)[0].decode("gb2312", "replace")  # NUL trim: assumption
    if len(text) < 4:
        return ProbeResult(1, (), None)
    fields = tuple(text[4:].split("\t"))
    mac = fields[1] if len(fields) > 1 else None
    protocol = 1
    if len(fields) >= 5:
        try:
            p1, p2 = int(fields[3]), int(fields[4])
        except ValueError:
            return ProbeResult(1, fields, mac)
        if p1 == 1:
            protocol = 1
        elif p1 == 2:
            protocol = 2
        elif p1 == 3:
            protocol = 3 if p2 == 1 else 2 if p2 == 2 else 1
        elif p1 == 8003:
            protocol = 3 if p2 == 1 else 2 if p2 == 2 else 8002 if p2 == 8002 else 1
    return ProbeResult(protocol, fields, mac)


def probe_protocol(host: str, timeout: float = JAVA_PROBE_TIMEOUT_S,
                   port: int = UDP_PROBE_PORT) -> Optional[ProbeResult]:
    """Send the probe to ``host`` and return the parsed reply, or ``None`` on timeout/error.

    ``None`` corresponds to Java returning generation 1 after printing "Receive timed out".
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.sendto(PROBE_PAYLOAD, (host, port))
        data, _addr = sock.recvfrom(512)
    except (socket.timeout, OSError) as exc:
        log.warning("protocol probe to %s:%s failed (%s); assuming old protocol", host, port, exc)
        return None
    finally:
        sock.close()
    return parse_probe_reply(data)
