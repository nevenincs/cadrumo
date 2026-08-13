---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:8c684d60e0a03c099ae1052da0945231bd16e34192bbdb9a38ebe46662c99613'
step_id: 'S05'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace advisory-grounding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-08-10-advisory-grounding-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Thread a registry object into the five modules that hold none, as its own change rather than inside a citation change. The invoice-devengo advisory, the retencion-rate advisory, the invoice source resolver and the prior-payment advisory hold no revision, snapshot or casilla definition anywhere. Every provision they cite has a catalogue entry, so this is threading rather than grounding. The disconfirming observation: if threading a revision into any of these modules would invert a dependency direction the architecture forbids, stop and report rather than route around it, because that would mean the advisory belongs at a different layer and ## Scope

- `src/cadrumo/application/aggregation/`
- `src/cadrumo/application/invoices/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

**The fifth (`_retencion_rate_advisory.py`'s administrador/consejero site) is the disconfirming observation, and it is reported rather than routed around.** Its existing `legal_refs=tuple(treatment.legal_refs)` already looks typed and grounded, but `treatment` is `WorkIncomeRetencionTreatment` from `core/aggregation.py` -- a hardcoded Python-literal constant carrying both the citation AND the 35%/19%/100.000€ rate values themselves, not a registry-loaded object. Threading a genuine registry object here is not a parameter-passing fix like the other four: no `LegalParameter` entry for this rate/threshold exists in the registry tree today, so the honest fix is authoring one (moving the rate constants out of `core/` into registry TOML, which `aeat-registry-authority-flow` requires for exactly this shape) -- a legal-authoring decision with its own review weight, not a mechanical thread. Stopped here rather than inventing a shortcut. The module's OTHER two diagnostics (the art. 95 sectoral-rate sites) are unaffected and already read their grounding from a real `LegalParameter` via `rirpf_art95_retencion_legal_refs()` -- found already resolved by measurement, not touched.

## Notes

**Population arithmetic, stated so a later reader does not have to re-derive it.** The row and its governing ADR both say "five modules" while naming four; the fifth is the bienes-inversion module, unnamed in either source and found only by checking registry-object reachability per FUNCTION rather than per file (a file-level check misses it, because the module's OTHER class does hold a revision).

**The `casilla_registry_legal_refs` promotion leaves two pre-existing private near-duplicates in place** (`_minimo_descendientes_advisory.py`'s and `_undeclared_activity_advisory.py`'s own copies), deliberately not retargeted in this Step: those modules carry P02 work delivered by a different agent on this same feature during this campaign, and retargeting them is a separate, small follow-up rather than something to fold in here.

**A transient "registry directory changed during cache fingerprinting" error surfaced repeatedly across every test run in this Step**, always on a different test each retry, from a peer's concurrent registry-tree writes on the shared drive. Never the same failure twice, never reproduced after one retry -- consistent with the standing local-execution guidance rather than a real regression, and not investigated further.
