---
tags:
  - '#audit'
  - '#adr-corpus-reconciliation'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a0bbacb68911f0858289eb512f73dd6f7df6cdc89c8db6cde0ed1e09d5607d18'
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

### aic-routing-and-rate-box-implementing-rows-absent-from-plan | medium | two amendments ruling on code have no corresponding vault/plan Step

Both of the above amendments explicitly state "this amendment rules on code
and is not self-executing" and describe the corpus/implementation work as
"tracked as separate open rows." Searched .vault/plan/ for any Step naming
the AIC re-route, the rate-box per-block test, the recargo mismatch advisory,
or the art-161 re-key: none exists. The only tracking artefacts found are
ephemeral coordination-fleet task-board entries (not .vault/ documents,
not durable, not visible to a future reader of the ADR corpus). Per
plan-closure-requires-exec-records and this campaign's own discipline
("an ADR amendment that rules on CODE is not self-executing... open the
implementing rows in the same action as the amendment"), these amendments
currently read as in-force rulings with no durable row a future session can
find. Recommend a plan Step (or a small dedicated plan) enrolling: the AIC
re-route (M390 ISP-line to AIC-line correction plus its two cross-modelo
residues - AIC base imponible reaching no official box on either return, and
the zero rate-kind gap), the four-block rate-box precondition test, the
art-161 recargo re-key plus its blocked-on-ADR mismatch advisory.

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
deleted). D8a's own text states that the sibling ADR's status note is
amended to record the partial supersession in the same change that lands the
reinstated gate, referring to llm-evidence-classification-adr. That
follow-up edit does not appear to have landed: the "Partial supersession"
section in llm-evidence-classification-adr makes no mention of D8a or the
reinstatement.

This is a premise-superseded case in the dangerous direction the brief
described: the record is internally consistent, was accurate when written,
and its own prose gives no sign of age - the tell is entirely external (a
sibling proposed ADR's own text, plus the live gate's symbol set). A reader
of llm-evidence-classification-adr alone would conclude the cloud exception
is categorically gone; it is not - it is narrower than before, but live and
wired.

Not corrected in place: unstructured-document-ingestion-adr is proposed,
not accepted, so treating its D8a ruling as settled fact inside an already
accepted sibling ADR would be a premature acceptance-by-proxy - exactly
the kind of judgment call the reconciliation playbook reserves for human
resolution rather than silent rewrite. Recommend the amendment noted below.

## Recommendations

- Add a brief follow-up note to 2026-06-10-llm-evidence-classification-adr's
  "Partial supersession (2026-08-07)" section stating that the cloud
  exception was subsequently narrowed-and-reinstated by
  2026-08-07-unstructured-document-ingestion-adr D8a (currently proposed),
  scoped to in-memory HTTP providers only, and pointing at that record rather
  than restating its content. This is a factual-currency fix, not a new
  decision, and should land in the same change that ADR is (or is not)
  accepted, per D8a's own stated intent. Left unapplied here because the
  reinstating record has not itself been ratified.

- Open a .vault/plan Step (or small dedicated plan) enrolling the two
  amendments' implementing work: the AIC re-route (with its two named
  cross-modelo residues), the four-block rate-box precondition test, and the
  art-161 recargo re-key plus its ADR-gated mismatch advisory. Currently
  tracked only in an ephemeral coordination-fleet task board, which is
  invisible to a future reader of the vault corpus and does not satisfy
  plan-closure-requires-exec-records.

- When 2026-08-07-unstructured-document-ingestion-adr is ratified or
  rejected, its closing action should include landing the
  llm-evidence-classification-adr follow-up note above in the same change
  (as D8a itself already commits to), closing the drift identified in the
  high-severity finding.

No contradictions, duplications, or fragmented-decision clusters were found
in the reconciled set beyond the one drift finding above. The corpus's
handling of premise-superseded situations elsewhere in this cluster (the
activity-type-placement ADR's self-audit, the rate-box and IVA-routing
amendments' explicit withdrawals) is unusually disciplined and is noted as a
positive pattern worth preserving.
