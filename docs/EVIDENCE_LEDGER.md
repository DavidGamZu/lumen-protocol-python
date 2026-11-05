# EVIDENCE_LEDGER

Confidence: **H** = byte-exact reproduction of real SDK encoder output and/or independent manual agreement ·
**M** = bytecode reading only · **L** = inference/assumption. Offsets are into `analysis/javap/<class>.txt`
(`javap -p -c -constants -s`) or `analysis/docs_text/*.txt`. **No entry is hardware-verified.**

| # | Behaviour implemented | Source (class / method / doc section) | Observed constants | Cross-check | Conf. |
|---|---|---|---|---|---|
| 1 | Validation window 0..32, color 1..7, size 0..7 | `ExtSendUtil.sendText` | `bipush 32`, `7`, messages "nWndNo must be 0 ~ 32" | - | M |
| 2 | Payload header `02 wnd effect' h+4v speed stayHi stayLo` | `ExtSendUtil.sendText` bastore 0..6 | `iconst_2`, `iload*4`, `get8HighByte` | Manual `CC=0x02` field order; `CC=0x12` example | H |
| 3 | Effect remap | `ExtSendUtil.getCorrectEffectValue` | 255, 12→14, 13→12, 14→15, 15→13, 55/56 +2, 57..64 +3, ≥65 +4 | Oracle, effects 0..80 all equal | H |
| 4 | Rich3 body, tag = color·16+size, terminator `00 00 00` | `ControlGetProtocol.textProgramMatDataPack` (switch case 2) | `bipush 16`, array `(n+1)*3` | Manual "3 bytes per char, end with 3 bytes of 0"; oracle vectors incl. `<font>`,`<bkcolor>`,`<size>`,`<color>` | H |
| 5 | Markup parser | `Utils.analysisContentLabel` | regex `<[^>]+>`, `<font=`,`<size=`,`<color=`,`<bkcolor=` | Oracle (valid + exception cases) | H |
| 6 | Char → bytes (all 65,536 units) | `StringUtil.getEncoding/getStringCode` | GB2312→ISO-8859-1→UTF-8→GBK round-trip; `3F BA` fallback | Oracle exhaustive table | H |
| 7 | Foreign wrapper `flags LL LH PO TP` | `ControlGetProtocol.packForeignData` | flags=1, `iload_2-1` | Manual 2.1.1 (PO/TP/LL LH); oracle | H |
| 8 | Old network frame | `ControlGetProtocol.package_control_old_forein` | ID 4B, LEN=6+n, `68 32 FF 7B`, checksum sum(8..) | Manual 2.2.1; oracle (2 ID codes) | H |
| 9 | Direct frame | `ControlGetProtocol.package_control_old(…,17)` | add=0x11, LEN=7+n | Oracle (0x46, 0x76) | H |
| 10 | Default protocol = old (1) | `ExternalNetworkSendProtocol.<init>` (`packageDataType=1`), `initSocket` | `iconst_1` | - | M |
| 11 | UDP probe `CPower~?\0` → 57274, 3 s, fallback old | `UdpProtocol.getCardProtocol` | `ldc "CPower~?"`, `int 57274`, `sipush 3000` | parse table unit-tested ([SIM]) | M |
| 12 | TCP connect timeout 0.5 s; receive 5 s | `initSocket` `timeout=500`; `ExternalNetworkSendProtocolPojo.<init>` `5000` | - | - | M |
| 13 | Success rule `reply[12]==0` | `ExternalNetworkSendProtocol.sendDataMulti` | `bipush 12; iaload; ifne` | **no document for 0x7B replies** | M (L for meaning) |
| 14 | Save/clear flash payload `07 00/01 00 00`, quit `06` | `ExtSendUtil.saveSentDataToFlash/clearSavedDataFromFlash/quitExternalScreen` | `bipush 7`, `bipush 6` | none | M |
| 15 | Brightness query/set (proto 0x46) | `ControlGetProtocol.get_bright/set_bright`, `ExtSendUtil.getBrightness` | `bipush 70`; `-1→32`; `reply[14..38]` | Manual CMD 0x46 (24 hourly bytes, >31 auto) ; oracle frames | H (frame) / M (reply) |
| 16 | Screen switch (proto 0x76) | `ControlGetProtocol.setScreenSwitch` | `bipush 118`, 10-byte array | Manual example has 9 data bytes | M |
| 17 | Serial escape A5/AA/AE | `ControlGetProtocol.packageDataWithAESExternal` | `0xAA`, `&0x0F` | Manual 2.1.3 | H |
| 18 | Unified frame (tests only) | `package_unified`/`packageDataWithAESExternal` | MAC bytes, fixed `14+n+1` buffer | Oracle with 12-char and empty MAC | H |
| 19 | `3F BA` is a quirk, not designed | `StringUtil.getStringCode` (case `UTF-8`) pads with a 2-byte literal and drops one byte | literal's glyph was lost in console output; first byte `BA` inferred **from oracle output** | Oracle | H (bytes) / L (cause) |
| 20 | Colour names 1..7 | Manual Rich3 | red green yellow blue purple cyan white | Java comment says "blue" twice | M |
| 21 | Font point sizes | Java sample comment; Manual (indices 0,2..7) | 8,12,16,24,32,40,48,56 | index 1 only from Java comment | M |

## Open questions (do not treat as facts)
1. Meaning of byte 12 in 0x7B replies on real firmware; whether non-zero is "busy", "error" or other.
2. Hebrew: bytes `3F BA` per letter are what the SDK sends; actual display unknown. Right-to-left layout is not addressed anywhere in the sources.
3. Default TCP port: the bytecode takes the port from the caller; no value (e.g. 5200) appears in the Java path.
4. Whether windows > 7 work on a given controller; whether the UDP probe is required for firmware that lacks it.
5. Whether `A2 E3`-style GBK extension bytes (e.g. `€`) render on any firmware font.
6. Exact identity of the text on `ldc #128` in `getStringCode` (display lost to console encoding); only its first GBK byte (`BA`) is established, by oracle.
