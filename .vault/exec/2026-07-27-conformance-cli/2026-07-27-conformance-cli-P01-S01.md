---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S01'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The add the RevisionReviewStatus StrEnum (pending_review, agent_reviewed, operator_reviewed) to the core closed-value-set surface and export it through the core facade and ## Scope

- `src/cadrumo/core` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the RevisionReviewStatus StrEnum (pending_review, agent_reviewed, operator_reviewed) to the core closed-value-set surface and export it through the core facade

## Scope

- `src/cadrumo/core`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Add `src/cadrumo/core/_revision_review.py` declaring the `RevisionReviewStatus` StrEnum with members `pending_review`, `agent_reviewed`, and `operator_reviewed`.
- Derive the companion `REVIEWED_REVISION_REVIEW_STATUSES` frozenset from the member list rather than hand-listing it, so a future reviewed member enrolls automatically in the reviewed-requires-a-reviewer invariant.
- Export both symbols eagerly through the core facade `__init__` import block and `__all__`, and name them in the facade module docstring beside the sibling closed value sets.
- Regenerate the API reference stubs with the apidocs scaffold verb and stage only the two stubs naming this module.

## Outcome

The core layer now owns a closed, three-state review-provenance vocabulary for
modelo registry revisions, with `pending_review` as the fail-closed member.
Nothing consumes it yet; the registry schema binding lands in the next Step.

Modified files: `src/cadrumo/core/_revision_review.py` (new),
`src/cadrumo/core/__init__.py`, `docs/api/cadrumo.core._revision_review.rst`
(new), `docs/api/cadrumo.core.rst`.

Naming decision, recorded because the namespace is crowded. Three same-shaped
vocabularies already ship and none can carry this subject. `ReviewStatus` in
`src/cadrumo/domain/calculations/registry/_schema_base.py` is the degenerate
`Literal["reviewed"]` scoped to the legal catalogue rows; it has no unreviewed
member at all, so it structurally cannot express the pending state this feature
exists to make visible, and widening it would silently change the assertion
carried by every legal-reference, source-reference, and legal-parameter row.
`LedgerReviewStatus`, `InvoiceReviewStatus`, and `DeclaracionReviewStatus` in
`src/cadrumo/application/review/_filter.py` are CLI filter-value catalogues over
a taxpayer's own bucket rows: per-taxpayer runtime data, not the authorship of a
shipped registry schema, and they sit outward of the registry domain that needs
this set. A fourth, revision-scoped enum in `core` is therefore the right home,
and `core` specifically because the architecture rule requires closed value sets
to be StrEnums there so the registry domain can consume them without depending
outward.

Verification. `ruff format` reported both files unchanged and `ruff check`
reported `All checks passed!`. The project type checkers were both clean:
`ty check` reported `All checks passed!` and `pyright` reported
`0 errors, 0 warnings, 0 informations`. A facade smoke import through
`cadrumo.core` resolved both symbols and confirmed the member values and the
derived reviewed set. The core suite was run with an explicit empty marker
selector, since this repo's default selector is
`-m 'unit and not external_tool and not os_keychain'` and would otherwise
under-collect: `1 failed, 427 passed in 92.96s`. The docstring core-struct links
gate ran under its `docs` marker: `3 passed in 9.08s`. The apidocs drift check
reported exactly one missing stub for this module before the scaffold and the
scaffold changed only the two stubs naming it.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Semantic discovery ran under an explicit operator waiver: the code index is
broken and the service is stopped under a hands-off order, so grounding used
`rg` concept sweeps plus whole-file reads of the epicenter and its nearest
analogues. The concept was swept under several plausible names (review status,
provenance, stamp, governance, signoff, attestation, curation) and every core
StrEnum was enumerated before naming this one, which is how the three existing
review-status vocabularies were found and read in full rather than shadowed.

The single core-suite failure is not owned by this Step. The repo-wide period
combined-string gate `test_period_combined_string_gate` flags findings only in
`src/cadrumo/adapters/inbound/sanitizer/fixtures.py` and neighbouring
declaracion tests. That file carries no working-tree modification and last
landed in a peer commit, so the gate is red at HEAD independently of this
change; no file touched here appears in its findings.

The one-way boundary was respected: the new module is pure stdlib and imports
nothing, so it adds no layer edge and no function-local import that would move
the lazy-import ratchet.
