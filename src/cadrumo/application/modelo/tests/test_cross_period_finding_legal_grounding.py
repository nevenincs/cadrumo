"""Cross-period verification findings carry their legal grounding.

The verification-reports how-to promises every finding carries "the legal
references behind the rule". Before this gate the cross-period
``CROSS_PERIOD_DEPENDENCY_UNCLEAN`` findings (and the first-filer
activity-start finding) shipped with empty ``legal_refs``, so ``view`` rendered
no ``finding_legal_refs`` line for the most common blocking outcome on a
quarterly IVA filing. This locks the grounding onto each finding the
:func:`_cross_period_clean_state_findings` builder emits.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ....core import CasillaId, Period, validated_casilla_id
from ....core.directory_scan import scan_directory
from ....core.resources import bundled_path, resources
from cadrumo.domain.calculations.registry.ids import LegalRefId, SourceRefId
from cadrumo.domain.calculations.registry.legal import verify_legal_catalogue
from ....domain.modelos import ModeloVerificationFindingKind
from ...calculations import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from .._action_errors import WORKFLOW_GATE_LEGAL_REFS
from .._verification_actions import (
    _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
    _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS,
    _IVA_COMPENSATION_CARRY_LEGAL_REF,
    _cross_period_clean_state_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_APPLICATION_ROOT = Path(__file__).resolve().parents[2]
_LEGAL_REF_CONSTANT_RE = re.compile(r"LEGAL_REFS?$")
_M303_SOURCE_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_M303_SOURCE_CASILLA_01")
_DEFAULT_DEPENDENCY_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-58-2003:art-119",)
_DEFAULT_DEPENDENCY_SOURCE_REFS: tuple[SourceRefId, ...] = ("aeat-modelo-303-procedure",)


def _unclean_evidence(
    *,
    origin_ids: tuple[str, ...],
    legal_refs: tuple[LegalRefId, ...] = _DEFAULT_DEPENDENCY_LEGAL_REFS,
    source_refs: tuple[SourceRefId, ...] = _DEFAULT_DEPENDENCY_SOURCE_REFS,
) -> CrossPeriodDependencyEvidence:
    return CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=origin_ids,
            legal_refs=legal_refs,
            source_refs=source_refs,
        ),
        blockers=(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION,),
    )


def _verdict(evidence: CrossPeriodDependencyEvidence) -> CrossPeriodCleanStateVerdict:
    return CrossPeriodCleanStateVerdict(
        bucket_id="cross-period-grounding",
        target_modelo="303",
        target_filing_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        dependencies=(evidence,),
    )


def _literal_strings(node: ast.AST | None) -> tuple[str, ...]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return tuple(item for element in node.elts for item in _literal_strings(element))
    if isinstance(node, ast.Starred):
        return _literal_strings(node.value)
    return ()


def _names_legal_ref_constant(targets: object) -> bool:
    if isinstance(targets, ast.Name):
        return bool(_LEGAL_REF_CONSTANT_RE.search(targets.id))
    if isinstance(targets, (list, tuple)):
        return any(_names_legal_ref_constant(target) for target in targets)
    return False


def _legal_ref_literal_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.keyword):
        return node.value if node.arg == "legal_refs" else None
    if isinstance(node, ast.AnnAssign):
        return node.value if _names_legal_ref_constant(node.target) else None
    if isinstance(node, ast.Assign):
        return node.value if _names_legal_ref_constant(node.targets) else None
    return None


def _application_literal_legal_refs() -> frozenset[str]:
    refs: set[str] = set()
    for path in scan_directory(_APPLICATION_ROOT, pattern="*.py", recursive=True):
        if "tests" in path.relative_to(_APPLICATION_ROOT).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            refs.update(ref for ref in _literal_strings(_legal_ref_literal_value(node)) if ":" in ref)
    return frozenset(refs)


def test_application_legal_refs_resolve_to_bundled_corpus() -> None:
    """Application-level literal legal refs must stay registry and corpus backed."""
    catalogues = resources().modelos.authority.catalogues
    ref_ids = _application_literal_legal_refs()

    missing = sorted(ref_ids - set(catalogues.legal))
    assert missing == [], f"application legal_refs absent from the registry: {missing}"
    references = {ref_id: catalogues.legal[ref_id] for ref_id in sorted(ref_ids)}
    verify_legal_catalogue(references, source_root=bundled_path())

    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= ref_ids
    assert set(_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS) <= ref_ids
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF in ref_ids
    assert set(WORKFLOW_GATE_LEGAL_REFS) <= ref_ids
    assert all(ref.article for ref in references.values())
    assert all(ref.corpus_ref for ref in references.values())
    assert all(ref.required_text for ref in references.values())


def test_iva_compensacion_dependency_finding_cites_liva_and_lgt() -> None:
    """A compensación carry cites the prior-declaration LGT basis plus LIVA art. 99."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-303-compensacion-pendiente-anteriores",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    blocking = next(
        f
        for f in findings
        if f.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        and f.message_locale_key == "application.modelo.findings.cross_period_dependency_unclean"
    )
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(blocking.legal_refs)
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF in blocking.legal_refs
    assert tuple(blocking.source_refs) == _DEFAULT_DEPENDENCY_SOURCE_REFS


def test_dependency_finding_carries_registry_requirement_refs() -> None:
    """Registry-origin legal/source refs survive into the blocking finding."""
    verdict = _verdict(
        _unclean_evidence(
            origin_ids=("modelo-130-pagos-fraccionados-anteriores",),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-modelo-130-instructions",),
        ),
    )

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    blocking = next(
        f for f in findings if f.message_locale_key == "application.modelo.findings.cross_period_dependency_unclean"
    )
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(blocking.legal_refs)
    assert "rd-439-2007:art-110" in blocking.legal_refs
    assert tuple(blocking.source_refs) == ("aeat-modelo-130-instructions",)


def test_non_compensacion_dependency_finding_cites_lgt_only() -> None:
    """A non-compensación carry cites the prior-declaration LGT basis, not LIVA art. 99."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-100-rel-pago-fraccionado",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    blocking = next(
        f for f in findings if f.message_locale_key == "application.modelo.findings.cross_period_dependency_unclean"
    )
    assert tuple(blocking.legal_refs) == _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF not in blocking.legal_refs
    assert tuple(blocking.source_refs) == _DEFAULT_DEPENDENCY_SOURCE_REFS


def test_missing_activity_start_finding_cites_censo_alta() -> None:
    """The first-filer fail-closed finding cites the start-of-activity censo basis."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-303-compensacion-pendiente-anteriores",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    activity_start = next(
        f for f in findings if f.message_locale_key == "application.modelo.findings.cross_period_activity_start_missing"
    )
    assert tuple(activity_start.legal_refs) == _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS


def test_every_cross_period_finding_carries_legal_refs() -> None:
    """No cross-period finding ships with empty grounding (the page's promise)."""
    verdict = _verdict(_unclean_evidence(origin_ids=("modelo-303-compensacion-pendiente-anteriores",)))

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    assert findings
    assert all(f.legal_refs for f in findings)


def test_not_applicable_suppression_summary_carries_dependency_legal_refs() -> None:
    """The not-applicable suppression summary cites the scoped dependency basis."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("modelo-303-compensacion-pendiente-anteriores",),
            legal_refs=_DEFAULT_DEPENDENCY_LEGAL_REFS,
            source_refs=_DEFAULT_DEPENDENCY_SOURCE_REFS,
        ),
        modelo_not_applicable_advisory=True,
    )
    verdict = _verdict(evidence)

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    summary = next(f for f in findings if f.kind is ModeloVerificationFindingKind.ADVISORY)
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(summary.legal_refs)
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF in summary.legal_refs
    assert tuple(summary.source_refs) == _DEFAULT_DEPENDENCY_SOURCE_REFS
    assert summary.message_locale_key == "application.modelo.findings.cross_period_modelo_not_applicable.message"
    assert summary.message_facts["source_modelos"] == "303"
    assert "next_action" not in summary.model_dump(mode="json")


def test_non_official_local_chain_advisory_carries_dependency_legal_refs() -> None:
    """The same-year local-chain disclosure cites the dependency basis."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("modelo-303-compensacion-pendiente-anteriores",),
            legal_refs=_DEFAULT_DEPENDENCY_LEGAL_REFS,
            source_refs=_DEFAULT_DEPENDENCY_SOURCE_REFS,
        ),
        non_official_local_chain_advisory=True,
    )
    verdict = _verdict(evidence)

    findings = _cross_period_clean_state_findings(verdict, activity_start_date=None)

    assert len(findings) == 1
    advisory = findings[0]
    assert advisory.kind is ModeloVerificationFindingKind.ADVISORY
    assert set(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS) <= set(advisory.legal_refs)
    assert _IVA_COMPENSATION_CARRY_LEGAL_REF in advisory.legal_refs
    assert tuple(advisory.source_refs) == _DEFAULT_DEPENDENCY_SOURCE_REFS
