---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:fdac11269fa2f91079bf90455c7a8bbbc6ce2011d13cbe6bd26f6433899c04a8'
step_id: 'S26'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Run the manual authenticated sweep with the operator present and create one exec record per completed command group

## Scope

- `.vault/exec/2026-06-12-live-pull-verification-sweep`

## Description

- Created an isolated encrypted profile root (`CADRUMO_LOCAL_STORAGE_ROOT` scoped to a fresh `var/live-auth-...` directory, file-backed secret store, process-local passphrase), created a real profile (`config profile create ... --quiet --accept-defaults`), configured Cl@ve Móvil, and confirmed `identity_alignment=matches`.
- Acquired a fresh authenticated Cl@ve Móvil session with the operator present via `config auth login --provider clave_movil --fresh --reset-lock` (succeeded on the third attempt; see Notes).
- Ran every read-only `app live` command group against the live session, in order: `filed list/pull/pull-sources` (recorded fully in `S11`), `expedientes pull/list/view/latest` (recorded fully in `S12`), `notifications pull/list/latest`, `justificante list/pull`, `iva-wallet pull/history`, `verify nif-iva/tgvi/list/latest`, `borrador 100 list`, `portals list`, and the local-only `overview status/agenda/calendar` projections (recorded fully in `S27`).
- Confirmed the session stayed live and re-usable across every command group without re-authenticating (`config auth status` reported `authenticated=true`, `persisted_session_state=live` throughout).

## Outcome

Every command group in the runbook was exercised against the live authenticated session; the filed-declaration and expediente results are recorded in `S11`/`S12`, and the calendar-projection results are recorded in `S27`. The remaining groups:

- `notifications pull/list/latest`: `row_count=0` (a genuine, typed empty state — no DEHú notifications on the isolated identity), persisted `snapshot_id`, round-tripped through `list`/`latest`.
- `justificante list`: `count=0`. `justificante pull --modelo 303 --year 2024 --period 1T` refused twice, even after populating the expedientes tree for the exact `expediente_id` it named, with `REFUSED_APPLICATION_LIVE_INPUT`: "declaration for modelo='303' period='1T' references expediente '202430313520389Q' which is not present in the expedientes tree." Root-caused this to `_default_justificante_expedientes` in `_justificante.py`'s caller (`_default_justificante_capture` path in `application/live/__init__.py`, ~line 464): it calls `expedientes_provider(session, settings, modelo=modelo)` with **no `year` parameter**, so it live-refetches an unscoped procedure tree via `walk_expedientes_tree` rather than reusing the year-scoped tree `expedientes pull` had just persisted — the unscoped live refetch does not return the 2024 expediente. This is a real, reproducible defect independent of any local caching; it blocked every justificante-pull attempt in this sweep.
- `iva-wallet pull --year 2024 --period 1T` refused with `FAIL_SEDE_PARSE` / `external_shape_changed`: "IVA wallet summary total 63.79 does not equal the sum of Cuota Disponible rows 446.40; refusing to persist an inconsistent wallet observation." The refusal is the correct fail-closed behaviour (no partial/inconsistent wallet state was persisted), but the underlying parser interpretation looks wrong: `iva-wallet history` (built from the already-persisted filed-declaration observations, not the live wallet page) shows the 2023 4T `generated_amount=63.79` and a running `available_end_amount=446.40` at that same point — i.e. the two numbers the live parser is comparing are plausibly a single period's generated amount versus a cumulative available-balance table, not two views of the same total. Worth a parser-selector review; not something to fix inside this sweep.
- `verify nif-iva ESA39000013` (public CIF, not personal data) refused with a typed error: "IXVI form requires AEAT auth tier above cl@ve-movil; landed on AEAT 4033 page (failure_mode=auth_gate_detected)" — an honest, typed access-tier refusal, not a defect.
- `verify tgvi A39000013` (public CIF) succeeded: `verdict=valid`, persisted and round-tripped through `list`/`latest`.
- `borrador 100 list`: `count=0` (no persisted M100 borrador snapshots — expected, since this sweep never pulled one).
- `portals list`: `count=41`, a local read-only catalogue, unaffected by the live session.

## Notes

- Two prior `config auth login --provider clave_movil --fresh --reset-lock` attempts (diagnostics `20260715T082112Z`, `20260715T082335Z`) timed out after 120s with no phone approval reaching AEAT before the operator confirmed they were actively watching; the third attempt (diagnostic implicit in the success payload) succeeded immediately once the operator was standing by. This reconfirms the established finding that the approval window is the scarce resource, not the mechanism.
- The `justificante pull` and `iva-wallet pull` defects above are genuine, reproducible findings from this sweep, not blockers to closing this step (which asks only that the sweep be *run* and *recorded*, one record per command group) — they are flagged here for a follow-up fix, not silently absorbed.
- Redacted per the sweep convention: no raw NIE/NIF, Cl@ve support number, passphrase, or session token appears above.
