---
name: aeat-calculation-grounding
trigger: always_on
---

# AEAT calculation grounding and legal provenance

## Tax semantics come from official sources

Ground tax semantics in BOE, AEAT publications, AEAT workbooks, registry sources
or live oracle replay. **Do not invent legal behavior, and do not treat user
preference as authority for regulated calculations.** Where an identity or
classification judgment is required, it is a TAX REVIEW against official sources
— never text similarity — and it records honest reviewer provenance.

## Grounding travels to the operator

**Carry regulatory grounding through every domain boundary.** Every casilla
observation, calculation revision, filing draft, export record and CLI emit MUST
preserve its `legal_refs`, `source_refs` and `formula_id` provenance from the
registry source to the operator-facing surface.

**Persist typed envelopes, not flat scalar mappings.** `RegistryFilingObservation`,
`CasillaObservation`, `CalculationRevision.observations` and equivalent typed
records are canonical; do not collapse them to `dict[str, Decimal]` for
downstream consumers. Expose a derived mapping as a property if a flat view is
needed.

**Emit every casilla in `engine_result.values`, not only computed entries.** Input
and bound casillas MUST produce `CasillaObservation` rows pulled from the registry
casilla definition; computed casillas pull the same fields from the matching
engine entry. Never drop a casilla on the way to the persisted revision.

**Surface `legal_refs` and `source_refs` on every operator-facing CLI JSON
payload.** Wrap typed observations in a parallel JSON list alongside any flat
`casilla_values` mapping — the flat view is for readability, the typed list is
the contract.

**Validate referential integrity at snapshot build.** Every typed-ID reference
must point at an existing entity; every per-source binding selector must satisfy
its typed selector model; every cross-domain routing table must reference real
casillas in the modelo revision.

**Treat type-system escapes as boundary leaks.** `cast(...)`, `dict[str, Any]`
returns and bare `str(...)` coercion of typed aliases are documentation debt or
design escapes. Document third-party API boundaries inline; remove them
everywhere else.

## Every value cites the provision that establishes it

Every regulatory value compiled into the registry — a rate, bracket tranche,
threshold, deadline window, reduction coefficient — MUST declare in its
`legal_refs` the specific binding provision that *establishes that value*, and
that provision MUST be defined in the legal catalogue with a `corpus_ref`
resolving to real BOE or AEAT text.

**Citing the general framework article alone is insufficient** when a more
specific provision — a transitional disposition, a phased schedule, a modifying
law — actually fixes the number. A value whose binding provision is not in the
schema is ungrounded and MUST NOT ship. Confirm the provision is cited, defined,
backed by corpus text the evidence gate validates, and **consistent with the
value** — the corpus clause states the number encoded.

**Correcting a generic-default grounding:** where a casilla's `legal_refs` carry a
chapter as a generic default and the box is not actually of that kind, re-ground
it to its own concept's binding article, keyed by the **renumbering-immune
section tag** (the leaf of `section = [...]`), **never by casilla id across
filing years** — ids renumber, so an id-keyed map injects the wrong article. A
framework article that *applies* a regime is a valid foundation home even when
the regime is *established* elsewhere. For a casilla that is a member of a
construct or binding, sweep the casilla, its construct AND its bindings in ONE
change: the validator requires a construct's refs to cover both its member
casillas' and its bindings' refs, so a partial sweep breaks registry load.

## Verify against the bundled corpus, and distrust it on numbers

Verify legal text against the BUNDLED authoritative consolidated corpus under
`src/cadrumo/_data/corpus/normatives/html/` FIRST. Never author a corpus excerpt
from a secondary source without that cross-check, and prefer pointing
`corpus_ref` at the bundled file over hand-authoring a duplicate.

**The bundled corpus is preferred but NOT infallible.** For any numeric AMOUNT or
RATE, cross-check against the live BOE or AEAT consolidated text even when the
bundled corpus states it. An excerpt authored from a secondary source once
carried a fabricated year list while the repo already bundled the authoritative
text — and the `required_text` cross-check was tautological, because the same
author wrote both the excerpt and the phrase validating it.

**A fetched file can still be unfit.** A consolidated-legislation payload carries
every historical version, oldest first, so taking the first block bundles
repealed law under a current filename; and a truncating shell heredoc silently
loses text. Take the **last** version, assert the amending norm's identifier,
never pass legal text through a shell, and read the file back before trusting it.

## Total aggregations enumerate every contributing tier

An IVA "total cuota devengada" aggregation — M303's total casilla, M390's annual
total, any IVA modelo's equivalent — MUST sum the **recargo de equivalencia**
cuota tiers (LIVA art. 161) alongside the standard, reducido and super-reducido
repercutido tiers and the autorepercutido cuota. Omitting them silently
under-declares for any recargo filer and desynchronises the annual return from
the summed quarters. Generalise it: when a tier or category is added to any
total, confirm every downstream total and every return that reconciles against it
enumerates it too.

## How

- **Good:** `rg` the bundled consolidated file for the provision's anchor, read
  the verbatim text, and point `corpus_ref` at that file with a `required_text`
  phrase distinctive enough to match only the target provision.
- **Good:** if the bundled corpus is wrong, correct the corpus, the grounded
  parameter, the legal-entry notes and any tautological test that baked the wrong
  value, in ONE atomic commit.
- **Good:** the total formula enumerates every tier, the construct's `legal_refs`
  cite art. 161, and a grounded parity test against a manual worked example
  charging recargo reproduces the printed total exactly.
- **Bad:** authoring an excerpt from a blog or summary site — the
  self-referential `required_text` gate passes anyway.
- **Bad:** stamping an agent-authored legal entry as reviewed under the
  operator's name without the cross-check; the legal catalogue is a
  human-reviewed, filing-grade surface.
- **Bad:** mapping one year's casilla id to another's to copy grounding; or
  grounding a construct-member casilla without its construct and bindings.
- **Bad:** "fixing" a failing recargo-inclusive parity test by adopting a
  recargo-excluded expected value — fix the formula, not the test.

Source: ADR `2026-06-14-bindings-interface-hardening-adr`; audits
`2026-06-14-legal-grounding-centralization-audit`,
`2026-06-14-aeat-grounding-completion-audit`.
