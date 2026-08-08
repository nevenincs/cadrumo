---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b3ff34125df394628d34227dc4e659866fe9a517bbd630702a0928bc93d2909f'
step_id: 'S73'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Point the two sibling gates at the registry's canonical box-number marker

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Outcome

**Both remaining copies retired. Zero four-digit box-marker declarations remain anywhere in the registry package** — verified by search after the change, not assumed.

The concept had four declarations: one canonical five-digit definition in production, and three test-module copies capped at four digits. The span gate's copy was retired earlier in this campaign after it was measured reading **23 of Modelo 200's 3,440 boxes**. These are the other two.

**Verdicts measured before and after, as the row required: 7 passed before, 8 passed after** — the eighth is a new assertion, not a recovered finding. No verdict changed, and that is the honest result rather than a disappointment:

- **The declared-box-number gate is scoped to Modelo 390**, whose boxes are two and three digits, so its cap could never have bitten there.
- **The rate-keyed gate iterates every modelo in the authority**, so it *could* have. Measured: widening gains nothing today — Modelo 200 declares **no** rate-keyed row at either width, and Modelo 390's **210** are identical under both. So the blind spot was real in reach but empty in content.

The value is therefore removing a second and third definition of one concept **before** it under-reads, not a boundary recovered. Stated that way in both modules so a later reader does not infer the change fixed a live defect.

**The rate-keyed gate now COMPOSES the canonical pattern** into its row regex rather than restating the bracket shape, so there is one source for what a bracketed box looks like and the rate-label prefix is the only thing that module declares.

**The declared-box-number gate keeps its own bare-number pattern, and that is deliberate.** `_BOX_SHAPED` matches a bare registry casilla number rather than a bracketed one in design text, so the canonical marker cannot be reused directly. Two patterns for one notion of "a box number" is exactly the shape that produced the 23-of-3,440 reading, so their agreement is **asserted rather than maintained by habit**: a new test requires the bracketed marker and the bare-number pattern to accept the same digit widths.

That assertion is gated on **agreement, not on a digit count** — it takes whatever width the canonical marker accepts and requires the bare pattern to match it, across widths 1 to 8. So widening the canonical definition later cannot silently leave this module behind, which is the failure this row exists to close rather than merely repair.

## Verification

    before:  uv run --no-sync pytest <both gates> -p no:randomly -n0 -q    7 passed in 20.54s
    after:   uv run --no-sync pytest <both gates> -p no:randomly -n0 -q    8 passed in 17.92s

    rate-keyed boxes, 4-digit cap vs 5-digit:
      m200: 0 vs 0   (gained 0)
      m303: 0 vs 0   (gained 0)
      m390: 210 vs 210 (gained 0)

    grep for remaining 'd{1,4}' declarations in the registry package: none

    ruff check / ruff format --check / ty check   All checks passed!

## Notes

**No mutation proof, and the reason is that there is nothing to mutate into a failure.** The change is a substitution that provably alters no verdict on today's corpus, so a mutation restoring the four-digit cap would red nothing — which is itself the measurement reported above. The durable guard is the agreement assertion, which does bite: it fails if the two patterns ever diverge in accepted width.

**Not measured.** Whether any modelo outside the three sampled declares a rate-keyed row with a five-digit box. The probe covered Modelo 200, 303 and 390 because those are the modelos with five-digit numbering or with rate-keyed rows; a fourth modelo combining both would be newly visible and was not enumerated.
