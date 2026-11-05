# IMPLEMENTATION_STATUS

Last updated: 2026-10-29 · Environment: Windows 11, Python 3.12.10, JDK 25 (Temurin) used only for `javap`/`javac`
of the original oracle harnesses. **No device or network host other than 127.0.0.1 was contacted. No hardware verification.**

## Update 2026-10-29 - Generation 2 (real controller 192.168.1.251:5200, MAC 00606edfd2c5, ID CPB0306215)
* **Why gen 2 was rejected:** the initial implementation treated any probe result other than 1 as unsupported; the real controller's probe fields
  (`…,8003,0002,…`) map to generation 2. The sample Java call had worked because Java honours generation 2 (`package_unified` + MAC).
* **Java handling (bytecode):** generation 2 = MAC prefix + `A5…AE` framing + escaping, same payload; no AES (`doCypher=false`), no handshake.
* **Changes:** `protocol/decoder.py` (`decode_serial_reply`, ack rule on body), `protocol/commands.py` (`wrap_foreign`, `validate_mac`, generation/mac args),
  `transport/{base,tcp}.py` (`receive_serial_frame`), `client.py` (generation selection from probe/config, per-generation build/decode),
  `config.py` (`protocol_generation`, `mac`), `models` (`ReplyFrame.generation/mac`), CLI (`--generation`, `--mac`, gen-aware `--dry-run`).
  Generation 1 code paths and all 81 earlier tests are unchanged (one test updated: generation 3 replaces generation 2 as the "unsupported" example).
* **Verification:** 104 tests OK (23 new). Gen-2 request frames compared with the real jar's `package_unified` for 6 payloads incl. escape bytes and the exact
  text-"10" payload (`tests/test_generation2.py`, oracle regenerated). Replies: SIMULATED only.
* **Hardware:** not yet transmitted from Python. Single controlled test prepared; awaiting explicit approval.

## Phase checklist
| Phase | State | Evidence |
|---|---|---|
| 1 Audit / inventory / reverse engineering | **Done for the `sendText` path and the listed control commands**; the rest of the 123-class protocol package is disassembled to `analysis/javap/` but not analysed | SOURCE_INVENTORY, SDK_ANALYSIS, PROTOCOL, SDK_COMPATIBILITY, EVIDENCE_LEDGER |
| 2 Package design | Done (`lumen_protocol/`, `pyproject.toml`) | tree below |
| 3 Native implementation | `send_text` + 6 control commands + UDP probe done; others explicit `NotSupportedError` | API_COVERAGE |
| 4 Offline tests | Done: 81 tests, 0 failures, 0 skipped | below |
| 5 Documentation | Done | README + docs/ |
| Hardware | **Not started - no controller** | README "Hardware tests" |

## Test results (exact)
```
python -B -m unittest discover -s tests -v     # cwd Extruct_Led_code
Ran 81 tests in ~2.2s   OK   (failures 0, errors 0, skipped 0)
  test_char_table 6 · test_cli 11 · test_client 23 · test_commands_and_decoder 18
  test_manual_crosscheck 5 · test_oracle_vectors 7 · test_runtime_isolation 5 · test_udp_probe 6
Installed-package run (venv .venv, `python -I`, cwd .tmp, repo not on sys.path): 65 tests (all except test_cli) OK
Copied-folder scenario (.tmp/copytest: lumen_protocol + ReportExternalProjector.py, no other files): --help, --dry-run, import OK
pip install --no-index --no-deps --no-build-isolation .  -> lumen_protocol-0.1.0 built and installed in .venv only
```
Evidence classes in the tests: **oracle** (output of the real jar's pure static encoders, run offline), **manual** (examples
printed in the vendor .doc files), **simulated** (fake transport / 127.0.0.1 servers / constructed replies). Only the first two
say anything about real-SDK byte equality; none say anything about controller behaviour.

## Bugs found by the oracle while implementing (all fixed)
1. Unmappable/Hebrew characters: SDK emits `3F BA`, not `00 3F` (my first assumption). 2. JDK GBK ≠ Python `gbk` for 2,152
UTF-16 units (e.g. `€`, private-use, `U+2295`, `U+30FB`) → generated override table. 3. My PE export-table parser mis-read the
header (caught while verifying a claim; static-scan results regenerated). 4. A generated table concatenated adjacent string
literals (caught by tests).

## Known deviations from Java (deliberate)
Stricter argument ranges (speed 1-100, alignment 0-2, stay time 0-65535, effect 0-255) · `id_code` applied to all commands ·
one TCP connection per client instead of per call · length-prefixed reply reading · typed errors/timeouts instead of `false` +
stack trace · generations 2/3/8002 refused rather than guessed.

## Uncovered functionality
See API_COVERAGE: pictures/video/files, multi-text, split-screen, templates/programs, timers, restart, SPI/IO, `sendText` boolean
overload, `sendTextRGB`, instant message, Big5 "complex" text, new/encrypted protocol, C-SDK password/ID-baud/private-code/
upgrade/temperature/bad-point commands.

## Blockers / limitations
* Vendor `.doc` text was extracted heuristically; tables (font, effect codes) incomplete. No parser for Word tables was available
  offline, and none was installed.
* `The communication protocol for set the controller ID, baud rate…` is not a document (it is a PE file); no such protocol text exists in the workspace.
* DLLs/EXEs were only parsed as bytes (never loaded/executed), so C-SDK byte output was not compared with Java output.
* Java version string 1.4.7 is not verifiable from the jar. Python 3.11 and Linux not exercised.
* SDK licence terms not provided.

## Isolation audit
* **Reference files:** 24 files outside `Extruct_Led_code/` were hashed (SHA-256), sized and timestamped before any work
  (`analysis/baseline_outer_inventory.json`) and again at the end (`analysis/after_outer_inventory.json`): **identical in path, size,
  SHA-256 and mtime for all 24**. This proves those files were not modified or removed; it does not prove that nothing else on the machine changed.
* **Write destinations (all inside `Extruct_Led_code/`):** `lumen_protocol/`, `tests/`, `docs/`, `examples/`, `analysis/` (javap dumps,
  doc-text extractions, oracle harness + `.class` output, scan JSON, tools), `.venv/` (local venv; pip compiled `.pyc` there),
  `.cache/pip/`, `.tmp/` (temp dirs for java/python/pip; copied-folder test), `pyproject.toml`, `README.md`, `ReportExternalProjector.py`.
  Transient `build/` and `*.egg-info/` from the pip build were created inside the tree and removed.
* **Environment handling:** `TMP/TEMP/TMPDIR`, `PIP_CACHE_DIR`, `XDG_CACHE_HOME` pointed into `.tmp/`/`.cache/` for child processes only;
  `PYTHONDONTWRITEBYTECODE=1`; no global installs; Java was run with `JAVA_TOOL_OPTIONS=-XX:-UsePerfData …` (process-local). `javac`
  output went to `analysis/java_oracle/out/`.
* **Deviation to disclose:** one early command ran with the wrong working directory and created `analysis/javap/analysis/…` and printed errors;
  everything stayed inside `Extruct_Led_code/` and the stray folder was deleted.
* **Not executed:** `ReportExternalProjector.exe`, `TestCP5200.exe`, any DLL, `ExtSendUtil.sendText`, any socket to a non-loopback address.
  The oracle called only pure static encoders (and the private `getCorrectEffectValue` on a fresh `ExtSendUtil` whose constructor performs no I/O).
* **Limits of this audit:** machine-wide locations outside the project (e.g. user profile caches, Java/pip global state) were not snapshotted.

## File tree created
```
Extruct_Led_code/
├── lumen_protocol/ {__init__,client,config,exceptions}.py  models/__init__.py
│   protocol/{__init__,packets,encoder,decoder,commands,_java_gbk_overrides}.py  transport/{__init__,base,tcp,udp}.py
├── ReportExternalProjector.py   pyproject.toml   README.md   examples/send_text.py
├── tests/ (8 test modules, helpers.py, fixtures/*.tsv)
├── docs/ (7 required documents)
└── analysis/ (javap/, docs_text/, java_oracle/, tools/, scan + inventory JSON)   [.venv/ .cache/ .tmp/ local-only]
```
Note: `transport/tcp.py` and `transport/udp.py` exist because the evidence shows TCP commands and a UDP probe; `transport/base.py`,
`protocol/_java_gbk_overrides.py` and `models/` enums are the only additions to the illustrative tree.
