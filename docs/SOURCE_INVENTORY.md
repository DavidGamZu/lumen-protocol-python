# SOURCE_INVENTORY

Read-only inventory of everything outside `Extruct_Led_code/` (hashes are SHA-256 prefixes; full values in `analysis/baseline_outer_inventory.json`, taken BEFORE any work).

**Content-based file type is shown because several legacy file names do not match their contents (see findings below).**

| Path | Bytes | SHA-256 (16) | Detected content | Role |
|---|---:|---|---|---|
| `cpower_legacy/C-Power SDK/CP5200.dll` | 5010432 | `FB6A75615EDF36D5` | OLE2 |  |
| `cpower_legacy/C-Power SDK/CP5200.lib` | 589824 | `4C8898B91D01CD8F` | PE |  |
| `cpower_legacy/C-Power SDK/CP5200API.h` | 97482 | `29D08CFA22035E7A` | ar-archive |  |
| `cpower_legacy/C-Power SDK/C-Power external calls communication protocol.doc` | 313856 | `8F578476679E3597` | OLE2 |  |
| `cpower_legacy/C-Power SDK/C-Power5200 SDK API Manual.doc` | 735744 | `F3E9EA7253ADC898` | OLE2 |  |
| `cpower_legacy/C-Power SDK/LafDll.dll` | 50410 | `E0C4360C576DE2C6` | c-header-text |  |
| `cpower_legacy/C-Power SDK/TestCP5200.exe` | 217088 | `52103F27EA27A723` | PE |  |
| `cpower_legacy/C-Power SDK/The communication protocol for set the controller ID, baud rate and network parameters .doc` | 638976 | `A9F13AA4C286348A` | PE |  |
| `cpp_2024/CPowerSDK-20240531/CP5200.dll` | 2099200 | `934E4CB3B0AF4773` | PE |  |
| `cpp_2024/CPowerSDK-20240531/CP5200.lib` | 112964 | `D46F4B0866E468E2` | ar-archive |  |
| `cpp_2024/CPowerSDK-20240531/CP5200API.h` | 57962 | `E9084201DC5A8A19` | c-header-text |  |
| `cpp_2024/CPowerSDK-20240531/TestCP5200.exe` | 2109952 | `C5E001B866696C46` | PE |  |
| `cpp_x64_2021/CPowerSDK(x64)-20211230/CP5200.dll` | 2798592 | `3714006623E1FC71` | PE |  |
| `cpp_x64_2021/CPowerSDK(x64)-20211230/CP5200.lib` | 102774 | `37275AECF2A86F36` | ar-archive |  |
| `cpp_x64_2021/CPowerSDK(x64)-20211230/CP5200API.h` | 57396 | `F23492B5AC8B7CAE` | c-header-text |  |
| `cpp_x64_2021/CPowerSDK(x64)-20211230/TestCP5200.exe` | 2830336 | `FA98636411346635` | PE |  |
| `cpp_x64_2021/CPowerSDK(x64)-20211230/testcp5200.ini` | 141 | `637685A7DCACA747` | other |  |
| `HelloWorld.java` | 133 | `CE199F336BB9DFD9` |  | Unrelated sample |
| `lib/lumen_protocol.jar` | 904495 | `1A1A4EDB54845A35` |  | Java SDK - PRIMARY behavioural reference |
| `ReportExternalProjector$1.class` | 781 | `2CF85F90E229A8AC` |  | Compiled anonymous listener (not executed) |
| `ReportExternalProjector.class` | 2214 | `4A281C0086F248A1` |  | Compiled demo (not executed) |
| `ReportExternalProjector.exe` | 2442804 | `9FA3B7F15CD3108F` |  | Jar2Exe build of the demo (NOT executed) |
| `ReportExternalProjector.java` | 2052 | `57D8B7DDD6CBD1BE` |  | Original Java demo (behavioural reference) |
| `task.md` | 28162 | `831E0CF94E973BE5` |  | Task specification (read-only, never edited) |

## Findings

1. **`cpower_legacy/C-Power SDK/` names are rotated relative to content.** Detected by magic bytes: `CP5200.dll` is a Word/OLE2 document (the C API manual), `CP5200.lib` is a PE DLL (340 exports, x86), `CP5200API.h` is an `ar` archive (an import library), `LafDll.dll` is the C header text (340 declarations), `TestCP5200.exe` is a PE with 25 exports (i.e. a DLL), and the file named *The communication protocol for set the controller ID, baud rate and network parameters* is a PE (the demo executable, strings include `C-Power5200 API Demo`). Nothing was renamed or executed.
2. **The document named *...controller ID, baud rate and network parameters* is not a document.** No protocol document for ID/baud/network parameters exists in the workspace. The 2024 header does declare `CP5200_MakeReadIDBaudrateData`/`CP5200_Net_ReadIDBaudrate` etc., but no wire description is available, so none was implemented.
3. `C-Power external calls communication protocol.doc` contains *Basic Protocol of CPower LED Display Controller*, V0.04 (2012-07-27) - the RS232/RS485 serial envelope and file/time/brightness/power commands. `C-Power5200 SDK API Manual.doc` contains the extended protocol (network frame 2.2.1, `CC` sub-commands such as `0x02` text). Both were read with a string-extraction heuristic (`analysis/tools/extract_doc_text.py`); **tables and some numbers were lost** (e.g. the font-size and effect code tables are incomplete).
4. **`Basic Protocol of CPower LED Display Controller...` as a separate file: NOT PRESENT** (its text is the content of the *external calls* document above).
5. **C# SDK: NOT PROVIDED.** No `.cs`/`.csproj` in the workspace; the jar contains no .NET artifacts; the document text contains no C# samples.
6. `cpp_x64_2021/.../testcp5200.ini` (141 bytes) is a settings file for the demo exe; not parsed for protocol facts.

## JAR facts (static)

- Entries: 540; class-file major version 52 (Java 8). Manifest was written by the *bundled gson* build (`Build-Jdk: 11.0.4`); it carries no Lumen SDK version string, so **"V1.4.7 (2024-10-29)" is taken from the task text and is not independently verifiable from the jar**.
- Lumen code: `com/lumen/ledcenter3/protocol/` (123 class files incl. nested), `com/lumen/ledcenter3/pojo/` (4). Bundled third-party: Google Gson 2.8.6, Apache commons-net 3.6 (FTP/Telnet/NTP... used for file/video upload paths).
- Public entry points used by the demo: `ExtSendUtil`, `ExternalNetworkSendProtocol` (+ listener interfaces). Disassembly: `analysis/javap/*.txt` (`javap -p -c -constants -s`).

## Static SDK scan (no binary executed or loaded)

| Folder | File | Content | Exports/Decls | Machine |
|---|---|---|---:|---|
| cpower_legacy | `CP5200.dll` | OLE2 |  |  |
| cpower_legacy | `CP5200.lib` | PE | 340 | 0x14c |
| cpower_legacy | `CP5200API.h` | ar-archive |  |  |
| cpower_legacy | `LafDll.dll` | c-header-text | 340 |  |
| cpower_legacy | `TestCP5200.exe` | PE | 25 | 0x14c |
| cpp_2024 | `CP5200.dll` | PE | 394 | 0x14c |
| cpp_2024 | `CP5200.lib` | ar-archive |  |  |
| cpp_2024 | `CP5200API.h` | c-header-text | 394 |  |
| cpp_2024 | `TestCP5200.exe` | PE | 0 | 0x14c |
| cpp_x64_2021 | `CP5200.dll` | PE | 390 | 0x8664 |
| cpp_x64_2021 | `CP5200.lib` | ar-archive |  |  |
| cpp_x64_2021 | `CP5200API.h` | c-header-text | 390 |  |
| cpp_x64_2021 | `TestCP5200.exe` | PE | 0 | 0x8664 |
| cpp_x64_2021 | `testcp5200.ini` | other |  |  |
