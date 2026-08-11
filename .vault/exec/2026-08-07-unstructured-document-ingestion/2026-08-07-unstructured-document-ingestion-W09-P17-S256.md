---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:bc97eb5519c96af6b7a605e4f990a630df85d11fd5f6f24d0684748cac8fd15d'
step_id: 'S256'
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
     The S256 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Carry the field identity from the raise site, the half of S239 that is not delivered and cannot be delivered by the projection. The row asked for the field and the constraint, and an operator meeting the motivating case gets root and value_error with the exception class, so they still cannot tell WHICH field. That is not the projection's fault: the invoice counterparty normaliser raises from a model-level before-mode validator, so pydantic has no field location to report and the projection faithfully reports the location the raise site never provided. The fix is at the raise site, where a domain validator that knows which field it is judging should raise in a way that carries it. Opened separately rather than left inside S239, so the row does not read as fully delivered when half its deliverable is structurally out of its reach and ## Scope

- `src/cadrumo/domain/invoices` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Carry the field identity from the raise site, the half of S239 that is not delivered and cannot be delivered by the projection. The row asked for the field and the constraint, and an operator meeting the motivating case gets root and value_error with the exception class, so they still cannot tell WHICH field. That is not the projection's fault: the invoice counterparty normaliser raises from a model-level before-mode validator, so pydantic has no field location to report and the projection faithfully reports the location the raise site never provided. The fix is at the raise site, where a domain validator that knows which field it is judging should raise in a way that carries it. Opened separately rather than left inside S239, so the row does not read as fully delivered when half its deliverable is structurally out of its reach

## Scope

- `src/cadrumo/domain/invoices`

## Description

- Reproduce what an operator meeting the motivating case actually sees.
- Name the field at the raise site, preserving everything the error carries.
- Pin the structure the first attempt destroyed.

## Outcome

Delivered. The refusal now names the field it judged.

The row diagnosis was exact. The validators the normaliser calls judge a VALUE
and say so, and none names the field because none knows it -- the same country
validator judges an issuer country elsewhere. The normaliser DOES know, and it
is the last place that does: it runs inside a model-level before-mode
validator, so pydantic has no field location to attach and the projection
faithfully reports the location the raise site never provided. Naming the
field downstream would mean guessing it back out of the message.

THE FIRST ATTEMPT WAS WRONG IN A WAY THAT LOOKED RIGHT, and it is the finding
this row leaves behind. Rebuilding the exception as its own type around a
better message is the obvious shape and it silently dropped the structured
attributes the constructor does not take -- the translation key and the
context mapping. A rebuilt instance arrives with a better developer message
and no localisation, on the exact path a separate campaign is migrating TO
localisation. It was caught by a shipped assertion on that key, which is
precisely the value such an assertion has, and it is now pinned again beside
the fix so the next author reaching for a rebuild is stopped in this file
rather than two packages away.

The shipped form annotates the raised exception in place, touching only the
message and leaving the type, the translation key, the context and the
traceback untouched.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

REACH STATED rather than implied, because this row is half of another row and
should not be read as closing more than it does. The prefix reaches whoever
reads the message: a developer, a log, a traceback, and the CLI boundaries
that render the exception directly. A surface rendering the LOCALISED message
resolves the translation key instead and still does not name the field.
Carrying it there means adding the field to the structured context and giving
the key a slot for it, which changes a localisation contract that is currently
mid-migration -- so it is deliberately not built here against a shape that is
still moving.

Two adjacent stale expectations in the same suite were absorbed, and the
naming rule rather than my judgement settles them: production says "Spanish
IVA identification" and the tests still said VAT.
