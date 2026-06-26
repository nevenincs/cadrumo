# Testimonial — `docs/explanation/editing-and-verifying.md`

- **Doc path:** `docs/explanation/editing-and-verifying.md`
- **Persona:** A curious taxpayer reading the *explanation* of what a saved calculation is, what verifying checks, and why a verified version is required before the upload file is built. Not running a tutorial — reading for understanding and checking that the story matches the app.
- **Date:** 2026-06-18

This is an *explanation* page, so there are no commands printed on it to run literally. My job (per assignment) was claim-by-claim verification against the real CLI and source, cross-link/term resolution, and judging whether the narrative matches actual app behavior — with special attention to known findings (verify blocks on cross-period dependencies; the DRAFT_HAS_ERRORS path; export refuses drafts).

## Claim-by-claim walkthrough

### Claim 1 — "Each time you run a calculation, the tool saves that result as its own version and keeps the ones that came before. Nothing is overwritten." (lines 13–22)
- **Expect:** Calculations are immutable, content-addressed versions; identical inputs collapse to one version; a changed number yields a new one alongside the old.
- **Actual:** Confirmed. `aeat app modelo work calculate --help` = "Calcular una nueva revisión draft para la unidad de trabajo". Revisions are persisted in a `CalculationRevisionCatalogue` via `upsert_calculation_revision`; revision ids are derived from contents. The "identical inputs = same version, change a number = new version" claim matches the content-addressed `calculation_revision_id` model.
- **Verdict:** OK.

### Claim 2 — "Some of a modelo's numbers come straight from your imported bank data. Others can't… you supply the missing value and recalculate, which produces a new saved version." (lines 30–33)
- **Expect:** Editing = supplying a box value, then recalculate → new draft.
- **Actual:** Confirmed by the `calculate` verb (new draft per run) and the casilla input model. The cross-link to `Review and supply calculation inputs` (`../how-to/review-calculation-values.md`) resolves — file exists.
- **Verdict:** OK.

### Claim 3 — "Verifying runs a completeness check over a draft… the check asks three things: required boxes present? sums consistent? anything that blocks completion?" (lines 42–49)
- **Expect:** verify is a local completeness + consistency gate over a *draft*.
- **Actual:** Confirmed. `aeat app modelo work verify --help` = "Verificar una revisión draft contra el contrato verified-complete". `evaluate_modelo_verification` refuses any revision not in `BORRADOR` (draft) state: "only DRAFT revisions can be verified" (`_verification_actions.py:1070`). The three questions map to missing-required, consistency/blocking-rule findings, and the overall block decision.
- **Verdict:** OK.

### Claim 4 — "It produces a report and saves it, whatever the result — even a draft that fails leaves a record." (lines 51–55)
- **Expect:** Report persisted on success *and* failure.
- **Actual:** Confirmed verbatim in code: `# Persist the report regardless of outcome — failed attempts are part of the audit trail` then `vr_repo.save(...)` (`_verification_actions.py:1167–1169`). A `verification-report` inspection verb exists at `aeat app modelo verification-report`.
- **Verdict:** OK.

### Claim 5 — Three states: Complete / Incomplete / Blocked (lines 57–67)
- **Expect:** Complete = nothing blocks, marked verified, locked; Incomplete = only required-but-empty boxes; Blocked = a failed rule or consistency problem.
- **Actual:** This is an *exact* match to `_classify_verification_outcome` (`_verification_actions.py:1460–1480`): no blocking finding → `COMPLETE` + granted; blocking findings that are *only* `MISSING_REQUIRED_CASILLA` → `INCOMPLETE`; otherwise (a `BLOCKING_RULE` or consistency issue) → `BLOCKED`. The "Complete → finalised, locked state" claim matches the `VERIFICADO_COMPLETO` transition persisted only when `granted` (`_persist_verified_revision_evidence`, line 1171/1257–1266). Genuinely impressive fidelity here.
- **Verdict:** OK.

### Claim 6 — "It separates issues that block the form from issues that are only a warning… a warning surfaces something worth a second look but doesn't stop the draft." (lines 70–74)
- **Expect:** A blocking-vs-warning (advisory) severity split.
- **Actual:** Confirmed. The filing validator uses `BaseSeverity.ERROR / WARNING / INFO`; "Any WARNING only → VALIDADO" (`domain/filing/_validator.py:216`). The verify path also appends advisory (non-blocking) findings, e.g. `_missing_evidence_advisory_findings` (line 1118). Cross-link to `verification-reports.md` resolves.
- **Verdict:** OK.

### Claim 7 — "What verifying does NOT mean: not AEAT accepting your filing; not a guarantee the upload succeeds; not a deadline check. The tool never contacts AEAT." (lines 77–98)
- **Expect:** Local-only check, no AEAT contact, no deadline awareness.
- **Actual:** Strongly confirmed and consistent with the project's safety posture. `export` help: "Local; nunca contacta con AEAT." `work file` help: "Marcar una revisión verificada como internamente presentada. NO envía a la AEAT." The "not a deadline check" claim is accurate — verify computes findings from registry rules/clean-state/provenance, with no deadline-window evaluation in the finding set. This whole section is the page's best material and it is correct.
- **Verdict:** OK.

### Claim 8 — "When you ask the tool to produce the upload file, it works only from a version that has passed the completeness check (or one already recorded as filed). It refuses a plain draft." (lines 100–110)
- **Expect:** Export refuses drafts; accepts verified or filed.
- **Actual:** Confirmed. `aeat app modelo export --help`: "Exporta una revisión de modelo **verificada o presentada**" / "verificada o presentada más reciente". The parenthetical "(or one already recorded as filed)" precisely matches the "presentada" alternative. Export gracefully refuses when preconditions aren't met (I hit `Refused. No hay un perfil activo…` first because there's no profile, but the verb's contract is verified-or-filed only).
- **Verdict:** OK.

### Claim 9 — Cross-links and the `{term}`modelo`` glossary term
- **Expect:** All five outbound links resolve; the `{term}` directive resolves to a Handbook concept.
- **Actual:** All targets exist: `../how-to/review-calculation-values.md`, `../how-to/verification-reports.md`, `index.md`, `building-on-earlier-filings.md`, `reviewing-and-exporting.md`. The `{term}`modelo`` resolves — `src/aeat/_data/terminology/concepts/modelo.toml` is enrolled.
- **Verdict:** OK.

### Claim 10 (SCRUTINY) — "The check reads the agency's published rules for that modelo and year, then measures your draft against them." (lines 51–52) — scope of what verify actually checks
- **Expect (from the page):** verify = registry rules for *this* modelo/year, measured against *this* draft. The page frames verify as a purely *local, single-period* completeness check.
- **Actual:** The real verify gate is **broader than the page admits.** `evaluate_modelo_verification` appends findings from at least three additional gates beyond same-period registry rules:
  - **Cross-period clean-state** — `_cross_period_clean_state_findings(...)` (`_verification_actions.py:1099–1117`). A draft can be **BLOCKED at verify because of a *different* period's filing state** (e.g. an upstream period lacking official AEAT evidence — `cross_period_clean_state_incomplete`, line 930). This is the known finding: verify blocks on cross-period dependencies, yet the page's "for that modelo and year" wording implies the check is confined to the current period.
  - **IVA wallet reconciliation** — `_require_iva_compensation_revision_match` can inject a blocking finding (line 1092–1098).
  - **Missing-evidence advisories** — line 1118.
- **Severity:** The narrative under-describes verify. A naive reader who sees "Blocked" will look in *this* draft's required boxes / rules per the page, but the actual blocker may be an *earlier period's* missing official AEAT evidence — which the page never hints at. The page's own "Where this sits in the journey" section does link `building-on-earlier-filings.md`, but it frames carry-forward as a *feed-in convenience*, not as something that can **block this period's verify**.
- **Verdict:** DOC-ISSUE.

## Findings

1. **[MAJOR] [DOC]** — Verify's scope is under-described: the page says the check reads "the agency's published rules for that modelo and year" and frames Blocked as an issue *within this draft*, but the real `evaluate_modelo_verification` also blocks on **cross-period clean-state** (an *upstream* period missing official AEAT evidence), IVA-wallet reconciliation, and provenance. A reader hitting a `BLOCKED` verdict caused by a prior period will hunt in the wrong place.
   - *Repro:* `src/aeat/application/modelo/_verification_actions.py:1099–1117` (clean-state findings folded into verify), error `cross_period_clean_state_incomplete` at line 930.
   - *Suggested fix:* In "Complete, incomplete, or blocked" or "What verifying checks", add one sentence: "A draft can also be blocked by something outside this period — for example, an earlier filing this one depends on not yet having official AEAT evidence; see *How filings build on earlier ones*." Make the dependency explicit as a *blocking* cause, not just a feed-in.

2. **[MINOR] [DOC]** — "marked as verified… keeps the version in this finalised, **locked** state" (lines 60–62). The code transitions a Complete draft to `VERIFICADO_COMPLETO`, but the page never explains what "locked" entails for the user (can you still recalculate? does it create a new draft?). A curious reader is left guessing whether they can edit after verifying.
   - *Suggested fix:* One clause: a locked version is immutable; correcting it means recalculating, which produces a *new* draft alongside it (consistent with the "saved version" section).

3. **[NIT] [DOC]** — "A guarantee the upload **will succeed**" (lines 89–91) is slightly redundant with the AEAT-acceptance bullet for a lay reader (both say "we don't promise AEAT takes it"). Not wrong, just two bullets making one point. Optional tightening.

4. **[NIT] [APP→DOC]** — Spanish-only refusals (`Refused. No hay un perfil activo…`) surface to an English-doc reader. The page itself prints no commands so this is out of its scope, but the cluster it belongs to should set the Spanish-CLI expectation somewhere. No action on *this* page.

## Testimonial (first person)

Reading this page, I genuinely understood what a "saved calculation" is and why verifying isn't filing — the "What verifying does not mean" section is the clearest, most honest thing I've read in these docs, and the app backs every word: export really does refuse a plain draft, the tool really never phones AEAT, and the three states (Complete/Incomplete/Blocked) map one-to-one onto the actual classifier. Where the page quietly oversells itself is scope: it tells me verify measures *this* modelo and year against the agency's rules, so when the tool blocks me I'll go looking inside this draft — but the real check can block me because an *earlier* period is missing official evidence, and nothing on the page warns me that a Blocked verdict might live in another period entirely. Fix that one omission and this becomes an excellent explanation page.

## Scorecard

- **Doc clarity:** 4 / 5 (clear, well-structured, honest about limits; loses a point for under-scoping what "Blocked" can mean)
- **App capability:** 5 / 5 (every behavioral promise — immutable versions, report-saved-on-failure, three-state classification, export-refuses-drafts, no-AEAT-contact — is delivered exactly as described)
- **Findings by severity:** BLOCKER 0 · MAJOR 1 · MINOR 1 · NIT 2
