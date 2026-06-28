---
tags:
  - '#research'
  - '#live-parity-oracle'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - '[[2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr]]'
  - '[[2026-05-07-aeat-vies-auth-tier-research]]'
  - '[[2026-05-06-cross-reference-oracle-binding-adr]]'
  - '[[2026-05-06-oracle-environment-consistency-adr]]'
  - '[[2026-05-06-oracle-surface-compatibility-adr]]'
---

# `groi-oracle-delivery-checklist` research: residual work to fully deliver the GROI Spanish-ROI oracle slice

## Context

The GROI Spanish-ROI consult oracle is end-to-end functional in HEAD
as of 2026-05-07. Live probing confirms:

- `GroiSedeDriver` navigates the AEAT GROI form via authenticated
  cl@ve-movil BrowserSession and returns
  `{"A28015865": "valid", "B00000001": "invalid"}` for known inputs.
- `GroiOracle.verify_payload` returns `ParityResult(verdict="match")`
  when expected and observed agree, `verdict="mismatch"` when they
  disagree, `verdict="blocked"` when guard preflight rejects.
- `aeat app registry audit-oracles` registers both
  `aeat-nif-iva-checker` (auth-gated; raises auth-gate diagnostic)
  and `aeat-groi-spanish-roi-checker` (live-verified) in the
  catalogue and reports zero binding failures against the current
  registry.
- Read-only mandate is enforced at four layers (pytest collection,
  guard, policy forbidden_actions, driver form-action attribute
  check).

This research note enumerates the residual work to "fully deliver"
the slice.

## Residual delivery items

### 1. Bind GROI to a real modelo cross-reference

**Status**: not started. The audit pass currently has nothing to
audit because no modelo declares `oracle_id =
"aeat-groi-spanish-roi-checker"` on any cross-reference.

**Target**: modelo 349 (recapitulative declaration of intra-community
operations). Spanish counterparties on modelo 349 must be ROI-
registered; GROI is the surface that confirms it.

**Required cross-reference shape**:

- `id`: e.g., `modelo-349-groi-spanish-counterparty-check`.
- `surface`: `public_read_surface` (the only surface the
  surface-kind compatibility table pairs with `vat_id_check`).
- `oracle_id`: `"aeat-groi-spanish-roi-checker"`.
- `allowed_hosts`: `("www2.agenciatributaria.gob.es",)` —
  matches GROI's host.
- `forbidden_actions`: must include the canonical
  `AEAT_WRITE_FORBIDDEN_ACTIONS` set (the 8 write-class action
  labels). Per the read-only mandate hardening, NO cross-reference
  may ship with empty forbidden_actions.
- `legal_refs`, `source_refs`: match what AEAT publishes about the
  ROI registry consult procedure (orden + sede source).
- `synthetic_data_allowed`: `true` (the form accepts arbitrary NIFs;
  no live filing data is involved).
- `requires_authentication`: `true` (cl@ve-movil empirically
  required).
- `requires_aeat_authorization`: `false` (no separate AEAT
  authorisation beyond standard cl@ve-movil registration).

**Risk**: modelo TOMLs are heavily edited by parallel agents; a
cross-reference addition could collide. Coordinate via the
project-level delegation thread or do the edit inside a focused
slice with quality gates.

### 2. Probe certificate auth against IXVI

**Status**: research note `2026-05-07-aeat-vies-auth-tier-research`
captures the protocol; not executed yet.

**Required setup**:

1. User configures certificate provider:
   `uv run --no-sync aeat setup auth configure --provider certificate --file <p12_path>`
2. User authenticates: `uv run --no-sync aeat setup auth login --fresh`
3. Re-run `.tmp/probe_aeat_vies_surfaces.py`.

**Expected outcomes**:

- IXVI unlocks under certificate -> capture form HTML, replace
  `_nif_iva_check.py` fallback selector lists with verified
  specific selectors. The IXVI oracle becomes runnable.
- IXVI still 4033s under certificate -> hypothesis (2): caller's
  NIF must itself be ROI-registered (modelo 036/037 box 582).
  Document outcome; pivot to EU Commission's public VIES at
  ec.europa.eu (separate adapter; requires expanding host-pinning
  allow-list).

### 3. CI / pre-deploy gate on `audit-oracles`

**Status**: command exists; not gated in CI.

**Target**: a CI step that runs `aeat app registry audit-oracles`
and fails the build on non-zero exit code. Wires the boot-time
audit into the project's continuous-integration flow so a developer
who mis-spells an oracle_id, or binds a production cross-reference
to a test-environment-only oracle, sees the failure on PR review
instead of deployment.

### 4. Drift-detector schedule

**Status**: `test_groi_check_live.py` has 3 form-shape drift tests
gated on `AEAT_LIVE_TESTS_ENABLED=1`; not on a schedule.

**Target**: a periodic CI run (weekly) that authenticates with the
project's cl@ve-movil session and runs the live drift suite. AEAT
silently changing the form shape is detected within a week instead
of when a developer next runs the tests manually.

**Risk**: AEAT auth requires phone-side approval (cl@ve-movil push)
or certificate. Headless CI cannot trigger phone push; certificate
in CI carries its own security implications.

**Mitigation**: CI runs only the drift detector (not the full live
oracle Protocol), uses a dedicated AEAT identity (separate cl@ve
or certificate), and the secret rotation/storage follows the
project's existing `.tokens/` storage-state convention.

### 5. Documentation: how to bind an oracle to a modelo

**Status**: scattered across the cross-reference-oracle-binding
ADR, the surface-compatibility ADR, and the auth-tier research
note. No single how-to.

**Target**: a focused how-to under `.vault/reference/` (or similar)
that walks through:

1. Pick an oracle id from the catalogue.
2. Confirm the surface-kind matches the cross-reference's surface
   per the compatibility table.
3. Add the cross-reference declaration with the required fields
   (legal_refs, source_refs, hosts, forbidden_actions).
4. Run `aeat app registry verify` and `aeat app registry audit-oracles`
   to confirm validity.
5. Write a `live_read` regression test that exercises the binding
   end-to-end.

Item (5) deferred — see "delivery checklist" in the next section.

## Delivery checklist (in order)

1. ☐ Bind GROI to modelo 349 cross-reference (item 1 above).
2. ☐ Probe certificate auth for IXVI (item 2 above).
3. ☐ Wire `audit-oracles` into CI (item 3).
4. ☐ Schedule live drift sweep (item 4).
5. ☐ Document oracle-binding how-to (item 5).

Each item is independently shippable; (1) is the highest-value
single slice because it gives the audit pass a real positive case
to verify.

## What's already delivered (HEAD as of 2026-05-07)

- ✅ `_groi_oracle.py` — Protocol-conforming oracle wrapper, replay
  driver, register_default helper. 38 offline tests passing.
- ✅ `_groi_check.py` — live BrowserSession driver with verified
  selectors + verdict markers + form-action read-only guard. 19
  offline tests passing.
- ✅ `test_groi_oracle_live.py` — 3 end-to-end Protocol tests
  passing against AEAT.
- ✅ `test_groi_check_live.py` — 3 form-shape drift tests passing
  against AEAT.
- ✅ Read-only mandate enforced at 4 layers (collection, guard,
  policy, driver form-action attribute).
- ✅ `audit-oracles` CLI command — registers GROI + NIF-IVA, runs
  catalogue audit, exits non-zero on failure.
- ✅ ADR `2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr` —
  the surface-split decision.
- ✅ Research `2026-05-07-aeat-vies-auth-tier-research` — auth-tier
  hypotheses + cert probe protocol.
- ✅ Corpus fixtures `corpus/aeat_official/groi_response_samples/`
  — verbatim AEAT response text for verdict-parser regression.
