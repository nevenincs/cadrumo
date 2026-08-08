---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:58df469be32d8c54b28cd728e20160a124f5add893dbcd8e660318c06c6da88f'
step_id: 'S03'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-classification-reference]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Classify each census row as calculation input, reconciliation target only, or display only

## Scope

- classification only, no production files

## Description

- Find the registry's own classification axis rather than inventing one: the
  closed `treatment` field on each dependency classification, declared per source
  modelo per revision with its own required legal and source refs.
- Join all 81 pulled-reachable carry bindings to the treatment governing each,
  through `relation_refs` for a relation slot and through the dependency on the
  selector's source modelo for a previous-filing binding.
- Read each row's own declared legal refs rather than transferring a sibling
  modelo's rationale.
- Establish what the calculation layer actually does with the declared treatment.
- Persist the classification as a committed reference.

## Outcome

52 bindings are calculation inputs, 12 are reconciliation targets only, 17 cannot
be classified from their own declaration, and the display-only bucket is EMPTY by
measurement: every one of the 81 is wired into a binding a formula reads, so none
of them exists merely to be shown.

The classification is grounded per row and non-analogically, because the registry
declares it per row. Modelo 100's dependency on modelo 130 is
`direct_annual_settlement` citing `rd-439-2007:art-109` and
`orden-hac-277-2026:art-3`. Modelo 100's dependency on modelo 193 is
`factual_evidence` citing `ley-35-2006:art-99`, `rd-439-2007:art-108` and
`orden-eha-3377-2011:art-1` — the retención the taxpayer SUFFERS while the payer
files it. Modelo 303's dependency on its own prior quarter is `factual_evidence`
citing `ley-37-1992:art-99`, `art-115`, `art-116` and `rd-1624-1992:art-71`,
`art-29`, `art-30`. Modelo 200's prior-year bases imponibles negativas are
`factual_evidence` citing `ley-27-2014:art-26`, `art-25`, `art-13`. Modelo 390's
dependency on modelo 303 is `direct_annual_settlement` citing eleven provisions.
None of those rationales was carried across from another modelo.

Two findings the ruling needs.

FIRST: the calculation layer does not act on the distinction. The only production
read of `classification.treatment` on the resolution path is in
`relation_source_requirements`, which folds it into the requirement's GROUPING
KEY. It discriminates which requirements bucket together and gates nothing, so a
`factual_evidence` relation and a `direct_annual_settlement` relation resolve
identically into binding values.

The precise statement is stronger than "the classification is unused". A pulled
modelo 193 retención is evidence of tax SUFFERED, which this taxpayer did not file
and the payer did. A pulled modelo 130 pago fraccionado is a payment this taxpayer
made and filed. Those are different legal objects carrying different provenance,
and they reach the annual return by the identical path: THE ENGINE CANNOT TELL
THEM APART AT THE POINT IT CONSUMES THEM. The registry draws the line; the code
has no access to it where the consumption happens.

SECOND: the registry is silent on 21 % of the carry surface. 15 `previous_filing`
bindings and both `iva_compensation_annual_partition` bindings are governed by no
dependency classification at all — modelo 100 negative-base carry, modelo 130
prior pagos and negative results, modelo 131 negative results across four
revisions, modelo 353 prior modelo 322 figures, modelo 720 prior-year valuation
baselines, and modelo 390's two compensación partition slots. There is no
declared treatment to read, and classifying them would require the analogy this
step is forbidden to draw — correctly forbidden, since modelo 720's valuation
baseline and modelo 130's negative results are not the same kind of carry.

## Verification

    uv run --no-sync python <scratch>/classify_probe.py
    total pulled-reachable carry bindings examined: 81
        2  iva_compensation_annual_partition | UNDECLARED
       15  previous_filing | UNDECLARED
        2  previous_filing | factual_evidence
       52  relation_prefill | direct_annual_settlement
       10  relation_prefill | factual_evidence

The class counts sum to 81, matching the census subtotal exactly, which is the
check that no binding was silently dropped between the two steps. The probe also
enumerated the 17 undeclared rows individually rather than reporting a count, so
each is named in the reference and can be checked one at a time.

The declared legal refs quoted above were read off the loaded authority rather
than transcribed from prose, through a direct print of each sampled dependency
classification's `treatment`, `legal_refs` and `source_refs`.

No pytest lane was run: this step produced no production code and no test.

## Notes

The probe reports the two modelo 390 partition slots as not-pullable. That is a
PROBE ARTEFACT, not a finding: the reachability column derives the source modelo
from a relation or a previous-filing selector, and those two slots carry neither,
so the derivation yields an empty set and the check short-circuits to false. They
read filed modelo 303 history and modelo 303 is pullable. The census verdict for
them stands and the reference says so at the point of use rather than leaving the
artefact to be discovered later.

The classification does NOT rule. It records what the registry declares, what the
code does with the declaration, and where the declaration is missing. Whether a
`factual_evidence` pulled fact may be a calculation input, and what the 17
undeclared rows should be, are the ruling's questions.

The non-official-evidence boundary was deliberately not re-examined and is
untouched: a locally-filed observation still carries a non-official source kind
and still cannot satisfy the gate external AEAT filing evidence satisfies. That
boundary governs whether a filing is PROVEN; this classification governs what a
proven filing's figures are FOR. Conflating them would be the erosion the ADR's
constraints warn against, so the reference states the two are independent and
that any promotion must say why it does not erode the first.
