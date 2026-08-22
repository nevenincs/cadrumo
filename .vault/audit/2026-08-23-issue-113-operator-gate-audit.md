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
