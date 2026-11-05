"""Transport abstraction so the client can be tested with mocks and swapped for other links."""
from __future__ import annotations

import abc


class Transport(abc.ABC):
    """Byte pipe to one controller. Implementations own their socket and must be closable twice."""

    @abc.abstractmethod
    def open(self) -> None:
        """Establish the link. Raises ``ConnectError`` on failure."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release the link. Idempotent, never raises."""

    @abc.abstractmethod
    def send(self, data: bytes) -> None:
        """Write all bytes. Raises ``TransportError`` on failure."""

    @abc.abstractmethod
    def receive_frame(self, timeout: float) -> bytes:
        """Return one reply frame (length-prefixed "old" frame).

        Raises ``ReceiveTimeoutError`` if nothing arrives; if a frame is only partially received
        when the deadline passes, the partial bytes are returned so the caller can report them.
        """

    def receive_serial_frame(self, timeout: float) -> bytes:
        """Return one ``A5 .. AE`` delimited frame (protocol generation 2).

        ``AE`` never occurs inside an escaped payload, so the first ``AE`` after ``A5`` ends it.
        Same timeout/partial-data contract as :meth:`receive_frame`. Optional for transports.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support generation-2 framing")

    @property
    @abc.abstractmethod
    def is_open(self) -> bool:
        ...

    def __enter__(self) -> "Transport":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
