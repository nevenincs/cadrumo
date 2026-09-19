---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:3e35843edb19142ce64b197d0d927ac4a1d15566ded9c790df5c2ab15562a06b'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `s38 fixed width codec`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

Audited W02.P03.S38 against the accepted generator-authority decision, its linked source-authority and S08 gap research, the S37 execution record, the plan's strict-consolidation row, and the final production and test diff. The review covered the core decimal coercer, registry schema and codec, filing writer/parser/verifier, outbound registry renderer, public facades, deletion of the dormant adapter `_formats` tree, structural audit tests, and the amended accepted fichero-BOE decision.

The final snapshot has a single public field-codec owner, routes cross-package consumers through the registry facade, hydrates padding, justification, and encoding as closed public enums, rejects absent generic numeric values, rejects fractional integers and invalid boolean/sign spellings, re-renders parsed values to reject noncanonical wire spellings, and deletes the dormant adapter codec without a shim. The reviewed S38 tests contain no mock, fake, stub, monkeypatch, skip, xfail, or tautological expected-value shortcut.

Independent final verification passed: 137 focused tests, scoped Ruff, and scoped strict BasedPyright with zero diagnostics. The whole-vault check returned status `ok` with zero errors; its 60 warnings are pre-existing or peer-owned hygiene inventory, including no ADR-status, dangling-link, reference, encoding, or structural error. The broader registry-dependent lane remains outside this proof because concurrent legal-catalogue work still makes that shared lane unstable.

## Findings

### numeric-absence-default | high | Missing numeric values became filed zeroes

The initial review found the canonical codec mapping `None` and empty text to `Decimal(0)`, the outbound renderer supplying missing casillas as empty text, and the verifier replacing absent expected values with zero.

Resolution: **RESOLVED.** Generic numeric coercion now accepts only the strict public decimal coercer; `None` and empty text refuse. The verifier no longer defaults an absent expected value, and cross-route tests require both renderers to refuse missing or empty generic numeric values. The only absent-to-zero path left is the explicit S37 selected/unselected checkbox policy, whose reviewed policy contract owns that semantic.

### schema-axis-redeclaration | high | Padding and justification had a second private authority

The initial review found registry `_export.py` declaring private padding and justification Literals, returning raw tokens from binding-field derivation, and tests importing those private aliases.

Resolution: **RESOLVED.** The private aliases are deleted; binding-field derivation returns the public `ExportPadding` and `ExportJustification` enum members, tests assert those members, and the structural guard covers the schema-producing site as well as runtime consumers.

### accepted-adr-conflict | high | An accepted decision mandated the deleted adapter codec

The initial and first remediation reviews found the accepted 2026-04-22 fichero-BOE ADR retaining the generic adapter `_formats` runtime while S38 deleted it.

Resolution: **RESOLVED.** The accepted record now carries a 2026-08-10 amendment that explicitly identifies itself as the latest governing fixed-width runtime clause, preserves registry TOML as layout-data authority, replaces only the prior retention clause, and overrides contrary runtime-home language in the historical sections. It assigns schema validation and render/parse semantics to the public registry-domain codec, constrains core to exact numeric coercion, names every active consumer, preserves the distinct S37 policy and XML-boolean contracts, and requires deletion without aliases or shims. The amendment remains accepted and does not introduce a competing ADR, a false supersession edge, or ambiguity about which historical clause governs.

### encoding-boundary | medium | The record encoding axis was raw and failed differently by route

The initial review found `ExportRecordDefinition.encoding` typed as bare `str`, with an invalid token hydrating and failing late through different application and adapter exceptions.

Resolution: **RESOLVED.** A public closed `ExportEncoding` axis now hydrates the schema for the supported ASCII, CP1252, ISO-8859-1, ISO-8859-15, and Latin-1 spellings; the adapter consumes the typed value directly; an invalid codec token is rejected at schema validation.

### deleted-surface-reference | medium | Core prose pointed at a removed private symbol

The initial review found `core/external_constants.py` documenting `ISO_8859_1_ENCODING` through the deleted private `_formats._record_spec.FicheroBoeEncoding` type.

Resolution: **RESOLVED.** The dangling private-symbol reference is removed and the prose now describes the public registry-codec spelling.

## Recommendations

No follow-up is required for S38. Preserve the final invariants: generic numeric absence refuses; explicit zero emits zero; only an explicit value policy may project absence to wire data; schema producers and runtime consumers share the public closed axes; and future fixed-width behavior changes amend the public registry codec contract rather than recreating an adapter-owned taxonomy. Re-run the broad registry-dependent lane when concurrent legal-catalogue work stabilizes, without weakening this PASS boundary.
