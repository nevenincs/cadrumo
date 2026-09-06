---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:2db62903579eaea69ae89515035f1ce4c2624d68b8650931258a4125aaa422df'
step_id: 'S56'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Record the campaign's clearest cost finding and one supersession: the encrypted stage-S1 transcription cache is never populated, its own docstring stating that re-reading is the expensive half of ingestion at a vision model pass over every page and that re-running the cheap semantic stages is only affordable if the transcription is kept, while the single live reader is the consent-withdrawal path that touches the cache to erase it; and the standalone corpus manifest writer is subsumed by the bundle builder that writes the manifest inside the zip archive

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

The staleness gate caught a symbol added to a cluster on a `modulesplit` zero:
`load_extracted_document_cache` shows no cross-module reference but is NOT an
audit finding, because an intra-module caller reaches it. That is the tool
limitation recorded at `W05.P12.S52`, and this is the first time it produced a
wrong ledger entry rather than a wrong reading. The cluster now names the writer
only. Check a candidate against the audit's reported set before clustering it,
not just against the reference count.
