---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S10'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-quality-backlog with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-17-cli-authority-quality-backlog-plan placeholders are machine-filled by
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
     The Replace literal-membership namespace checks with a non-vacuous production-root adoption gate that recognizes cadrumo-prefixed declarations, detects local metadata declarations, and proves each storage binding consumes the registered definition and ## Scope

- `src/cadrumo/application/tests/test_storage_namespace_adoption.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace literal-membership namespace checks with a non-vacuous production-root adoption gate that recognizes cadrumo-prefixed declarations, detects local metadata declarations, and proves each storage binding consumes the registered definition

## Scope

- `src/cadrumo/application/tests/test_storage_namespace_adoption.py`

## Description

- Authored `test_storage_namespace_adoption.py`, a production-root structural gate over the whole `cadrumo` package that replaces the brittle literal-membership namespace allowlist with three scans plus a non-vacuity proof.
- Recognition: assert the storage registry is the non-empty authority set and every registered namespace uses a `cadrumo`-family prefix (`cadrumo.` / `cadrumo-test.` / `cadrumo-tests.`), so a newly registered definition is auto-covered with no edit to the gate; the closed cadrumo whitelist inherently excludes any retired `aeat.*` prefix.
- Redeclaration detection: an AST walk flags any secure-object write site passing a raw `SensitivityClass.<MEMBER>` or integer literal for its metadata instead of a definition-sourced value. Write sites are matched structurally as a `save(namespace=..., classification=...)` call (the `SecureObjectRepository.save` shape), an `Envelope(classification=...)` construction, or a `sensitivity`/`schema_version` ClassVar inside a `SecureBoundRepository` subclass.
- Consumption proof: enumerate every production `SecureBoundRepository` subclass and assert each binds its `namespace` / `sensitivity` / `schema_version` ClassVars to a `<NAME>_NAMESPACE.<attr>` definition attribute; assert the consumer count is the full surface (14).
- Non-vacuity: a self-test feeds the detector a synthetic drifted repository (raw sensitivity/schema_version ClassVars plus a raw-literal save site) and asserts every site is flagged, with a definition-sourced negative-control fragment the detector must leave clean.

## Outcome

- Six gate tests plus two detector-probe tests all green on the canonical tree; the production redeclaration scan returns zero findings (S27 clave, the LLM/session/review-package single-sourcing, and the 14 profile-adapter + 4 not-def-bound repo sweeps are all confirmed def-sourced).
- The detector caught one true-but-out-of-scope site during development — a `schema_version` field on the keystore DEK document `_WrappedBucketDekDocument` — which drove scoping the ClassVar branch to `SecureBoundRepository` subclasses only (secure-object namespace bindings), the correct scope for this step.
- Gates green: focused pytest, ruff lint + format, ty, import-hygiene test-only-underscore-reaches, and a 5513-test collect-only over `application` + storage.

## Notes

- Scope held to secure-object namespace bindings only; custody (S09's separate concern), the `SecretStore`/`SecretRecord` certificate backend (no namespace definition), and the `TRANSACTION_PARTICIPATION_INDEX_NAMESPACE` def-authoring string are intentionally not flagged — the `SecretRecord` construction and secret-store save carry no `namespace=`+`classification=` shape and so are naturally excluded.
- Two marker-integrity checks are red from peer churn outside this surface (the S09 `test_review_package_namespace_binding.py` hex marker and the P06.S18/S19 MCP campaign-metadata docstrings); owner-triaged as not this step's files.
