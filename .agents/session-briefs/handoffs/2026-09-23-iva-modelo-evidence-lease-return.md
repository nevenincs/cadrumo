# IVA-01 → shared Modelo/TUI owner: ordinary-M303 evidence lease returned

Date: 2026-09-23. Scope: the lease granted in `2026-09-22-iva-modelo-evidence-contract.md` ("Shared Modelo/TUI owner disposition"). This file is the handback; the evidence below is bound to the named commits and runs.

## Outcome

The accepted contract is implemented on the existing `modelo.work.calculate` operation; no second operation, TUI-only calculator or plaintext evidence path exists.

- `aacf15b688` — `ModeloWorkCalculateOrdinaryM303EvidenceRequestV1` nested as `ModeloWorkCalculateRequest.ordinary_m303_filing_evidence` (two explicit booleans, attachment id/sha as `Hex64Str`). The executor derives year, period, bucket and pinned authority from the admitted work unit, resolves the pair through the existing secure attestation service, authors `FilingInstanceEvidence` through `author_ordinary_m303_filing_instance_evidence`, and hands it to the canonical calculation before revision persistence. Evidence is required for 303 and refused for any other modelo. Request storage and sensitive input moved to `SECURE_REFERENCE`; request schema is v2. A recorded v1 invocation no longer reproduces the pinned definition contract and is refused, never replayed with defaults. The encrypted attachment store is injected through `operation_composition` (`build_attachment_store`). TUI: `tui/modelo/m303_evidence.py` evidence form (two unanswered yes/no selects, either an existing id/sha pair or an explicit offset-qualified observation instant that admits a new attestation through the injected application door), lifecycle door pass-through, overview wiring with visible cancel / stale-context / unavailable-admission notices; 12 locale keys in en/es/ca/hu through `dev.locales set-batch`.
- `3e824a2785` — the Modelo workspace overview did not compose for any 303 declaration (edit-surface Input ids built from semantic casilla ids such as `iva.prorrata-volumen-con-derecho`; Textual rejects `.`). `edit_control_id` encodes keys one-to-one; numeric and hyphenated ids (income's `modelo-edit-scalar-0165`) are unchanged.
- `a27d7962e3` — official export refuses with `REFUSED_MODELO_EXPORT_PRODUCT_IDENTITY_UNAVAILABLE` (exit 2), naming "Versión del Programa" and "NIF del desarrollador", with record and positions in the typed context (DP30300 93-96 / 101-109 from the registry prefix fields). The operation modal and the workspace notice render the registry message for codes that declare it public.
- `63a201418e` — ordinary evidence coordinates are registry-driven (quarterly, and the selected record design declares the three evidence header fields): 2022 through 2026 author; monthly refuses. ADR amendment 2 records it. This commit also carries CALENDAR-01's concurrently staged S06 holiday re-authoring paths (facts 0066/0067, `legal/dias-inhabiles-age.toml`, BOE corpus captures, two tests, calendar ledger/plan); those remain CALENDAR's.
- `d5219ddcc2` — IVA tests reach the governed-facts scope and the synthetic IVA ledger transaction through public seams.
- `93e9a327ed` — 17 docs sequence contracts attest 2026/1T and pass the four evidence flags; export frames expect the product-identity refusal (exit 2). 42 goldens regenerated through `dev.docs.sequences refresh`; check and coherence clean on all six pages.
- `bba67b495f` — installed-wheel helpers renamed to public modules (`dev/packaging/acquire_common.py`, `installed_wheel_binding.py`); the capture/reopen driver hashes the installed `__init__` by path, not by import.
- `2991dc000a` — six M303 CLI help keys in all four locales; four orphaned quickfile M303 error keys removed.
- `056513f0c1` — `dev/acceptance/iva/installed_m303_evidence_journey.py`, its pure gate tests (oracle, outcome gate, reopen gate) and its import-load target line.
- `c0063d730a` — an unadmissible Modelo 390 attestation (malformed or mismatched pair, unknown to the profile, another period or role, stale against the profile, conflicting) raises `REFUSED_MODELO_M303_APPLICABILITY_ATTESTATION_UNADMISSIBLE` (public message, four locales). Before, it was an attachment-integrity error and the calculate operation settled FAILED with an opaque diagnostic; it now settles REFUSED.
- `740105ffd0` — the four `how-to/modelo-303` sequences that attach the office-supplies invoice show `C-2026-0087` instead of a hashed placeholder (LEDGER's evidence fix `c7198c95ad`); page check and coherence clean.
- `976971d1be` — the seven `operation.modal.terminal.*` keys and `application.modelo.lifecycle.refusal.edit_unavailable` in all four locales; the partial-success terminal key is a named locale-key constant so the catalogue audit sees it (audit `extra=0`).

- `b6eb0cadfc` — DP30301 position 129 (annual volume, art. 121 LIVA) printed `1` in any period on a yes answer; Nota 3 requires `0` except in the last period for a Modelo 390-exempt filer, and Nota 5 fixes it at `2` under exclusively foral taxation.
- `72a449933c` — the 390 attestation refusal renamed to `M303Exonerado390AttestationUnadmissibleError` / `REFUSED_MODELO_M303_EXONERADO_390_ATTESTATION_UNADMISSIBLE` (its key tripped the retired-export-override guard); storage-backed tests moved to `adapters/persistence/storage/tests/`, removing six application-to-adapter import edges.
- `5d4415ac8c`, `38b4cba798`, `a5eb4dc920` — ADR Amendment 3 and plan `2026-09-23-iva-workflow-plan` S01–S05: ordinary evidence asks each period only what DP30301 asks (joint-return election every period; Modelo 390 attestation only in 4T or 12, refused elsewhere; no annual-volume answer on the ordinary path); monthly periods admitted for filers whose registry filing schedule is monthly (REDEME or large company), others refused; calculate request schema v3 with pending v1/v2 invocations refused; one application entry authors evidence for the operation, CLI and quickfile; the governed last-period fact is resolved under the pinned authority, including for the TUI form.
- `b5cd51718e` — shared installed-driver helper settles a self-dismissed operation modal from the workspace notice (every lane's driver).

## Checks (all `-n0`, explicit markers)

| Command / selection | Result | Log |
|---|---|---|
| `pytest -m unit application/modelo/tests/test_lifecycle_operation_conformance.py` | 65 passed | `…/20260923T122502.606465Z-pytest-31344-72b7e127/run.log` |
| same + authoring + attestation custody + CLI M303 roundtrip + quickfile 2026 case (`-m "unit or integration"`) | 79 passed | `…/20260923T135447.481093Z-pytest-52432-052b94f7/run.log` |
| `pytest -m unit tui/modelo/view/tests/test_m303_evidence_*.py` | 19 passed | `…/20260923T134124.020810Z-pytest-61288-c8463869/run.log` |
| `pytest -m "unit or integration" tui/modelo/view/tests/test_workspace_overview.py` | 8 passed | `…/20260923T141415.853533Z-pytest-41172-8bd0f83a/run.log` |
| `pytest … test_operation_modal.py -k "refusal_code_is_explained or terminal_receipt_reaches"` | 3 passed | `…/20260923T134242.245179Z-pytest-66144-88e36e5c/run.log` |
| export refusal: `test_export_output_paths` (303 positions) + CLI M202 refusal | 3 passed | `…/20260923T132136.119377Z-pytest-37704-f254cda9/run.log` |
| committed-tree isolation (temp worktree at `aacf15b688`) | 82 passed | console |
| Ruff, `ruff format --check`, `ty` on every changed file; basedpyright strict and pyrefly on changed application/domain files | clean | — |

Inherited, pre-existing (identical at the parent commit, not introduced here): `entrypoints/tests/test_operation_composition.py` 4 failures and `adapters/persistence/operations/tests/test_workspace_refresh_target_resolution.py` 3 failures (owner-import and registration-ordering invariants); `core/errors/tests/test_exception_base_hygiene.py` 2 failures naming actividad_asset and withholding modules. Global import gate: red with pre-existing findings; none sourced from these modules. Its single loadability failure is `dev/acceptance/income_tax/cli_journey.py` (peer-dirty; `installed_tui_continuations` imports removed `_ingest`/`_result`).

## Installed proof

PROVEN on 2026-09-24, journey 01:59:38–02:15:47, exit 0. The source was `70fdb5c85b`, built into a fresh detached worktree with its own wheel and venv and `CADRUMO_AUTHORITY_ROOT` unset. Wheel `cadrumo-0.5.1-py3-none-any.whl`, SHA-256 `883579f8…`. Authority generation `02bd5859…` (database `3d8f5697…`), and the bundled generation equals the one read. Installed `__init__` SHA-256 `930e3f61…`. Periods 4T, 12 and 1T of 2025, over four synthetic encrypted stores.

- **tui-led** (4T), in the TUI:
  - a missing answer stays on the form;
  - cancelling sends no request;
  - a mismatched attachment pair and an attestation from the wrong filing context are both refused as unadmissible, visibly;
  - calculate and verify succeed;
  - in a fresh process, the export is refused visibly because no reviewed product identity exists, not as a failure.
- **continuation**: a changed joint election produces a distinct revision.
- **monthly** (2025/12): a REDEME filer.
- **first-quarter** (1T): the joint-return question only, and the CLI refuses attestation flags.

The receipt declares what it leaves unexercised:
- numeric readback on Results, because the workspace admits static inspection only;
- official export, because the EEDD header identity is unavailable;
- multi-line invoice capture;
- AEAT submission.

Earlier attempts, and what each found:

- **`3ddd8d54b7`**: the TUI export failed where the CLI refused, because the export operation carried none of the elections. Fixed in `ba73e0945f` and `9ea5028fa4`.
- **`e9b5c65c33`**: the monthly store called a profile `set` command that does not exist. Fixed in `0e46b2a89a`, and now guarded by the harness argv gate `c40315b8d7`.
- **`0e46b2a89a`**: the mismatched-pair calculation was refused in the journal within a second, but no workspace notice appeared for 300 s. It was not reproduced at `70fdb5c85b`, which adds the timeout diagnostic.
  - With rehearsal run 1, this symptom has appeared in two of five installed runs. It is open as a notice-delivery investigation, not as a closed harness race.

Quiet-host measurement on 2026-09-23: unauthenticated CLI start 1.4–2.4 s, profile creation 45.7 s, authenticated calls 4.7–18.9 s. The call phases of the two IVA CLI journeys alone take 337–713 s, so they carry measured per-journey timeouts.

## Returned surfaces

`application/modelo/operation_definitions.py`, `entrypoints/operation_composition.py`, `tui/modelo/lifecycle.py`, `tui/modelo/view/overview.py`, the `_modelo_lifecycle_door` launcher hunk and the focused tests are returned to the shared Modelo/TUI owner. IVA keeps `tui/modelo/m303_evidence.py`, its tests and `dev/acceptance/iva/` as the evidence-entry owner.
