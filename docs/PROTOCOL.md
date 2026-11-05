# PROTOCOL - wire format as implemented

Evidence classes used below (see `EVIDENCE_LEDGER.md`):
**[BC]** deduced from Java bytecode (`analysis/javap/`) · **[MAN]** printed in the local C-Power manuals
(`analysis/docs_text/`, heuristic text extraction) · **[ORA]** reproduced byte-for-byte by running the
SDK's pure static encoders offline (`analysis/java_oracle/`, golden vectors in `tests/fixtures/`) ·
**[SIM]** simulated only · **[HW]** hardware-verified (**nothing is [HW]**).

## 1. Transport and session [BC]

| Item | Value | Source |
|---|---|---|
| Command channel | TCP, `connect(ip:port, 500 ms)`; port is caller-supplied (no default exists in the bytecode) | `ExternalNetworkSendProtocol.initSocket` |
| Pre-connect probe | UDP datagram `"CPower~?" + 00` (9 bytes, GBK) to `<ip>:57274`, 3000 ms timeout | `UdpProtocol.getCardProtocol` |
| Probe failure | Exception (printed "Receive timed out") is swallowed; protocol generation **1 (old)** is assumed | same |
| Probe reply | GB2312 text; drop 4 chars; split on TAB; `[3]`/`[4]` select generation 1/2/3/8002 | same ([SIM] fixtures only) |
| Receive deadline | 5000 ms (see SDK_ANALYSIS: the public `setReceiveTimeout` does not reach this) | `Receive()` / `ExternalNetworkSendProtocolPojo` |
| Per-call behaviour | Java re-runs probe+connect on **every** call; Python keeps one connection per `LEDClient` | design choice |
| Generation 2 | MAC prefix + `A5..AE` escaping, no cipher - **implemented** (§5) | `initSocket` case 2 |
| Generations 3/8002 | extra switch command / AES - **not implemented**; the client raises `UnsupportedProtocolError` | - |

## 2. "Old" frame (generation 1, TCP) - implemented

```
offset  size  field
0       4     ID code, from dotted quad "a.b.c.d" (default 255.255.255.255 -> FF FF FF FF)   [BC][MAN 2.2.1]
4       2     LEN, little endian = bytes from "packet type" to checksum inclusive           [BC][MAN 2.2.1]
6       2     reserved 00 00                                                                [BC][MAN 2.2.1]
8       1     packet type 0x68 (send) / 0xE8 (return)                                       [BC][MAN]
9       1     card type 0x32                                                                [BC][MAN]
10      1     card ID 0xFF (group address)                                                  [BC][MAN]
11      1     protocol code (0x7B foreign data, 0x46 brightness, 0x76 power switch, ...)    [BC][MAN]
12      ...   payload (see 2.1 / 2.2)
end-2   2     CHECKSUM, little endian = sum of bytes[8 : end-2] mod 65536                   [BC][ORA][MAN]
```
No `A5/AE` delimiters and **no escaping** on the network path [MAN 2.2.1 "does not need transcoding"].

### 2.1 Foreign-data frames (protocol 0x7B): `frame_old_foreign`
Payload = `flags(01) LL LH PO TP | CC data...` where `LL LH` = len(CC+data) little endian,
`PO` = packet number (0), `TP` = total packets - 1 (0). Here LEN = 6 + len(payload) (no extra
"additional information" byte after the protocol code - the `flags` byte plays that role) [BC][ORA][MAN 2.1.1].
Single-packet only: the Java text path never splits; this SDK rejects >65535 bytes.

### 2.2 Direct frames (e.g. 0x46, 0x76): `frame_old`
`... 68 32 FF <code> <additional=0x11> <data...> CHK`; LEN = 7 + len(data) [BC][ORA].

## 3. Commands implemented

| Command | `CC`/code | Payload | Evidence |
|---|---|---|---|
| **Send text** | `CC=0x02` | `02 · window · effect' · (h + 4·v) · speed · stay_hi · stay_lo · body` | [BC][ORA][MAN CC=0x02] |
| Save to flash | `07` | `07 00 00 00` | [BC] only |
| Clear saved flash | `07` | `07 01 00 00` | [BC] only |
| Quit external screen | `06` | `06` | [BC] only |
| Get brightness | proto `0x46` | `01`; reply `reply[14:38]` = 24 hourly values | [BC][ORA][MAN 0x46] |
| Set brightness | proto `0x46` | `00` + 24 bytes (`-1` -> `32` = sensor auto; manual: 0..31 valid) | [BC][ORA][MAN 0x46] |
| Screen switch | proto `0x76` | `00 <on> 00×8` (10 bytes; the manual's example shows 9) | [BC][ORA]; **[MAN] differs by one byte** |

`effect'` = `getCorrectEffectValue(effect)`: `0 -> 255`, otherwise `e = effect-1` then
`12→14, 13→12, 14→15, 15→13, 55/56 → e+2, 57..64 → e+3, ≥65 → e+4`, else `e` [BC][ORA for 0..80].
Alignment byte: horizontal 0/1/2 in bits 0-1, vertical 0/1/2 in bits 2-3 [BC][MAN 0x11/0x12]. Stay time is
**big endian** [BC][MAN]. `speed` is a single byte, smaller = faster [MAN].

### 3.1 Text body ("Rich3", 3 bytes per UTF-16 unit) [BC][ORA][MAN]
```
[font*16, 00, 1C]        only if a <font=N> tag with N>0 is present
[bk, 00, 11]             only if a <bkcolor=N> tag is present (N: 1→30 2→0C 3→3C 4→03 5→33 6→0F 7→3F)
(color*16 + size, hi, lo) per UTF-16 code unit        ; color 1..7, size 0..7
00 00 00                 terminator ("end with 3 bytes of 0" [MAN])
```
Markup `<font=N> <size=N> <color=HEX> <bkcolor=N>` is parsed from the text; **any other `<...>`
is silently consumed** [BC]. Colors 1..7 = red, green, yellow, blue, purple, cyan, white [MAN].
Sizes 0..7 = 8,12,16,24,32,40,48,56 pt [BC comment; MAN confirms all but index 1].

### 3.2 Character encoding and Hebrew [BC][ORA, exhaustive]
`getStringCode` is reproduced for **all 65,536 UTF-16 units** (`tests/test_char_table.py`):
* GB2312 characters (ASCII, Latin letters in GB2312, CJK) → their GBK bytes (ASCII: `00 xx`).
* Other Latin-1 characters → one byte padded `00 xx`.
* Everything the JDK GBK table can map → GBK bytes (the JDK table differs from Python's `gbk` for
  2,152 units, e.g. `€ → A2 E3`; these are carried in `_java_gbk_overrides.py`).
* **Everything else, including all Hebrew letters, Arabic, emoji (as surrogate halves)** → the pair
  `3F BA` (Hebrew etc.) or `00 3F` (lone surrogates). `3F` is `?`. The bytes are
  exact [ORA]; the *cause* of `BA` (probably the first byte of a two-byte padding literal that the SDK
  fails to strip completely) is an inference - bug-compatible either way.
**Consequence: the Java SDK path cannot display Hebrew.** The SDK warns and carries the
warning in `SendResult.warnings`; whether a controller shows `?`, garbage or nothing for `3F BA`
is an open hardware question. A `getComplexStringCode` (Big5, `textComplex==1`) path exists in
the bytecode and is **not implemented**.

## 4. Replies [BC][SIM]
`Receive()` returns whatever bytes arrive; the callers index them: success for foreign commands is
`reply[12] == 0`; brightness uses `reply[14:38]`; `setBrightness`/`setScreenSwitch` accept any reply.
The 0x7B reply layout is **not documented** in the available manuals, so what byte 12 means on a real
controller is unverified [HW needed]. Python reads a length-prefixed frame (`8 + LEN`), reports
`checksum_ok`, and never reports more than: write sent → reply received → Java-rule ack. Display
confirmation is not observable.

## 5. Generation 2 (implemented 2026-10-29 after a real controller reported it)

**Observed hardware probe reply** (192.168.1.251:5200): fields `IP, MAC 00606edfd2c5, ID CPB0306215, 8003, 0002, 0010, 1450`.
Java `getCardProtocol` maps `fields[3]=8003` + `fields[4]=2` → generation **2** (`8003` with `[4]==1` → 3, `==8002` → 8002).

**What Java does for generation 2 [BC]** (`ExternalNetworkSendProtocol.initSocket`, case 2): `packageDataType = 2`,
`CypherManage.doCypher = false` - **no encryption, no handshake, no extra init command.** Only the MAC learned from the probe
(`backIps` → `mac = fields[1]`) and the framing change. (Generation 3 additionally sends a switch command `E1`; 8002 enables AES; both unsupported.)

Request (`ControlGetProtocol.package_unified(123, packForeignData(payload), mac)`) [BC][ORA]:
```
A5 | MAC as 12 ASCII bytes | 00 | escape( 68 32 FF 7B | foreign | CHK(2,LE = sum of 68..last foreign byte) ) | AE
escape: A5→AA 05, AA→AA 0A, AE→AA 0E
```
Differences from generation 1: no 4-byte ID code, no LEN field, no `00 00`, escaping, `A5…AE` delimiters, MAC prefix.
The foreign payload (`01 LL LH PO TP 02 …`) and the text body are **identical** to generation 1.
Text "10" for window 0 with the real MAC: `a5 30 30 36 30 36 65 64 66 64 32 63 35 00 68 32 ff 7b 01 10 00 00 00 02 00 00 05 01 00 03 12 00 31 12 00 30 00 00 00 b5 02 ae`
(42 bytes; everything after the MAC prefix is byte-identical to the real jar's output for the same payload [ORA]).

Reply [BC, decoding verified only against SIMULATED frames]: `Receive()` for generation ≠ 1 returns the raw bytes unchanged if shorter than 20,
else skips 14 bytes, un-escapes `AA x → A0|x` up to the final byte, and exposes `reply[11]=cmd`, `reply[12]=first body byte`.
Success rule is again `reply[12]==0`. Python reads until the first `AE` after `A5`, un-escapes, checks packet type `E8` and the checksum
(reported, not enforced - same as Java), and applies the same rule. **Hardware capture (2026-10-29, one text "10" request to 192.168.1.251:5200, forced gen 2):** the controller answered with 27 bytes
`a5 30 30 36 30 36 65 64 66 64 32 63 35 00 e8 32 ff 7b 00 01 00 00 00 02 97 02 ae` - i.e. `E8 32 FF 7B`, body `00 01 00 00 00 02`, checksum `0x0297`
(verified), so `reply[12]==0` held. This confirms the layout and the Java success rule for this one case; it still says nothing about
what the other body bytes mean. Display confirmation is the operator's visual observation only.

Not implemented for generation 2: `getBrightness`, `setBrightness`, `setScreenSwitch` (Java uses a different builder, `packageDataWithAES`, that was not analysed - the client raises `NotSupportedError`).
Serial RS232/485 framing is the same envelope [MAN]. AES (`CypherManage`) remains unimplemented.
