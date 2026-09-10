---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b892e1c8e619ba66b0f814ac46123cde2b4b00776222d1fb99dc71b7bd01f5f7'
step_id: 'S24'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Add the legal-reference period-correctness gate: a casilla's citations must resolve to the dated reference rows governing its own edition window. This refuses the residual authoring drift and must land before modelo 100 migrates, or its delta will show drift as though it were law. Proof: the known drifting rows are refused by name and the rest of the corpus passes.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

- `A` `src/cadrumo/domain/calculations/registry/casilla_legal_citation_period.py`
- `M` `src/cadrumo/domain/calculations/registry/_snapshot_internals.py`
- `A` `dev/registry/analysis/legal_citation_period_ledger.py`
- `A` `dev/registry/analysis/legal_citation_period_ledger.toml`
- `A` `dev/registry/tests/test_casilla_legal_citation_period_gate.py`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_casilla_legal_citation_period_gate.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check` / `ruff format --check` / `ty check` on the touched files -> `pass`

## Notes

- Corpus measurement: 157,265 casilla citations, judged with the snapshot's revision-scoped legal-window predicate. 1,116 are refused, all of them in modelo 100 (editions 2020 to 2023) and modelo 190 (edition 2024). Every refused reference is also listed in the modelo's own `legal_refs`, which the snapshot check exempts as cross-year authority, so no existing gate could see them. Plain window overlap gives the same 1,116. The 345 substantive and 6,704 procedural citations that overlap the edition without containing it all pass under the devengo predicate.
- Refused groups: 100/2020-2023 `ley-35-2006:art-20` (20+3+3+3); 100/2020 `ley-35-2006:art-23` (134); 100/2021-2023 `ley-35-2006:art-23` (118+116+116, `ley-35-2006:art-23-2021` governs); 100/2020-2022 `ley-35-2006:art-32` (175+176+182); 190/2024 `orden-hac-1431-2025:art-2` (70). This includes the research's anachronistic modelo 100 casilla `0066` (2020 cites the 2024 redaction of art. 23).
- The research's modelo 200 (13 pairs) and modelo 303 (9 pairs) drift is citation-set churn: every cited row still covers both editions. It is period-correct, so this gate does not refuse it.
- Placement: the corpus does not pass cleanly, so the rule is enforced as a dev-lane gate with a per-citation classified ledger (350 `superseded_row_cited`, 766 `no_governing_row_catalogued`), not as a load-time validator. Registry data was not edited.
- Persistent failure, not introduced here: `src/cadrumo/tests/test_docstring_cross_reference_targets.py` fails 4 tests, including the detector's own fixture self-tests. None of its findings names a touched file.
- Code review is still pending. The Step is left unchecked.

- The reviewer persona could not be launched; the orchestrating session reviewed the rule and the ledger against the ADR. The rule reuses the snapshot builder's one legal-window predicate, which is shared through the package-private `__all__`. The ledger admits refused citations per row, classified, and reports stale entries. No registry data was edited. Re-run: 14 gate tests passed, `registry verify` exit 0, ruff and ty clean. Before modelo 100 migrates, its 350 `art-23` rows for 2021-2023 can be re-cited to `ley-35-2006:art-23-2021`; the other 766 refused rows (modelo 100 `art-20`, `art-23` for 2020 and `art-32`, and modelo 190/2024 `orden-hac-1431-2025`) need the older redactions added to the legal catalogue from official BOE sources first.
