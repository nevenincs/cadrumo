"""Shared verification finding coordinates, source families, and refusal vocabulary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ...domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
)

if TYPE_CHECKING:
    pass


M349_NUMERO_RECTIFICACIONES_CASILLA: CasillaId = "decl.numero-rectificaciones"


M349_IMPORTE_RECTIFICACIONES_CASILLA: CasillaId = "decl.importe-rectificaciones"


M210_UNRESOLVED_RATE_REASONS = frozenset(
    {
        RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED,
        RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
    },
)


#: Stands in a finding fact whose subject genuinely does not exist, so the fact
#: can be supplied on EVERY branch. ``tr()`` leaves an unsupplied placeholder in
#: the rendered string rather than raising, so a conditionally-supplied fact
#: reaches the operator as a literal ``%{binding_id}``. The marker is the
#: established spelling for this on adjacent findings (``pulled_filing_reconcile``,
#: ``_attribution_received_advisory``) and says which case it is: an absent
#: subject reads differently from one whose id is blank.
ABSENT_FACT: Final[str] = "absent"


REGISTRY_SNAPSHOT_GRADE_INSUFFICIENT_SCENARIO: Final[str] = (
    "modelo.work.verify.registry_snapshot.authority_grade_insufficient"
)


REGISTRY_SNAPSHOT_UNAVAILABLE_SCENARIO: Final[str] = "modelo.work.verify.registry_snapshot.unavailable"


REGISTRY_SNAPSHOT_REFUSAL_SCENARIOS: Final[frozenset[str]] = frozenset(
    {REGISTRY_SNAPSHOT_GRADE_INSUFFICIENT_SCENARIO, REGISTRY_SNAPSHOT_UNAVAILABLE_SCENARIO},
)


#: Legal grounding for missing IVA evidence. Deducting input IVA requires the
#: original factura (LIVA art. 97, RD 1619/2012 art. 2). Output-IVA evidence
#: gaps stay advisory until the transaction model can distinguish every valid
#: issued-invoice support path without over-blocking.
MISSING_EVIDENCE_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-97",
    "rd-1619-2012:art-2",
)


#: Legal grounding for a cuota-less row that declares no base. LIVA art. 164.Uno.6
#: obliges the taxpayer to declare the operations; the M303 base casillas are
#: where an exempt, zero-rated, not-subject or intra-community operation is
#: reported, since by law it carries no cuota. RD 1624/1992 art. 71.7 fixes the
#: content of the periodic self-assessment those bases feed.
CUOTA_LESS_WITHOUT_BASE_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-164",
    "rd-1624-1992:art-71",
)


#: The ``source_ref`` form a ledger IVA source issue names its row by.
LEDGER_TRANSACTION_SOURCE_REF_PREFIX: Final = "transaction:"


UNRECORDABLE_DEDUCTION_SCENARIOS: Final = {
    "intra_eu_self_assessment": "intra_eu_self_assessment_unrecordable",
    "customs_declaration": "import_document_unrecordable",
    "reagp_receipt": "reagp_document_unrecordable",
    "rectification_evidence": "rectification_document_unrecordable",
}


BLOCKED_VERDICT_KINDS: Final[frozenset[ModeloVerificationFindingKind]] = frozenset(
    {ModeloVerificationFindingKind.BLOCKING_RULE, ModeloVerificationFindingKind.STALE_CALCULATION}
)
"""Finding kinds that make a check blocked rather than incomplete, whatever else it found missing."""
