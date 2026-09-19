---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:8b12abb7577f11158367279182308b6fd33b46a11389e26fbd9f45d0bd3122bf'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S14 official box status`

## Scope

Reviewed W02.P05.S14 against the accepted canonical-derivations decision, campaign plan, and repository quality constraints. Scope was limited to `_official_box_status.py`, the core facade, and `test_official_box_status.py`. The required contract is one core-owned `OfficialBoxStatus` `StrEnum`, exactly three named wire members, direct public identity, and a structural gate that excludes duplicate declarations and aliases without test doubles.

## Findings

### alias-exactness-gate | medium | Enum iteration does not prove the required absence of aliases

The current production enum is correct: `OfficialBoxStatus.__members__` contains exactly `ADDRESSED`, `REPRESENTED_VIA_BINDING`, and `UNDEFINED`, with the required wire values. The public facade imports the owner directly and exposes the same class identity, and the AST declaration scan finds one class declaration under the package.

The test's exact-member assertion uses `tuple(OfficialBoxStatus)`. Python enum iteration omits aliases. A fourth declaration such as `ADDRESSED_ALIAS = "addressed"` would therefore leave both the asserted enum tuple and the asserted value tuple unchanged, while violating S14's explicit no-alias closed-vocabulary contract. An independent probe reproduced this behavior: iteration returned the same three canonical members while `__members__` exposed four names. The gate consequently proves current iterable values and sole class ownership, but not the required exact member-name set.

No other findings. The scoped source contains no second declaration, compatibility alias, duplicate facade definition, fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct. The AST scan imports real production ownership and is otherwise non-tautological.

## Verification

- Focused core test: 1 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed, with only the existing CRLF normalization warning on the facade file.
- Exact symbol sweep: one class declaration, one owner `__all__` entry, one facade import, and one facade `__all__` entry.
- Runtime identity: `cadrumo.core.OfficialBoxStatus` is the owner module's class.
- Current enum membership: exactly the three required names and values.
- Alias bite probe: a same-valued fourth name is absent from enum iteration but present in `__members__`, confirming the test gap.
- Prohibited test-construct scan: no hits.

## Recommendations

Tie the exact closed vocabulary to the public enum-name registry, for example by asserting the ordered keys of `OfficialBoxStatus.__members__` are exactly the three required names. Retain the existing value, facade-identity, and AST sole-declaration assertions.

Verdict: **CHANGES REQUESTED.** The S14 implementation is currently correct, but its mandatory structural proof does not reject enum aliases and therefore does not lock the explicit no-alias acceptance contract.

## Re-review resolution

### alias-exactness-gate | resolved | Exact member-name assertion rejects aliases

The corrected structural test now asserts the ordered keys of `OfficialBoxStatus.__members__` are exactly `ADDRESSED`, `REPRESENTED_VIA_BINDING`, and `UNDEFINED`. Because `__members__` includes aliases, the same-valued fourth-name probe that escaped enum iteration can no longer pass. The original iterable-order, wire-value, public-identity, and sole AST declaration assertions remain intact.

Independent re-verification found no new findings. The focused test passed; scoped Ruff passed; scoped BasedPyright reported 0 errors, 0 warnings, and 0 notes; scoped `git diff --check` passed apart from the already noted line-ending warning; and a direct runtime probe confirmed both exact `__members__` membership and facade identity.

Final verdict: **PASS.** The MEDIUM alias-exactness finding is resolved, and W02.P05.S14 now locks the sole public core identity, exact names, exact wire values, and absence of aliases or duplicate declarations.
