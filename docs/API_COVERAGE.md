# API_COVERAGE

Status legend - **V-off**: implemented, verified from reference logic **offline only** (oracle/manual) · **I**: implemented, not
externally validated (bytecode only) · **P**: partial · **U**: unsupported (explicit `NotSupportedError` or absent) ·
**X**: incompatible protocol generation · **N/A**: out of scope. **No row is hardware-verified.**

## Java `ExtSendUtil` (all 49 public methods / 46 distinct names, plus the constructor; checked by script against `javap`)

| Java member | Python | Status | Notes |
|---|---|---|---|
| `initNetwork(ip,port,idcode)` / `(…,int)` | `LEDClient(host, port, config=ClientConfig(id_code=…))` | V-off | 4-arg overload sets protocolModel (skips probe): `probe_protocol=False` approximates it for model 1 |
| `sendText(9 args)` | `LEDClient.send_text` | **V-off** | frame byte-identical to SDK pure encoders; reply rule unverified |
| `sendText(…, boolean)` | - | U | overload not analysed |
| `sendTextRGB` | - | U | not analysed |
| `sendInstantMsg` | - | U | manual documents `CC=0x11`; not implemented without bytecode confirmation |
| `saveSentDataToFlash` | `save_sent_data_to_flash` | I | bytecode-only payload `07 00 00 00` |
| `clearSavedDataFromFlash` | `clear_saved_data_from_flash` | I | payload `07 01 00 00`; destructive on device |
| `quitExternalScreen` | `quit_external_screen` | I | payload `06` |
| `getBrightness` / `setBrightness` | `get_brightness` / `set_brightness` | V-off (frames) | manual 0x46 agrees; reply semantics unverified |
| `setScreenSwitch` | `set_screen_switch` | V-off (frame) | manual 0x76 example differs by one data byte |
| `setReceiveTimeout/getReceiveTimeout` | `ClientConfig.receive_timeout` | P | Java setter is ineffective (SDK_ANALYSIS §2.3) |
| `disconnectNetwork`, `uninstallSocket` | `close()` | V-off | |
| `setListener`, `setListenerWithBackdata`, `setProtocolDataListener`, `getListener` | `SendResult`, `logging` | N/A | callbacks replaced by return values + logging |
| `getTextComplex/setTextComplex` | - | U | Big5 path not implemented |
| `splitScreen`, `sendMulti`, `sendMultiAndSpeedAlign`, `createGlobalAreaWindow`, `clearAllGlobalArea` | stubs (`split_screen`, `send_multi`) | U | bytecode not analysed |
| `sendPicture` ×2, `sendPictureWithScale`, `sendVideo`, `sendFullPackage`, `updateSystemFile` | stubs (`send_picture`, `send_video`) | U | image/video/file pipeline not recovered; FTP involved |
| `setScreenOnAndOffTime`, `getScreenOnAndOffTime`, `exitSetScreenOnAndOffTime`, `getScreenSize` | stubs | U | builders not analysed (manual 0x45 exists) |
| `restartApp`, `restartHard` | stubs | U | use a separate file-protocol path (manual CMD 0xFE / 0x2D) |
| `writeSPI`, `readSPI`, `setIO` | - | U | hardware-level, out of scope until needed |
| `setVariableValue`, `selectPlayProgram`, `exitSelectPlay`, `getPlayProgramContent` | - | U | not analysed |
| `readyToUseProgramTemplate`, `deleteTemplateProgram`, `sendTemplateProgram`, `enterOrExitTemplateProgramMode` | - | U | template protocol (manual §2.2.3) not implemented |
| Encrypted/new protocol (`CypherManage`, `package_unified` w/ AES) | `frame_unified` (no AES, tests only) | X | client refuses generation ≠ 1 |

`ExternalNetworkSendProtocol` is internal to the demo path; its transport behaviour is covered by `TcpTransport` and
`probe_protocol`. `getWH` (screen size query) is not implemented.

## C/C++ SDK functions (listed separately; none are callable from Python)
* Legacy header: 340 declarations; 2024: 394; x64 2021: 390 (full lists in `analysis/sdk_static_scan.json`).
* Families: `CP5200_Net_*` (network), `CP5200_RS232_*`, `CP5200_Make*Data`/`CP5200_Parse*Ret` (pure builders),
  `CP5200_Playbill_*`, `CP5200_Program_*` (program files), `CP5200_CmmPacker_*`, `CPowerBox_*` (2024).
* Mapping to implemented Python behaviour: `CP5200_Net_SendText`/`SendPureText` ≈ Java `sendText` family (colour/alignment
  types differ); `CP5200_Net_SaveClearWndData` ≈ flash save/clear (`nSavaOrClear`); none are implemented as C-signature clones.
* **Not implemented**: everything else, including password (`SetPassword`), ID/baud-rate, private code, upgrade, file
  upload, programs/playbills, bad-point detection, time/temperature queries. These need protocol documents that are
  missing from the workspace or bytecode/DLL analysis that was not performed.
