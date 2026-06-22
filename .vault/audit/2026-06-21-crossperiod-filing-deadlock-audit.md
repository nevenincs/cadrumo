---
tags:
  - '#audit'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
related:
  - "[[2026-06-19-crossperiod-filing-deadlock-adr]]"
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace crossperiod-filing-deadlock with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `crossperiod-filing-deadlock` audit: `Cross-period filing deadlock remediation - code review`

## Scope

Code review of the cross-period filing deadlock remediation (campaign finding C0), implemented in two commits on `chore/eliminate-shims`: `6e635f566` (Decision A, late local `work file` for closed-window targets) and `84add274d` (Decision B same-year scope, within-year `app_filing` local-chain export with a disclosing advisory). Touched surfaces: `src/aeat/application/workflow/_engine.py`, `src/aeat/application/calculations/_cross_period_clean_state.py`, `src/aeat/application/modelo/_verification_actions.py`, and their tests, plus the owned size-budget ratchet. The review prioritises the safety boundary: this is a safety-adjacent gate, and Decision B relaxes the cross-period clean-state guard, so the anti-laundering partition (locally-clean advisory vs genuinely-unclean blocking) is the load-bearing concern. Method: independent dispatch via `vaultspec-code-reviewer` over the diffs and HEAD source, plus coordinator confirmation of the relaxation boundary, the cross-year canary test, the `app_filing` data invariant, and the legal-catalogue ids.

## Findings

### Verdict

**approve-with-findings.** Both commits are safe to merge. The anti-laundering boundary is airtight; all findings are MEDIUM-and-below (consistency / grounding polish), none blocking.

### Safety verdict (anti-laundering boundary) — SOUND

`_relax_same_year_local_chain` (`src/aeat/application/calculations/_cross_period_clean_state.py:661-681`) is airtight. It is a conjunction of four guard clauses, each returning the evidence unchanged on failure; only the final `model_copy` clears blockers and stamps the advisory:

- **Cross-year guard** (`:671`): `requirement.filing_year != target_filing_year` returns unchanged. `requirement.filing_year` is the upstream (prior) period's year; `target_filing_year` is `snapshot.filing_year` at the call site. The M100/2024 folding an unevidenced M100/2023 case has `2023 != 2024`, so it stays BLOCKING. Confirmed end-to-end by the canary `test_verify_gate_blocks_chain_carrying_non_official_prior_year` (asserts `granted_verificado_completo is False` plus a BLOCKING `cross_period_dependency_unclean` finding naming "100"/"2023").
- **Source-kind guard** (`:673`): only `observation_source_kind == "app_filing"` is relaxed. An `operator_manual` prior also carries a separate `OPERATOR_MANUAL_SOURCE` blocker, so it is double-protected (fails this guard AND the subset guard).
- **Non-empty-blockers guard** (`:675`): a genuinely-clean row is returned unchanged (no spurious advisory).
- **Subset guard** (`:677`, load-bearing): `set(evidence.blockers) <= {MISSING_AEAT_ACCEPTANCE, MISSING_EXTERNAL_EVIDENCE, LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE}`. The blocker list is additive and merged into one set during evaluation, so `OBSERVATION_REVISION_VALUE_DIVERGENCE`, `REGISTRY_REVISION_DIVERGENCE`, `MISSING_OBSERVATION`, `MISSING_CURRENT_FILING_RECORD`, `OPERATOR_MANUAL_SOURCE`, and group-member coverage blockers each break the subset relation and keep the dependency BLOCKING. The relaxation fires only when the blocker set is exactly a subset of the three official-evidence-delta blockers.

The relaxation never inspects or asserts `aeat_accepted=True`; `file_modelo_revision` sets `aeat_accepted=False`, so nothing is laundered past an AEAT-acceptance assertion. `app_filing` remains absent from `_OFFICIAL_SOURCE_KINDS` (preserved verbatim by `test_app_filing_source_kind_is_not_official_evidence`). The relaxation is applied uniformly across `PREVIOUS_FILING_BINDING` and `REGISTRY_RELATION` origins, so the M100 fold-in and the M130/M303 carry are covered identically, and grupo-member gaps stay blocking.

### MEDIUM

- **No production-code defects.** The review surfaced no MEDIUM-or-higher defect in shipped logic. Finding A3 below (legal-catalogue existence) was raised at MEDIUM-informational by the reviewer and **resolved to SOUND** by coordinator confirmation: `ley-58-2003:art-119` and `:art-120` exist in `legal/lgt-autoliquidacion.toml` with `corpus_ref`; `ley-37-1992:art-99` exists in `legal/iva.toml` with `corpus_ref`; `rd-1065-2007:art-9` exists in `legal/censo.toml` with `corpus_ref`. All cross-period finding legal_refs resolve to real, corpus-backed catalogue entries.

### LOW / NIT

- **A1 (NIT) — advisory finding omits `legal_refs`.** `_cross_period_non_official_local_chain_advisory_finding` (`src/aeat/application/modelo/_verification_actions.py:843-869`) does not set `legal_refs`, while every sibling cross-period finding gained them in the same commit. The disclosing advisory is the operator's primary signal that they rest on a non-official local chain; omitting its legal basis (`ley-58-2003:art-119/120`) is a minor inconsistency with `aeat-calculation-grounding`. Remediation: add `legal_refs=_cross_period_dependency_legal_refs(requirement.origin_ids)`.
- **A2 (LOW) — advisory prose is an English literal, not a locale key.** The advisory `message` / `next_action` are hardcoded English, not `tr(...)` keys. This matches the local precedent of the sibling suppression advisories (which are also literals) rather than introducing new drift, but per `aeat-locales-cli` operator prose should route through the locale catalogue. Remediation: author the strings via `python -m aeat.locales set ...` if the surrounding findings are migrated.

### Confirmed SOUND

- Decision A re-scope fires only for `WorkflowPurpose.FILE` with an explicit target whose `filing_year != today.year`; the as-of-today `pending_obligations` projection keeps `today.year` (single-producer invariant intact).
- `NO_PENDING_OBLIGATION` still aborts a never-existing obligation (the `obligation is None` check runs after the re-scope); the `NoDeadlineWindowsError` fallback cannot mask a real obligation.
- `work file` contacts AEAT zero times (the submission filing-window preflight is skipped for `FILE`); `aeat-safety-legal-gates` is not weakened. The overdue admit records the `extemporanea`/`overdue` marker then returns the obligation so the carry observation is persisted.
- `no-silent-under-declaration` honoured: the relaxed dependency emits a visible WARNING `ADVISORY`, never a silent grant; a WARNING keeps the verify grant open via `_classify_verification_outcome` without a silent `pass`. The BLOCKING `CROSS_PERIOD_DEPENDENCY_UNCLEAN` still fires for every non-relaxed unclean dependency.
- Test integrity: real-behaviour, real-adapter, no mocks/skips/xfail/tautology. The reconciled same-year test was UPDATED (not deleted) — assertion (a) flipped blocks→clean+advisory+blocker-cleared, assertion (b) flipped `pytest.raises` → admit-with-advisory, and it ADDS a cross-year non-relaxation assertion; seeds are read back from the persisted revision (anti-tautology).
- No parallel carry mechanism (`calculation-source-canonical-mechanism`, `one-aggregation-path-pull-equals-calculate`): the carry still reads the single `previous_filing` observation; Decision B only reclassifies the verdict. The facet mirrors the existing `NoPriorObligationProvenance` pattern (`aeat-architecture-boundaries`, no shims).

### External-state note (owner-distinguished)

At audit time the working tree carries an UNRELATED peer campaign's in-flight M100/2024 registry edit (the construct `0002-renta-2024-mini-model-actividades-economicas-directa.toml` modified ` M`, plus new untracked ledger bindings `0021`-`0025`, an incomplete construct legal-grounding sweep — the mixed-income aggregation work). This raises `RegistryValidationError` / `ModeloAggregationBindingError` at registry-load / calculate time and reds 54 tests in `test_cross_period_clean_state.py` and the two e2e files BEFORE the C0 verify gate is reached. Per `full-tree-gate-must-distinguish-owner`, those reds are owned by the mixed-income campaign, not this feature. The C0 logic surfaces are green at HEAD: `test_engine.py` 47/47, `test_local_cross_period_carry.py` 5/5, with zero non-registry assertion failures. Do NOT attribute the reds to the C0 commits and do NOT edit the peer registry files.

## Recommendations

- Action A1 (NIT) in a follow-up: attach `legal_refs` to the non-official-local-chain advisory finding so its legal basis is disclosed at parity with its sibling findings. Low effort, isolated to `_verification_actions.py`.
- Treat A2 (LOW) as deferred: migrate the advisory prose to the locale catalogue only when the sibling suppression advisories are migrated, to avoid partial locale drift.
- No change required for the safety boundary, Decision A, or the tests — confirmed sound.
- Peer churn: leave the M100/2024 registry reds to the mixed-income campaign owner; re-run the C0 surface once that campaign's construct legal-grounding sweep lands to confirm 88/88 green on a clean registry (it was green at the two commits' authoring time).

## Codification candidates

Two candidates were proposed by the authorizing ADR and survive this review; both are eligible (the implementation landed and is green, satisfying the "held across at least one full execution cycle" bar). They are recorded here but NOT promoted in this pass, because promotion is the discretionary sixth pipeline phase and lies outside the requested deliverable (research, ADR, plan, code review); the second candidate's wording must additionally be updated to the implemented same-year scope before promotion. Defer to a follow-up codify pass.

- **Source:** Decision A (the FILE-gate year re-scoping and late local filing).
  **Rule slug:** `late-local-work-file-allowed-for-existing-overdue-obligation`.
  **Rule:** A LOCAL `work file` (mark-as-filed, no AEAT contact) MUST be permitted for a closed / overdue window when the obligation genuinely existed for the target `(modelo, period, year)` — recording the registry-grounded extemporanea / recargo marker — and MUST still refuse `NO_PENDING_OBLIGATION` a target for which no obligation ever existed; the obligation schedule for an explicit FILE target is resolved against the target period's filing year, never `today.year`.

- **Source:** Decision B (the same-year locally-clean tier) and finding A1 (the disclosing advisory must carry its grounding).
  **Rule slug:** `local-filing-chain-exports-with-non-official-advisory`.
  **Rule:** A SAME-FILING-YEAR cross-period dependency whose ONLY blockers are the official-evidence delta over a present, value-consistent, revision-confirmed `app_filing` local chain MUST verify and export with a NON-BLOCKING, legally-grounded non-official-local-chain advisory (never a silent grant); a cross-YEAR prior, an `operator_manual` source, value/revision divergence, and missing observation/filing stay BLOCKING, and the official-evidence demand stays BLOCKING for any AEAT-acceptance assertion. This refines, and must be promoted in lock-step with, `local-filed-observations-are-non-official-evidence`.
