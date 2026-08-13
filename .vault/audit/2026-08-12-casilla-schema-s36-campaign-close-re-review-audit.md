---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:92571e5f91c2cda0a91b4860fd1f36015edc21000e24a24420283dc1f8030f7c'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-12-casilla-schema-s36-campaign-close-honesty-review-audit]]"
---

# `casilla-schema` audit: `S36 campaign-close honesty re-review`

## Scope

The second fresh-context honesty review of the casilla-schema campaign close, run after the seven findings of the first review were actioned. Conducted as a review-as-if-inherited pass rather than an independent dispatch, which the orchestration rule permits as one of its three sanctioned forms; the form is stated here rather than left for a reader to infer.

Measured against the decision statements of the four governing accepted ADRs, quoted below, never against a paraphrase.

## The four decision statements, quoted

**Canonical derivations.** "In `domain/calculations/registry`, four facade-exported derivations" - the binding-to-casilla reverse join `casillas_by_binding`, `relations_by_target_binding`, the promoted `relation_consumption_index` with `alternate_bindings` as its fourth channel, and `classify_official_boxes` returning a three-state status. Amended 2026-08-11: the gate is "no revision carrying ledger-IVA bindings contains a non-BOUND casilla declaring a binding", replacing an emptiness assertion the corpus refutes at a population of 50.

**Blocker spine.** "A new core StrEnum `OperatorActionAxis` ... whose members each name one distinct operator ACTION class", with each surface-reaching vocabulary declaring "one total projection table beside its own enum in its owning layer, asserted total at import", finding `message_facts` copied into `Notice.context`, and the duplicate discrepancy enums reconciled to one with the loser deleted in the same commit as its consumer sweep.

**Dead surface.** Adjudicate `verify_declaracion` against the live reconcile surface with "a written per-capability disposition table in the exec record", then delete the `application/verification` package, its tests and the registry rows naming it; delete the strict bound-input resolver and both facade exports; wire `verify_export` into `export_draft` as a post-write self-check; delete `_BINDING_SOURCE_TO_READINESS`.

**Read model.** "One frozen pydantic model `ModeloWorkReview` with a single producer `build_modelo_work_review(...)`, exported through the `application.modelo` facade", the nullable official reference derived from the canonical classification and never from `export_refs`, one `BlockerRef` shape at both grains, progress counts against a named manifest denominator with no ratio tokens in field names, and `modelo.requires` widened rather than replaced.

## Disposition of the first review's seven findings

**spanish-casilla-stem - resolved.** The English alias family over the AEAT casilla concept was destructively renamed to one Spanish-stem authority under S82. The exact Spanish-stem conformance gate passes all five nodes.

**m303-revision-split-regression - resolved.** The real M303-quarter-to-M390 end-to-end suite law-selects each live split revision and passes all four scenarios (S83). The retired revision identifier has no remaining Modelo 303 location in any executable, test, fixture or locale surface, and the hard-cut structural gate that measures this passes (S88).

**retired-verification-locales - resolved.** Re-measured at current HEAD rather than executed from the stale finding: the retired family is already absent from all four catalogues and `dev.locales scaffold --check` reports `ok` for each (S84). The Step closed on verification.

**stale-relation-applicability-counts - resolved.** The seven hardcoded tallies are replaced by invariants derived from the loaded authority - a registry-derived row set, a total applicability partition, a per-row join back to the revision's own dependency classification - with two out-of-repository bite proofs (S85).

**generated-feature-index - resolved.** Regenerated through its owning verb; the feature-scoped vault check is clean.

**iva-stem-gate-prose - resolved.** Three vault lines, not the two the first review named: the paragraph reporting the finding reproduced the prohibited token itself, so correcting only the named pair would have left the gate red. All three now state the same conclusion without it (S86).

**s02-empty-description - resolved.** The checked S02 execution record's required Description is authored (S86); the feature body-sections check is clean.

## Findings

### m303-deducible-fold-regression | high | resolved in-session

Three modules were red at HEAD on a signature unrelated to any casilla-schema surface: an unevidenced purchase's IVA did not reach the deducible casillas. The cause is the aggregation candidate gate, which refuses an input-IVA row lacking an exact `IvaDeductionFactKind` and immutable provenance and drops it with the typed `MISSING_DEDUCTION_CLASSIFICATION` reason. Two gates bind on two different axes and neither displaces the other: aggregation gates the deduction CLASSIFICATION, verify gates the attached invoice DOCUMENT under LIVA art. 97. The fold-then-block-at-verify contract those modules were written for was never broken; the rows needed classification to be folded at all. Fixtures modernised on the outgoing leg only, scenario preserved. The sibling bucket-aggregation module carried the same regression outside the campaign's scope and was absorbed rather than left (S91).

### spanish-casilla-label-coverage | medium | resolved in-session

The M303 revision split left shared continuity casilla-label keys unresolved in the mandatory Spanish source (S90), and no gate measured the property tree-wide. A gate now sweeps every modelo, revision and casilla through the production resolver chain and is proven to bite from outside the repository (S92). It deliberately measures through `resolve_modelo_localization` and never through catalogue YAML: the resolver walks an ordered key chain whose first entry is only the revision-specific tier, so a direct read reported 201 missing labels per revision where the true figure was 84.

### cutover-gate-attribution | medium | resolved in-session

The retired-identifier gate carried two attribution defects that made a clean corpus read as violated. It judged a line by its enclosing function, so a Modelo 180 assertion about that modelo's own live identically-named revision was flagged because an unrelated keyword forty-five lines away mentioned Modelo 303; and its selector check flagged any container carrying both a modelo token and a revision id, which every work-unit, receipt and report fixture satisfies now that two live M303 revisions are bare four-digit years. Both narrowed and bite-proved (S88).

### registry-diff-anchors | low | resolved in-session

The span split invalidated two registry-diff anchors. Orden HAC/819/2024 moved to revisions the year-keyed diff entry point refuses as ambiguous, so the gained-a-later-orden witness is unreachable through that surface; the dropped-superseded-orden half is asserted and the unreachable direction stated rather than fabricated. The added-parameters anchor moved to the two transitional reduced-rate percentages the 2023 revision introduces (S88).

## Recommendations

- Clear `.git/index.lock` and land the campaign's final commit. Every Step above is complete and verified in the working tree; the single remaining action is a staging operation no agent in this worktree may perform, because removing anything under `.git/` is absolutely forbidden.
- Treat the Modelo 303 deducible-fold episode as the standing argument for measuring a regression before repairing its fixtures. Four plausible causes - the prorrata no-volume-data branch, the revision split, the recent supply-nature classification work, and the verify-time evidence gate - were each excluded by evidence before the real one was named, and three of the four would have produced a confident, wrong fixture edit.
- Prefer the production resolver over the catalogue file whenever a localisation gap is counted. The YAML read overstated the Modelo 303 gap by more than a factor of two, and a gate written against it would have failed loudly on a corpus that renders correctly.
- Do not re-create the retired campaign rule. Its durable mandates are carried by the permanent rule corpus and by these audits, which is where the centralisation rule places a campaign lesson.

## Verification

- Full tracked-suite serial collection `pytest src dev packaging --collect-only -q -n 0 --override-ini=addopts=`: 32,665 tests collected, exit zero.
- Campaign gate battery over the eight affected modules: 47 passed.
- Registry authority `validate_registry()`: clean.
- Every Modelo 303 casilla label resolves in all four catalogues across all six revisions: zero unresolved, measured through the production resolver.
- `python -m dev.locales scaffold --check`: `ok` for `ca`, `en`, `es`, `hu`.
- Feature-scoped vault check: clean.
- Every closed Step carries a matching execution record; P11 holds no open steps.

## Carry-forward

One item, environmental rather than substantive, and it is not deferred work: **the campaign's final commits have not landed.** `.git/index.lock` has been held since 19:31:00 with a frozen mtime and no HEAD movement for over an hour - a dead holder. Removing anything under `.git/`, including the lock, is absolutely forbidden by the worktree-safety rule, so it is reported rather than worked around. Every Step recorded above is complete and verified in the working tree; what remains is a single staging operation that no agent in this worktree can perform until the lock is cleared by its owner.

During this review a peer's uncommitted previous-filing coverage validator transiently reddened whole-tree registry validation on Modelo 130 and Modelo 720. The peer reverted it and validation recovered; every figure above was re-measured after the recovery. It is recorded because a reader comparing timestamps would otherwise see two contradictory verdicts.

## Verdict

**PASS.** All seven findings of the first review are resolved with verification. Four further findings surfaced by this pass were actioned in-session, none deferred. Completion measured against the quoted decision statements of the four accepted ADRs, not against a narrowed reading.

The campaign is structurally complete subject to the single environmental carry-forward above.
