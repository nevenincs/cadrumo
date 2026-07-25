---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S06'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Update the three parser-boundary modules the layout change reaches

## Scope

- `parser boundary modules`

## Description

- Shrink the two profile-casilla frozensets in the shared parser-boundary support module.
- Replace the parse-path engine comparison with a document-internal printed-arithmetic assertion.
- Re-source the primitive-summation anti-tautology proof onto the calculate path.
- Rename the misnamed real-declaration-copy constant and its consuming test.

## Outcome

The three parser-boundary modules collapse to one shared support edit, because the set-equality assertions reference the frozenset symbols rather than restating the ids and so auto-track the shrink.

The arbitration the ADR deferred to this lane is settled by removing the engine from the parse path rather than by discarding either side. The engine cannot participate: it derives boxes 27 and 45 by summing primitives the printed form does not carry, and the printed totals cannot be substituted because the engine refuses computed casillas as inputs. The parse path now asserts a property of the document — printed box 46 equals printed box 27 minus printed box 45, grounded in Orden EHA/3786/2008 art. 1 — and its falsifiability is proven by perturbing each of the three amounts in turn.

The anti-tautology proof is re-sourced, not deleted. It supplies its primitive directly, which is how the calculate path supplies it in production, and keeps a non-zero baseline assertion so the delta identity cannot pass vacuously. The shared extraction helper is deliberately left alone because six other modelos' verification-chain tests depend on it.

## Notes

The replaced assertion's second half compared the engine's resultado against the engine's own box 27 minus box 45, which is precisely the registry formula for resultado; it held by construction and would have passed at zero. Replacing it with a falsifiable check is a strengthening.

Engine coverage on the parse path is genuinely lost and re-established on the calculate path. This is recorded plainly rather than described as free.
