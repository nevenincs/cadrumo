---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:5282a6f09c84f97c518ca215b1ddf351457b2c70b578565a5ab8895edd5d1b2f'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `RC1 IVA classification remediation review`

## Scope

Reviewed the current uncommitted S86 IVA-classification surface in `classification.py`, `_classification_rules.py`, and `test_classification.py` against the accepted governed-fact catalogue decision and the operation-pinned authority boundary. The review covered registry grammar fidelity, legal-semantics ownership, fail-closed behavior, operation coherence, public API integration, token comparison, and test lifecycle. No source code or quality gate was modified or run. Current-HEAD integration conditions that predate the latest rule-projection batch are identified explicitly rather than attributed to that batch.

## Findings

### dual-authority-source | low | Candidate authority silently overrides a supplied pinned operation

`classification.py:850-863` accepts both `operation` and `authority`, then silently chooses `authority`. A caller that accidentally supplies different generations receives no coherence error, even though the operation contract exists to keep one complete application operation on one generation. This dual-source condition predates the latest rule-projection batch but remains on the reviewed boundary.

### collection-time-authority | medium | The migrated unit module requires the published authority artifact during collection

`test_classification.py:32-37` opens the bundled indexed authority and resolves four catalogues at module import time. In the present checkout the generated `authority.current.json` descriptor is absent, so pytest cannot collect the module. The cached tokens are also created under an operation that has ended and then compared with results produced by later operations; value equality makes the assertions pass without proving one-generation coherence.

### result-invariant-gap | high | The reviewed surface permits an exemption article on a non-exempt category

`classification.py:656-735` no longer enforces the category/exemption-article invariant. The existing negative contract in `test_exemption_article.py:44-66` therefore has no enforcing validator on this model. This condition was already present in the live dirty base before the latest projection batch, but it is a current correctness blocker: direct model construction can represent a legally inconsistent result.

### non-atomic-operation-cutover | high | Required operation parameters are not migrated across existing consumers

`classification.py:411-478` and `classification.py:888-895` require a pinned operation, while existing callers still use the displaced contract. Examples include `establishment.py:280` and `establishment.py:583`, which pass `authority=` to `require_iva_territorial_scope`, and multiple domain/application tests that still call `classify_iva(criteria)` without `operation=`. This condition predates the latest rule-projection batch but means the public boundary is not atomically usable repository-wide; a three-file focused type result cannot establish S86 integration.

### opaque-predicate-language | high | A generic mapping mini-language is executed without closed compile-time validation

`_classification_rules.py:34-104` parses semicolon-delimited strings from a generic mapping payload, but no typed schema or compiler validator closes the permitted fields and values. Unknown fields and unknown expected values do not raise during projection; they become predicates that return false and allow a later rule, including the terminal unknown row, to win. `classification.py:792-827` also validates only a subset of row structure and ignores undeclared extra rows and keys. A malformed or partially migrated legal rule can therefore publish and degrade into a different classification instead of being refused before publication.

### python-owned-legal-semantics | high | Runtime Python reconstructs filing-affecting meanings absent from the authority declaration

`_classification_rules.py:48-81` defines the membership of `outside_comunidad`, `outside_tai`, `b2b_or_public`, `b2c_or_public`, and the `domestic_default` exclusions in Python. `classification.py:820-825` independently infers reverse-charge treatment from a Python-authored category set. These are legal decision-table meanings, not neutral predicate-execution mechanics, and the registry fact does not declare the expansions or reverse-charge flag. The implementation therefore moves tokens into the authority while retaining operative legal semantics as a parallel Python authority path.

## Recommendations

- For `dual-authority-source`, accept exactly one source at each API or reject simultaneous `operation` and `authority` arguments before resolution.
- For `collection-time-authority`, use a scoped fixture that obtains the admitted authority without import-time I/O and keeps projection plus classification within one operation lease; preserve the real authority path in the test.
- For `result-invariant-gap`, restore the invariant at an operation-aware construction boundary and keep the negative contract without ambient registry access.
- For `non-atomic-operation-cutover`, complete the operation-parameter consumer migration in the owning plan scope before treating the focused result as integration evidence.
- For `opaque-predicate-language`, introduce a closed typed predicate/row schema with exhaustive compiler validation, including unknown field/value, missing field, duplicate clause, extra row/key, priority, dynamic-category, and terminal-row refusal tests.
- For `python-owned-legal-semantics`, declare territorial/status groups, kind exclusions, and reverse-charge behavior as typed registry data with provenance; leave Python responsible only for validated predicate execution.
### dangling-provisional-consumer | high | Committed application code still imports the rolled-back projection API

`classification_assembly.py:109` imports `resolve_iva_classification_inputs`, and `classification_assembly.py:839`, `classification_assembly.py:948`, `classification_assembly.py:1077`, and `classification_assembly.py:1275` call it, while no definition remains under `src` or `dev`. These references arrived through concurrent committed work, not the rollback itself, but they prevent the repository from importing coherently after the safe module restoration.

## Post-rollback disposition

The rollback removes `classification_predicate_from_declaration` completely: no Python reference remains, and the current `_classification_rules.py` blob exactly matches its pre-`50f24bf718` blob. The `opaque-predicate-language`, `python-owned-legal-semantics`, and collection-time test-migration findings are therefore disposed as rolled back, not accepted implementation. The baseline `dual-authority-source`, `result-invariant-gap`, and `non-atomic-operation-cutover` findings remain open, as does the newly exposed dangling committed consumer above.

No RC1 implementation is accepted or represented as complete. The S81 authority blocker remains the governing next decision: classification requires an approved closed typed fact-family/schema and compiler validation that puts legal meanings in registry authority before runtime projection can be reintroduced.
