# Registry calculation values cite their binding legal source

Every regulatory value compiled into the registry — a rate, bracket tranche,
threshold, deadline window, reduction coefficient — MUST declare in its
`legal_refs` the specific binding provision that *establishes that value*, and
that provision MUST be defined in the legal catalogue with a `corpus_ref`
resolving to real BOE or AEAT text.

**Citing the general framework article alone is insufficient** when a more
specific provision — a transitional disposition, a phased schedule, a modifying
law — actually fixes the number. A value whose binding provision is not in the
schema is ungrounded and MUST NOT ship.

When authoring or changing a regulatory value, confirm the binding provision is
(1) cited on the value's `legal_refs`, (2) defined in the legal catalogue,
(3) backed by corpus text the evidence gate validates, and (4) consistent with
the value — the corpus clause states the number encoded.

A phased corporate-tax rate once carried only its framework article while the
transitional disposition that actually set that year's figure was absent from
the schema, so a wrong rate sat undetected and was later compounded.

## Correcting a generic-default grounding

Where a casilla's `legal_refs` carry a chapter as a **generic default** — the box
is not actually of that kind — re-ground it to its own concept's binding article,
keyed by the **renumbering-immune section tag** (the leaf of `section = [...]`),
**never by casilla id across filing years**: ids renumber, so an id-keyed map
injects the wrong article.

A framework article that *applies* a regime is a valid foundation home even when
the regime is *established* elsewhere — check for one before concluding a concept
needs a separate corpus.

For a casilla that is a member of a calculation **construct or binding**, sweep
the casilla, its construct, AND its bindings in ONE coherent change: the registry
validator requires a construct's `legal_refs` to cover both its member casillas'
and its bindings' refs, so a partial sweep breaks registry load.

Where the original chapter is genuinely correct for that box, preserve it.

Companions: `legal-grounding-verifies-bundled-authoritative-corpus`,
`aeat-calculation-grounding`, `aeat-schema-central-config`.
