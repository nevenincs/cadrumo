---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:fbeee127a19e6118733ea13367dd190f5c1ebe689a30de3e9865dc9424bce893'
step_id: 'S167'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S167 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The propagate physical-closing authority and continuity evidence through secure inventory ingress and ## Scope

- `src/cadrumo/application/inventory`
- `src/cadrumo/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# propagate physical-closing authority and continuity evidence through secure inventory ingress

## Scope

- `src/cadrumo/application/inventory`
- `src/cadrumo/entrypoints/cli`

## Description

- Add a guarded encrypted repository mutation for one immutable closing-authority record.
- Accept exact-fingerprint retries as idempotent and refuse every divergent replacement without overwriting the original.
- Compose movement-derived and physical-observation authority through bounded structured stdin or a one-shot file descriptor.
- Route all ingress validation through the canonical domain record and resolver.
- Remove the retired `closing_stock` transport field and rename report-only output to `derived_closing_value`.
- Project only authority fingerprints to ordinary CLI results while withholding evidence, actor, command, and timestamp facts.
- Align command specifications, schema-v3 payloads, and Catalan, English, Spanish, and Hungarian locale keys.
- Add encrypted reload, replay, divergence, malformed-input, channel, confidentiality, and command-envelope tests.

## Outcome

Operators can now attach one provenance-complete closing-authority bundle to an activity/year inventory ledger through a credential-free structured channel. The write is revision-guarded in the encrypted inventory repository; exact replay succeeds without a second write, while any changed decision, physical observation, or continuity source refuses without replacing the admitted record.

The CLI returns fingerprints only. Raw evidence references, content digests, reviewer identity, source command, and decision timestamps remain encrypted and are absent from normal output, refusal output, captured logs, and subsequent movement payloads. The application intentionally emits no separate bucket event because the inventory and event repositories do not share a transaction.

Verification completed with 16 passing real CLI integration tests, 75 passing focused application and contract tests, two passing locale-coverage tests, clean Ruff and type-checker runs, and an independent formal review reporting zero findings.

## Notes

Semantic discovery was unavailable because the installed `vaultspec-rag` client was version 0.4.1 while the running service was 0.4.2; targeted source and ADR inspection supplied the required grounding. During verification, concurrent CLI authentication work briefly raised `NameError: verb_path` before command dispatch. The shared owner corrected that regression, after which the complete integration matrix passed.

The implementation was swept into concurrent shared commit `167a42c22e` together with unrelated work before lifecycle finalization. This Step record and plan closure preserve S167 traceability without rewriting or reverting that shared commit.
