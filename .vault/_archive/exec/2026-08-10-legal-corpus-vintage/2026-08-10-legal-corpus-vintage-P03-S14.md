---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:4be95b7e3fa287df7a551d5a8dfbe5ea56e5992a92e5cf2b732e7460ecdf23c2'
step_id: 'S14'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
  - "[[2026-08-13-legal-corpus-vintage-vintage-screen-review-audit]]"
  - "[[2026-08-10-legal-corpus-vintage-adr]]"
---

# Refuse the version pile structurally, rather than resting on nothing pointing at it yet. The 58 acquired article payloads carry BOE's full redaction history by design, but the extractor folds every version into ONE undelimited unit with no fecha_vigencia attribution, and boe-a-1991-14392-a30-redacciones is ten versions in a single 15.8k-character unit. Any corpus_ref resolving there fuses repealed and current law, and a required_text presence check passes on REPEALED text, which is the trap the grounding rule states verbatim and the trap the S05 row names in its own heading. S06 handled it for the screen by reading the raw payload and reducing to the redaction in force, but the committed DATA is still a pile. Either split the article-endpoint extraction one unit per version carrying its fecha_vigencia, or refuse at registry build any corpus_ref resolving to a redacciones sidecar. Prove the refusal bites by breaking it on purpose from outside the repo

## Scope

- `dev/docs/preprocess/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/_data/corpus/normatives/html/`

## Description

This record documents work found already present and already committed at sha
`58b78beaa5aaf894b2092c4cbbfe0fb157b83a72` ("registry(legal): resolve
consolidated-article redaction marks by norm and vigencia"). It is written
retrospectively from the committed diff and tests, not from having performed
the implementation; the exec record file existed with a scaffolded frontmatter
and heading but a blank body, which this fills.

- Add `CorpusRedactionMark` / `corpus_redaction_marks` and
  `extracted_unit_count` to `core.corpus_text`, reading the raw payload's dated
  redaction markers rather than the sidecar's unit split.
- Add `_assert_redactions_are_not_fused` to `_legal.py` and call it from
  `_legal_corpus_text` before a citation's unit is resolved: if the cited
  document declares fewer than two dated redactions it is untouched; if it
  declares two or more, the citation is refused with a message naming the
  entry, the file, the redaction count and vigencias, and the two remedies
  (cite a consolidated current-text document, or reduce the capture to the
  redaction in force through the acquirer's own rule).
- Detection is structural (redaction-mark count in the raw payload), not by
  filename: the row's own two named cases are both driven —
  `boe-a-1991-14392-a30-redacciones.html`, whose stem announces the fusion, and
  `rd-1065-2007-art-25.html`, which the live catalogue actually cited and whose
  stem does not.
- A present-but-unreadable document refuses (`OSError` on read); a document
  absent on disk is out of scope for this check specifically, because its
  presence is already a separate, prior gate.
- Add `test_legal_fused_redaction_refusal.py` (6 tests), driven against the
  real bundled corpus rather than a synthetic fixture.

The row offered two remedies ("split the article-endpoint extraction one unit
per version... or refuse at registry build any corpus_ref resolving to a
redacciones sidecar"). The committed change takes the refusal path and records
the split-extraction alternative as "CONSIDERED AND DEFERRED" in the
function's own docstring, reasoning that it reshapes shared production
extraction output several concurrent efforts consume and warrants its own
decision record.

## Outcome

Re-ran `test_legal_fused_redaction_refusal.py` for this record: `6 passed` in
20.5s (`pytest -n 0 -q`). The suite proves both directions of the row's claim
against real bundled artefacts:

- `test_registry_build_refuses_a_citation_into_a_fused_redaction_history`
  (parametrized x2): a citation into `boe-a-1991-14392-a30-redacciones.html`
  and into `rd-1065-2007-art-25.html` — the file the live catalogue actually
  cited — both refuse, quoting a phrase the fused unit genuinely contains
  (so what refuses it is the shape of the evidence, not a missing phrase),
  with the refusal message naming the entry, the file, the redaction count,
  and both remedies.
- `test_a_fused_unit_states_one_provision_two_ways_that_cannot_both_be_law` and
  `test_a_fused_unit_states_its_own_provision_more_than_once` ground the
  hazard against the real committed data (a repealed peseta tariff and its
  current delegation both present in the same unit; RGAT art. 25's heading
  stated once in the consolidated document and more than once in the fused
  capture).
- `test_a_single_redaction_capture_is_accepted_despite_the_redaction_history_stem`
  proves the stem does not convict: an unamended article carrying the
  `-redacciones` naming convention but only one redaction is accepted.
- `test_no_committed_legal_entry_cites_a_fused_redaction_history` is the
  control that decides closure per the plan's own `aeat-quality-gates`
  discipline: every committed legal-catalogue entry is validated through the
  real registry-build path and none refuses, and the deliberately
  year-vintaged excerpts named in the plan's P01.S02 row are confirmed still
  present in the catalogue (a refusal catching one of those would be wrong).

## Notes

This record documents work found already present and committed by a prior
session; it does not represent implementation performed by the agent writing
this record.

**The row's "prove the refusal bites by breaking it on purpose from outside
the repo" clause is evidenced, but not in the literal plant-then-restore shape
that phrase and the project's own quality-gates discipline usually mean.**
No test here writes a synthetic corrupted document from outside the repo,
observes the gate red, then restores. Instead, every "broken" case in
`test_registry_build_refuses_a_citation_into_a_fused_redaction_history` is a
real, already-bundled, already-fused corpus document — `rd-1065-2007-art-25.html`
is the exact file the live catalogue actually cited before this fix. The test
module's own docstring states the choice explicitly: "these tests drive that
refusal against the REAL bundled corpus rather than a synthetic fixture,
because a detector that is correct on synthetic input and never reaches the
real site is the failure mode a synthetic proof cannot see." This is a
stronger site-fidelity proof than a synthetic plant would be — it demonstrates
the refusal fires on a genuine defect that shipped in the live catalogue,
not merely on a fixture built to trigger it — but it is a different proof
shape than "break it on purpose from outside the repo," and this record does
not claim the latter occurred.

Two smaller items worth flagging rather than silently absorbing:

- `document.is_file()` returning `False` makes `_assert_redactions_are_not_fused`
  a no-op (documented in the function's own docstring as "out of scope rather
  than fail-closed"), which is a narrower guarantee than "every fused citation
  refuses" — it is "every fused citation whose document is present refuses,"
  with document presence itself covered by a separate prior gate. The record
  states this rather than letting the outcome section imply a universal
  guarantee.
- The redaction-count threshold is `< 2` (untouched) versus `>= 2` (refused),
  read directly from the raw document rather than compared against the
  sidecar's extracted-unit count. The function's own docstring explains why a
  unit-count comparison was rejected as insufficiently fail-closed; this
  record does not re-litigate that reasoning, only notes where to find it
  (`_assert_redactions_are_not_fused` in `_legal.py`).

Verification command and result: `pytest src/cadrumo/domain/calculations/registry/tests/test_legal_fused_redaction_refusal.py -n 0 -q` → `6 passed, 1 warning in 20.54s`, full output captured to a log file and read back from disk before reporting.
