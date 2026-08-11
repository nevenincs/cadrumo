---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:d4c3409dd747ca22367258413559c9dd7e3d9855df90ab74c0ab86a8502ee602'
step_id: 'S308'
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
     The S308 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Assert the FINAL URL in the BOE acquirer, because its identity check does not establish which endpoint answered. Measured on a live probe: a request to the consolidated endpoint act.php SILENTLY REDIRECTED to doc.php, the single-document view, and the identity check passed because doc.php carries the requested id in the same form input. Only the version-selector check refused the payload, and it refused for an unrelated reason, that a single-document view offers no versions. So the check that sounds like it establishes provenance verifies the REQUEST rather than the SOURCE: an identity check that reads the id back out of a response is satisfied by ANY endpoint that echoes the id. Today the version check happens to catch the treaty case. It would NOT catch a redirect landing on something version-bearing, and the acquirer is the only thing standing between this fleet and hand-fetching, so the gap matters more than its current blast radius. REMEDY: assert the final URL of the response against the endpoint that was requested, since the payload cannot say which endpoint served it and only the response can. Carry the structural fact that motivated it: BOE holds no consolidated text for bilateral tax conventions at all, and each convention excerpt's own permalink already recorded that by pointing at doc.php rather than act.php, a provenance marker sitting in plain sight and unread because nobody was looking for a SHAPE difference in a URL and ## Scope

- `dev/corpus` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert the FINAL URL in the BOE acquirer, because its identity check does not establish which endpoint answered. Measured on a live probe: a request to the consolidated endpoint act.php SILENTLY REDIRECTED to doc.php, the single-document view, and the identity check passed because doc.php carries the requested id in the same form input. Only the version-selector check refused the payload, and it refused for an unrelated reason, that a single-document view offers no versions. So the check that sounds like it establishes provenance verifies the REQUEST rather than the SOURCE: an identity check that reads the id back out of a response is satisfied by ANY endpoint that echoes the id. Today the version check happens to catch the treaty case. It would NOT catch a redirect landing on something version-bearing, and the acquirer is the only thing standing between this fleet and hand-fetching, so the gap matters more than its current blast radius. REMEDY: assert the final URL of the response against the endpoint that was requested, since the payload cannot say which endpoint served it and only the response can. Carry the structural fact that motivated it: BOE holds no consolidated text for bilateral tax conventions at all, and each convention excerpt's own permalink already recorded that by pointing at doc.php rather than act.php, a provenance marker sitting in plain sight and unread because nobody was looking for a SHAPE difference in a URL

## Scope

- `dev/corpus`

## Description

- Read the acquirer identity check and establish what it actually verifies.
- Assert the response final URL against the endpoint requested, on both arms.
- Cover the precision cases a too-strict comparison would break.

## Outcome

Delivered. Both arms of the acquirer now assert the endpoint that ANSWERED,
which no payload check can establish.

The row measurement holds: a request to the consolidated endpoint silently
redirected to the single-document view, and the identity check passed, because
that view echoes the requested id in the same form input. An identity check
that reads the id back out of a response is satisfied by ANY endpoint that
echoes it -- it verifies the REQUEST rather than the SOURCE. Only the
version-selector check refused that payload, and for an unrelated reason: a
single-document view offers no versions. It would not catch a redirect landing
on something version-bearing.

Compared on scheme, host and path, deliberately NOT on the query string. BOE
echoes and reorders parameters, so a comparison including it would refuse
correct responses -- which is how a guard gets switched off rather than fixed.
That precision half is covered rather than asserted in prose.

The structural fact the row asked to carry is in the code where the next
reader meets it: BOE holds no consolidated text for bilateral tax conventions
at all, and each convention excerpt permalink had already recorded that by
pointing at the document view rather than the consolidated one -- a provenance
marker in plain sight, unread because nobody was looking for a SHAPE
difference in a URL.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Six cases, all pure-function over URL pairs, so they need no network and no
HTTP double -- which is what lets them run everywhere rather than being the
kind of acquisition test that only the maintainer can execute. The article arm
is covered separately from the consolidated one because it carries its
identifier in the PATH rather than the query, so a check that over-refused on
path segments would break exactly that arm and pass on the other.
