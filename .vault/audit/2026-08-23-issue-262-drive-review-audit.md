---
tags:
  - '#audit'
  - '#issue-262-drive-review'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8c96cebf2a6c1aeade7f449a9bda227a44de1ecced4f69389151bfb910b4d32a'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace issue-262-drive-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `issue-262-drive-review` audit: Drive attachment review journey

## Scope

Reviewed the issue #262 implementation from encrypted Drive attachment custody through
review discovery, safe provenance inspection, field extraction, explicit confirmation,
invoice linkage, and idempotent repeat ingestion. The review covered production code,
typed CLI envelopes, locale additions, real secure-repository tests, and command-policy
registration. Gmail and OAuth scope changes were excluded.

## Findings

### drive-locator-canonicalization | high | Drive review output can disclose query credentials from a non-canonical source reference

`_project` recognizes Drive provenance with a substring search for `/file/d/` and then
copies every character up to the next slash into `provider_locator`. It neither parses
the URL nor validates its scheme, host, query, fragment, user-info, path shape, or file
id grammar. Consequently a Drive manifest whose source reference ends in
`/file/d/id?access_token=secret` projects `id?access_token=secret` into the CLI envelope;
an unrelated host containing the marker is also accepted. This violates the required
safe-metadata boundary even though raw manifest metadata, notes, and non-Drive locators
are otherwise excluded.

Required correction: parse the reference as a URL; require HTTPS, an explicitly allowed
Drive host, the canonical `/file/d/{id}` path form, no user-info/query/fragment, and a
validated file-id token. Any non-canonical input must refuse or project `not-exposed`.
Add hostile tests for query and fragment credentials, user-info, a lookalike host,
malformed paths, and invalid file ids, alongside the canonical positive case.

### non-drive-locator-redaction | medium | Generic attachment view could expose a local path or credential-bearing URL

The first review projection copied `source_reference` into `provider_locator` for
non-Drive records. Since the command accepts any attachment id, that could expose a
local source path or a URL query token. Corrected before delivery: only a Drive file id
is projected; every other source reports `not-exposed`. The test continues to prove
manifest metadata and notes never reach the envelope.

### command-policy-oracle | low | New read callbacks were absent from the semantic policy oracle

The live commands were correctly decorated as encrypted-fact, local-I/O, read-only
operations, but the exhaustive callback oracle initially rejected the two additions.
The exact read-only tuples were added and the focused contract now passes.

## Recommendations

- Keep provider locators source-specific; never generalize the projection back to raw
  `source_reference`.
- Keep the queue derived from encrypted manifests and invoice back-links so repeat pulls
  cannot drift a second review-state store.

## Independent verification

Commit `828dba23370a5d564762f96bb06b8202fbddf279` was reviewed at an exact clean HEAD.
The queue is derived directly from authoritative encrypted manifests, selects only
unconfirmed Google Drive attachments, preserves manifest digest/media/size/source/time
identity, and uses the established explicit extract/confirm flow. Confirmation remains
guarded and idempotent, invoice back-links remove confirmed items from repeat queues,
unsupported extraction refuses without falsely confirming, Gmail scope is unchanged,
and the CLI additions are read-only encrypted-fact operations with translations limited
to English, Spanish, Catalan, and Hungarian.

Focused evidence: the secure attachment service/store suite passed 17 tests; the real
Drive CLI journey passed 2 integration tests; and the selected command loading/policy
lane passed 11 tests with 14 tests explicitly deselected by its unit marker. A Ruff
invocation used two incorrect repository-relative paths and therefore supplied no lint
evidence; it does not affect the behavioral results above.

Verdict: not safe to integrate and issue #262 cannot close until
`drive-locator-canonicalization` is corrected and its hostile cases pass.
