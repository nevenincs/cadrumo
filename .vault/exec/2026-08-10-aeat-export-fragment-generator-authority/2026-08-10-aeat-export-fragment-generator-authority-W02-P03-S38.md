---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:fe4a83d3a5c354a91c204e041e2b467a82df04bb5f1ace7e544bef89edb33a21'
step_id: 'S38'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s38-fixed-width-codec-audit]]"
---
# Consolidate strict fixed-width integer, money, boolean, padding, and sign coercion behind canonical public domain policies consumed by the filing writer, parser, verifier, and outbound registry renderer, deleting redeclared normalization behavior, rejecting lossy truncation and silent zero-or-blank substitution, and proving both production routes emit and refuse identically

## Scope

- `src/cadrumo/core/decimal/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/adapters/outbound/aeat/export/`

## Description

- Add one public registry-domain fixed-width codec for strict integer, decimal, money, boolean, text, padding, sign, and encoding behavior.
- Reuse exact finite decimal coercion and canonical euro-cent rounding without lossy truncation or invalid-value substitution.
- Hydrate padding, justification, and encoding as public closed axes and refuse contradictory field shapes at schema load.
- Delegate filing writes, fixed-width parsing, exact-wire verification, and the active outbound registry renderer to the canonical codec.
- Keep ordinary `X`/blank booleans distinct from explicit numeric checkbox policies and keep XML dictionary boolean vocabularies format-specific.
- Delete the adapter-local `_formats` model and its duplicate coercion, padding, sign, serialization, and deserialization implementations.
- Replace stale semantic-audit and round-trip inventory references with the canonical owner and real production-route proof.
- Add exact-byte parity, strict refusal, parser mutation, amendment-header, schema-axis, and structural single-owner tests.

## Outcome

Fixed-width filing values now cross one exact semantic-to-wire boundary. Integer inputs must be integral, numeric inputs must be canonical finite values, money rounds through `round_to_cents`, signed money uses the declared leading space or `N` byte, and all padding modes fill the complete declared slot. Missing or empty generic numeric values refuse instead of becoming zero; only an explicit S37 value policy may project absence. Ordinary booleans accept only bool, blank, exact `X`, or the application producer's exact `true`/`false` spelling and emit canonical `X`/blank bytes.

The parser validates field width, policy wire shape, declared padding, sign, and boolean tokens, then re-renders non-policy parsed values to reject noncanonical wire spellings. XML dictionary `LGC` and `S_N` booleans retain their separate official `1`/`0` and `SI`/`NO` vocabularies. Verification compares parsed raw bytes against the canonical rendering of the expected value by record-and-field identity.

The registry schema owns public `ExportPadding`, `ExportJustification`, and `ExportEncoding` closed axes. Binding-derived fields consume those axes directly. The filing writer and outbound registry renderer emit and refuse identically through the public codec; the deleted adapter `_formats` package has no remaining production reference or semantic-audit exception.

Focused domain, filing, value-policy, parser, and outbound-renderer verification passed with 132 tests. Focused structural-audit inventory verification passed with 3 tests. Scoped Ruff passed and strict BasedPyright reported zero diagnostics. The import architecture gate kept the registry, domain, and core boundaries; its aggregate result remained red only for concurrent `application.storage.sync_runs` imports outside S38.

## Notes

Mandatory semantic search found and remediation removed the application integer truncation, tolerant invalid-money zeroing, ordinary-boolean blanking, adapter padding/sign duplication, private binding padding/justification aliases, and the deleted encoding taxonomy's stale reference. A final production search returns the registry codec as the only fixed-width value-policy owner. Generic calculation rounding, XML dictionary formatting, and record-positive-value guards remain distinct semantics rather than wire-codec redeclarations.

The accepted 2026-04 fichero-BOE ADR retained an obsolete adapter `_formats` location in a later amendment. S38 closure waited for the separately owned in-place ADR refinement; no ADR text was changed in this execution slice.

A broader registry-dependent test attempt reached 175 passes before concurrent legal-catalogue work caused 29 registry-load failures; the same peer state also blocked the historical implicit-decimal and total-padding tests that construct full registry providers. Two unrelated outbound export model tests failed on newly tightened `justificante_csv` fixtures, and one repository audit test failed on a concurrent complexity-baseline path. These failures were preserved and not modified. No S38-owned focused gate failed on the final snapshot.
