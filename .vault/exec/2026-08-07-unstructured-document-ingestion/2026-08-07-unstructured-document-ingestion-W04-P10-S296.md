---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:f6073a904ccd827031c58bc34122852aea36c326578c1ac38a8aaf325b2f72f2'
step_id: 'S296'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S296 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Score the draft the reading ROUTER hands on rather than the extractor's raw output, since suggested_kind is derived deterministically by ground_draft_against_transcription from the filer tax id one stage AFTER ground_extracted_fields, and iva_category is decided by the single classification authority at the confirm boundary. A capture taken at the extractor stage reports both None and cannot distinguish never-produced from produced-one-stage-later, which is what motivated a proposal to route both through the LLM classifier and would have replaced two deterministic authorities with probabilistic ones and ## Scope

- `dev/ingest_harness/_runner.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Score the draft the reading ROUTER hands on rather than the extractor's raw output, since suggested_kind is derived deterministically by ground_draft_against_transcription from the filer tax id one stage AFTER ground_extracted_fields, and iva_category is decided by the single classification authority at the confirm boundary. A capture taken at the extractor stage reports both None and cannot distinguish never-produced from produced-one-stage-later, which is what motivated a proposal to route both through the LLM classifier and would have replaced two deterministic authorities with probabilistic ones

## Scope

- `dev/ingest_harness/_runner.py`

## Description

- Confirm the row's diagnosis and find where a stage guard could live.
- Attempt it at the projection boundary, meet the module's own design pushing
  back, and revert.
- Record where the capture actually is, and what the harness can and cannot say
  about it.

## Outcome

DIAGNOSIS CONFIRMED, and the in-repo half is SMALLER than the row's scope
implies. The row names the harness runner. The runner cannot carry this guard,
and neither can the projection, and the reason is a design decision both of
them state about themselves.

The diagnosis holds exactly. Neither field is read off the page: the suggested
kind is derived deterministically from the filer's own tax id one stage after
extraction, and the IVA category is decided by the single classification
authority at the confirm boundary. A capture taken at the extractor stage
reports both absent, and scoring it books two DETERMINISTIC fields as model
misses -- a wrong number that argues for a change, and it already did: an
identical residual across every pilot document motivated a proposal to route
both fields through the LLM classifier, which would have replaced two
deterministic authorities with probabilistic ones.

There IS a clean structural discriminator, and it is worth recording because
the next attempt will want it: a DRAFT always carries both fields, empty or
not, because they are fields of the record; the extractor's own output does not
have them at all. So an absent key is a stage error and a present-but-empty one
is a real result.

WHERE IT CANNOT LIVE. The projection function is declared DATA rather than
translating code -- it moves values between names and does nothing else, and
comparison is deliberately kept in the scoring module. A stage refusal there
also breaks the module's own unit tests, correctly: they hand small payloads to
check re-keying, which is what that function is for. Implemented and reverted;
the harness is back to 109 green with no diff.

The runner cannot carry it either. It declares that it does not read documents
and takes measured rows from a caller, and its row record carries counts rather
than the scored field NAMES -- so it cannot see which fields a row scored.

WHERE THE CAPTURE ACTUALLY IS: outside this repository, in the caller that
drives the product entry points. The row's real deliverable is a change at that
call site, and the in-repo surfaces are stage-agnostic by design rather than by
omission.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The row stays open on that finding rather than being closed on a guard placed
where it does not belong. Two placements were tried and both were refused by
the surface's own stated contract, which is a stronger result than a third
attempt: it says the harness is deliberately blind to capture stage, so a guard
must either be given the stage as data by its caller, or live at the caller.

Recorded so a later pass does not re-derive the discriminator: present-but-empty
is a result, absent is a stage error, and that distinction is available from the
payload alone without any new plumbing.
