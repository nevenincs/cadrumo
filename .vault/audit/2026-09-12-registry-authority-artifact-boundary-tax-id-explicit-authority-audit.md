---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:40236e062fa23f113fe2e4e4c469eae80d6b342e083a01837967d74f2a76e63b'
related:
  - "[[2026-09-12-registry-authority-artifact-boundary-tax-id-bootstrap-boundary-reference]]"
---
# `registry-authority-artifact-boundary` audit: `Explicit tax-ID authority boundary`

## Scope

Reviewed the current explicit Spanish tax-ID authority implementation and caller migration against the accepted registry-authority artifact decision, its execution plan, the tax-ID bootstrap reference, and the mandatory architecture, authority-flow, calculation-grounding, no-legacy, and quality-gate rules. The review covered the pure core format value and validation kernel, `SubjectTaxId` relocation, runtime authority adapters, `NifString` context injection, fact-first candidate compilation, facts-first artifact decoding, product/software identity separation, direct callers, authored fact `0102`, and focused tests.

Verification included exact symbol/import searches, a clean-process package-resource bootstrap probe, direct malformed-format projection, focused identity/schema/artifact/compiler tests, API-documentation tests, and Ruff. The resource probe confirmed that importing `bundled_data` loads neither the tax-ID stack nor registry authority/schema modules. The initial focused boundary run produced 62 passing tests and one migration collection error. A subsequent source/software suite produced 20 passing tests and one failure caused by broad concurrent registry validation defects unrelated to this boundary. Later focused runs were partly blocked during fixture setup by a concurrent `categories.profile` artifact/source mismatch; the isolated candidate ownership test itself passed.

## Findings

### subject-tax-id-test-caller | high | A test caller retained the removed core `SubjectTaxId` location

`test_tax_id_identity_token_type.py` imported `SubjectTaxId` from `core.identity.tax_id` after the canonical alias moved to `domain.calculations.registry.tax_id_format`. The old surface was correctly absent, so collection failed instead of masking the incomplete atomic relocation. This was corrected during review; an exact import search now finds no Python caller importing the alias from its removed core home, and Ruff is clean for the corrected test.

### software-identity-import-order | low | The relocated software-identity module failed Ruff import ordering

`domain.filing.software_identity` mixed an absolute domain import between relative core imports. Ruff reported `I001`. This was corrected during review and the focused Ruff check now passes.

### candidate-format-ownership-proof | medium | Candidate ownership initially had only a static no-artifact gate

The implementation compiled authored fact `0102` before Modelo validation and threaded the resulting format through Pydantic context, but the existing gate only searched the compiler import closure for `bundled_authority` calls. It did not prove that a candidate whose format differs from the installed artifact accepts candidate-only identifiers and refuses installed-format identifiers. A self-contained behavioral test was added during review. It traps `bundled_authority`, compiles an altered authored fact, validates through the real `NifString` context, accepts the altered-only identifier, and rejects the installed-format identifier. The isolated test passes.

### malformed-format-shape | high | The format projection accepts malformed and undeclared mapping shapes

`tax_id_format_from_declarations` checks a required subset but does not require the exact declaration vocabulary, so unknown keys are silently ignored. `SpanishTaxIdFormat.__post_init__` also accepts a multi-digit NIE substitution even though each leader substitution is one decimal digit used to preserve the identifier body's declared width. A direct probe successfully constructed a format containing both `tax_id.typo = "ignored"` and `tax_id.check.nie_prefix.X = "00"`. Because the same projection bootstraps both candidates and artifacts, a digest-consistent malformed fact can become operative rather than failing closed. The current negative artifact test removes one required key only and does not detect these malformed-but-present cases.

### subject-tax-id-documentation-caller | medium | Documentation ownership still points at the removed core alias

The API stub ownership table in `dev.docs.apidocs.manager` still declares `SubjectTaxId` under `cadrumo.core.identity.tax_id`, and its owning test still requires that obsolete target. Several production and test docstrings also link the removed qualified name. The API documentation test reports the obsolete `cadrumo.core.identity.tax_id.SubjectTaxId` target as unresolved. Other failures in that run involved concurrently drifting aliases and a `categories.profile` fixture-setup mismatch, but they do not explain this exact stale target. Architecture rules require production code, tests, dynamic references, and user documentation to move atomically with a public symbol.

### tax-id-fact-grounding | high | Fact `0102` evidence does not substantiate its operative declarations

The authored fact's fourteen filing-affecting width, leader, substitution, and checksum declarations cite one Modelo 036 procedure source with required text limited to the generic phrase `numero de identificacion fiscal`. That evidence establishes the presence of a tax identifier but not the exact widths, leader partitions, prefix substitutions, NIF letter table, CIF control partitions, or CIF letter table now used to accept and reject filing identities. Moving these values out of Python establishes the authority boundary, but it does not make them filing-grade without specific official AEAT or BOE evidence for the exact operative claims.

## Re-review

### malformed-format-shape-re-review | high | Resolved: malformed declarations now fail closed

`tax_id_format_from_declarations` now enforces the exact declaration vocabulary derived from the declared NIE leaders, refusing both missing and unknown keys. `SpanishTaxIdFormat` requires every NIE substitution to be exactly one decimal digit. Focused strict-format and NIF regressions cover unknown declarations and multi-digit substitutions; the confirmed isolated run passed all eight tests. Ruff and formatting checks are clean.

### subject-tax-id-documentation-caller-re-review | medium | Resolved: API ownership follows canonical defining modules

The API alias table now assigns `SubjectTaxId` to `cadrumo.domain.calculations.registry.tax_id_format`, `TaxIdIdentityToken` to `cadrumo.core.identity.tax_id`, and `ContentDigest` to `cadrumo.core.identity.digest`. Its source-aware test recognizes PEP 695 aliases and asserts each generated target at its defining module. Exact review found no remaining qualified Python docstring reference to the removed core `SubjectTaxId` target. Both focused API alias ownership tests pass, and Ruff and formatting checks are clean.

The `tax-id-fact-grounding` HIGH finding remains open: the current source citation still establishes only a generic NIF-identification phrase, not the operative width, leader, substitution, and checksum values.
### tax-id-fact-grounding-increment | high | Partially resolved: format widths and leader families now have bundled AEAT evidence

Re-review of the two captured AEAT identity pages, their pinned `censo.toml` source records, and fact `0102` citations confirms that bundled primary text now substantiates the nine-character Spanish identifier width, the K/L/M prefixed-person NIF leader family, the X/Y/Z NIE leader family, and the complete A/B/C/D/E/F/G/H/J/N/P/Q/R/S/U/V/W juridical/entity leader family. It also substantiates the one-leading-character, seven-body-character, one-control-character composition for those families. The pinned source records name the captured corpus paths, byte sizes, SHA-256 digests, retrieval date, official AEAT URLs, and reviewed evidence tier; the direct byte/digest/citation-normalization verification passed.

The HIGH finding remains open, narrowed to declarations the enrolled text does not establish: the `ES` country prefix and its 11-character/2-character stripping geometry; the NIF/NIE checksum-letter table; the X/Y/Z-to-0/1/2 checksum substitutions; and the CIF digit-only, letter-only, mixed control partitions and `JABCDEFGHI` lookup table. The captured pages state that verification/control characters exist but do not provide those algorithms or tables. The Interior Ministry page found externally is research evidence only and is not treated as authority until its exact primary text is captured, pinned, and cited through the registry.
### tax-id-prefix-grounding-correction | high | Prefix and prefixed-width geometry are grounded

The enrolled legal unit `rd-1065-2007:art-25` points to the bundled consolidated BOE article 25 and requires the exact text that the identifier is prefixed with `ES` under ISO-3166 alpha-2. This directly grounds `tax_id.country_prefix = "ES"`. Combined mechanically with the separately grounded nine-character identifier width, prepending the literal two-character prefix proves `tax_id.country_prefixed_width = 11`; removing that same prefix proves `tax_id.country_prefix_strip_width = 2`. The prior narrowed scope is corrected accordingly. The HIGH finding now remains open only for the NIF/NIE checksum-letter table, the X/Y/Z-to-0/1/2 checksum substitutions, the CIF digit-only/letter-only/mixed control partitions, and the `JABCDEFGHI` CIF lookup table.
### nif-nie-checksum-grounding | high | Resolved: NIF and NIE checksum declarations have bundled official evidence

The captured DGOJ official page is pinned as `dgoj-nif-nie-control` with its corpus path, exact byte size, SHA-256 digest, retrieval date, official government URL, and reviewed source tier, and fact `0102` cites its normalized text. The source states division by 23, maps remainders 0 through 22 across the two complete letter-table rows, states the exact X/Y/Z-to-0/1/2 substitutions, and requires NIE control to use the same algorithm as NIF. Concatenating the cited remainder rows yields `TRWAGMYFPDXBNJZSQVHLCKE` exactly. The recorded SHA/byte/citation normalization, TOML parse, catalogue load, and source-catalogue verification all pass. This resolves the NIF/NIE checksum-letter table and the three NIE substitutions. The HIGH grounding finding now remains open only for the CIF digit-only, letter-only, and mixed control partitions and the `JABCDEFGHI` CIF lookup table.
## Recommendations

- For `malformed-format-shape`, define and enforce the exact declaration-key set, require each NIE substitution to be exactly one ASCII decimal digit, validate the remaining tables and leader values at their structural granularity, and add candidate and digest-recomputed artifact tests for unknown, malformed, missing, and conflicting declarations.
- For `subject-tax-id-documentation-caller`, move the API data-alias ownership entry and its expectations to `cadrumo.domain.calculations.registry.tax_id_format`, update every stale qualified docstring reference, and rerun the API stub and qualified-reference suites.
- For `tax-id-fact-grounding`, bind each operative declaration family to specific official evidence whose anchored text establishes the asserted values; keep the capability non-filing-grade until that evidence passes the normal legal/source grounding gates.
- Retain the resolved caller, lint, and candidate-ownership entries as the rolling review log and rerun their focused gates after concurrent artifact/source state stabilizes.
