# Unofficial Lumen Protocol – Native Python SDK

**An independent, pure-Python SDK for communicating with Lumen / C-Power LED controllers.**

- **Public release language support:** English text (ASCII).
- **Protocol support:** Generation 1 and Generation 2 for the operations documented below.
- **Runtime:** Python standard library only.
- **Tested development environment:** Python 3.12.10 on Windows 11.
- **Project status:** Community-maintained, unofficial implementation. Controller capabilities vary by model and firmware.

> The packet encoders have been compared byte-for-byte with reference encoder output and examples in vendor documentation. Generation 2 text transmission, acknowledgment handling, and visible output have also been exercised on one physical controller. This does **not** establish compatibility with every controller or every SDK command. See [Validation status](#validation-status) and [Hardware testing](#hardware-testing).

## Features

- Automatic controller protocol detection using the UDP discovery probe.
- Generation 1 and Generation 2 packet construction, checksums, and reply validation.
- English text transmission with configurable window, color, font size, speed, effect, duration, and alignment.
- Flash save/clear and quit-external-screen commands where implemented.
- Brightness and screen-switch commands for Generation 1.
- Explicit error handling; a missing acknowledgment is not reported as success.
- Offline packet generation and deterministic tests.

## Installation

Clone or download this repository, then choose one of the following approaches.

**Option A — Copy the package directory into an existing project:**

```powershell
Copy-Item -Recurse .\lumen_protocol C:\my_project\lumen_protocol
```

**Option B — Install from the repository root:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

The Python import name is `lumen_protocol`; the distribution name defined in `pyproject.toml` is `lumen-protocol`. Installation from PyPI is not implied by these instructions.

## Quick start

```python
from lumen_protocol import LEDClient

with LEDClient(host="192.168.1.100", port=5000, timeout=5) as client:
    result = client.send_text(
        window=0,
        text="Hello World",
        color=1,
        font_size=2,
        speed=1,
        effect=1,
        stay_time=3,
        horizontal_alignment=1,
        vertical_alignment=1,
    )
    print(result.stage, result.acknowledged, result.display_confirmed)
```

The address and port above are **examples only**. Use a controller you own or are authorized to operate.

`result.ok` indicates that a request was sent and a controller acknowledgment was received and validated. It does **not** prove the content is visible on the display. `display_confirmed` is `None` because the protocol does not provide visual confirmation.

A missing reply raises `ReceiveTimeoutError`: the request may already have reached the controller, so its outcome is **unknown**. Display-changing commands are not automatically retried. Use `build_text_request(...)` when you need the encoded request bytes without network access.

## Command-line tool

If `ReportExternalProjector.py` is included in your checkout, its positional argument order is `IP PORT WINDOW TEXT`:

```powershell
# Inspect a request without network access
python .\ReportExternalProjector.py 192.168.1.100 5000 0 "Hello World" --dry-run

# Transmit to an authorized controller
python .\ReportExternalProjector.py 192.168.1.100 5000 0 "Hello World"
```

Common options: `--color`, `--font-size`, `--speed`, `--effect`, `--stay-time`, `--h-align`, `--v-align`, `--timeout`, `--no-probe`, `--dry-run`, `--generation`, `--mac`, and `-v` / `--verbose`.

Use `--help` for the options supported by the version you have installed. Running `--help`, `--dry-run`, or an ordinary package import does not contact a controller.

### CLI results

| Situation | Message | Exit code |
|---|---|---:|
| Valid acknowledgment | `Success: Command acknowledged by controller.` | 0 |
| No reply before timeout | `Error: Controller response timed out. Command status unknown.` | 4 |
| Connection failed | `Error: Unable to connect to controller.` | 3 |
| Reply without valid acknowledgment | `Error: Command was not acknowledged by controller.` | 5 |
| Unsupported generation | `Error: Controller protocol generation is not supported.` | 6 |
| Other communication failure | `Error: Communication with controller failed.` | 1 |

Usage errors return exit code `2`. Verbose mode may expose the text or other payload data in request/reply traces; treat logs accordingly.

## Protocol generations

The client attempts to detect a controller using the UDP discovery probe (`CPower~?`, port `57274`):

- **Generation 1:** Legacy ID-code framing. Used as the compatibility fallback when the probe does not respond; a timeout does not prove that a controller is actually Generation 1.
- **Generation 2:** MAC-addressed `A5 … AE` framing. Text, flash save/clear, and quit-external-screen operations are implemented.
- **Generation 3 / 8002:** Not supported, including encrypted protocol variants.

Generation 1-only operations include brightness and screen switching. Generation 2 implementations should not be assumed to support those commands.

For offline Generation 2 packet generation, provide the controller MAC with `--mac` (12 hexadecimal characters). The `--generation 1` / `--generation 2` options can override automatic selection when appropriate.

## API overview

| Operation | `LEDClient` API |
|---|---|
| Connect | `LEDClient(host, port, timeout=..., config=ClientConfig(id_code=...))` |
| Send text | `send_text(window, text, color, font_size, speed, effect, stay_time, horizontal_alignment, vertical_alignment)` |
| Save / clear flash | `save_sent_data_to_flash()` / `clear_saved_data_from_flash()` |
| Exit external screen | `quit_external_screen()` |
| Brightness (Generation 1) | `get_brightness()` / `set_brightness(seq)` |
| Screen power (Generation 1) | `set_screen_switch(on)` |
| Cleanup | `close()` or use the context manager |

Common parameter conventions (actual rendering may be controller-dependent):

- `window`: `0–32` accepted by the library; supported window counts vary by controller.
- `font_size`: indices `0–7` corresponding to nominal sizes `8, 12, 16, 24, 32, 40, 48, 56`.
- `color`: values `1–7` conventionally map to red, green, yellow, blue, purple, cyan, and white; monochrome displays may ignore unsupported colors.
- `speed`: `1–100` (lower is faster).
- `stay_time`: `0–65535` seconds.
- `horizontal_alignment` / `vertical_alignment`: `0` = left/top, `1` = center/middle, `2` = right/bottom.

See [API coverage](docs/API_COVERAGE.md) for implementation and generation limitations.

## Text support and encoding

**This public release officially supports English text only.** Plain ASCII letters, digits, spaces, and common punctuation are the recommended input. The underlying protocol encoding is derived from the vendor's GBK character conversion, but that is **not** a guarantee of correct display for additional languages or arbitrary Unicode text.

The controller's installed font library also affects how character codes appear. Text markup such as `<font=...>`, `<size=...>`, `<color=...>`, or `<bkcolor=...>` may be interpreted by the controller; behavior varies by implementation. See the protocol documentation before relying on markup.

### Roadmap: multilingual text

**Future goal:** support text in all languages, including Unicode scripts, without requiring users to work with device-specific character substitutions. Achieving broad language coverage may require new font-rendering and/or image-based transmission features, and depends on controller capabilities. **Multilingual support is not available in this public release and is not yet guaranteed.**

## Validation status

| Area | Status |
|---|---|
| Frame layouts, checksums, text bodies, and encoding | Compared offline with reference encoders and manual packet examples |
| Generation 1 behavior | Offline tests and simulated peers; verify on your target hardware |
| Generation 2 text and acknowledgment | Exercised with one physical controller; visible text output observed |
| Other commands, controller models, and firmware variants | Not comprehensively hardware-verified |
| General display rendering | Cannot be inferred from acknowledgment alone |

A simulated controller or a byte-for-byte encoder match validates software behavior, not physical display compatibility. See [Compatibility](docs/SDK_COMPATIBILITY.md) and [Evidence ledger](docs/EVIDENCE_LEDGER.md) if these documents are included in this release.

## Errors and safe operation

The SDK provides `LEDError` subclasses including `ValidationError`, `ConnectError`, `ReceiveTimeoutError`, `TransportError`, `ProtocolError`, `NegativeAcknowledgmentError`, `UnsupportedProtocolError`, and `NotSupportedError`.

- Run commands only on devices and networks you are authorized to use.
- Prefer offline packet inspection before sending to new controller models.
- Treat timeouts as an **unknown outcome**, not as proof that nothing happened.
- Treat flash erase, persistent storage, screen power, and exit-screen operations as potentially disruptive.
- Do not enable byte tracing in production logs unless payload disclosure is acceptable.

## Tests

From the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
python -B -m unittest discover -s tests -v
```

The offline tests include protocol vectors, packet encoding, mock transports, local TCP/UDP test peers, and CLI behavior where the CLI is included. They do not require access to a physical controller. Avoid copying private test assets, vendor binaries, or disassembly artifacts into a public repository.

## Documentation

- [Protocol notes](docs/PROTOCOL.md)
- [API coverage](docs/API_COVERAGE.md)
- [SDK compatibility](docs/SDK_COMPATIBILITY.md)
- [Evidence ledger](docs/EVIDENCE_LEDGER.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)

## License and attribution

This is an **unofficial, independently developed** project. It is not affiliated with, sponsored by, or endorsed by Lumen or C-Power.

## Hardware testing

When validating a new controller, start with `--dry-run` and test only on an authorized, preferably isolated network:

1. Check TCP connectivity and the UDP probe response.
2. Send a short English message and compare the acknowledged response with the visible display.
3. Verify window selection, font size, alignment, speed, effect, and duration.
4. Confirm behavior when a message exceeds the available screen width.
5. Test repeated sends on a single connection and controller-initiated disconnects.
6. Test flash, brightness, and power commands only when the risks are understood and recovery is available.

**Acknowledgment is not proof of a successful visual update.** Record actual hardware observations separately from protocol-level success.
