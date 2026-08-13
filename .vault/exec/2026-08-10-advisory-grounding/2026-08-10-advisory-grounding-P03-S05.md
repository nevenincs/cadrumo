---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:cbf1ff1a2305ad32da3db2ee77fb075f8ae3e22649bb1012e6eb7e48679f1f8c'
step_id: 'S05'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Thread a registry object into the five modules that hold none, as its own change rather than inside a citation change. The invoice-devengo advisory, the retencion-rate advisory, the invoice source resolver and the prior-payment advisory hold no revision, snapshot or casilla definition anywhere. Every provision they cite has a catalogue entry, so this is threading rather than grounding. The disconfirming observation: if threading a revision into any of these modules would invert a dependency direction the architecture forbids, stop and report rather than route around it, because that would mean the advisory belongs at a different layer

## Scope

- `src/cadrumo/application/aggregation/`
- `src/cadrumo/application/invoices/`

## Description

- Measured the real population rather than trusting the row's four named modules: traced every `CalculationSourceDiagnostic` construction site citing a legal provision back to whether a `ModeloRevision`/`RegistrySnapshot`/`CasillaDefinition` was reachable from that exact function (not merely imported somewhere in the same file). Found a fifth, unnamed site sharing the identical shape: the capital-goods IVA regularización advisory (`ley-37-1992` arts. 107-110), whose builder functions took no registry object even though the surrounding module does.
- Confirmed, for every named site, that the registry object was already available one call frame up (the coordinator or resolver already holds `revision` / `context.revision`) and simply never threaded down -- no dependency-direction inversion anywhere in this population.
- Added `casilla_registry_legal_refs(revision, casilla_id)` to the aggregation package facade: the casilla-derived grounding read (casilla's own `legal_refs` union its binding's), promoted out of `_minimo_descendientes_advisory.py`'s and `_undeclared_activity_advisory.py`'s private near-duplicates into one shared, exported primitive for this and future callers.
- `_prior_payment_advisory.py`: threaded `revision` into both Modelo 130 casilla-05 collectors; casilla `05` already carries `rd-439-2007:art-110` (plus three more refs) in its own registry grounding, so `legal_refs` is casilla-derived.
- `_bienes_inversion_regularizacion.py`: threaded `revision` into both builder functions; casilla `43` already carries `ley-37-1992:art-107/108/109/110` plus two more refs, so both the annual and the disposal advisory ground via the same casilla-derived read. The M303 gate on the caller made the M303 casilla constant unconditionally correct (no M390 branch reaches this diagnostic).
- `_invoice_devengo.py` and `_source_resolver.py` (invoices): no casilla is addressable for either advisory (devengo attribution applies across every IVA-relevant modelo; the M349 clave-inference disclosure is about the invoice catalogue as a whole). Declared `asserted_legal_refs` literally instead of threading an object with nothing to read -- `ley-37-1992:art-75` and `ley-37-1992:art-25`/`art-27` respectively, both already resolving in the live catalogue.
- Updated every direct-call test site (unit and coordinator-level) for the new parameters and added a grounding assertion per site.

## Outcome

Four of the five modules are threaded and grounded: two via the casilla-derived path now available through the shared `casilla_registry_legal_refs` primitive (prior-payment, bienes-inversion), two via `asserted_legal_refs` literals because no casilla is addressable (invoice-devengo, invoice source resolver). 94 tests green across every touched module and its test suite, ruff/format clean on every touched file.

**The fifth (`_retencion_rate_advisory.py`'s administrador/consejero site) is not a mere scope boundary -- it is a standing rule violation on a filing-critical value, and this record names it as one rather than as a decision merely awaiting a legal-authoring call.** `WorkIncomeRetencionTreatment` in `core/aggregation.py` carries the 35%, 19% and 100.000€ figures (LIRPF art. 101.2, RIRPF art. 80.1.3.º) as hardcoded Python literals. `aeat-registry-authority-flow` requires exactly the opposite for this shape: AEAT schema, constants, thresholds and regulatory codes belong in the central config or the registry authoring tree, never inlined as literals in a feature module, because these values are versioned by filing year and revision -- a literal bakes one year's number into the call site, scatters the authority, and drifts silently the moment a revision changes the rate.

The site is MORE dangerous than an ungrounded one, not merely equally so: it already carries a typed `legal_refs=tuple(treatment.legal_refs)`, so it reads as verified to an auditor who sees the citation and moves on -- while the number the citation sits beside is not read from any authority at all. A citation beside a hardcoded literal is worse than no citation, because it converts an ungrounded value into one that presents as checked.

The remedy is authoring a real `LegalParameter` for the three figures against LIRPF art. 101.2 / RIRPF art. 80.1.3.º and migrating the constants out of `core/aggregation.py`, mirroring the pattern `rirpf_art95_retencion_legal_refs()` already establishes for this module's sibling art. 95 sites. Not done in this Step -- landing it here would have bundled a legal-authoring change inside a threading Step, exactly the "own change, not inside a citation change" boundary this row itself draws. Taken up as the next Step instead of routed around. The module's OTHER two diagnostics (the art. 95 sectoral-rate sites) are unaffected and already read their grounding from a real `LegalParameter` via `rirpf_art95_retencion_legal_refs()` -- found already resolved by measurement, not touched.

**Method note, generalised beyond this one finding.** The fifth module (bienes-inversion) and this rule violation were both found by the same discipline: checking registry-object reachability, and now registry-SOURCE authenticity, per FUNCTION and per VALUE rather than trusting a file- or module-level signal. A file that imports `ModeloRevision` somewhere can still hold a function with none in reach; a field that carries a typed `legal_refs=` can still be citing a value nothing loaded. This is the same class of blind spot as a directory-shape glob that misses a modelo stored in the other shape, or a name-keyed census that misses a diagnostic field a different channel populates -- the fix in every case is checking the thing itself, not a proxy for it.

## Notes

**Population arithmetic, stated so a later reader does not have to re-derive it.** The row and its governing ADR both say "five modules" while naming four; the fifth is the bienes-inversion module, unnamed in either source and found only by checking registry-object reachability per FUNCTION rather than per file (a file-level check misses it, because the module's OTHER class does hold a revision).

**The `casilla_registry_legal_refs` promotion leaves two pre-existing private near-duplicates in place** (`_minimo_descendientes_advisory.py`'s and `_undeclared_activity_advisory.py`'s own copies), deliberately not retargeted in this Step: those modules carry P02 work delivered by a different agent on this same feature during this campaign, and retargeting them is a separate, small follow-up rather than something to fold in here.

**A transient "registry directory changed during cache fingerprinting" error surfaced repeatedly across every test run in this Step**, always on a different test each retry, from a peer's concurrent registry-tree writes on the shared drive. Never the same failure twice, never reproduced after one retry -- consistent with the standing local-execution guidance rather than a real regression, and not investigated further.
