---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:40a757efa749f70dd632dcbdb1d5302a265d7f56f43137000606dfed94ef1b9c'
step_id: 'S199'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`

## Scope

- `src/aeat/application/calculations/_binding_prefill.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.application.calculations` and `aeat.domain.calculations` module, rewriting every cross-package private import onto the owning package's promoted top-level facade, plus a hand-rewrite of the remaining `_parse_iso8601_date` call site in `application/calculations/_row_set_assembly.py` onto the public `parse_iso8601_date` name. This record anchors and covers Phases `W02.P43` and `W02.P44` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 17 files as one atomic explicit-pathspec commit.

## Outcome

17 files rewritten and committed (commit `bd7d5abdb`, `refactor(calculations): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps across `W02.P43` and `W02.P44` are covered by this one record and this one commit, batched per the Wave dispatch brief. `CasillaFieldKind` (the `W01.P30.S43` promotion target) was investigated and reverted: `aeat.domain.calculations.__init__` is a hard-gated namespace container (`test_domain_calculations_init_has_no_explicit_imports` in `src/aeat/tests/test_wizard_locale_and_typed_payloads.py` asserts zero import statements), so `CasillaFieldKind` stays reachable only through `aeat.domain.calculations.registry` or the direct private submodule for its sole documented cycle-avoidance consumer (`domain/user_profile/_registry_contract.py`, left untouched — it carries unrelated concurrent peer WIP). Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
