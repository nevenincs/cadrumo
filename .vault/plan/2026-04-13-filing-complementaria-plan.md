---
tags:
  - "#plan"
  - "#filing-complementaria"
date: 2026-04-13
modified: '2026-04-13'
title: Filing Complementaria / Amendment Engine — Plan
related:
  - "[[2026-04-13-filing-complementaria-research]]"
  - "[[2026-04-13-filing-complementaria-adr]]"
issue: wgergely/aeat#93
---

# implementation plan: filing complementaria

## scope

Deliver the amendment engine for issue #93 as an additive extension to the
existing filing and submission stack:

- strict amendment models in `aeat.application.filing`
- delta computation against a prior submitted filing
- legality gates for complementaria vs sustitutiva vs post-2024 IVA
  rectificativa
- amendment persistence on the existing file-backed substrate
- CLI build and submit commands under `aeat filing complementaria`
- unit coverage plus one live-gated dry-run amendment submission path
- mandatory execution records and final code review artifacts

No changes to `aeat.adapters.outbound.aeat.auth`, `aeat.adapters.outbound.aeat.browser`, `aeat.status`, or Track B audit
internals.

## phases

### phase-1 — amendment schema and builder

- Add `src/aeat/application/filing/_complementaria.py` with:
  `AmendmentKind`, `CasillaChange`, `CasillaDelta`, `FilingAmendment`, and the
  builder helpers.
- Export the public amendment surface from `src/aeat/application/filing/__init__.py`.
- Reuse the existing original-draft builders to recompute new absolute casilla
  values, then derive the delta against a prior filing.
- Encode the per-model legality rules:
  `130 -> complementaria`, `390 -> sustitutiva`, `303 -> legacy-only before the
  2024 IVA rectificativa cutover`.

### phase-2 — prior-filing lookup and file-backed persistence

- Add a small amendment-store layer on top of the existing persisted filing and
  submission JSON records.
- Resolve the original justificante / CSV / model / period from the prior
  `SubmittedFiling`.
- Persist every built amendment as its own strict JSON audit record, with a
  stable identifier and a clear link to the source filing.
- Keep any optional audit callback behind a local Protocol seam so issue #82 is
  not hard-imported.

### phase-3 — submission engine extension

- Extend `aeat.adapters.outbound.aeat.export` with:
  `AmendmentSubmissionResult` and
  `SubmissionEngine.submit_amendment(amendment, dry_run=True)`.
- Route amendment submission through the existing `Modelo130Submitter` transport
  for supported paths.
- Detect and surface the current transport gap when the underlying submitter
  cannot safely set the AEAT complementaria/sustitutiva controls.
- Preserve the current live-safety contract:
  dry-run by default, `dry_run=False` only with the explicit live gate and
  manual confirmation semantics already used by the repo.

### phase-4 — cli surface

- Extend `aeat filing` with a nested `complementaria` app:
  `build <modelo> <period> <delta-json>` and
  `submit <amendment-id>`.
- Make `submit` dry-run by default and use `--live` for the explicit live path.
- Reuse the repo's existing confirmation style for real submissions.
- Print amendment details in a human-reviewable way before dispatch.

### phase-5 — tests and verification

- Add `src/aeat/application/filing/test_complementaria.py` for:
  delta computation,
  legal monotonicity,
  synthetic `130` / `303` / `390` fixtures,
  persistence round-trips.
- Add or extend submission tests for the amendment path and the typed transport
  gap outcome.
- Add `src/aeat/application/filing/test_live_complementaria.py` with
  `@pytest.mark.live`, gated by `aeat.entrypoints.cli._live.requires_live_enabled()`, and
  keep it dry-run only unless the repo's live gate is explicitly opened.
- Run `just lint`, `just typecheck`, `just test`, and `just hooks`.

### phase-6 — execution records and review

- Persist execution step notes under
  `.vault/exec/2026-04-13-filing-complementaria/`.
- Run `vaultspec-code-review` and persist the resulting audit file under
  `.vault/audit/`.
- Address any findings, rerun the four gates, and update the summary record.

## parallelization

- The schema/builder work and the CLI/persistence plumbing can proceed in
  parallel once the amendment identity and persistence shape are fixed.
- Transport work must wait for the amendment record shape because the submitter
  path depends on the final amendment metadata.
- Verification should be staged: unit coverage first, live-gated dry-run last.

## verification

- Unit tests prove the builder computes the expected delta against real existing
  formulas instead of hard-coded amendment arithmetic.
- `303` tests prove the date cutover is enforced with exact period boundaries.
- Persistence round-trips prove the amendment records remain strict pydantic v2
  and immutable.
- Submission tests prove dry-run remains the default and live mode cannot be
  reached accidentally.
- The four repo gates must pass on Windows exactly as the issue requires.

## plan review

**Outcome:** APPROVED (self-review, no human in the loop per the handover
contract).

**Review notes:** The plan stays inside the feature boundary by extending the
already-merged filing and submission packages instead of pushing new work into
the sibling certificate, browser, or AEAT status branches. It also tracks the
legal split discovered in research: `390` is sustitutiva, not complementaria,
and `303` needs a date gate because the legally correct path changed starting
with monthly `2024-09` and quarterly `2024Q3`. The referenced "SLOT A1"
14-bullet convention list was not present in the fetched issue context, so the
plan uses the local checked-in conventions from `AGENTS.md`, `.codex/rules`,
and the issue's explicit scope notes as the operative constraints.
