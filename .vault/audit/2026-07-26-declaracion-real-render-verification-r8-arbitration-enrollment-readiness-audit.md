---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:30be5f9695d946f9fe6f8dd9b57fce2994eea1ac56f76ff74479befcd1ac9cf3'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - "[[2026-07-26-declaracion-real-render-verification-specimen-less-static-route-audit-audit]]"
---

# `declaracion-real-render-verification` audit: `what deciding the R8 reconcile-enrollment arbitration would take`

## Scope

This is a research pass on the R8 arbitration the governing ADR left
deliberately open in its Constraints section: the nine `declaracion_pdf`
profiles whose target casillas are engine-formula-computed but whose
modelo is not enrolled in the reconcile module own casilla-level
comparison set. Report-only, no production code, registry data, or test
changes; the M202 stale-docstring rationale found by the companion audit
stays a reported finding, not a fix. The semantic code index remained
truncated throughout and was not used as evidence.

Every claim below is grounded in one of: reading the live production code
path directly (never inferring behaviour from a docstring alone), loading
each revision own fragmented `formulas/`, `casillas/` and
`verification_expectations/` subdirectories with `tomllib`, or reading
`git log`/`git show` for the commits that built and expanded the enrolled
set. Each finding states which of these it rests on.

## Findings

### the-live-path-refuses-loudly-before-opening-the-file | high | confirmed by reading production code, not by inference

Read `_require_declaration_enrolled_modelo` and its caller `modelo_reconcile`
directly (`application/modelo/_reconcile.py`). For a `DECLARATION` source
kind, the enrolled-modelo check runs FIRST, before `parse_declaracion` is
ever invoked and before any file is opened; a modelo outside the enrolled
set raises `ReconciliationDeclaracionSourceUnsupportedError` immediately.
`modelo_reconcile_bytes` refuses declaration source kind unconditionally,
for every modelo including the six enrolled ones, since that path is not
offered for declaracion at all.

This confirms, rather than merely repeats, the ADR own "refuses loudly"
characterisation: for the one live, CLI-reachable path that could act on a
declaracion_pdf profile target, the nine unenrolled modelos hit a named,
typed refusal before any parsing or comparison work happens. Nothing is
silently discarded and nothing silently reaches a persisted revision.

### a-second-registry-scoped-arbitration-mechanism-already-exists-and-is-unwired | medium | modelo-agnostic, but reachable by no production caller today

`application.verification.verify_declaracion` is a separate, exported,
documented function that performs the same printed-vs-computed comparison
concept for ANY modelo and period the registry resolves, scoped entirely
by `RegistrySnapshot.verification_policy()` -- the same registry fold
`_reconcile_declaracion_casillas` (the reconcile module own comparison,
used by the six enrolled modelos) also consumes. It excludes
`input_kind == COMPUTED` casillas from the calculation inputs it feeds the
engine, then separately compares every casilla in
`policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids`
against the freshly computed result.

Searching all of `src/cadrumo` for its only production or test callers
finds exactly its own test module and its own package `__init__.py`
re-export -- zero callers in `entrypoints/` or anywhere else in
`application/`. It is not wired to any CLI verb, so it does not change the
"not a live defect" conclusion for the nine unenrolled modelos: it simply
cannot be reached today, by any modelo, enrolled or not. Its existence
does show that the underlying comparison logic is already registry-driven
rather than modelo-specific -- the six-modelo gate in
`_reconcile.py` is a separate, additional restriction layered in front of
a generic mechanism, not evidence that the comparison itself needs
modelo-specific work.

### every-r8-hit-casilla-is-already-declared-reconciled-by-the-registry-itself | high | independently confirmed against two registry sources, not by name

For all nine unenrolled profiles, the R8-hit casilla ids (the ones the
companion audit found intersecting a formula `target_casilla_id`) were
checked a second time against that same revision own
`verification_expectations` fold. Every single one is already a member of
`computed_casilla_ids` there: `115` (03, 05), `123/2019-2023` (06, 08),
`123/2024-y-siguientes` (03, 06, 09, 12, 14), all three `131` revisions
(04, 06, 07, 10, 13, 15 each), `180` and `193` (decl.base-total,
decl.retenciones-total each), `202` (03, 34). Two independent registry
sources -- the formula target set and the verification-policy fold --
agree on every casilla, for every profile.

`_reconcile_declaracion_casillas` docstring states this is "the same
policy `application.verification.verify_declaracion` consumes ... the
registry own declared reconciliation scope, never an ad hoc casilla
list", and its body contains no per-modelo special case beyond the
enrolled-set gate itself. So the comparison mechanism these nine profiles
would need already exists, is already fed by data the registry already
declares for them, and does not require new code to run correctly if the
gate admitted them.

### casilla-id-alignment-is-already-complete-for-all-nine-profiles | high | zero missing definitions, zero internal duplicates, checked directly

Re-checked, beyond the R8-hit subset, every target casilla id on all nine
profiles resolves to a real casilla definition in its own revision
(`missing_casilla_def` is empty for all nine), and no profile carries a
duplicate target id. The enrolled-set docstring names "confirmed to line
up with its registry casilla ids one-to-one" as its stated enrollment
criterion; by this measure alone, all nine already satisfy it.

### enrollment-order-is-development-sequence-not-a-technical-discriminator | high | measured directly from git history, three commits, exact dates

Read the full commit history that introduced and expanded
`_DECLARATION_CASILLA_RECONCILE_MODELOS`. `130` was enrolled alone first
(`7a0ed699b6`, 2026-07-02 21:06, "casilla-level divergence detection
first slice"). Thirty-two minutes later `111`, `190`, `303`, `390` were
added together in one commit (`9cd85c7c0b`, 2026-07-02 21:38, "enroll
M303/M390/M111/M190 in casilla-level reconcile"), whose own message states
"M200/M202 stay unenrolled: they declare no declaracion_pdf extraction
profile at all" -- true at that moment. `100` was added three days later
(`2b59a9fa06`, 2026-07-05, "close m100 pagos declaration reconcile"). No
enrollment has happened since.

This is a rollout sequence, stated in the commits own messages, not a
technical or evidential filter -- confirmed rather than inferred.
Cross-referencing against specimen status: five of the six enrolled
modelos (`100`, `111`, `190`, `303`, `390`) are exactly the five that carry
a real or facsimile specimen, but `130` -- enrolled first, before any of
the others -- has none, which the governing ADR own D2 already records
("Modelo 130 keeps its zero floor with neither justification ... an
evidence gap"). The correlation with specimen availability is real but
not the rule; `130` is the counter-example that shows order, not evidence,
governed the sequence.

### the-m202-docstring-was-true-when-written-and-went-stale-31-hours-later | medium | dates the companion audit finding rather than repeating it

The companion static route audit reported the enrolled-set docstring
falsely excludes Modelo 202 as having "no declaracion_pdf surface at
all". Read against git history: the docstring text was written in
`9cd85c7c0b` at 2026-07-02 21:38, when that was true. Modelo 202 own
`declaracion_pdf` profile was authored in a different feature slice,
`c57f2445cc` ("declaracion-pdf extraction profile for pago fraccionado
result casillas (#325 slice)"), at 2026-07-04 04:56 -- roughly 31 hours
later. Nobody swept the now-stale exclusion rationale when that profile
landed. This dates the drift rather than changing the finding, which
stays out of this report scope to fix (`application/modelo/_reconcile.py`
is not touched by this audit).

### all-nine-are-specimen-less-not-eight-of-nine | high | re-measured against every sidecar declared provenance, corrects the dispatch briefs assumption

Re-checked every fixture sidecar under the justificante and manual-annex
fixture trees for the six modelos behind the nine unenrolled profiles
(`115`, `123`, `131`, `180`, `193`, `202`): every one declares
`provenance = "synthetic_generated"`. None carries `real_corpus` or
`aeat_published_facsimile`. This means all nine of the nine unenrolled
profiles are specimen-less, not eight of nine -- the dispatch brief
assumption is corrected here the same way the earlier 19-vs-22 count was
corrected in the companion audit, by direct re-measurement rather than
by adjusting the report to match the expectation.

Per the governing ADR D3 ("an untestable profile is an evidence gap,
never a pass"), all nine are therefore undecidable today on the one axis
this research cannot supply: parser reliability against a real AEAT
render. The registry-data readiness found in the two findings above
(verification-policy scope, casilla-id alignment) is a separate, already-
satisfied precondition; it does not substitute for confirming the parser
extracts the right box under real typography, which is exactly the R2/R6
exposure the companion audit register already names for these same nine
profiles. What each would need is unchanged from that register: a
`real_corpus` specimen, or an `aeat_published_facsimile` annex where a
real filing cannot be sourced without taxpayer identity.

## Recommendations

Decide, as a follow-on ADR question, whether registry readiness alone
(verification-policy scope plus id alignment, both already satisfied for
all nine) is sufficient to enroll a modelo in
`_DECLARATION_CASILLA_RECONCILE_MODELOS`, or whether a specimen-backed
parser-reliability confirmation is also required before enrollment --
this research measured that all nine are registry-ready and all nine are
specimen-less, but does not itself rule on which precondition governs
enrollment. If a specimen is required, acquiring one for even one of the
nine (starting with whichever has the smallest target-count and
therefore the smallest surface for a parser defect to hide in, per the
companion audit exposure ranking) would let that decision be made on
evidence rather than argument.

Sweep the enrolled-set docstring own stale Modelo 202 exclusion rationale
in the same change that next touches `_reconcile.py`, since this research
now dates exactly when it went stale; this audit does not perform that
edit.

Treat the correlation between reconcile-enrollment and specimen
availability (five of six) as suggestive context for a future enrollment
decision, not as the rule that produced it -- the `130` counter-example
and the dated commit messages both show the actual driver was
development sequence.
