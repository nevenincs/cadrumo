---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2c71136331858537dbd3c8ce3c158da3628fca3744c165eb3f3d864ace2e8c98'
step_id: 'S07'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Author the LegalParameter fix for the standing rule violation P03.S05 surfaced rather than merely flagged: the administrador/consejero retencion rate figures (35 percent, 19 percent, the 100.000 EUR INCN threshold) were typed Python literals in core/aggregation.py carrying a legal_refs citation that read as verified without being registry-sourced, which is more dangerous than no citation at all. Ground the three figures against LIRPF art. 101.2 and RIRPF art. 80.1.3.o, author them as registry LegalParameter entries, migrate them out of core/aggregation.py into a registry-backed loader mirroring the sibling RIRPF art. 95 rate set already established in this module, and thread the loader into the advisory in place of the literal-backed treatment field

## Scope

- `src/cadrumo/core/aggregation.py`
- `src/cadrumo/domain/transactions/_retencion_parameters.py`
- `src/cadrumo/application/aggregation/_retencion_rate_advisory.py`
- `src/cadrumo/_data/registry/aeat/legal/irpf-retencion-administradores.toml`

## Description

- Grounded the three figures (35 %, 19 %, 100.000 €) against the bundled consolidated corpus for both LIRPF art. 101 and RIRPF art. 80, then cross-checked each live against the BOE Legislación Consolidada open-data API; both articles state the same three figures byte-identically, no drift found, and neither article's tracked amendment history touches the administrador paragraph.
- Authored three new `LegalParameter` registry entries citing both the establishing law (`ley-35-2006:art-101`) and the developing reglamento (`rd-439-2007:art-80`), which were both already operator-reviewed catalogue entries — no new `LegalReference` needed. Stamped `reviewed_by` with an honest agent-authored disclosure naming itself and the live cross-check date, per the established convention; not under the operator's name, since these are genuinely new entries.
- Added a registry-backed loader (`AdministradorRetencionRates` / `load_administrador_retencion_rates` / `administrador_retencion_legal_refs`) to the same domain module that already holds the sibling RIRPF art. 95 rate set, mirroring its exact shape: frozen pydantic record, `lru_cache`-memoised loader, first-seen-order grounding function.
- Stripped the regulatory VALUE fields (`fixed_rate`, `fixed_reduced_rate`, `fixed_reduced_incn_threshold_eur`, `legal_refs`) off `core.aggregation.WorkIncomeRetencionTreatment`, and deleted the three `ADMINISTRADOR_RETENCION_*` module constants outright — `core` is the layer the registry schema imports FROM, so it cannot import back from the registry, and threading the real loader into it would have inverted that dependency direction. The type now carries only the STRUCTURAL fact (`is_fixed_rate`) a caller needs to route on; the sibling art. 95 rate set already lived one layer up for the identical reason, so this was a correction toward the established pattern, not a new one.
- Threaded the new loader into `administrador_retencion_rate_advisory_observations`, replacing the hardcoded-literal-backed `treatment.fixed_rate` / `treatment.legal_refs` reads with `load_administrador_retencion_rates()` / a cached `_administrador_refs()` wrapper (mirroring the existing `_art95_refs()` wrapper for the sibling family). The advisory message's "100.000 EUR" figure now also interpolates from the loaded rate set rather than a separate hand-typed literal.
- Rewrote the `core` layer test (`test_retencion_treatment.py`) to assert only the structural fixed-vs-progressive fact; the retired rate-value assertions moved to a new domain-layer gate (`test_administrador_retencion_parameters.py`, mirroring the sibling `test_retencion_parameters.py`) that chains bundled corpus → registry parameter → typed record → grounding function, plus a whole-identifier-boundary "no literal redeclared" gate.
- Updated the two application-layer grounding tests that previously read `treatment.legal_refs` directly to read the new `_administrador_refs()` function instead.

## Outcome

The rule violation P03.S05 surfaced — a typed `legal_refs=` citation sitting beside a hardcoded-literal rate value, reading as verified without being registry-sourced — is closed. All three figures now resolve from registry TOML through a memoised loader at parity with the sibling RIRPF art. 95 rate set; `core.aggregation` no longer carries any administrador rate literal or citation, only the structural fixed-vs-progressive taxonomy the registry schema's own dependency direction permits it to hold.

32 tests green across every touched module and its test suite (`core/tests/test_retencion_treatment.py`, `domain/transactions/tests/test_retencion_parameters.py`, the new `test_administrador_retencion_parameters.py`, `application/aggregation/tests/test_retencion_rate_advisory.py`), plus the registry catalogue-build and legal-grounding gates (34 tests) confirming the new TOML entries validate cleanly. Ruff check/format and the type checker are clean on every touched file. The import-hygiene scan reports zero new cross-package private-import findings for this change. A broader run across `core`, `domain/transactions` and `application/aggregation` tests showed 14 unrelated failures (period-string, hashing, split-lineage, config-reset and source-mesh gates) in files this Step never touched, matching other agents' concurrently dirty working-tree files already visible in `git status` — triaged as peer churn, not owned by this Step, and left untouched.

**Method note.** The same per-function, per-value reachability discipline P03.S05 used to find its fifth module found this fix's correct layer boundary too: `core.aggregation` is imported BY the registry schema, so a value needing the registry cannot live there without inverting that edge — the exact "stop and report rather than route around it" disconfirming observation P03.S05's own row states, applied one level deeper, to where the FIX itself must live rather than only to what it must thread.

## Notes

No incidents. No scaffolds left in code. The concurrent commit `fix(aggregation): ground the retencion rate advisories in the registry, not in prose` (landed by a peer agent between this Step's assignment and its start) had already wired `legal_refs=tuple(treatment.legal_refs)` into the diagnostic — i.e. it populated the field but left it reading the same hardcoded literal, which is precisely the "citation beside a literal" shape this Step's finding warned is worse than no citation at all. This Step's fix subsumes that commit's administrador-side change: the field is now populated from the registry loader instead.
