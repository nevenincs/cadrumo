---
related: []
date: '2026-08-23'
modified: '2026-08-25'
body_hash: 'sha256:b86fa67e18f1d22e112cb840f193e6fb3158101d2ea9530a96b77632c029ef64'
tags:
  - '#audit'
  - '#open-decisions-and-operator-gates'
---
# Issue #113 operator gate audit — 2026-08-23

## Scope and environment

- Commit: `fc8af5b4716ae02166b8835ee4d6bda12ae4bd96` (`origin/main` at the start of the gate).
- Isolated worktree: `Y:\code\aeat-worktrees\issue-113`.
- Branch: `audit/issue-113-operator-gate`.
- Data: bundled synthetic fixture `src/cadrumo/tests/fixtures/financial/synthetic-transactions.csv` and synthetic NIF `Y0000001S` only.
- Storage and secret directories were isolated under the untracked `.operator-gate/` directory. No live AEAT credentials were present and no AEAT request was made.

## Exact operator journey

### Clean install and help-only discovery

```text
uv sync --no-dev
```

Succeeded: 65 runtime packages installed in a fresh `.venv`.

```text
uv run --no-sync cadrumo --help
```

Failed before application startup: `program not found`. The installed project exposes `aeat`, not `cadrumo` (`pyproject.toml` `[project.scripts]`). This is a documentation/issue-body defect in acceptance step 1.

```text
uv run --no-sync aeat --help
uv run --no-sync aeat config profile create --help
uv run --no-sync aeat app ledger import --help
uv run --no-sync aeat app modelo work --help
```

All succeeded. Discovery showed the local profile, ledger import, and modelo lifecycle surfaces.

### Synthetic profile and import

With `CADRUMO_LOCAL_STORAGE_ROOT`, `CADRUMO_SECRET_STORE_DIR`, and `CADRUMO_SECRET_PASSPHRASE` set to isolated gate-only values:

```text
uv run --no-sync aeat config profile create gate113 \
  --entity-type natural_person --tax-id Y0000001S \
  --name Synthetic --surnames Operator \
  --activity "servicios profesionales" \
  --irpf-income-categories actividad_economica \
  --tax-residence-jurisdiction-scope common_regime \
  --tax-residence-ccaa madrid --iva-regime GENERAL \
  --iva-m303-regime-composition general \
  --no-iva-redeme-enrolled \
  --no-iva-cash-accounting-regime-enrolled \
  --no-iva-voluntary-sii-enrolled \
  --no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled \
  --irpf-estimation-regime directa_simplificada \
  --quiet --accept-defaults
```

Succeeded and reported `Perfil 'gate113' creado y listo`.

```text
uv run --no-sync aeat --format json config profile status
```

Succeeded and reported `configured: true`, `tax_id_present: true`, `activity_present: true`, `iva_regime: GENERAL`, and `tax_residence_ccaa: madrid`.

```text
uv run --no-sync aeat app ledger import \
  --file src/cadrumo/tests/fixtures/financial/synthetic-transactions.csv \
  --provider csv --year 2026 --period 2T --verify
```

The initial invocation persisted both synthetic rows. A deliberate retry succeeded with `Entradas importadas 0`, `Omitidos 2`, duplicate-ID notice, and `Válido Sí`, proving operator-visible idempotency.

### Modelo readiness and blocking defect

```text
uv run --no-sync aeat --format json app modelo describe 130
uv run --no-sync aeat --format json app modelo readiness \
  --modelo 130 --revision-id 2019-y-siguientes --year 2026 --period 2T
```

Describe succeeded. Readiness returned `profile_ready: true` and `registry_ready: true`. It correctly reported ledger classifications and prior-period bindings still needed.

```text
uv run --no-sync aeat --format json app modelo work create \
  --modelo 130 --year 2026 --period 2T --by issue113-operator
```

Refused with `REFUSED_MODELO_PROFILE_READINESS`: “La configuración del perfil está incompleta; termina el asistente de configuración antes de trabajar con modelos.” The error named no missing field. Re-running after `aeat config login gate113` produced the same refusal.

This is a product defect: three product surfaces disagree about the same profile. Create says “listo”, status says `configured: true`, and targeted readiness says `profile_ready: true`, while work creation says setup is incomplete. The refusal prevents work-unit creation, so calculate, inspect/review, verify/approve, and export cannot be exercised honestly.

### Permanent no-write boundary

```text
uv run --no-sync aeat app live --help
uv run --no-sync aeat app live submit
```

The live namespace describes itself as read-only and exposes no submit verb. The deliberate submit command was rejected locally with `No such command 'submit'`; it made no AEAT request.

The public production access gate was then invoked directly, outside pytest:

```text
uv run --no-sync python -c "from cadrumo.core.access_gate import AeatAccessGate; from cadrumo.core.config import Settings; AeatAccessGate(Settings()).require_live_write()"
```

It raised `LiveSubmitForbiddenError`: “live AEAT submission is permanently forbidden; use produce -> verify -> export and upload the file yourself in the AEAT portal”. This occurred before any adapter or network call.

### Live-read prerequisite

No AEAT/certificate/Cl@ve credential environment was available. Per issue scope, live filed pull/re-sync was not attempted. This is an external prerequisite and does not invalidate the local journey; the product defect above does.

## Findings and disposition

1. **Product defect — BLOCKER:** profile readiness is contradictory across create/status/readiness/work-create, and the final refusal does not identify the missing field. The lifecycle cannot reach calculate/review/verify/export.
2. **Documentation defect:** issue acceptance says `cadrumo --help`, but the installed executable is `aeat`.
3. **External prerequisite:** no safe read-only AEAT credentials were available, so pull/re-sync remains unexercised without blocking local acceptance.
4. **Pass:** clean install, help discovery through the actual executable, safe profile creation, real local CSV import, import verification/idempotency, and permanent no-write refusal all behaved safely.

**Recommendation: keep #113 open.** The complete produce → verify → export acceptance is red because work creation is blocked by contradictory profile readiness. Triage the readiness disagreement as a product defect; after its fix, rerun this same isolated operator journey and add read-only pull/resync when operator-owned credentials are safely available.

## Corrective rerun — 2026-08-23

The readiness defect was traced to an intentional two-stage profile lifecycle whose projections disagreed. A profile is born `INCOMPLETE` even when all required facts are present; the operator must explicitly declare it complete with `aeat config profile complete-setup`. `work create` enforced that state, while scripted create said “created and ready” and modelo readiness ignored `setup_state`.

The correction preserves the explicit declaration boundary:

- scripted create now names `aeat config profile complete-setup` instead of claiming readiness;
- modelo readiness reports `profile_ready: false` and the same actionable completion command while setup is incomplete;
- work creation retains its fail-closed refusal and now carries the actionable command through the shared locale message.

Focused verification:

```text
uv run pytest -q -m integration -n 0 \
  src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py \
  -k incomplete_setup
# 1 passed, 8 deselected

uv run pytest -q -m integration -n 0 \
  src/cadrumo/entrypoints/cli/_config/tests/test_profile_complete_setup_verb.py
# 2 passed

uv run ruff check src/cadrumo/application/state_projection.py \
  src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py
# All checks passed
```

A fresh isolated `.journey/` run then completed the formerly blocked portion:

1. profile create emitted the corrected completion guidance;
2. `config profile complete-setup` succeeded;
3. CSV import persisted two synthetic rows and both were classified through the real CLI;
4. M130 2026 2T work creation succeeded (`734542…328a4b`);
5. calculation succeeded and persisted revision `ab38f4…dd03fb`, with ledger-grounded casillas 01=`1020.30`, 02=`41.31`, and result 19=`95.80`;
6. revision inspection and work review succeeded with no review blockers.

Verification was then exercised rather than bypassed. It correctly remained blocked by evidence the synthetic one-period walkthrough does not possess: clean M100 2025 annual and M130 2026 1T filing lineage, an activity-start date, and invoice evidence for the deductible expense. Consequently no approval was granted and export was not attempted against an unverified revision. These are honest workflow prerequisites, not a recurrence of the fixed profile-readiness defect.

The local encrypted `.journey/` evidence was removed after recording these redacted identifiers. The permanent no-write boundary remains unchanged.

**Updated disposition:** the bounded readiness defect is fixed, but #113 should remain open because its complete verify → export acceptance still needs a synthetic operator fixture with authoritative prior-period lineage and deductible-expense evidence (or a first-period scenario whose registry dependencies genuinely do not require them). Do not weaken verification to close the gate.

## Purpose-specific lineage attempt — 2026-08-23

A second disposable `.journey2/` runtime tested whether the newly shipped external filing import could build the missing lineage without live AEAT access.

Locally creatable prerequisites were confirmed:

- `config profile create --activity-start-date 2025-01-01` records the required start date;
- `ledger evidence add` and `ledger attach --purchase-invoice-evidence-id …` expose the deductible-expense evidence path;
- M100 2025 work creation succeeds;
- `modelo reconcile file --kind declaration --file src/cadrumo/tests/fixtures/justificantes/100/2025-0A.pdf` parses locally and reports `verdict=matches`;
- `modelo reconcile file --kind justificante --file src/cadrumo/tests/fixtures/justificantes/modelo_100_2025A.pdf` also parses locally (and correctly reports the fixture/profile NIF mismatch).

The external-baseline production path is discoverable:

```text
aeat app modelo filing-record import WORK_UNIT_ID \
  --evidence-kind aeat_csv_register \
  --evidence-id synthetic-m100-2025 \
  --set 0235=0
```

It refuses before completeness validation:

```text
REFUSED_CLI_BOUNDARY
La evidencia de importación externa synthetic-m100-2025 (aeat_csv_register)
no está registrada como artefacto de justificante persistido.
```

This prerequisite has no safe local CLI creation path. `app live justificante` exposes only `pull`, `list`, and `view`; `pull` would make an AEAT call and was prohibited. Both successful `modelo reconcile file` invocations leave `app live justificante list` at `count: 0`. Reconciliation also leaves the M100 work in `borrador`, with `current_filing_record_id: null`, and no calculation observation. `work file` cannot bridge the gap because it accepts only an already verified calculation—the very lineage verification is trying to establish.

**Concrete product-surface blocker:** provide a local, fail-closed CLI composition that persists an imported AEAT CSV-register/justificante evidence artifact and returns its stable evidence id for `filing-record import`, or let `filing-record import --file` atomically persist and bind that source artifact after validating its source manifest. Without that door, a safe source-only fixture cannot create clean M100-2025 or M130-2026-1T external filing lineage; therefore M130-2026-2T cannot reach approval/export without a live pull or bypassing verification.

No AEAT call was made, no production code changed, and `.journey2/` was removed after the attempt. **Disposition remains keep #113 open.**

## CSV-register provenance correction — 2026-08-23

The blocker above was an evidence-kind contract error. `filing-record import
--file` already parses the operator-selected CSV/XLSX, validates its casilla ids
against the authoritative target registry, refuses an incomplete required-id
manifest before work-unit creation, preserves exact source lexicals, and
co-commits the calculation revision, filing record, work-unit pointers, and
bucket event. Despite that, `aeat_csv_register` was grouped with receipt-bound
sources and required unrelated persisted `Justificante` metadata. No public
local command could create that metadata without a live pull.

The corrected policy treats the CSV/XLSX register file as its own evidence
source. Its operator reference is bound in `ExternalEvidence` on the atomically
committed filing record, whose work-unit coordinates retain bucket/profile,
modelo, year, and period identity. `aeat_justificante_pdf` and
`aeat_live_capture` remain receipt-bound and still require matching stored
Justificante metadata including taxpayer identity.

The real CLI regression begins with credential-backed profile registration and
then uses only public commands for setup completion, work creation, and source
import. It proves the complete M130 CSV becomes a filing baseline with exact
lexicals (`" 001500.00 "`, `"300,0"`). Its negative twin imports a partial
required manifest and proves `filing-record list` remains empty and both the
work unit's current calculation and filing pointers remain null.

```text
uv run pytest -m integration -n 0 \
  src/cadrumo/entrypoints/cli/tests/test_modelo_external_source_file_cli.py -q
# 2 passed in 42.94s

uv run pytest -n 0 \
  src/cadrumo/application/modelo/tests/test_external_source_import.py \
  src/cadrumo/application/modelo/tests/test_import_flow_justificante.py \
  -k "source or csv_register or refuses_without_enrolled" -q
# 6 passed, 5 deselected in 35.80s

uv run ruff check \
  src/cadrumo/application/modelo/_external_import_actions.py \
  src/cadrumo/application/modelo/tests/test_external_source_import.py \
  src/cadrumo/application/modelo/tests/test_import_flow_justificante.py \
  src/cadrumo/entrypoints/cli/tests/test_modelo_external_source_file_cli.py
# All checks passed
```

An unfiltered adjacent run additionally reported 7 passes and four failures
before application execution because legacy Justificante test identifiers
contain hyphens while the current domain schema requires `^[A-Z0-9]{8,32}$`.
That fixture drift predates and is independent of this CSV correction; it was
not hidden by weakening the identifier contract.

### Fresh operator rerun with real prior-filing imports

A fresh disposable `.journey3/` run used the bundled synthetic M100 declaration
values rather than invented expectations. Profile creation included activity
start `2025-01-01`; setup completion succeeded. Public commands created M100
2025-0A and M130 2026-1T work units and imported complete CSV baselines. The
M100 file contained the exact 21 casilla/value rows printed by the committed
`100/2025-0A.pdf` fixture generator; M130 1T contained the complete required
01/02 zero manifest. Both imports succeeded and produced current, AEAT-accepted
external filing records.

The Q2 operator path then imported the bundled two-row ledger fixture,
classified income and software expense, registered encrypted purchase evidence
through `ledger evidence add`, attached it to the expense, and created the M130
2026-2T work unit. Calculation required an explicit
`modelo-130-pagos-fraccionados-anteriores=0` binding even though the clean 1T
filing existed; with the authoritative 1T zero value supplied, calculation and
review succeeded as revision `23b06b…c95499e` (01=`1020.30`, 02=`41.31`,
03=`978.99`, 04=`195.80`).

Verification remained blocked, so approval and export were correctly not
attempted. The exact blockers for both M100 2025-0A and M130 2026-1T are
`missing_observation|missing_external_evidence_record`. This is a second,
distinct integration gap: CSV import now creates the durable external filing
and its calculation observations, but the cross-period verifier reads a
separate `CalculationObservationRepository` and still treats every external
evidence kind as receipt-backed when looking for its evidence record. It
therefore neither projects the imported filing into its observation store nor
accepts the CSV-bound filing evidence that the import path just committed.

**Journey verdict:** the local CSV evidence-registration blocker is fixed, but
#113 remains open. The next product correction must compose imported filing
baselines into the cross-period observation/read model and distinguish
CSV-bound evidence from receipt-bound PDF/live evidence in clean-state
evaluation. No verifier gate was weakened and no AEAT call was made.

## Cross-period provenance projection correction — 2026-08-23

CSV import now prepares an `AEAT_CSV_REGISTER` calculation-observation envelope
from the imported revision and co-commits it with the revision, filing record,
work-unit pointers, and bucket event. Its encrypted provenance binds ALTA state,
authenticated profile identity, external evidence reference, filing-record id,
and stamped registry revision. A partial/refused import leaves this repository
empty as part of the existing atomic unit.

Clean-state evaluation now distinguishes receipt-bound evidence from the wider
set of accepted external filing evidence. PDF Justificante and live capture
still require matching persisted Justificante metadata. CSV requires the
official CSV observation source plus exact evidence-reference and filing-id
agreement; a tampered reference fails with
`mismatched_external_evidence_record`.

Focused evidence:

```text
uv run pytest -n 0 \
  src/cadrumo/application/modelo/tests/test_external_source_import.py -q
# 6 passed in 40.77s

uv run pytest -m integration -n 0 \
  src/cadrumo/entrypoints/cli/tests/test_modelo_external_source_file_cli.py -q
# 2 passed in 44.45s
```

A fresh `.journey4/` rerun proved the observation seam is live: after importing
M130 1T with its full zero filing/carry manifest, Q2 calculation resolved both
M130 previous-period bindings from the imported observation. It next requested
M100 2025 casilla 1479 for
`irpf.previous_year_economic_activity_net_income`. The bundled synthetic
M100-2025 declaration fixture has exactly 21 parser-grounded casillas and does
not contain 1479. No authoritative synthetic value exists in the fixture to
add without invention. This is the current external/fixture-authority boundary
(also relevant to the separately audited M100 full-form work in #455), not a
remaining CSV persistence defect. Per operator-gate policy, calculate stopped;
verify/approve/export were not fabricated. `.journey4/` was removed and no AEAT
call occurred.

### Observation-batch rollback proof

The enlarged import transaction is pinned by a real secure-store CAS-conflict
regression. After priming a complete external baseline, the test injects a
stale expected revision on the observation write of a replacement import. The
storage batch raises `SecureObjectRevisionConflictError`, and reads prove the
filing catalogue, calculation catalogue, WorkUnit pointers, bucket-event
history, and observation envelope all remain byte-for-byte at their baseline
state.

```text
uv run pytest -n 0 \
  src/cadrumo/application/modelo/tests/test_external_source_import.py \
  -k observation_write_failure -q
# 1 passed in 32.03s
```
