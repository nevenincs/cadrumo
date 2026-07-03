---
tags:
  - '#audit'
  - '#modelo-multiyear-renta'
date: '2026-06-02'
modified: '2026-06-29'
related:
  - '[[2026-06-02-modelo-multiyear-renta-plan]]'
  - '[[2026-06-02-modelo-multiyear-renta-income-adr]]'
  - '[[2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-adr]]'
---

# `modelo-multiyear-renta` audit: `multi-year-renta campaign-close honesty review`

## Scope

This is the campaign-close honesty review mandated by the
`aeat-campaign-close-honesty-review` rule for the `modelo-multiyear-renta`
campaign: every one of the 30 AEAT modelos must carry a real-adapter,
end-to-end persona enrollment spanning at least two distinct renta (annual)
years, enrolled in the default-deny authorization gate, before the campaign is
declared structurally complete. The code-reviewer agent led the fresh-context
review; the findings below are its inventory, verified against the current tree
by the executing agent before persistence (agent-as-discovery,
coordinator-as-confirmation).

The review sampled the enrollment surface across all four evidence classes
(`calculation`, `reconciliation`, `data_fidelity`, `threshold_continuity`), the
authorization-gate infrastructure and its meta-test, the registry legal/source
grounding behind the enrolled cross-renta hooks, and the documentation trail
(ADRs, plan). It asked the load-bearing question the rule exists to force: is the
gate genuinely un-fakeable and are the enrollments real, or is a fraction of the
roster theater?

## Verdict

The authorization gate is **un-fakeable** and the enrollments are
**predominantly genuine — not theater**. Of the 30 enrolled modelos, 18 sampled
enrollments were confirmed to drive real adapters (real encrypted-SQLite
observation store, real registry authority, real `previous_filing` /
`cross_model_output` resolvers, real calculation engine) with no mocks, span at
least two distinct renta years, and assert a non-tautological cross-renta wiring
invariant rather than a hand-computed value. The recorder enforces its
`>=2 distinct renta years` and per-observation un-fakeable-evidence contract at
its own type boundary, and `assert_enrollment_matches_manifest` converts the
manifest from an honour claim into a verified one.

Structural completeness remains **gated on the remaining HIGH and MEDIUM findings
below**. HIGH-1 and HIGH-2 are closed on the current corpus/registry path; HIGH-3
and the MEDIUM findings still require closure or formal deferral before the
campaign is declared complete.

## Current State — 2026-06-29

The current registry/corpus closes the two legal-grounding findings from this audit:

- HIGH-1 is closed: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_721/manifest.json`
  exists, and `src/aeat/_data/registry/aeat/legal/monedas-virtuales.toml` anchors
  Modelo 721 to Orden HFP/886/2023 / `BOE-A-2023-17429`. Unreferenced stale
  `orden-hfp-887-2023` corpus files that carried obsolete Modelo 721 text were
  removed from the shipped corpus so search cannot re-ground the model on the
  custodian-side order.
- HIGH-2 is closed: the M100 general-base negative carry is grounded on
  `ley-35-2006:art-48`; casilla 1388 also carries the base-liquidable context
  ref `ley-35-2006:art-50`. `ley-35-2006:art-49` remains reserved for savings-base
  formulas and casillas.

## Findings

### HIGH-1 — CLOSED: M721 legal-grounding gate resolves against bundled corpus

- **Pathway / site:** `aeat-dr-721` source-ref → the registry catalogue
  verification gate (`test_catalogue_verification`), which resolved to a missing
  `modelo_721/manifest.json` corpus manifest.
- **Original gap:** the M721 cripto-exterior source registry referenced a corpus manifest
  path that does not exist on disk, so the legal-grounding catalogue gate is RED.
  A reviewed-but-unresolvable source is higher risk than an absent one — a
  casilla author trusts it.
- **Current closure:** the bundled corpus now includes
  `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_721/manifest.json`.
  The manifest identifies the Modelo 721 record design as Orden HFP/886/2023, and
  `src/aeat/_data/registry/aeat/legal/monedas-virtuales.toml` points Modelo 721
  legal/source refs to `BOE-A-2023-17429`, not the custodian-side Orden HFP/887/2023.
  The obsolete unreferenced `orden-hfp-887-2023` corpus artifacts were removed to
  keep shipped search authority aligned with the current registry.
- **Verification gate:** `test_catalogue_verification` is green; the M721
  legal-grounding tier resolves. Tracked as task `#40`.

### HIGH-2 — CLOSED: M100 general-base carry uses Art. 48 grounding

- **Pathway / site:** the M100 Anexo-C carry binding
  `renta-{2024,2025}-base-liquidable-negativa-general-anterior`, `legal_refs`
  citing `ley-35-2006:art-49`.
- **Original gap:** `art-49` grounds the integración y compensación of the base
  imponible del **ahorro** (the savings base, 4-year window + inter-component
  límite). The carry the binding implements is the base liquidable **general**
  negativa carry-forward, whose binding provision is `art-48` (integración y
  compensación de la base imponible general). The general-base carry was grounded
  against the ahorro article — a mis-citation that the
  registry-calculation-legal-grounding rule forbids.
- **Current closure:** `src/aeat/_data/registry/aeat/legal/irpf.toml` defines
  `ley-35-2006:art-48` with resolving BOE corpus text. The 2024 previous-filing
  binding cites `ley-35-2006:art-48` and `ley-35-2006:art-50`; the 2025 binding
  cites `ley-35-2006:art-48` plus the current annual order. Casilla 1388 carries
  `ley-35-2006:art-48` and `ley-35-2006:art-50` in both revisions. Savings-base
  formulas remain grounded on `ley-35-2006:art-49`.
- **Verification gate:** the grounding evidence gate is green. Tracked as task
  `#39` (corpus prerequisite `#44`).

### HIGH-3 — M353 enrollment test carries stale "expected to fail / held-pending-A2" framing

- **Pathway / site:** `test_modelo_353_grupo_aggregation_continuity.py` — a
  docstring / comment framing the test as EXPECTED TO FAIL / HELD-PENDING-A2 plus
  a now-dead `type: ignore`.
- **Gap:** the A2 (353←322 grupo aggregation) mechanism has landed and the test
  PASSES, but its framing still declares it expected-to-fail and held pending A2.
  A passing test documented as expected-to-fail is a process leak (the
  roundtrip-discipline rule's "expected-to-fail is a process leak") and the
  `type: ignore` is dead. A future reader cannot tell the test is actually a
  live, green contract.
- **Remediation:** rewrite the docstring to describe the now-landed A2 contract
  the test verifies; drop the stale `type: ignore`.
- **Verification gate:** the test passes with no expected-to-fail / held-pending
  framing and no unjustified `type: ignore`; a grep for "EXPECTED TO FAIL" /
  "HELD-PENDING" in the module returns nothing. Tracked as task `#41`.

### MEDIUM-1 — untracked M721 enrollment orphan duplicates the data-fidelity surface

- **Pathway / site:** an untracked `test_modelo_721_cripto_exterior_fidelity.py`
  sitting alongside the committed `test_modelo_721_cripto_extranjero_fidelity.py`.
- **Gap:** two M721 fidelity modules — one tracked, one untracked orphan — risk a
  duplicate / divergent enrollment surface and basename confusion.
- **Remediation:** confirm the orphan carries nothing unique over the committed
  `_extranjero_` module, then delete it.
- **Verification gate:** one M721 enrollment module remains; the orphan is gone;
  the gate still enrolls 721. Tracked as task `#43`.

### MEDIUM-2 — M309 / M369 declare an engine but enroll via context-mode label only

- **Pathway / site:** M309 and M369 enrollment tests; both modelos declare
  `has_engine = True` yet enroll `data_fidelity` via context-mode
  (`record_context_year`, label-only) rather than a real calculation.
- **Gap:** this is the same evidence-class honesty shape the M100 finding caught
  (a `calculation`-capable modelo enrolled by a weaker mode than its capability
  implies). Either the engine is not actually the cross-renta surface (context
  mode is honest and `has_engine` is the over-claim) or the enrollment under-uses
  a real engine (mode is the under-claim).
- **Remediation:** confirm intentional and reconcile the `has_engine` /
  evidence-class declaration, OR upgrade the enrollments to calc-mode following
  the 303/322 pattern (the established IVA full-calc enrollment shape).
- **Verification gate:** the declared `has_engine` and the recorded evidence mode
  agree for 309 and 369; gate meta-test stays green. Tracked as task `#42`.

### MEDIUM-3 — A4 ADR over-describes the M100 carry with stale casilla IDs

- **Pathway / site:** `2026-06-02-modelo-multiyear-renta-income-adr` (A4), the
  M100 (A4.2) section.
- **Gap:** the ADR's M100 casilla mapping uses file-sequence prefixes confused for
  casilla IDs (the "0462/0465/1390→0393/0396/1391" mapping), an over-description
  that does not match the landed general-base carry (1391→1388). Two agents
  independently caught this. A doc-trail drift, not a code defect.
- **Remediation:** correct the A4 ADR's M100 section to the landed general-base
  carry (1391→1388, art-48) and scope the savings-base 0441-family rolling carry
  explicitly as the follow-on.
- **Verification gate:** the ADR's M100 casilla IDs match the committed registry;
  no file-sequence/casilla-ID confusion remains. Tracked under task `#39`'s
  doc-trail dimension.

### LOW-1 — M202 enrollment locally recomputes the 18% modalidad rate

- **Pathway / site:** `test_modelo_202_cuota_base_ejercicio_anterior_continuity.py`,
  the casilla-03 leg.
- **Gap:** the 18% modalidad-40.2 rate is recomputed locally in the test rather
  than asserted against an AEAT-202-instructions oracle, a mild
  non-tautology-rule softness (the rate the registry declares is the rate the
  test multiplies by).
- **Remediation:** ground the 18% against the AEAT Modelo 202 instrucciones
  oracle, or assert the rate as a registry-sourced parameter rather than a test
  literal.
- **Verification gate:** the 03-leg expected value derives from an external
  oracle, not a test-author literal. Tracked as task `#32`.

### LOW-2 — M714 "per art.30 escala" comment overstates a manual Phase-A figure

- **Pathway / site:** `test_modelo_714_patrimonio_baseline_fidelity.py`, a comment
  describing a manual Phase-A figure as "per art.30 escala".
- **Gap:** Phase-A M714 is data-fidelity with manual casillas and no tarifa engine
  yet (the art.30 escala / art.31 límite calc is Phase-B); the comment implies a
  computed escala that does not run.
- **Remediation:** soften the comment to reflect the manual Phase-A figure (no
  art.30 computation at Phase-A).
- **Verification gate:** the comment no longer asserts a computed escala for a
  manual figure. Tracked as task `#43`.

## Confirmed sound

The review positively confirmed the following are genuine and require no action;
they are recorded so a future audit need not re-derive them.

- **Gate un-fakeability.** The `EnrollmentRecorder` admits a year only with an
  evidence token the caller cannot fabricate (calculation mode: a strictly
  positive produced-value count from a real engine run; context mode: a named
  real two-year context). `EnrollmentEvidence` enforces the `>=2 distinct renta
  years` and per-observation evidence contract at its pydantic boundary, and
  `assert_enrollment_matches_manifest` requires the recorded year-set to equal the
  manifest's declared `renta_years`. A stub records nothing; a single-period test
  records one year; both turn the gate RED.
- **CALCULATION class genuine.** 303, 322, 202, 200, 130, 131, 210, 151, 353 each
  drive a real calculation across two distinct renta years (M100 joined this set
  once its enrollment was upgraded from resolver-only to full calc). 151 is the
  strongest: its cuota is checkable against the BOE Beckham flat-band escala
  oracle.
- **RECONCILIATION class genuine.** 190←111, 180←115, 193←123 (periodic→annual
  retenciones roll-up) and 390←303 reconcile a real same-/cross-year source set.
- **DATA_FIDELITY class genuine.** 347, 184, 232, 721, 308, 360, 349 persist and
  reload typed observations across two renta years with strict pydantic equality
  and per-year isolation.
- **THRESHOLD_CONTINUITY class genuine.** 036, 840, 720 assert a real
  obligation-threshold / baseline continuity across two renta years.
- **Dormant-engine set legitimate.** 308, 347, 360, 840, 721, 714 enroll without a
  numeric calculation by design (informativa / data-fidelity / threshold modelos
  whose cross-renta surface is fidelity or continuity, not a cuota), which is the
  recorder's documented non-calculation path — not a gap.

## Confirmed NON-finding — executable_parity_evidence gap is pre-campaign tier-debt

The registry coverage gate
`test_committed_registry_tree_has_required_model_law_coverage` reports an
`executable_parity_evidence` coverage gap for modelos
036 / 193 / 200 / 202 / 210 / 303 / 309 / 322 / 353 / 369 / 390. This was
investigated and is **scoped out of the campaign close as standing pre-campaign
tier-debt, NOT a campaign-induced regression**:

- `executable_parity_evidence` is the coverage tier that requires an executable
  AEAT calculation workbook as a numeric oracle. The modelos that miss it are the
  informativa / IVA / IS modelos for which AEAT publishes no public executable
  calculation workbook, so the tier is unsatisfiable by available authority — the
  standing "no public AEAT workbook oracle" debt.
- Git history confirms the temporal scoping: the parity-evidence tier logic was
  introduced in `feat: advance registry authority rebuild` (`3dfd17a39`,
  2026-05-05), a strict ancestor of the campaign's first authored commit
  (`docs(modelo-multiyear-renta): foundational gate + 3 mechanism ADRs + L4
  campaign plan`, `821375e00`, 2026-06-02) — verified by
  `git merge-base --is-ancestor`. The gap predates the campaign by roughly a
  month; no campaign commit introduced or widened it.

The campaign neither caused nor is obligated to close this gap. It is recorded
here so the close is honest about what it does and does not cover.

## Inventory (no campaign action)

- A `git stash` list carries 10 entries. `git stash` is categorically forbidden by
  the `aeat-git-worktree-safety` rule; the entries are a peer-campaign safety
  violation already flagged. The coordinator is adjudicating this out-of-band
  (popping / dropping is also forbidden and could strand the stasher's work). No
  campaign-close action — inventory only.

## Recommendations

- Close HIGH-1 (`#40`), HIGH-2 (`#39` + corpus `#44`), and HIGH-3 (`#41`) before
  declaring the campaign structurally complete; each has a concrete verification
  gate above.
- Reconcile the MEDIUM findings (`#42`, `#43`, and the A4 ADR doc-trail under
  `#39`) or formally defer each with a follow-up reference, per the
  campaign-close-honesty rule's "closed with verification or formally deferred"
  requirement.
- Action the LOW findings (`#32`, `#43`) opportunistically; they are softness, not
  correctness gaps.
- Treat the `executable_parity_evidence` gap as out-of-scope standing tier-debt
  (verified pre-campaign above); do not let it block the campaign close.
- Re-run a fresh honesty review after the HIGH/MEDIUM remediations land; a pattern
  of recurring multi-item discoveries per pass is documented and expected — the
  gate is that an honest review ran before closure was declared, which it did.

## Codification candidates

- **Source:** finding HIGH-3 (M353 enrollment test framed EXPECTED-TO-FAIL /
  HELD-PENDING-A2 while actually passing, with a dead `type: ignore`).
  **Rule slug:** `no-stale-held-pending-framing`.
  **Rule:** When the dependency a test was held pending lands, the test's
  expected-to-fail / held-pending framing and any then-dead `type: ignore` MUST be
  removed in the same change that makes the test pass; a green test must never be
  documented as expected-to-fail or held-pending. This is cross-session
  (a future reader inheriting the test cannot tell a live green contract from a
  stale skip-in-prose), constraint-shaped (never leave held-pending framing on a
  passing test), and project-bound (it sharpens the roundtrip-discipline rule's
  "expected-to-fail is a process leak" for the held-pending-on-a-peer-dependency
  case this campaign's A2→353 sequencing produced).
