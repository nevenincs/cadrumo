---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c61c7b41d70f201073abbb91eb5f239f033e5b2fa9b93cd3fc67e17841385a43'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-W01-P02-S10]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
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

# `tui-architecture` audit: `W01.P02.S10 independent review`

## Scope

Independent review of `W01.P02.S10`: the governing D4 exact-interaction decision, request and response contracts, direct tests, and execution evidence. The review checked immutable identity, revision, schema, presentation, expiry and continuation binding; token and intent discrimination; exact approval facts; deferred supervisor/domain/frontend boundaries; secret exclusion; and gates.

## Findings

### incomplete-exact-approval-binding | high | Apply responses omit baseline, proposed effect, and actor facts

D4 requires specialized approval to bind the exact request, baseline, reviewed proposal, proposed-effect digest, actor, and time. `OperationApplyResponse` carries operation and interaction IDs, revision, response token, continuation and proposal digests, and response time, but no baseline digest, proposed-effect digest, or actor identity. Those omissions let later consumers associate approval with baseline/effect/actor facts that were not part of the immutable signed-off response contract. They are approval operand identity, not supervisor single-use consumption or domain apply behavior that can safely be deferred. Current tests cannot detect their absence because they only validate the implemented field set.

## Recommendations

- Add canonical opaque baseline, proposed-effect, and actor bindings to the specialized apply contract, preserving domain payloads behind digests/references. Prove each is required and malformed or missing values fail closed, and prove apply/reject discrimination does not permit approval facts to drift.

The remaining reviewed boundary is sound: interaction requests bind immutable identity, revision, kind, stable presentation code, response schema reference, continuation digest, and optional UTC expiry; apply/reject are strict discriminated variants; all opaque IDs and digests reject malformed values; responses are frozen and reject extra payload/prose. Token consumption remains correctly deferred to the supervisor transaction, and no callback, frontend state, raw secret, proposal payload, domain apply logic, or S11 facade is introduced. Focused pytest reports 9 passes, Ruff passes, and basedpyright is clean, but these gates do not cover the missing D4 facts. No critical or medium finding is asserted.

## Final re-review disposition

### incomplete-exact-approval-binding | closed | Apply responses carry the complete immutable D4 evidence tuple

`OperationApplyResponse` now binds operation and interaction identities, revision, response token, continuation digest, baseline digest, reviewed-proposal digest, proposed-effect digest, actor reference, and UTC response time. Each evidence field is required and constrained, mutation tests fail malformed values, and the discriminated-union JSON round trip preserves the complete correlation tuple. No existing canonical actor-reference type is a semantic superset; the narrow machine-reference alias avoids domain actor redeclaration.

`OperationRejectResponse` appropriately retains actor, time, reviewed proposal, and continuation correlation while omitting apply-only baseline and proposed-effect evidence for a no-effect rejection. Single-use consumption, domain apply behavior, callbacks, frontend state, and secret payloads remain outside S10. Final evidence records 15 tests passed, Ruff passed, and basedpyright reported no diagnostics. No critical, high, or medium findings remain.
