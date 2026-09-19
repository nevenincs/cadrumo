---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:46bf2fb5068f5617e1d4e9383cacd9e4b3b0502e76feb0a197434faf66d21be7'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
---
# `registry-authority-artifact-boundary` audit: `runtime consumer routing`

## Scope

Reviewed W04.P07.S14 against the accepted immutable-runtime-publication ADR and its research grounding. The review traced production code throughout `src/cadrumo/domain/iva`, `src/cadrumo/domain/deadlines`, `src/cadrumo/domain/auth/apoderamientos`, and the regulated repositories under `src/cadrumo/domain/resources`, rather than limiting inspection to the current diff. It covered IVA regulation and place-of-supply projection, printed-country and alpha-3 vocabulary, territorial carve-outs and Spanish postal territory, Ley 58/2003 recargo bands, apoderamiento scopes, runtime legal grounding, repository caching and error translation, and the focused test amendments.

Production searches found no TOML parser, authoring-table filename, bundled authoring path, raw-root override, or consumer-owned identity cache remaining for the seven S13 runtime projections. Each operative loader now obtains typed records from `bundled_authority().catalogues.runtime`; repository wrappers add no cache, and their no-op `clear_cache` methods preserve the shared authority as the sole freshness owner. The IVA year-keyed repository translates unsupported year/catalogue selection to `ResourceNotFoundError` while allowing missing or corrupt publication errors to propagate as authority failures rather than misreporting them as absent resources.

The staged grounding fixture deliberately reuses the complete bundled facts and runtime projections because the v4 writer requires those catalogues, while substituting the minimal legal/evidence slice needed by the behavior under test. It does not introduce a production fallback or prove validity of that synthetic catalogue as a publication candidate; it adequately proves that runtime grounding reads the staged artifact and refuses unsupported evidence. Direct execution of the affected test bodies is meaningful evidence for this bounded routing behavior despite the independently reported collection failure, though the canonical pytest invocation should still be rerun when that external blocker is repaired.

## Findings

No findings. The reviewed production paths route the former parallel regulated tables through the published typed authority, preserve domain adaptations and refusal behavior, and introduce neither raw-source reparsing nor a parallel cache. W04.P07.S14 is closable.

## Recommendations

No corrective action is required for S14. Re-run the canonical focused pytest selection once the unrelated collection blocker is removed so the ordinary suite records the same already-exercised behavior.
