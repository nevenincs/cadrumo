---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:0ea010d325be5b4fa1b347ba52982ffda5df1623473bc4acacb24b80e6c70402'
step_id: 'S55'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Scan same-module read/write name pairs for a split half, which found five instances with no noise, and adjudicate the two that ground out as design rather than defect: the encrypted envelope tier is unreached as a group, appearing partly live only because its saver is called by a reencrypt helper that is itself unreached, while the plain tier beside it carries eighteen references and sensitive payloads encrypt through the application-layer secure-object envelope instead; and the mnemonic decoder is unnecessary because the custody design hands the twenty-four word phrase to the KDF as the recovery secret rather than decoding it to entropy

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

Two alarms were raised by the pair scan and neither survived grounding, which is
worth recording so they are not re-raised. A mnemonic that can be encoded and
not decoded reads as broken recovery; it is not, because the phrase itself is
the KDF secret. An encrypted envelope saved but never loaded reads as
unreadable data; it is not, because nothing writes through that tier at all --
its saver's only caller is also unreached.

Three pairs remain unadjudicated from the same scan: the extracted-document
transcription cache, the corpus manifest, and the already-recorded bucket
output-language hint.
