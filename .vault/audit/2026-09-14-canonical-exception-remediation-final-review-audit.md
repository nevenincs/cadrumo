---
tags:
  - '#audit'
  - '#canonical-exception-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:ee2e31f5ad60c559bba47cdeb115ff9b6743f629bf584fda006ebff430793744'
related:
  - "[[2026-09-14-canonical-exception-remediation-plan]]"
  - "[[2026-09-14-canonical-exception-remediation-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace canonical-exception-remediation with a kebab-case feature tag, e.g. #foo-bar.
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

# `canonical-exception-remediation` audit: `Canonical exception remediation final review`

## Scope

Audited the canonical-exception-remediation implementation against its accepted
decision, production inventory, migration plan, and operator acceptance criteria.
The review covered production exception ancestry, the 80-identity migration closure,
registry shards and aggregators, locale catalogues, envelope rendering and redaction,
representative raise/catch boundaries, the two global exception gates, and the TUI
source-descriptor repair. Validation evidence supplied by the executing supervisor was
also reconciled with read-only AST and registry checks.

## Findings

### builtin-raise-boundaries | high | Production runtime failures still escape as unregistered built-ins

A repository-wide AST check finds 2,367 direct production raises of built-in
exceptions: 1,890 `ValueError`, 218 `TypeError`, 147 `RuntimeError`, and 112 other
built-in failures. Some are validator or Python-protocol boundaries, but they have not
been classified or proven as the accepted ADR requires. The residual set includes
plain operational failures rather than validator contracts, for example the
uncomposed bucket event-history port and the installed-workbench session invariant.
The implementation therefore cannot establish that production failures use the
registered Cadrumo model or that built-in translation survives only at narrow,
evidence-backed external boundaries.

### dual-builtin-ancestry | high | Thirty owned exception definitions retain unexplained built-in bases

Thirty production exception declarations still combine a registered Cadrumo root
with `ValueError`, `RuntimeError`, `KeyError`, or `ImportError`. Examples include
`PeriodError`, `DomainValidationError`, the IVA compensation family,
`AggregationConfigError`, four authentication-result failures, two Modelo workspace
failures, and two profile-custody failures. The accepted ADR explicitly says internal
catch convenience does not justify dual inheritance and requires protocol evidence
for every retained built-in outward type. No per-family evidence or boundary test was
found, so the repository-wide definition review is incomplete even though no owned
class now roots *only* at a built-in.

### envelope-message-redaction | high | Migrated envelopes can expose raw dynamic arguments and bypass localization

The campaign adds localized registry messages, but 266 production calls construct a
campaign exception with a positional argument. `resolve_error_message` prefers that
argument over the registered message key, while `scrub_error_context` only redacts
structured context. A live check of `AuthorityArtifactUnavailableError` placed an
absolute private path verbatim in the serialized envelope message, and
`M036DeclarationNotFoundError` placed a supplied declaration identifier verbatim in
the message. Consequently the new registry identities do not yet guarantee stable,
localized, redaction-safe downstream envelopes at their real raise sites.

### registry-source-closure | medium | The registry gate does not prove declaration closure in both directions

The live registry contains 697 unique FQNs and 697 unique codes, and every class the
source scanner recognizes has a row. However, the same comparison reports 15 registry
rows absent from the scanner's descendant set. Four are campaign manifest exceptions;
their ancestry is written through the `_CoreValidationError` import alias, which the
source resolver does not recognize as a descendant. The enforcement test also lacks
an inverse assertion rejecting stale rows. Runtime binding covers these classes, but
the source-backed gate does not prove the claimed exact 80-identity closure or protect
it against orphan declarations.

### canonical-identity-enrollment | low | The 80 migrated identities are unique and locale-complete

The campaign registry set contains exactly 80 FQNs and 80 codes: 79 rows using new
`canonical_*` locale keys plus the existing `FormerProductStateError` key. Across the
full registry, all 697 FQNs and all 697 codes are unique. Each of the 79 new keys is
present and non-empty in English, Spanish, Catalan, and Hungarian, yielding 320
successful campaign locale renders when the reused core message is included.

### direct-root-hygiene | low | Owned direct built-in exception roots were removed

The production AST now finds only `CadrumoError` and the source-only Playwright
fallback rooted directly in built-ins. The latter remains the documented optional
dependency type shim. All temporary rationales on the migrated owned classes are
gone; only the canonical root and Playwright boundary retain declarations.

### descriptor-remediation | low | Source descriptors no longer override reserved class metadata

The exception gates use ordinary `module`, `qualname`, `name`, and `bases` data. The
TUI private-attribute-shadowing descriptor follows the same contract, and its corrected
relative inventory import permits the isolated integration test to collect and pass.

### validation-scope | low | Focused gates pass in isolation and core collection is restored

The isolated exception hygiene and registry run passed 13 tests; six focused hierarchy,
registry, and envelope modules passed 23 tests; the TUI descriptor integration test
passed once with its required marker selected; and core collection completed with
1,703 tests. The ordinary two-gate invocation still reports 13 setup errors from the
shared runtime fixture's unrelated authority-pin requirement, so its green evidence is
the deliberately isolated gate run rather than the repository-default fixture path.

## Recommendations

- For `builtin-raise-boundaries`, inventory and classify direct built-in raise sites by
  validator/protocol boundary versus owned operational failure. Migrate the latter and
  add narrow outward-translation tests for each retained protocol case.
- For `dual-builtin-ancestry`, remove the built-in secondary bases unless an
  authoritative protocol requires them; record the evidence and exercise both the
  internal registered error and outward built-in behavior where retained.
- For `envelope-message-redaction`, move dynamic values into structured context and
  construct migrated failures with registered translation keys. Add real-constructor
  envelope tests containing secret-like paths and identifiers, not only empty-instance
  locale renders.
- For `registry-source-closure`, resolve imported aliases in the descendant walk and
  assert both missing and orphan registry identities. Pin the exact campaign closure
  in a focused regression test.
- Re-run the documented focused gates and final core collection after these blockers
  are remediated. Do not mark the campaign complete on the current implementation.

## Resolution

### operational-builtin-raises-resolution | low | Owned RuntimeError construction was eliminated

All production `RuntimeError` construction sites were migrated to the registered
`InternalInvariantError`. The source hygiene gate now rejects every production
`RuntimeError(...)` call rather than checking only direct raise syntax. Directly
coupled catches, factories, and identity tests were updated.

### dual-builtin-ancestry-resolution | low | Mixed built-in ancestry was eliminated

No registered production exception retains a secondary built-in base. Pydantic
callbacks translate registered failures to `ValueError` only at the validator
boundary and retain the registered failure as `__cause__`.

### envelope-message-redaction-resolution | low | Public messages are registry-owned

Campaign registry entries select localized public messages even when exceptions
carry positional diagnostic text. Path, identifier, and internal-invariant envelope
tests confirm that diagnostics do not enter serialized public messages.

### registry-source-closure-resolution | low | Registry closure is bidirectional

The source scanner resolves relative aliases and rejects both missing registrations
and orphan rows. Registry identities and codes are unique.

### stale-builtin-contract-documentation-resolution | low | Documentation matches canonical ancestry

Production documentation no longer promises built-in ancestry. Pydantic behavior is
described as narrow boundary translation with the registered failure retained as the
cause.

### final-verdict | low | Canonical exception remediation accepted

Formal re-review returned PASS with no unexplained built-in-root exception, mixed
ancestry, production `RuntimeError(...)` construction, duplicate registration,
unsafe migrated envelope message, or unresolved catch-site regression.
