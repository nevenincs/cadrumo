---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f7bc9df6541fda0bdf02216e05908c16d04963b577aaaf8756525ff9401e2288'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `s41 singleton value policy`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

Independent review of S41 against the active plan row, accepted generator-authority ADR and fixed-width runtime amendment, and the S31, S37, S38, and S40 execution and audit records. The review covered the complete public `ExportValuePolicy` axis, required and optional typed schema surfaces, enumeration-domain authority, semantic and wire enforcement through the sole registry fixed-width codec, removal of the development-only `SingletonValuePolicy` alias, S32 mapper propagation, canonical-home guards, and focused real tests.

The final snapshot has one public policy enum owner and one registry fixed-width codec. Development profiles consume the public required policy type rather than a local literal taxonomy. Runtime fields use the optional public type, and an enumeration domain is valid if and only if its policy is `ENUMERATED_DIGITS`. The mapper projects all eleven public policies through an exhaustive keyed shape contract with explicit refusal for an unsupported policy. No fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored production logic appears in the reviewed tests.

The final import boundary routes development semantic-map `CasillaId` through its canonical core home. The reviewer independently collected 274 focused policy, codec, parser, render-profile, and real mapper passes; scoped Ruff passed and strict scoped BasedPyright reported zero errors, warnings, or notes. The executor's broader selected lane collected 290 passes with the same clean static gates. The requested all-policy mapper test invokes the real S32 derivation for all eleven enum members and asserts the resulting production `ExportFieldDefinition` shapes plus exact enum-key coverage. Two broader provenance tests remain excluded because paused S32 work has not yet reconciled their signature and schema expectations; no S41 test fails.

S41 intentionally evolves the historical S40 snapshot: generic policy-free `allowed_values` is removed and the domain becomes the required member set of the canonical enumeration policy. This does not create a competing authority or conflict with the accepted fixed-width amendment; it completes the later approved plan row while preserving the registry codec as runtime owner.

## Findings

### canonical-enumeration-redeclaration | high | Generic allowed-values fields remained beside the promoted enumeration policy

The initial review found the schema accepting `allowed_values` without a policy while also accepting and requiring the same domain with `ENUMERATED_DIGITS`. Both declarations rendered and parsed identically, leaving authors two runtime representations for one enumeration.

Resolution: **RESOLVED.** Schema hydration now requires `allowed_values` if and only if `value_policy` is `ENUMERATED_DIGITS`. Policy-free domains and domains attached to every other policy refuse. Checkbox member evidence remains development-only and is not emitted into the runtime field. The public enumeration policy and its required member set are now one composed authority.

### semantic-policy-roundtrip | medium | Parsed year, month, and day values could not be rendered again

The initial review found integer-shaped policy wires generic-parsed to `Decimal`, while the full-year, month, and day projectors accepted only integer or digit-string semantics. Render-parse-render therefore failed for those invertible policies, and the original test asserted the two directions separately.

Resolution: **RESOLVED.** Parsed full-year, month, and day wires normalize to renderer-admissible integers. The non-invertible final-two-digits year uses a typed `ParsedExportPolicyWireValue` that retains its validated policy and wire token without pretending to reconstruct the original four-digit year; the projector accepts only the matching typed token. The type is carried through the real parsed-payload boundary. The all-eleven test now asserts render, parse, and re-render equality, and the payload parser directly asserts the short-year wrapper.

### mapper-policy-fallthrough | medium | The S32 mapper silently mapped unhandled policies to integer shape

The initial mapper explicitly handled date, implied-decimal, and digit-identity policies, then sent every remaining current or future policy through a generic integer branch. That allowed a new public policy to acquire an unreviewed shape instead of refusing.

Resolution: **RESOLVED.** A complete public-enum-to-shape mapping names all eleven current members. Lookup absence refuses explicitly, as does an unknown shape. The real mapper regression constructs each reviewed singleton rule, invokes `_profile_singleton_derivation`, verifies policy, type, padding, date format, and enumeration domain on the produced `ExportFieldDefinition`, and asserts exact key equality with the public enum.

### semantic-enumeration-width | medium | Profile validation confused canonical semantic members with padded wire spellings

The initial profile required every enumeration member's text length to equal the official field width, while the public schema rejects leading-zero spellings and the codec owns zero padding. A two-byte enum could therefore express neither canonical `("1", "3")` nor padded `("01", "03")` consistently.

Resolution: **RESOLVED.** The authored profile now requires canonical ASCII integer tokens, rejects leading zeros, permits member length up to the declared integer width, and leaves padding exclusively to the canonical codec. Direct width-two acceptance and padded-token refusal regressions cover the repaired boundary.

## Recommendations

No S41 follow-up is required. Preserve the single public enum and codec owners, enumeration policy/domain iff relationship, explicit non-invertible short-year wrapper, render-parse-render proof for all policies, exhaustive mapper key coverage, canonical semantic enumeration members, and fail-closed unsupported-policy behavior. Keep the focused 290-test selector and zero-diagnostic static gates as the S41 regression boundary. Reconcile the two broader provenance expectations only within the paused S32 scope, without weakening this PASS.
