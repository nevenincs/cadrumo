# Edge-profile adversarial QA — PROFILE / IDENTITY surface

Persona: adversarial QA probing profile/identity edge cases via the real CLI.
Harness: `source .agents/persona_env.sh /tmp/edge-profile` + `uv run --no-sync aeat …`.
Date: 2026-06-19. All probes run against the live Typer CLI (no code/docs edited).

## Verdict summary

| # | Severity | Verdict | Area |
|---|----------|---------|------|
| F1 | CRITICAL | BUG | `profile import` accepts invalid / malformed tax-id (bypasses create's NIF/CIF checksum) |
| F2 | CRITICAL | BUG | `profile validate` reports `valid=True, issues=0` on a profile carrying an invalid tax-id |
| F3 | MEDIUM | BUG | gestor mode: `capabilities set cloud_evidence_upload on` reports `estado=on` EXIT=0 (misleading; resolution overrides to safe) |
| F4 | MEDIUM | BUG | `duplicate SOURCE TARGET --display-name X` discards TARGET id; profile only addressable by display name |
| F5 | LOW | BUG | Over-long name dumps a raw pydantic ValidationError dict to the stderr ERROR log before the clean refusal |
| F6 | LOW | INCONSISTENCY | tax-id redaction is inconsistent: valid NIF/NIE redacted to `sha256:…`, but invalid CIF / garbage shown in cleartext in error text |
| — | — | CORRECT REFUSAL | invalid NIF, invalid NIE, invalid CIF, garbage id, duplicate-NIF, foral CCAA, ceuta/melilla, bogus capability/state, switch-unknown, duplicate/target collision, logout-then-verb, corrupt/missing bundle, delete-active gating, --quiet missing flags, over-long name (rejected), unicode |

---

## CRITICAL findings

### F1 — `profile import` accepts an invalid / malformed tax-id (identifier-validation bypass)
- Setup: exported a valid profile (`cifok`, CIF `A58818501`) to a plaintext JSON bundle, then
  edited the tax_id by hand and re-imported.
- Command (a): `sed 's/A58818501/A58818502/' export.json > t.json; aeat config profile import t.json --label tampered1`
  - `A58818502` is an INVALID CIF (type-A control digit must be 1, not 2).
  - Expected: refusal at the import boundary, identical to `create`'s NIF/CIF checksum gate.
  - Actual: `EXIT=0`, "El perfil importado tampered1 es ahora el perfil ACTIVO". Profile created and made active.
- Command (b): `sed 's/A58818501/ZZZ99999/' export.json > g.json; aeat config profile import g.json --label garbageimp`
  - `ZZZ99999` is not even valid CIF *shape* (Z not a CIF prefix; 8 chars).
  - Actual: `EXIT=0`, imported and made the active profile. `profile show` → `identity.tax_id  ZZZ99999`.
- Contrast: `create … --tax-id A58818502` / `--tax-id ZZZ99999` / `--tax-id NOTANID` are all REFUSED (EXIT=2) with precise checksum/shape messages. The import path does NOT apply the same gate.
- Impact: an invalid fiscal identifier lands in an ACTIVE filing-grade profile. Per brief, an invalid identifier accepted is CRITICAL. Filing-grade identity bypasses validation.

### F2 — `profile validate` blesses a profile with an invalid tax-id
- Command: with `tampered1` (tax_id `A58818502`, invalid CIF) active → `aeat config profile validate`
  - Expected: report the bad control digit as an issue.
  - Actual (quote): `readiness  ready  issues=0` … `valid  True`, EXIT=0.
- Impact: the validation verb that is supposed to be the safety net does not re-check the identifier checksum, so the F1 bypass is invisible to `validate` too.

---

## MEDIUM findings

### F3 — gestor mode: capability `set` reports success for an absolutely-barred capability
- Command: `AEAT_EVIDENCE_GESTOR_MODE=1 aeat config profile capabilities set cloud_evidence_upload on`
  - Expected: refusal / warning (gestor mode bars cloud evidence upload absolutely; rule `sensitive-financial-data-secure-storage-only`).
  - Actual (quote): `capacidad  cloud_evidence_upload` / `estado  on`, EXIT=0.
- Mitigation (why MEDIUM not CRITICAL): the resolved view IS safe —
  `capabilities show` under gestor mode (quote): `cloud_evidence_upload  desactivado  safety_floor  gestor mode bars cloud evidence upload for this deployment`.
  So the effective posture is correctly floored; only the `set` command's reported state is dishonest. An operator is told upload is enabled when the deployment will never honor it.

### F4 — `duplicate SOURCE TARGET --display-name X` silently discards the TARGET id
- Command: `aeat config profile duplicate cifok dupd --display-name "Dup Display"`
  - `duplicate` help documents TARGET as "Id del perfil de destino" (required).
  - Actual: EXIT=0; `profile list` shows the new profile only as `Dup Display`. `rename dupd …`, `show dupd` → "Perfil desconocido: dupd". The target id `dupd` is lost; the profile is addressable ONLY by the display name.
  - Control: `duplicate cifok dup2` (no `--display-name`) → addressable as `dup2` (display name defaults to id). So the id is honored only when no display name is given.
- Impact: documented TARGET id is non-functional when `--display-name` is supplied — a confusing addressing inconsistency; a script that duplicates with an explicit id+label cannot then address the result by that id.

---

## LOW findings

### F5 — over-long name leaks a raw pydantic ValidationError dict to the log
- Command: `create <600×'N'> … --quiet --accept-defaults`
  - User-facing refusal is fine ("La entrada del comando no superó la validación…").
  - But stderr first emits: `[ERROR] aeat.entrypoints.cli._errors: command_error_boundary: pydantic ValidationError in setup: [{'type': 'string_too_long', 'loc': ('display_name',), 'msg': 'String should have at most 160 characters', 'input': 'NNNN…', 'ctx': {'max_length': 160}, …}]`
  - The full 600-char input and internal validation structure are dumped. Minor internal-detail leak; the clean channel exists alongside it.
- Boundary check: name of exactly 160 chars is ACCEPTED (correct cap behavior).

### F6 — inconsistent tax-id redaction in error output
- Valid NIF/NIE refusals redact the id: `…: sha256:cb6f3ba1 … raw_redacted: true`.
- But invalid CIF / garbage refusals print the id in CLEARTEXT in the message: `…no válido…: A58818500…`, `…NOTANID no tiene la forma de un CIF…`.
- Same surface, two redaction policies. A malformed id is still PII-adjacent; redaction should be uniform.

---

## Correct refusals (no bug) — evidence

- Invalid NIF `12345678A`: refused EXIT=2, names correct control letter Z. Good.
- Invalid NIE `X1234567A`: refused EXIT=2, names correct letter L. Good.
- Valid NIE `X1234567L`: accepted. Valid CIF `A58818501` (entity `legal_entity`, form `sl`): accepted.
- Invalid CIF `A58818500`: refused (control digit 1 expected, got 0). Garbage `NOTANID`: refused with shape help.
- Duplicate NIF: `create` with a NIF already in use → "ya lo usa el perfil 'dnilc'; un contribuyente debe tener un solo perfil." Good.
- Foral CCAA `pais_vasco` / `navarra`: REFUSED EXIT=2 with excellent guidance ("tributan ante la Hacienda Foral … no ante la AEAT … sede.bizkaia.eus / hacienda.navarra.es"). Good.
- `ceuta` / `melilla`: not in CCAA enum → refused at parse, accepted-set listed. Acceptable (common-regime cities not modeled).
- Bogus entity-type `legal_person`, bogus legal-entity-form `BOGUS`, bogus capability `bogus_cap`, bogus state `maybe`: all refused at parse with the accepted set surfaced (CLI-gate discipline upheld).
- `switch ghost`: refused, "Perfil desconocido: ghost".
- `duplicate cifok nieok` (existing target): refused, "El perfil nieok ya existe".
- `logout` → then `profile show`: refused "No hay un perfil activo…"; `status`: clean "Sin perfil configurado".
- Import corrupt bundle (truncated JSON): refused (schema/JSON error). Import missing path: refused "No se encontró el paquete".
- Export: writes plaintext bundle WITH a strong WARNING notice (NIF en claro, libro completo — bórralo tras la transferencia). Import roundtrip with `--label`: works, sets imported profile active with an INFO notice.
- Delete ACTIVE profile: without `--yes` refused ("La eliminación es destructiva"); with `--yes` tombstoned and active pointer cleared with a clear recovery notice. Good.
- `--quiet` missing required: clean refusal naming the missing flag (`--tax-id`). Good.
- Unicode surnames `Müller-Østergård 李 😀 Núñez`: accepted and round-trips byte-faithful in `show`.
