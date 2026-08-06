# Edge probe: EXPORT / VERIFY / RECONCILE (adversarial QA)

Persona: adversarial QA against the real CLI. Isolated state under `/tmp/edge-export`
(persona harness). Full chain built: profile `edgetest` (12345678Z, persona física,
name "Juan", surnames "Perez Garcia", activity-start 2025-01-01) → 303/130/390 work
units created, calculated, verified.

Surfaces exercised:
- `aeat app modelo export [WORK_UNIT_ID]`
- `aeat app modelo work verify`
- `aeat app modelo verification-report {list,view}`
- `aeat app modelo reconcile {file,pull,history}`

## Summary verdict

3 BUGs (all MEDIUM/LOW — unhandled output-path errors leaking raw Python tracebacks;
no crash in the calculation/parse/refusal core). All security/safety refusals held.

| # | Severity | Verdict |
|---|----------|---------|
| BUG-1 | MEDIUM | export `--output <existing-dir>` → raw `PermissionError` traceback + leaves orphaned `.tmp` with real data |
| BUG-2 | LOW-MED | export `--output ""` → raw `ValueError: WindowsPath('.') has an empty name` traceback |
| BUG-3 | LOW | export with `--year 1999` → raw pydantic `ValidationError` text echoed to log/stderr |
| OBS-1 | cosmetic | reconcile report prints `bucket  <profile-id>` literal placeholder token |
| OBS-2 | cosmetic | export `--select` accepts `latest-verified`/`filed`/`latest-draft` but `--help` only documents `current` |
| OBS-3 | cosmetic | reconcile `--file` to a nonexistent path returns the same "could not read PDF / maybe damaged" msg as a junk file (no "not found") |

---

## BUG-1 (MEDIUM) — export to an existing directory crashes with raw traceback + orphaned .tmp

Command:
```
aeat app modelo export --modelo 130 --year 2025 --period 1T --output /tmp/edge-export/adir   # adir is a directory
```
Expected: clean refusal ("output path is a directory / not a writable file").
Actual (exit 6, "Internal"):
```
Traceback (most recent call last):
  ...
  File ".../src/aeat/application/modelo/_export.py", line 622, in export_modelo_revision
    tmp_output.replace(command.output_path)
  File ".../pathlib/_local.py", line 780, in replace
    os.replace(self, target)
PermissionError: [WinError 5] Access is denied: '...\edge-export\adir.tmp' -> '...\edge-export\adir'
Internal. El comando falló por un error interno inesperado.
```
Compounding: the failed atomic-replace leaves `adir.tmp` (946 bytes of real exported
fichero-BOE financial data) on disk — the temp-write-then-replace path does not clean
up on the replace error. Verdict: BUG — raw traceback leak + stray cleartext artifact.
Root site: `_export.py:622 tmp_output.replace(command.output_path)`.

## BUG-2 (LOW-MED) — empty --output crashes with raw traceback

Command:
```
aeat app modelo export --modelo 130 --year 2025 --period 1T --output ""
```
Expected: clean refusal on empty path. Actual (exit 6, "Internal"):
```
  File ".../src/aeat/application/modelo/_export.py", line 565, in export_modelo_revision
    tmp_output = command.output_path.with_name(command.output_path.name + ".tmp")
  ...
ValueError: WindowsPath('.') has an empty name
```
Same family as BUG-1: the `--output` path is not validated before use. Verdict: BUG.

## BUG-3 (LOW) — non-existent filing year leaks a pydantic ValidationError

Command:
```
aeat app modelo export --modelo 303 --year 1999 --period 4T --output /tmp/x.boe
```
Expected: instructive "year must be >= 2000" via the Notice channel. Actual (exit 2,
refuses correctly but leaks parser internals to the log):
```
[ERROR] ... pydantic ValidationError in modelo_export_verb: [{'type': 'greater_than_equal',
 'loc': ('filing_year',), 'msg': 'Input should be greater than or equal to 2000', ...}]
Refused. La entrada del comando no superó la validación. ...
```
Verdict: BUG (low) — raw pydantic dict surfaced; violates `cli-notices-are-the-only-
diagnostic-channel` / instructive-CLI-gate intent.

---

## CORRECT REFUSALS / CORRECT BEHAVIOUR (no bug)

- export UNVERIFIED draft → exit 2: "current revision is still draft; verify it before
  exporting or select a verified revision explicitly". CORRECT.
- export bogus work-unit id `deadbeefdeadbeef` → exit 2: "work_unit_id debe ser una
  cadena hex en minúsculas de 64 caracteres (SHA-256)". CORRECT.
- export missing operator name (before name/surnames set) → exit 5: "faltan estos datos
  de perfil: ['identity.surnames', 'identity.name']". CORRECT (lists missing fields).
- export `--select wibble` → exit 2: lists accepted set (current, latest-draft,
  latest-verified, filed, explicit). EXEMPLARY instructive gate.
- export `--select explicit` w/o id → exit 2: "explicit revision selection requires an
  id". CORRECT.
- export to nonexistent nested dir `/nope/deep/x.boe` → auto-creates dirs, exit 0.
  Convenient + idempotent.
- **Export idempotency**: re-export + overwrite of the same verified 130 revision yields
  byte-identical `file_sha256 20248f2c...` (946 bytes) every time. Distinct
  `bucket_event_id` per run (correct: each export is an audited event; bytes are stable).
- **.boe structural sanity**: 130 = `<T130020251T0000><AUX>...</AUX><T13001000>...
  </T13001000></T...>`; 303 = balanced section tags `<T30301000>..<T30305000>`,
  `<T303DID00>` (7994 B). Fixed-width padded fields, tax-id/identity present, balanced
  open/close tags, no control chars, single line no trailing newline. Authentic
  fichero-BOE shape.
- verify (current) on already-`verificado_completo` revision → exit 2: "verification
  requires a draft revision". CORRECT.
- verify persists a NEW report on each run (7 reports across runs, distinct id+run_at).
  CORRECT audit trail.
- cross-period gating: 303-1T and 130-1T both BLOCKED on prior-period evidence until
  activity-start-date recorded; then scoped-out as pre-activity (advisory warning,
  granted=true). 390-0A BLOCKED with 16 legitimate cross-period findings (needs the 4
  quarterly 303s). All structured, no crash.
- verification-report view bogus id (`deadbeef` and 64-zero hex) → exit 2: "No existe
  ningún informe de verificación con id=...". CORRECT.
- reconcile file junk non-PDF → exit 2: "No se pudo leer el PDF..." (JustificanteParse
  Error surfaced cleanly, NO traceback). CORRECT.
- reconcile file no `--file` → exit 2: "Missing option '--file'". CORRECT.
- reconcile file wrong-but-valid empty PDF → exit 2: clean parse refusal. CORRECT.
- reconcile file vs a REAL 036 justificante PDF (wrong modelo) → exit 0: parsed and
  returned `verdict=mismatches` with structured diffs (modelo 130 vs 036, period 1T vs
  0A, tax_id mismatch). EXCELLENT — real parse + structured comparison, no leak.
- reconcile pull (no auth) → exit 2: refuses on Cl@ve identity mismatch, never contacts
  AEAT. Safety gate holds.
