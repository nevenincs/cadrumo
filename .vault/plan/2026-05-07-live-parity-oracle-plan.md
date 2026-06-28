---
tags:
  - '#plan'
  - '#live-parity-oracle'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr]]"
  - "[[2026-05-07-groi-oracle-delivery-checklist-research]]"
  - "[[2026-05-06-oracle-surface-compatibility-adr]]"
  - "[[2026-05-06-cross-reference-oracle-binding-adr]]"
  - "[[2026-05-06-oracle-environment-consistency-adr]]"
  - "[[2026-05-06-aeat-nif-iva-checker-adapter-adr]]"
  - "[[2026-05-07-aeat-vies-auth-tier-research]]"
---



# `live-parity-oracle` `groi-oracle-completion-plan` plan

Completes the GROI Spanish-ROI oracle slice and lands the residual
items the delivery-checklist research catalogued. Six phases; each
phase carries five mechanical per-slice checks (tautological test
pruning, AEAT legal grounding, pydantic strict-typed enrollment,
code-duplication check, code review) the executing agent ticks off
and the next agent verifies before claiming the phase complete.

## Proposed Changes

The GROI Spanish-ROI oracle is end-to-end functional under
cl@ve-movil authentication: live driver, registry oracle, replay
driver, audit-oracles CLI command, read-only mandate enforced at
four layers, dependency-chain test grounded in AEAT's authoritative
ROI registry. The remaining work falls into six slices the executing
agent runs in order:

- Phase 1 lands the surface-taxonomy ADR amendment that the empirical
  GROI semantics surfaced (authentication required + synthetic VAT-IDs
  accepted + POST submission, none of which fits the existing
  `public_read_surface` / `authenticated_read_surface` rules in the
  cross-reference schema validator).
- Phase 2 binds GROI to a real modelo 349 cross-reference using the
  amended taxonomy.
- Phase 3 wires `audit-oracles` into CI so a binding mismatch fails
  the build.
- Phase 4 schedules the live drift detector to run weekly under
  pre-existing cl@ve-movil credentials so AEAT silently changing the
  GROI form shape surfaces within seven days.
- Phase 5 authors a focused how-to under `.vault/reference/` for any
  future agent binding any oracle to any cross-reference.
- Phase 6 probes certificate-auth against IXVI to determine whether
  the foreign-EU surface is reachable under a stronger auth tier than
  cl@ve-movil. Outcome documented; if certificate also fails to
  unlock, the IXVI surface is dropped or the oracle pivots to the EU
  Commission's public VIES at ec.europa.eu.

Per-slice mechanical checks (apply to every phase):

- **TAUT** Tautological test pruning: every new test must verify
  against external authority (AEAT response, AEAT-published
  legal/source citation, real-world public fact). Hand-computed
  expected values fail the check.
- **LEGAL** AEAT calc and legal grounding: every legal_ref / source_ref
  added must point at a real AEAT publication or BOE order; the
  citation's evidence_tier must match the cross-reference's tier
  contract.
- **PYDANTIC** Strict-typed enrollment: any new boundary-crossing
  data structure must be a strict frozen pydantic v2 model; the
  registry's existing strict-frozen base classes are reused.
- **DUP** Code duplication check: any new module that mirrors an
  existing pattern (e.g., a sibling adapter) imports shared helpers
  rather than re-declaring; greps confirm zero literal-text
  duplication of helper bodies.
- **REVIEW** Code review: ruff format + ruff check + ty check pass on
  every changed file; pre-existing live and offline tests still pass;
  the per-phase verification block below confirms the slice's mission.

## Tasks

- **Phase 1 — Surface-taxonomy ADR amendment**

  1. ☐ Author ADR `2026-05-07-authenticated-synthetic-surface-taxonomy-adr.md`
     under `.vault/adr/` via `vault add adr`. The ADR documents the
     empirical finding (GROI requires cl@ve-movil + accepts synthetic
     NIFs + POST-submits) and proposes either (a) extending
     `LiveCrossReferenceDecision`'s surface enum with a new value
     such as `authenticated_simulator`, or (b) relaxing the existing
     `authenticated_read_surface` validator to allow synthetic NIFs
     and POST when the cross-reference's oracle's `surface_kind` is
     `vat_id_check`. Choose (b) if the relaxation is auditable; (a)
     if (b) introduces ambiguity. Decision must be a single,
     reasoned conclusion; no "either-or" left in the body.
  1. ☐ Implement the chosen schema change in `_schema.py`'s
     `LiveCrossReferenceDecision._validate_cross_reference`. Tests
     in `test_registry_schema.py` must continue to pass for every
     existing cross-reference shape.
  1. ☐ Extend `_live_parity._COMPATIBLE_SURFACE_PAIRS` to include
     the new pair (e.g., `("authenticated_simulator", "vat_id_check")`).
     Update the surface-compatibility ADR's allow-list table to
     reflect the addition.
  1. ☐ **TAUT**: any new test exercises a real AEAT response or a
     structural / error-path contract; no hand-computed Decimal
     verdicts.
  1. ☐ **LEGAL**: no new legal_refs needed (this slice is schema
     mechanics); confirm no existing cross-reference's tier contract
     regresses.
  1. ☐ **PYDANTIC**: the schema change re-uses
     `LiveCrossReferenceDecision`'s existing strict-frozen base; no
     new public model.
  1. ☐ **DUP**: ruff and ty pass on `_schema.py` and
     `_live_parity.py`; grep confirms the new surface kind is
     declared in exactly one place.
  1. ☐ **REVIEW**: full test sweep pre-commit (`uv run --no-sync
     pytest src/aeat/domain/calculations/registry --no-header -q`)
     reports all green.

- **Phase 2 — Bind GROI to modelo 349 cross-reference**

  1. ☐ Add a new `aeat-modelo-349-groi-procedure` source citation in
     `registry/aeat/legal/iva.toml` with a corpus_path pointing at a
     fresh capture of AEAT's GROI procedure documentation (download
     and commit the HTML under
     `corpus/aeat_official/instructions/modelo_349/files/`). The
     source's `evidence_tier` is `executable_parity_evidence` because
     the GROI servlet is a callable verification surface.
  1. ☐ Add a `[[revisions."2020-y-siguientes".live_cross_references]]`
     entry to `registry/aeat/modelos/349.toml` with id
     `modelo-349-groi-spanish-counterparty-check`, surface set to the
     value chosen in Phase 1, oracle_id `aeat-groi-spanish-roi-checker`,
     allowed_hosts `("www2.agenciatributaria.gob.es",)`,
     forbidden_actions equal to the imported
     `AEAT_WRITE_FORBIDDEN_ACTIONS` set, and source_refs referencing
     the new GROI procedure source plus the existing modelo 349
     source.
  1. ☐ Run `uv run --no-sync aeat app registry verify` and confirm
     no validation failure.
  1. ☐ Run `uv run --no-sync aeat app registry audit-oracles --json`
     and confirm `failure_count == 0` with the new cross-reference
     declared.
  1. ☐ Promote the existing `test_groi_dependency_chain_live.py` to
     resolve through the registry-data cross-reference (instead of
     constructing `RemoteStateGuardPolicy` directly) and confirm
     the live tests still pass.
  1. ☐ **TAUT**: the new live test still queries AEAT's authoritative
     response for the registered Telefónica NIF; expected verdicts
     come from public ROI-registration ground truth, not analyst
     arithmetic.
  1. ☐ **LEGAL**: the new source's corpus_path SHA256 matches the
     captured HTML; the source's `applies_from` is the date AEAT's
     GROI procedure went live; the source links to a stable AEAT URL.
  1. ☐ **PYDANTIC**: the new TOML entry parses through the existing
     `LiveCrossReferenceDecision` strict-frozen model; no new model
     declared.
  1. ☐ **DUP**: the new cross-reference's forbidden_actions imports
     `AEAT_WRITE_FORBIDDEN_ACTIONS` rather than re-listing the eight
     write-class action labels; grep confirms the canonical set
     stays centralised in `_remote_state_guard.py`.
  1. ☐ **REVIEW**: ruff + ty + pytest all clean across the modified
     surface; the dependency-chain live test passes against AEAT.

- **Phase 3 — Wire `audit-oracles` into CI as a build gate**

  1. ☐ Add a `audit-oracles` step to the project's CI workflow
     (`.github/workflows/ci.yml`) that runs
     `uv run --no-sync aeat app registry audit-oracles --json`
     after the registry-validation step.
  1. ☐ The step's exit code must fail the workflow on any binding
     mismatch.
  1. ☐ Document the failure mode in the CI section of the workflow
     (clear remediation: "an oracle_id binding mismatch was detected;
     run `aeat app registry audit-oracles` locally and fix the
     binding").
  1. ☐ **TAUT**: the audit command itself is non-tautological — it
     compares declared bindings against the catalogue at runtime, no
     hand-computed expected.
  1. ☐ **LEGAL**: no legal_refs touched.
  1. ☐ **PYDANTIC**: no new models.
  1. ☐ **DUP**: the CI step calls the canonical CLI command rather
     than re-implementing the audit; grep confirms zero
     re-implementation in the workflow file.
  1. ☐ **REVIEW**: opening a draft PR triggers the workflow; the
     audit step appears in the run; passing run shows a green check;
     deliberately mis-binding an oracle_id locally and pushing
     produces a failing run with the expected error message.

- **Phase 4 — Schedule live drift detector weekly**

  1. ☐ Add a `.github/workflows/aeat-drift-detector.yml` workflow
     scheduled weekly (Sunday off-minute, e.g., `0 7 * * 0`) that
     authenticates with the project's cl@ve-movil session via
     stored secrets and runs the
     `test_groi_check_live.py` + `test_groi_oracle_live.py` suites.
  1. ☐ Failure of any drift test creates a GitHub issue (via the
     workflow's existing `create-issue-on-failure` action or
     equivalent) tagged `aeat-drift` so the maintainer is notified
     within hours of AEAT changing the form shape.
  1. ☐ **TAUT**: the drift tests already query AEAT's authoritative
     response and assert the form shape + verdict-text shape stay
     compatible; non-tautological by construction.
  1. ☐ **LEGAL**: cl@ve-movil credentials are personal — must use a
     dedicated secrets account, not a shared one. Document the
     secret-management procedure in the workflow's README block.
  1. ☐ **PYDANTIC**: no new models.
  1. ☐ **DUP**: the workflow imports the project's existing live-test
     justfile target; grep confirms zero duplication of the live-test
     env-setup logic.
  1. ☐ **REVIEW**: the workflow runs successfully on the next
     Sunday off-minute; the issue-on-failure path is exercised once
     manually (revert to a known-bad selector, push, confirm issue
     created, restore selector) before declaring the loop closed.

- **Phase 5 — Author oracle-binding how-to under `.vault/reference/`**

  1. ☐ Scaffold the reference document via
     `vault add reference --feature live-parity-oracle --title "binding-an-oracle-to-a-cross-reference"`.
  1. ☐ Walk a future agent through the binding procedure: pick
     oracle id from catalogue, confirm surface-kind compatibility,
     add cross-reference declaration with required fields, run
     `aeat app registry verify` and `aeat app registry audit-oracles`,
     write a `live_read` regression test grounded in real AEAT data.
  1. ☐ Cite every relevant ADR via wiki-links in the related: field;
     no in-body wiki-links per project conventions.
  1. ☐ **TAUT**: the how-to specifically documents the
     no-tautology mandate as part of step 5 (writing the regression
     test): "the test must query an external authority — AEAT
     response, public registry, BOE-published worked example —
     not a hand-computed Decimal".
  1. ☐ **LEGAL**: the how-to includes a section "choosing legal_refs
     and source_refs" that points at the registry's existing
     catalogue files and explains how to add new entries with proper
     evidence_tier.
  1. ☐ **PYDANTIC**: no new models.
  1. ☐ **DUP**: the how-to references existing ADR / research
     artefacts rather than restating their contents.
  1. ☐ **REVIEW**: the document parses through the vault's wiki-link
     resolver (`vault check all`); a fresh agent reading only the
     how-to can complete a binding end-to-end without consulting
     other artefacts.

- **Phase 6 — IXVI certificate-auth probe**

  1. ☐ User configures certificate provider via
     `aeat setup auth configure --provider certificate --file <p12>`.
  1. ☐ User authenticates via `aeat setup auth login --fresh`.
  1. ☐ Run `.tmp/probe_aeat_vies_surfaces.py` under the certificate
     session.
  1. ☐ Document the outcome in the existing
     `2026-05-07-aeat-vies-auth-tier-research.md` note: either
     certificate unlocks IXVI (proceed to capture form HTML and
     replace fallback selectors) or it doesn't (advance to
     hypothesis 2: caller must be ROI-registered themselves).
  1. ☐ If certificate unlocks IXVI: replace the fallback selector
     lists in `_nif_iva_check.py` with verified specific selectors
     captured live; add a parametrised regression test mirroring
     the GROI corpus-fixture pattern.
  1. ☐ If certificate doesn't unlock IXVI: open a follow-up plan
     for either (a) ROI-registered probe or (b) pivot to EU public
     VIES at ec.europa.eu.
  1. ☐ **TAUT**: any new test in this phase queries AEAT's actual
     IXVI response and asserts the response shape, not a hand-computed
     verdict.
  1. ☐ **LEGAL**: any new source_ref points at AEAT's published VIES
     procedure documentation with proper evidence_tier.
  1. ☐ **PYDANTIC**: re-uses `AeatNifIvaObservation` and the existing
     IXVI Protocol; no new models.
  1. ☐ **DUP**: the IXVI driver reuses the
     `_browser_stage` runner factory and shared sede error mapping;
     grep confirms no duplication of helper bodies.
  1. ☐ **REVIEW**: ruff + ty + pytest clean; the IXVI live test
     either passes (cert unlocked) or fails with the
     `auth_gate_detected` diagnostic naming the next hypothesis.

## Parallelization

Phases 1 and 6 are independent. Phase 1 unblocks Phase 2 (modelo 349
needs the surface-taxonomy decision). Phases 3, 4, 5 are independent
of one another and of Phases 1-2; they can ship in any order once
the audit-oracles command exists in HEAD (it does).

A single autonomous executing agent should run Phase 1 first, then
Phase 2, then Phases 3 / 4 / 5 in whatever order makes sense, then
Phase 6 when the user provides certificate credentials. Two
concurrent agents can split (Phase 1 → Phase 2) on one rail and
(Phase 3 → Phase 4 → Phase 5) on the other; they do not conflict.

## Verification

Mission success when, simultaneously:

- `aeat app registry verify` and `aeat app registry audit-oracles`
  both return exit 0 against committed registry data, with the
  modelo 349 GROI cross-reference declared and resolving.
- The `test_groi_dependency_chain_live.py` suite passes against
  live AEAT through the registry-data cross-reference (not the
  in-memory `RemoteStateGuardPolicy` shortcut currently used).
- The CI build fails on any deliberate oracle_id mismatch and
  passes on a clean registry.
- The weekly drift workflow runs and creates issues on form-shape
  changes (verified once via deliberate selector regression).
- A fresh agent reading only `.vault/reference/...binding-an-oracle...md`
  can land an oracle binding end-to-end on a different modelo
  without escalating.
- The IXVI auth-tier question is resolved one way or another:
  either certificate unlocks the surface and the live tests pass,
  or it doesn't and the research note documents the next-tier
  hypothesis with a follow-up plan filed.

Honest test caveat: every live test depends on AEAT staying online
and responding within timeout budgets. Drift detector creates issues
on AEAT outages too — that is a feature (escalates AEAT downtime
that affects production filing) not a bug. CI gating uses offline
contract tests + the audit-oracles command; live tests are
opt-in (`AEAT_LIVE_TESTS_ENABLED=1`) and don't gate the build.
