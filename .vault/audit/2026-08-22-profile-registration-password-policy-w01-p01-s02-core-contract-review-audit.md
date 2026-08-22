---
tags:
  - '#audit'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7783e0e512d3f4f78c1089575e8666ee90f0ec50d7b9363aa1083c977b5b52fd'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
  - "[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-registration-password-policy with a kebab-case feature tag, e.g. #foo-bar.
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

# `profile-registration-password-policy` audit: `w01 p01 s02 core contract review`

## Scope

Commit `63617870cb` and current HEAD were reviewed against the accepted canonical
credential capability ADR, its research and incident reference, the active plan, and
the S02 execution record. Semantic discovery located the governing core and custody
surfaces before exact-symbol confirmation. The review covered the complete
`src/cadrumo/core/_credentials.py`, every live exact consumer of its removed and added
symbols, the public core facade, the commit diff, direct Unicode-boundary probes, and a
representative registration test collection.

The pure assessment correctly counts Python Unicode scalar values after refusing
surrogates, preserves composed and decomposed inputs without rewriting, accepts 15
through 256 scalars and 1,024 UTF-8 bytes, exposes only numeric facts plus finite typed
results, and keeps strength advisory. The byte-first ordering for overlapping upper
bounds is coherent with the requirement for an independently observable 1,025-byte
refusal: under Unicode's four-byte maximum, a 1,025-byte candidate necessarily also
exceeds 256 scalars. Ruff, formatting, and diff-hygiene checks passed for the owned
module. The repository state is nevertheless not independently coherent for the reason
below.

## Findings

### step-atomicity | high | The committed core change breaks the live public facade and registration import graph

`src/cadrumo/core/_credentials.py:37-51` removes
`NIST_PASSPHRASE_MIN_LENGTH`, `PassphraseStrength.TOO_SHORT`, and the public
`character_class_count`, and `src/cadrumo/core/_credentials.py:86` changes
`assess_passphrase_strength` from a required `minimum_length` API to a one-argument
advisory API. However, `src/cadrumo/core/__init__.py:155-159`,
`src/cadrumo/core/__init__.py:535`, `src/cadrumo/core/__init__.py:752`,
`src/cadrumo/core/__init__.py:1003`, and `src/cadrumo/core/__init__.py:1125` still
publish or lazily resolve the deleted names, while
`src/cadrumo/application/user_profile/_registration.py:39`,
`src/cadrumo/application/user_profile/_registration.py:63`,
`src/cadrumo/application/user_profile/_registration.py:115`, and
`src/cadrumo/application/user_profile/_registration.py:152` still import or call the
old contract. `src/cadrumo/adapters/inbound/tui/_registration_screen.py:120` and
`src/cadrumo/adapters/inbound/tui/_registration_screen.py:131` also still require the
deleted enum member. Conversely, none of the new profile-specific types, constants, or
assessment function is exposed through the public core facade yet.

This is an observable repository break, not merely an unintegrated new feature:
accessing `cadrumo.core.NIST_PASSPHRASE_MIN_LENGTH` raises `AttributeError`, and pytest
cannot even collect `src/cadrumo/application/user_profile/tests/test_registration.py`
because `_registration.py` cannot import the removed constant. The S02 execution record
acknowledges this state at lines 47-49, but acknowledgment does not make a committed Step
independently coherent. S03 only changes the facade and S07 is deferred until W02, so
following the current plan literally would preserve broken application and TUI imports
across multiple intervening commits. This violates the architectural direction of a
public core authority consumed through stable boundaries and prevents meaningful gates
for subsequent Steps. It is HIGH and blocks continuing until the commit boundary or
Step sequence is repaired.

## Recommendations

- Resolve `step-atomicity` before dispatching further implementation. Make the canonical
  contract, public facade, and all compile-time consumers one coherent landing unit,
  either by amending/squashing the dependent S03 and consumer migration into S02 or by
  immediately landing the full dependency-ordered migration before unrelated W01 work.
  Do not restore aliases, shims, `TOO_SHORT`, or the eight-character constant: the
  accepted ADR requires their deletion rather than compatibility scaffolding.
- After migration, prove the repaired boundary with at least a core public-facade import
  probe and test collection for application registration and TUI registration, in
  addition to the planned core boundary tests. Keep the byte-before-upper-scalar
  precedence explicit in those tests by asserting a 257-astral-scalar / 1,028-byte
  candidate maps to `TOO_MANY_UTF8_BYTES`, while 257 ASCII scalars map to
  `TOO_MANY_SCALARS`.

## Resolution

The HIGH `step-atomicity` finding was resolved immediately in the S03 remediation
landing before unrelated W01 work. The core facade now exports every canonical
profile-password bound, assessment type, refusal reason, and assessor while the
deleted generic floor, refusal-strength member, and character-class export remain
absent. Registration, rotation, CLI composition, TUI rendering, package facades, and
their immediate tests consume the canonical assessment directly; no alias, shim, or
restored legacy symbol was introduced.

Registration and rotation refuse every invalid prospective password before custody
work. The existing precise localized minimum-length key remains in use for the lower
bound, while other expected shape refusals use the existing localized generic custody
refusal until the locale-owned reason-specific work in S07. The TUI renders invalid
assessments as refused independently of advisory strength and clears stale refusal
styling when the candidate becomes valid.

A public-facade import probe passed, both affected test modules collected all 15 tests,
and the focused real-behavior registration, rotation, and headless-TUI run passed all
22 tests. Exact repository search finds no live consumer of the removed constant,
enum member, public helper, application assessment model, or application minimum alias.
The remaining byte-precedence and exact Unicode matrix belongs to S04 as recommended.
