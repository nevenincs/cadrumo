---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:39656c536b0a87261b7ea29cee56deedfb40b0781db90aa3cf0257d646593bc1'
step_id: 'S63'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-13-aeat-design-relayout-boundary-audit]]"
---

# Decide and record whether Modelo 200 and Modelo 390 should declare continuidad ids for their casillas as Modelo 303 already does

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/`

## Description

- Re-measured the row's three premises against HEAD rather than adopting
  them: the Modelo 303 stamp count, and whether Modelo 200 and Modelo 390
  declare none.
- Measured semantic-role uniqueness per modelo, which is what decides whether
  the sanctioned mechanical derivation of a chain id is admissible at all.
- Confirmed how the localisation cascade actually consumes the stamps, so the
  duplication cost the row asserts is grounded rather than assumed.
- Confirmed the completeness ratchet's scope, to establish whether anything
  forces the decision today.
- Recorded the ruling as a finding in the campaign audit document.

## Outcome

**The question resolves differently for the two modelos, and one of them
needed no decision.**

**Modelo 390 is already done.** The row records it as declaring none; that
did not reproduce. At HEAD it declares 88 continuity stamps across 88
casillas — its whole casilla set — landed by a commit that states it gave all
88 casillas a continuity identity ahead of the split, and the Spanish
catalogue carries 88 continuity chains with 88 non-null values. This half of
the row is closed as already satisfied.

**Modelo 200 is refused for now, with a precondition.** Continuity identity
is a grounded tax judgement against official sources, never a bulk mechanical
stamp. The one mechanical shortcut the grounding discipline sanctions —
deriving the chain id from the casilla's `semantic_role` — is admissible only
where the role identifies exactly one box per revision. Modelo 390 satisfies
that perfectly, 88 casillas over 88 distinct roles, with every chain id
exactly its role lowercased and underscore-to-dash converted and zero
mismatches; that is why an 88-stamp pass was legitimate there.

Modelo 200 does not. Its single revision declares 3,250 casillas over only
621 distinct roles: 308 roles unique, 313 colliding, and the colliding roles
cover 2,942 casillas, 90.5 percent of the modelo. The Estados Contables
tables dominate, one role covering a hundred or more distinct accounting
lines. Mechanical derivation there would merge distinct legal concepts into
one chain — the failure the discipline names as silent — so an honest Modelo
200 stamping is roughly 2,942 hand adjudications, a grounding campaign rather
than a row.

**Nothing forces it today, which is what makes the refusal legitimate rather
than evasive.** Modelo 200 carries exactly one revision; the completeness
ratchet counts only casilla groups appearing in two or more revisions, which
is why neither Modelo 200 nor Modelo 390 appears in its committed baseline.
The duplication cost is contingent on a split, and Modelo 200's split is
blocked on the sibling generator campaign.

**Precondition:** Modelo 200 must carry a grounded continuity set before its
second revision directory lands, authored in the same change as that
revision. While the modelo has one revision the work is a naming act over a
fixed set and does not grow; once a second exists, every unstamped casilla
additionally needs cross-revision adjudication against both endpoint years.

**Cost of leaving it open, accepted deliberately:** Modelo 200's occurrence
keys stay its only resolution source, so its first split duplicates the whole
Spanish label set per revision and a later official-label correction must be
applied in every revision's copy. Paying that early by bulk-stamping would
buy a cheaper translation surface with 2,942 ungrounded identity assertions,
which the grounding discipline forbids.

Recorded in the campaign audit document as the finding
`continuidad-declaration-ruling-modelo-390-done-modelo-200-refused-with-precondition`.

## Notes

Two row premises did not reproduce and are corrected in the audit finding
rather than carried forward.

Modelo 303 is recorded as declaring stamps for 231 casillas and carrying 234
continuity keys. At HEAD it declares 202 stamps per revision across six
revisions, resolving to 202 distinct chain ids, and the Spanish catalogue
carries 202 continuity chains with 206 non-null values. The claim's shape
holds — Modelo 303 does carry a populated revision-independent tier — but the
figures are stale.

The plan describes resolution as walking the revision occurrence key through
the casilla alias key to the continuity key. The loader builds a casilla's
chain as two tiers, the occurrence key followed by the continuity key when
one is declared; alias keys form a separate per-alias chain rather than an
intermediate tier. The behaviour the cost argument actually turns on is
confirmed exactly as described: resolution advances on the absence of a
VALUE, not of a key, which is what lets the continuity tier fire given that
the scaffold emits a null occurrence key for every casilla in every revision.
