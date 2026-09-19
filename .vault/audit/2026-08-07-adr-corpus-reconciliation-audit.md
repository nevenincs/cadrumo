---
tags:
  - '#audit'
  - '#adr-corpus-reconciliation'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:299b41afa93688fdb98da21a1978a04461ffd8d869e3a3227f1b33df6802afed'
related: []
---
# `adr-corpus-reconciliation` audit: `Reconciling the ADR corpus against HEAD`

## Scope

Reconciles the ADR corpus against HEAD following a night of heavy decision churn:
amendments, corrections, refutations, and records whose premises may have been
invalidated by later work. Scoped to the records the dispatching brief named
plus what those records led to. This is not a full 625-ADR sweep; it is a
targeted reconciliation of the cluster the brief identified as high-risk,
plus the mechanical precondition pass (vault check all --fix) over the
whole corpus.

## Findings

### rate-box-evidence-assertion-precondition | low | correction fully landed, no third instance survives

2026-08-07-rate-box-evidence-assertion-adr claimed the two-layer rate-box
shape "generalises to every rate-keyed box in the registry." Measured false:
M303's [27] total-cuota-devengada formula enumerates the tier cuota boxes
directly (including the RD-ley 4/2024 transitional rungs), so it has no
rate-blind total for a second layer to feed - a rate-blind sibling there would
double-count. Verified at HEAD (221fb5b562, c8392873fb, a1fd812d8c,
63c69e8b08, all ancestors of HEAD): the generalisation claim now carries its
precondition explicitly ("whose modelo carries a rate-blind total"), the
Constraints section correctly demotes the four unmodelled regimen blocks to
"CANDIDATES to follow this decision, not inheritors of it," and a dedicated
Amendment section documents the M303 counterexample and withdraws the
original unqualified claim. A corpus-wide grep for the unqualified phrase
("generalises to every rate-keyed box") returns exactly this one file, and
only in its corrected (qualified) form. No third instance survives. Status
accepted is accurate - nothing here needs action.

### iva-routing-carry-withdrawal | low | false-absence claim correctly withdrawn, Tier 2 gate correctly closed

2026-06-09-modelo-iva-routing-carry-adr's 2026-08-07 amendment first draft
asserted LIVA art. 85 was absent from the legal catalogue/corpus and that the
Tier-2 grounding gate had grown to nine articles. Both claims were false - the
grep used id = "..." while the catalogue declares entries as
[legal."..."] table headers, a syntax mismatch that produces a false
absence rather than an error. Verified at HEAD (63b0014c4e, 8cf1e93007,
both ancestors): the record's own text now states the withdrawal explicitly,
names the measurement method that produced the false absence, and states "Tier
2 is no longer grounding-gated for this routing." This is not described as
open anywhere in the current body. Confirmed independently: art. 85 and all
eight previously-missing articles are grounded and resolve through the live
legal-catalogue resolver. No action needed.

### aic-routing-and-rate-box-implementing-rows-absent-from-plan | medium | closed: plan opened, both ADRs repointed at it

Both of the above amendments explicitly state "this amendment rules on code
and is not self-executing" and described the corpus/implementation work as
"tracked as separate open rows." Searched .vault/plan/ for any Step naming
the AIC re-route, the rate-box per-block test, the recargo mismatch advisory,
or the art-161 re-key: none existed. The only tracking artefacts found were
ephemeral coordination-fleet task-board entries (not .vault/ documents, not
durable, not visible to a future reader of the ADR corpus).

Closed by this reconciliation: opened
2026-08-07-adr-amendment-implementing-rows-plan (tier L1, related to all
three governing ADRs) with Steps S02 (the AIC re-route plus its two named
cross-modelo residues), S03 (the four-block rate-box precondition test), S04
(the recargo mismatch advisory, blocked on recargo-equivalencia-source-of-truth-adr
reaching accepted), S05 (the art-161 re-key - recorded CLOSED rather than
pending, since d43bd3366a is an ancestor of HEAD; a Step reading open when
its work is done is the same class of lie as one reading closed when it is
not). Then re-checked both amended ADRs' own text: modelo-iva-routing-carry-adr
said "the corpus work and the re-route are tracked as separate open rows" -
rewritten to name S02 by plan stem directly. rate-box-evidence-assertion-adr
did not use that exact phrase but had no pointer at all for its per-block
test obligation - added one naming S03. The phrasing that made the tracking
invisible in the first place ("separate open rows" with nothing to resolve
to) no longer appears ungrounded anywhere in the reconciled set.

One tooling gap surfaced while closing this: `vault add exec --step S05`
refuses to scaffold an execution record because a cluster-plan's feature tag
carries no ADR of its own (by design - it spans three ADRs under different
feature tags). S05's provenance rests on the plan's Description prose plus
the citable commit sha rather than a formal exec artifact; scaffolding under
a wrong feature tag to work around the refusal would have been worse; a
mis-tagged exec record looks like provenance while pointing at the wrong
feature.

### llm-invoice-read-reconciliation-still-blocking | low | genuinely current, correctly proposed

2026-08-06-llm-invoice-read-reconciliation-adr is status: proposed and
carries two explicit open operator rulings (domestic-vs-not discriminator;
transcribed taxable base). Verified: the file has received zero commits since
its creation, and classify_iva in domain/iva/_classification.py shows no
evidence of the domestic-discriminator question having been resolved in code.
The blocker recorded against it (a fleet task-board item citing this ADR as
blocking classify_iva's fate) is accurate at HEAD. No stale-blocker
condition found here - this is a live, correctly-scoped block.

### corpus-data-hydration-already-corrected | low | prior stale-governance finding already fixed in the record

The corpus-hydration ADR's Implementation section was reported (fleet
task-board history) as prescribing a CLI verb (aeat manual fetch) a later
test forbids. Read at HEAD: the record already carries an inline correction
naming test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry and
describing the actually-runnable mechanism
(dev/corpus/sync_aeat_record_design_corpus.py --pull). Confirmed the named
test file exists in the tree. No further action needed; this was fixed
before this reconciliation pass began.

### output-casilla-id-question-already-has-a-record | low | T-05 "needs a superseding ADR" is satisfied

A prior finding held that the reverted output_casilla_id schema field
needed a superseding ADR before the underlying structural question could be
closed. 2026-08-07-calculation-chain-integrity-binding-output-casilla-declaration-adr
already exists, is status: proposed, correctly frames the reverted
implementation as evidence rather than a live artefact, and does not reopen
the settled W01 T-05-pattern ruling - it raises a narrower, undecided
structural question (can a binding selector ever declare a match casilla
distinct from its output casilla) and records three options without
choosing. This is exactly the shape the reconciliation playbook wants for an
undecided structural gap: recorded, not silently authored around. No action
needed.

### activity-type-placement-adr-self-corrected | low | exemplary self-audit already present, tripwire verified live

2026-08-07-calculation-chain-integrity-activity-type-placement-adr records
its own violation: W03.P05.S11 shipped Transaction.tipo_actividad (the
activity-type VALUE on the row), which the ADR's own Option B explicitly
rejects. The record's amendment states this plainly, attributes it to a
discovery-discipline gap (code was searched, decisions were not), and installs
a tripwire test rather than silently absorbing the drift. Verified:
src/cadrumo/tests/test_tipo_actividad_single_home.py exists in the tree and
is committed. This record needs no correction - it is the model case for how
a "premise superseded by later code" situation should be handled, and is
cited here as a positive example rather than a finding needing action.

### llm-evidence-classification-off-taxonomy-status | mechanical | fixed

2026-06-10-llm-evidence-classification-adr carried H1 status "accepted,
partially superseded," outside the canonical taxonomy (proposed,
accepted, rejected, superseded, deprecated). Per the taxonomy,
superseded always names a full replacement; a partial supersession is
recorded in prose (which this record already does, extensively, under its
own "Partial supersession (2026-08-07)" heading), not encoded in the status
token. Normalized the H1 to accepted. vault check adr-status is now
clean on this file.

### stray-concept-sweep-missing-h1-status | mechanical | fixed

2026-08-07-stray-concept-sweep-iva-purchase-refund-representation-adr had
no parseable status: its H1 stated the status parenthetical without the
canonical Title-pipe-status pipe-delimited form the taxonomy tooling parses.
Normalized the H1 to the canonical encoding, preserving the already-correct
proposed value. vault check adr-status is now clean on this file.

### llm-evidence-classification-partial-supersession-text-is-now-stale | high | an accepted ADR asserts a deletion the tree no longer carries

2026-06-10-llm-evidence-classification-adr's own "Partial supersession
(2026-08-07)" section states that 2026-08-06-llm-package-split-adr deletes
the consent gate, the cloud_evidence_upload capability, the
cadrumo_evidence_gestor_mode and cadrumo_evidence_cloud_upload_permitted
settings, the evidence-acknowledged flag and the subprocess provider
family outright, so the narrow cloud exception this record sanctioned no
longer exists in the tree.

Measured at HEAD: the subprocess provider family and the
evidence-acknowledged flag are indeed gone (confirmed against
src/cadrumo/tests/test_cloud_transport_fully_deleted.py's declared deleted
symbol set). But cadrumo_evidence_gestor_mode and
cadrumo_evidence_cloud_upload_permitted are present in
src/cadrumo/core/config.py and actively read
(src/cadrumo/application/user_profile/_capabilities.py,
src/cadrumo/llm/_consent.py,
src/cadrumo/entrypoints/cli/_config/_check_cli.py), and
ServiceCapability.CLOUD_EVIDENCE_UPLOAD exists and is wired at the
LLMClient.complete dispatch choke point. The claim "no longer exists in the
tree" is false at HEAD for these four symbols.

The reason is a third, still-proposed record:
2026-08-07-unstructured-document-ingestion-adr, section D8a, explicitly
reinstates exactly these symbols behind a narrower consent gate scoped to the
in-memory HTTP providers only (never the subprocess family, which stays
deleted). D8a's own consolidated-supersessions paragraph commits to amending
2026-08-06-llm-package-split-adr's status note (the ADR that carries D5, the
decision D8a partially supersedes) "in the same change that lands the
reinstated gate" - but as originally written it named only that record, not
llm-evidence-classification-adr, even though llm-evidence-classification-adr
is the file whose own prose asserts the now-false claim. Checked: neither
follow-up had landed - llm-package-split-adr carries zero mention of D8a or
the reinstatement either.

This is a premise-superseded case in the dangerous direction the brief
described: the record is internally consistent, was accurate when written,
and its own prose gives no sign of age - the tell is entirely external (a
sibling proposed ADR's own text, plus the live gate's symbol set). A reader
of llm-evidence-classification-adr alone would conclude the cloud exception
is categorically gone; it is not - it is narrower than before, but live and
wired.

Not corrected in place on llm-evidence-classification-adr itself:
unstructured-document-ingestion-adr is proposed, not accepted, so treating
its D8a ruling as settled fact inside an already accepted sibling ADR would
be a premature acceptance-by-proxy - exactly the kind of judgment call the
reconciliation playbook reserves for human resolution rather than silent
rewrite.

Applied instead: unstructured-document-ingestion-adr's own consolidated-
supersessions paragraph (in its Consequences section) now explicitly names
llm-evidence-classification-adr alongside llm-package-split-adr as needing
the same follow-up note in the same change, and states plainly that this
audit found it uncorrected while the record was still proposed. This puts
the pointer where whoever ratifies D8a will see it directly, not only in
this audit.

### output-casilla-id-framing-checked-against-tonights-fourth-enum-member | low | framing survives, unaffected

Follow-up check: a fourth IvaFlowDirection member, OPERACION_CON_INVERSION,
landed tonight (src/cadrumo/domain/iva/_flow.py, the supplier's side of a
reverse-charge operation, deliberately contributing to NEITHER settlement
side). Asked whether this is the kind of schema change the
binding-output-casilla-declaration-adr's framing needs to survive, since it
is exactly the sort of precedent someone could later cite.

Checked: it is not analogous. The new member widens the VALUE SET of an
existing field (flow_direction) that _IvaLedgerSelector already carries; the
ADR's structural claim is that _IvaLedgerSelector has NO FIELD AT ALL to
express a casilla-divergence (a different axis - a missing selector field,
not a missing enum value). Also checked whether OPERACION_CON_INVERSION's
landing exercised the gap in practice: it has zero production registry
consumers (only its own definition and test file reference it), so no
binding has yet tried to route it through the casilla-declares-binding
mechanism at all, let alone hit the missing-field wall. The ADR's framing is
unaffected and needs no correction.

### amended-adrs-now-point-at-the-plan | mechanical | closed by this reconciliation

Verified both ADRs' closing text points at
2026-08-07-adr-amendment-implementing-rows-plan by name rather than at
"separate open rows": see the closed finding above for the exact edits.

## Recommendations

- When 2026-08-07-unstructured-document-ingestion-adr is ratified (or
  rejected), land in the same change: a follow-up note on
  2026-06-10-llm-evidence-classification-adr's "Partial supersession
  (2026-08-07)" section, and the equivalent note on
  2026-08-06-llm-package-split-adr's D5 status line, each stating that the
  cloud exception was narrowed-and-reinstated by D8a, scoped to in-memory
  HTTP providers only, pointing at that record rather than restating its
  content. This is a factual-currency fix, not a new decision. The pointer
  to do this now lives in D8a's own text (added by this reconciliation), not
  only in this audit.

No contradictions, duplications, or fragmented-decision clusters were found
in the reconciled set beyond the one drift finding above. The corpus's
handling of premise-superseded situations elsewhere in this cluster (the
activity-type-placement ADR's self-audit, the rate-box and IVA-routing
amendments' explicit withdrawals) is unusually disciplined and is noted as a
positive pattern worth preserving. The corpus was scoped to the named
cluster rather than swept in full: the rest of the 625-record corpus is
unswept, not clean.
