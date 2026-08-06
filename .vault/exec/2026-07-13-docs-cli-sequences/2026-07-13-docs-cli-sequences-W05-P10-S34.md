---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:f415091d72d67f7189dfb1d83533d6670534f1b484e04576cc3aca2bd96f84f1'
step_id: 'S34'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Author the first greenfield tutorial page with real cli-sequence directives and generate its committed goldens via the refresh CLI

## Scope

- `docs/tutorials`

## Description

- Author the greenfield tutorial `docs/how-to/first-quarterly-filing.md`: a story-driven first-filing walk-through in singular imperative voice with two real `cli-sequence` directives and inline-only command mentions (no plain executable fences, per the enrolled-page tier).
- Sequence `import-quarter-transactions`: a visible `ledger import ... --provider csv` frame reading the synthetic fixture, terminating in an `@result` `ledger list` inspection asserting `result.total == 2`.
- Sequence `modelo-130-first-quarter`: seeded by `autonomo-irpf-2026`, a visible create then calculate (capturing `work_unit_id` and `calculation_revision_id`), terminating in an `@result` `work verify` asserting `result.granted_verificado_completo == true` and `exit_code == 0`.
- Generate both committed goldens with `python -m dev.docs.sequences refresh --page how-to/first-quarterly-filing` (the only sanctioned writer); never hand-edit.
- Wire the page into the nav: a toctree entry after Quickstart in `docs/index.md` and a discoverability card in `docs/how-to/index.md`.

## Outcome

The page enrolls two executed sequences whose committed goldens carry `granted_verificado_completo: true` and `total: 2`. `check --page how-to/first-quarterly-filing` is clean.

Placement deviation (recorded per the dispatch brief): ADR ruling D7 places the first enrolled pages under `docs/tutorials/`, but that tree does not exist at HEAD, so the page lands under `docs/how-to/` per the brief's binding fallback. A future move to `docs/tutorials/first-quarterly-filing.md` MUST move the golden directory with it: rename `docs/_sequences/how-to/first-quarterly-filing/` to `docs/_sequences/tutorials/first-quarterly-filing/` (the golden `page` key is the docname-style path), update the two `docs/index.md` / `docs/how-to/index.md` toctree references, then re-run the refresh CLI to confirm the goldens still match under the new page path.

## Notes

- The `@result` asserts the verified status (`granted_verificado_completo`); a specific casilla value could not be asserted on the result frame because the `@expect` json-path grammar (`[A-Za-z_][A-Za-z0-9_]*` segments) cannot address numeric casilla keys such as `03`, and the verify envelope carries no `casilla_values`. The casilla figures (net yield `500.00`, instalment `100.00`) are shown in the visible calculate frame output and narrated.
- The calculate golden is large (~1000 lines) because it captures the full calculate envelope (20 casillas, observations, result summary, deadline); this is the pre-mask capture-raw contract, not bloat.
