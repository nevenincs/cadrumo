---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:a1e4120b4ca375f8fcbf68c8ec7d27b5d581c83885b3b6f32a7659be0a234156'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `P05.S14 legal reference surface review`

## Scope

Audit commit `289a3e1020e4d349a96d872f70ea7ae018c88006` for the P05.S14 legal
reference-surface contract against the accepted search ADR, the active plan,
and the generated-surface patterns. The review was grounded with
vaultspec-rag. No tests, builds, Pagefind runs, live probes, deployment, or
reindexing were run.

## Findings

### root-toctree | high | Generated legal index is not connected to the root docs toctree

The generator writes an index and per-document pages, but the root reference
toctree does not include the legal index. The pages can therefore be orphaned
under a warnings-as-errors documentation build.

### stale-generated-pages | high | Obsolete generated pages are retained

Generation writes current pages but does not remove a legal page for a
document removed from the catalogue. An incremental build can therefore keep
stale legal destinations in the source tree.

### unknown-fields | medium | Unknown legal-table fields are silently dropped

The parser selects known fields and ignores additional fields in an authored
legal table. That violates the metadata-fidelity and fail-closed expectation:
catalogue schema drift should be visible rather than disappear from the
surface.

### reserved-index | medium | A document id can collide with the generated index

The `index` output name is reserved by the generated surface but is not
rejected as a document slug, so a catalogue document id that folds to
`index` could overwrite the generated index.

### rst-safety | medium | Control characters and link values are not fail-closed

RST free-text values are escaped for inline punctuation but are not rejected
when they contain newlines or other control characters, and the authored BOE
permalink is inserted into an inline link without a safety check. Malformed
catalogue data could break the generated field list or markup.

### review-status | low | Source shape and shared target authority otherwise pass

The patch reads only legal tables, groups 589 current rows by document, emits
deterministic page/anchor/target inventories, exposes reusable target helpers,
and uses site-relative HTML targets with BOE grounding rendered at the
destination. The reviewer returned FAIL because of the findings above, not
because of a duplicate record-kind architecture. Runtime acceptance remains
pending.

### optional-fields | high | Validation rejects valid optional legal metadata

The follow-up review found that `_validate_records` validates every field in
the rendered-text field list as though it must be a string. Current catalogue
rows such as the `iva-rates.toml` first legal entry omit the optional `section`
field, so the generator would fail before rendering. The same shape would
reject intended law-level page-only records.

## Remediation

The initial findings were addressed in three scoped commits. The legal index is
now registered in the root reference toctree; generation removes only validated
generated legal RST files; unknown catalogue keys, reserved slugs, output
collisions, unsafe control characters, and malformed BOE links fail closed;
and omitted optional fields remain valid while authored values stay strictly
validated. The follow-up fix also preserves page-only law targets.

## Final review

The final review of commit `46d1a42d7d85a9f0cb32e809b57baefa6b483307`
returned PASS with no blocking source findings. The review was grounded by
`vaultspec-rag` semantic searches over the accepted consolidation ADR, the
active P05 plan, and this audit, followed by `get_code_file` retrieval of the
current legal-reference source and documentation toctree.

Source review is complete. Runtime acceptance remains pending: no tests,
documentation builds, Pagefind runs, live probes, deployment, or reindexing
were run, as required by the current work lane. Keep S14 open until those
authorized runtime/build gates are completed.

## Recommendations

Keep S14 open until the authorized runtime and documentation-build gates pass.
Then continue with P05.S15 through P05.S17 for the legal record kind,
relevance-target reconciliation, and per-kind parity gate.
