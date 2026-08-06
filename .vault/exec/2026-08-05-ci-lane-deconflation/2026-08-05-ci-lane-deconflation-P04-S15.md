---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:ca7d33f3de561b8799ec0302fe6a4abe5f9840c2b091004efb04277716a1e2ea'
step_id: 'S15'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Repair the four core tests broken by the root-only Modelo localization migration, it stripped title and official_name and label from the M036 manifest without updating hand-derived expectations

## Scope

- `src/cadrumo/core/tests/test_toml_registry_parity.py`

## Description

- Establish whether the stripping of `title`, `official_name` and `label` was deliberate or collateral, because the two repairs are opposites.
- Drop the three presentation expectations rather than restore the fields.
- Record at each expectation that the absence is the declared shape, so a later reader does not repair it back.

## Outcome

Landed as commit `0a953558df` ("test(core): drop the M036 presentation fields from the TOML
parity expectations"), one file, 6 insertions and 6 deletions. Sha resolved by `--grep` and
read with `git show <sha> --numstat`.

The repair direction was the whole question, and it was settled from the governing record
rather than from the failure text. `2026-08-04-modelo-localization-cascade-adr` makes the
stripping deliberate in two independent places: its Constraints require that schema records
"retain identifiers, legal/source grounding, structural metadata, language-neutral locale-key
enrollment, and evidence, but no language-specific presentation value", and its D1 both
assigns "Modelo presentation and official-name fields" and "Revision presentation fields" to
the shared catalogues and states that revision schema fragments "must not carry
natural-language labels, help, titles, names". Verified both passages at source. The
fragments are therefore in their declared shape and the expectations were stale; expectations
updated, no field restored.

## Notes

**The tautology risk was the real hazard and it was closed properly.** A parity test updated
to match the reader it gates is worthless — it would agree with any output that reader
produced, including a wrong one. Confirmed independently rather than accepting the claim: the
committed expectations are reproduced exactly by `tomllib`, a stdlib parser with no
relationship to the one under test, for both the manifest and the revision fragment. The
expectations therefore agree with an independent reading of the committed source bytes, not
merely with the parser they exist to check.

**Discriminating power confirmed structurally, not just asserted.** The revision expectation
carries one `date` and one `int` among fifteen strings, which is precisely the shape the
module docstring says it exists to defend: a type-coercion regression that stringified the
local TOML date or the nested integer breaks equality. A parity expectation reduced to all
strings would have lost that property silently while still passing.

**A scope correction belongs in this record, and it narrows the row.** The row names four
broken tests; only three are localization-migration breakage. The fourth,
`test_loader_fingerprint_content_collision.py`, contains no M036 data at all — confirmed,
zero occurrences of the modelo id — and passes at HEAD. It was a separate defect, the gate
not actually running, already fixed by commit `ad4fa570de`. The two surfaced in one
verification run and were bundled by that coincidence rather than by a shared cause. The row
is closed on three tests repaired and the fourth shown to be someone else's already-closed
defect, not on four repairs.

**Verification.** Three tests pass on the repaired file. The fourth test passes at HEAD in
its own lane. Reported gates on the landing: `ruff format`, `ruff check` and `ty check`
clean, with 689 passing across the full core test suite.

One lane note, the third instance of this shape today. The first attempt to confirm the
fingerprint test reported `NOTHING RAN` with its single test deselected — it carries the unit
marker, not integration, so an integration-scoped invocation selects nothing and exits
green. A green there would have been a selection matching nothing rather than evidence the
test passes.

**A comment was added at each expectation** recording that the absence of presentation text
is the declared shape rather than a stripped field. That is the right durable defence: the
next reader meeting a manifest expectation with no title has the same two candidate repairs
this row faced, and nothing else in the file would tell them which. It is stated as a domain
fact carrying no vault reference, per the code-stands-alone mandate.
