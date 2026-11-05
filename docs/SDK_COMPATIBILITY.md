# SDK_COMPATIBILITY

Nothing here assumes the SDKs share a protocol; each cell states what was actually observed.

| Aspect | Java `lumen_protocol.jar` | C legacy (`cpower_legacy`) | C++ 2024 | C++ x64 2021 | Manuals |
|---|---|---|---|---|---|
| Version evidence | Not in the jar manifest (it is gson's). "1.4.7 / 2024-10-29" comes from the task text only | no version string read | folder date 2024-05-31; 394 exports | folder date 2021-12-30; 390 exports; PE x64 | Basic Protocol V0.04 (2012-07-27); API manual has 2015-05-04 revision entry |
| ABI | JVM (class-file v52) | PE x86, 340 exports | PE x86, 394 exports | PE **x64**, 390 exports | - |
| Packet builders exposed | via `ControlGetProtocol` (package-private use) | `CP5200_Make*Data` / `Parse*Ret` | same + 4 more than 2021 | as 2024 minus 4 | frame layout, `CC` codes |
| Address of target | dotted-quad "ID code" in frame prefix; TCP ip:port | `nCardID` + `dwIDCode` in `Net_Init` | + `Net_InitEx(... bySupportQuickSearch)` | as 2024 | "ID Code 0x00000000-0xFFFFFFFF, high byte first" |
| Auth | none seen | none seen | **`CP5200_Net_SetPassword`** (not implemented here) | none seen | - |
| Colour in text API | index 1..7 | `COLORREF` (RGB) | `COLORREF` | `COLORREF` | Rich3: 4-bit index 1..7; RGB variants for `0x11/0x12` |
| Transport | TCP (+UDP probe 57274) | `Net_*` and `RS232_*` | same | same | RS232/485 and network |
| Text charset | GBK-based; Hebrew → `3F BA` | C `const char*` (codepage not analysed) | same (not analysed) | same | Rich3: "text encoding" hi/lo |

## Which implementation targets which family
`lumen_protocol` implements **only** the Java SDK's *generation 1 ("old") TCP* behaviour, cross-checked against the
manual's network-frame description. That frame (`ID(4) LEN(2) 00 00 68 32 FF 7B ...`) is described by the same
manual that documents the C SDK's `Make*Data` helpers, so the C SDKs most probably speak the same frame
family for the shared commands - but this was **not proven** (the DLLs cannot be run, and their code was not
disassembled). Generations 2/3/8002 (MAC-addressed, escaped, optionally AES) are reported by the UDP probe in the
Java SDK and are **not supported**.

## Differences that change behaviour if mixed
* C `nAlignment` is one integer, Java has two (horizontal/vertical); the manual packs them as bits 0-1 / 2-3, matching Java's `h + 4*v`.
* Java colour `1..7` ≠ C `COLORREF`. Do not pass RGB values to `LEDClient.send_text`.
* Window range: manual says valid windows **0..7**; Java validates **0..32**; the controller may only honour what its split-screen configuration defines ("Support to split to 8 / 32 windows" strings appear in the demo exe).
* Power-switch data: Java 10 bytes vs manual example 9 bytes (checksum identical; whether firmware tolerates both is unknown).
* 0x7B replies: layout undocumented; Java's `reply[12]==0` rule is the only evidence.

## Not compared (blocked)
Binary-level equivalence of `CP5200.dll` output vs the jar (would require executing or disassembling the DLLs); the
"controller ID / baud rate / network parameters" protocol document (absent - see SOURCE_INVENTORY); Word tables
(effect/font code tables were lost by the text extraction).
