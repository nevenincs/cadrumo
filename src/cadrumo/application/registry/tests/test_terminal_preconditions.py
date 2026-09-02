"""Totality and runtime contracts for registry terminal refusals."""

from __future__ import annotations

import ast
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import override

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.config import override_settings
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.manuals.schema import ManualPart
from ....tests.registry_conformance import _AxisIndex
from ..corpus import (
    RegistryCitationShowCommand,
    RegistryManualId,
    RegistryManualRulesCommand,
    RegistryManualShowCommand,
    RegistryManualsListCommand,
    list_registry_manual_rules,
    list_registry_manuals,
    registry_manual_id,
    show_registry_citation,
    show_registry_manual,
)
from ..diff import _revision_for_year, diff_registry_revisions
from ..errors import RegistryApplicationInputError
from ..filed_state import _verified_required_casilla_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REGISTRY_ROOT = Path(__file__).resolve().parents[1]
# The conformance projection is test substrate and lives in the shared
# test-support package, which is excluded from the wheel.
_TEST_SUPPORT_ROOT = Path(__file__).resolve().parents[3] / "tests"
_REFUSAL_SOURCES = (
    _REGISTRY_ROOT / "diff.py",
    _REGISTRY_ROOT / "filed_state.py",
    _TEST_SUPPORT_ROOT / "registry_conformance.py",
    _REGISTRY_ROOT / "corpus.py",
    _REGISTRY_ROOT / "_corpus_manual_helpers.py",
)


def _refusal_error(operation: Callable[[], object]) -> RegistryApplicationInputError:
    with pytest.raises(RegistryApplicationInputError) as exc_info:
        operation()
    return exc_info.value


def _assert_no_action_contract(
    error: RegistryApplicationInputError,
    *,
    condition_id: str,
    facts: Mapping[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.model_dump(mode="json") == {
        "failed_condition_id": condition_id,
        "evidence": [
            {
                "condition_id": condition_id,
                "evidence_id": f"{condition_id}.observation",
                "provenance": provenance.value,
                "values": dict(facts),
            },
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": outcome.value,
    }


def test_revision_diff_refusals_preserve_distinct_selection_causes() -> None:
    definition = bundled_authority().modelo("100")
    original = definition.revisions["2025"]
    twin = original.model_copy(update={"id": "2025-twin"})
    ambiguous_definition = definition.model_copy(update={"revisions": {**definition.revisions, twin.id: twin}})

    ambiguous = _refusal_error(lambda: _revision_for_year(ambiguous_definition, filing_year=2025))
    _assert_no_action_contract(
        ambiguous,
        condition_id="registry.diff.revision_selection.unambiguous",
        facts={
            "modelo": "100",
            "filing_year": 2025,
            "revision_selection_unambiguous": False,
            "candidate_revision_count": 2,
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    unavailable = _refusal_error(lambda: diff_registry_revisions("303", from_year=1999, to_year=2023))
    _assert_no_action_contract(
        unavailable,
        condition_id="registry.diff.revision.available",
        facts={
            "modelo": "303",
            "filing_year": 1999,
            "revision_available": False,
            "candidate_revision_count": len(bundled_authority().modelo("303").revisions),
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_filed_state_casilla_refusals_classify_input_identity_and_declaration() -> None:
    snapshot = bundled_authority().snapshot("303", filing_year=2023, period="1T")
    common_facts = {"modelo": "303", "revision_id": str(snapshot.revision.id)}

    malformed = _refusal_error(lambda: _verified_required_casilla_ids((object(),), snapshot=snapshot))
    _assert_no_action_contract(
        malformed,
        condition_id="registry.filed_state.casilla_id.canonical",
        facts={**common_facts, "casilla_id_canonical": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    undeclared = _refusal_error(
        lambda: _verified_required_casilla_ids((validated_casilla_id("not-real"),), snapshot=snapshot),
    )
    _assert_no_action_contract(
        undeclared,
        condition_id="registry.filed_state.casilla.declared",
        facts={**common_facts, "casilla_id_declared": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_conformance_axis_refusals_are_safety_invariants() -> None:
    index = _AxisIndex(
        grounding_rows={},
        classification_rows={},
        coverage_ledgers={},
        construct_evidence_ledgers={},
        support_entries={},
    )

    missing_classification = _refusal_error(lambda: index.require_classification_row("303"))
    _assert_no_action_contract(
        missing_classification,
        condition_id="registry.conformance.classification_row.present",
        facts={"modelo": "303", "classification_row_present": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.SAFETY,
    )

    missing_grounding = _refusal_error(lambda: index.require_grounding_row("303", "2023"))
    _assert_no_action_contract(
        missing_grounding,
        condition_id="registry.conformance.grounding_row.present",
        facts={"modelo": "303", "revision_id": "2023", "grounding_row_present": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.SAFETY,
    )


def _write_unextracted_manual(root: Path) -> None:
    part_root = root / "renta" / "2025" / "part1"
    part_root.mkdir(parents=True)
    (part_root / "source.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (part_root / "manifest.json").write_text(
        json.dumps(
            {
                "content_length": 12,
                "fetched_at": "2026-01-01T00:00:00Z",
                "manual_id": "renta",
                "part": "part1",
                "relative_pdf_path": "source.pdf",
                "sha256": "0" * 64,
                "source_pdf_url": "https://example.invalid/synthetic/renta-2025-part1.pdf",
                "synthetic": True,
                "year": 2025,
            },
        ),
        encoding="utf-8",
    )


def test_corpus_refusals_classify_selection_and_missing_extraction_state(tmp_path: Path) -> None:
    invalid_locale = _refusal_error(
        lambda: list_registry_manuals(
            RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025), locale="zz"
        ),
    )
    _assert_no_action_contract(
        invalid_locale,
        condition_id="registry.topics.output_language.supported",
        facts={"output_language_supported": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    missing_citation = _refusal_error(
        lambda: show_registry_citation(RegistryCitationShowCommand(legal_id="ley-35-2006", articulo="999")),
    )
    _assert_no_action_contract(
        missing_citation,
        condition_id="registry.citations.reference.available",
        facts={"citation_reference_available": False, "article_requested": True},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    unsupported_manual = _refusal_error(lambda: registry_manual_id("sociedades"))
    _assert_no_action_contract(
        unsupported_manual,
        condition_id="registry.manuals.id.supported",
        facts={"manual_id_supported": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    _write_unextracted_manual(tmp_path)
    with override_settings(aeat_manuals_root=tmp_path):
        missing_structure = _refusal_error(
            lambda: show_registry_manual(
                RegistryManualShowCommand(
                    manual=RegistryManualId.RENTA,
                    year=2025,
                    part=ManualPart.PARTE_1,
                    section="missing-section",
                ),
            ),
        )
    _assert_no_action_contract(
        missing_structure,
        condition_id="registry.manuals.section_structure.available",
        facts={"manual_structure_available": False, "section_requested": True},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.SAFETY,
    )

    listed = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))
    structured_part = next(
        part
        for part in listed.parts
        if show_registry_manual(
            RegistryManualShowCommand(
                manual=RegistryManualId(part.manual_id),
                year=part.year,
                part=ManualPart(part.part),
            ),
        ).structure_available
    )
    unknown_section = _refusal_error(
        lambda: show_registry_manual(
            RegistryManualShowCommand(
                manual=RegistryManualId(structured_part.manual_id),
                year=structured_part.year,
                part=ManualPart(structured_part.part),
                section="missing-section",
            ),
        ),
    )
    _assert_no_action_contract(
        unknown_section,
        condition_id="registry.manuals.section.declared",
        facts={"manual_structure_available": True, "requested_section_declared": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_manual_rule_kind_refusal_is_a_no_action_operator_decision() -> None:
    unsupported_kind = _refusal_error(
        lambda: list_registry_manual_rules(
            RegistryManualRulesCommand(manual=RegistryManualId.RENTA, year=2025, kind="not-a-kind"),
        ),
    )
    _assert_no_action_contract(
        unsupported_kind,
        condition_id="registry.manuals.rule_kind.supported",
        facts={"manual_rule_kind_supported": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _expression(call: ast.Call, name: str) -> str:
    return ast.unparse(next(keyword.value for keyword in call.keywords if keyword.arg == name))


def _terminal_refusal_calls(path: Path) -> set[tuple[str, str, str, str, str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls: set[tuple[str, str, str, str, str, str]] = set()

    class _Visitor(ast.NodeVisitor):
        scope = "<module>"

        @override
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous_scope = self.scope
            self.scope = node.name
            self.generic_visit(node)
            self.scope = previous_scope

        @override
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id == "registry_terminal_refusal":
                calls.add(
                    (
                        path.name,
                        self.scope,
                        _expression(node, "condition"),
                        _expression(node, "facts"),
                        _expression(node, "provenance"),
                        _expression(node, "outcome"),
                    ),
                )
            self.generic_visit(node)

    _Visitor().visit(tree)
    return calls


def test_all_twelve_registry_refusals_delegate_to_the_canonical_no_action_helper() -> None:
    observed = set().union(*(_terminal_refusal_calls(path) for path in _REFUSAL_SOURCES))
    assert observed == {
        (
            "diff.py",
            "_revision_for_year",
            "RegistryPreconditionCondition.DIFF_REVISION_SELECTION_UNAMBIGUOUS",
            "{'modelo': str(definition.id), 'filing_year': filing_year, 'revision_selection_unambiguous': False, "
            "'candidate_revision_count': len(exc.candidate_ids)}",
            "ActionEvidenceProvenance.APPLICATION_STATE",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "diff.py",
            "_revision_for_year",
            "RegistryPreconditionCondition.DIFF_REVISION_AVAILABLE",
            "{'modelo': str(definition.id), 'filing_year': filing_year, 'revision_available': False, "
            "'candidate_revision_count': len(definition.revisions)}",
            "ActionEvidenceProvenance.APPLICATION_STATE",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "filed_state.py",
            "_verified_required_casilla_ids",
            "RegistryPreconditionCondition.FILED_STATE_CASILLA_ID_CANONICAL",
            "{'modelo': str(snapshot.modelo.id), 'revision_id': str(snapshot.revision.id), 'casilla_id_canonical': False}",
            "ActionEvidenceProvenance.RUNTIME_OBSERVATION",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "filed_state.py",
            "_verified_required_casilla_ids",
            "RegistryPreconditionCondition.FILED_STATE_CASILLA_DECLARED",
            "{'modelo': str(snapshot.modelo.id), 'revision_id': str(snapshot.revision.id), 'casilla_id_declared': False}",
            "ActionEvidenceProvenance.RUNTIME_OBSERVATION",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "registry_conformance.py",
            "require_classification_row",
            "RegistryPreconditionCondition.CONFORMANCE_CLASSIFICATION_ROW_PRESENT",
            "{'modelo': str(modelo_id), 'classification_row_present': False}",
            "ActionEvidenceProvenance.APPLICATION_STATE",
            "NoRecoveryOutcome.SAFETY",
        ),
        (
            "registry_conformance.py",
            "require_grounding_row",
            "RegistryPreconditionCondition.CONFORMANCE_GROUNDING_ROW_PRESENT",
            "{'modelo': str(modelo_id), 'revision_id': str(revision_id), 'grounding_row_present': False}",
            "ActionEvidenceProvenance.APPLICATION_STATE",
            "NoRecoveryOutcome.SAFETY",
        ),
        (
            "corpus.py",
            "show_registry_manual",
            "RegistryPreconditionCondition.MANUAL_SECTION_STRUCTURE_AVAILABLE",
            "{'manual_structure_available': False, 'section_requested': True}",
            "ActionEvidenceProvenance.APPLICATION_STATE",
            "NoRecoveryOutcome.SAFETY",
        ),
        (
            "corpus.py",
            "show_registry_manual",
            "RegistryPreconditionCondition.MANUAL_SECTION_DECLARED",
            "{'manual_structure_available': True, 'requested_section_declared': False}",
            "ActionEvidenceProvenance.RUNTIME_OBSERVATION",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "corpus.py",
            "_registry_topic_locale",
            "RegistryPreconditionCondition.TOPIC_OUTPUT_LANGUAGE_SUPPORTED",
            "{'output_language_supported': False}",
            "ActionEvidenceProvenance.RUNTIME_OBSERVATION",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "corpus.py",
            "_citation_not_found_error",
            "RegistryPreconditionCondition.CITATION_REFERENCE_AVAILABLE",
            "{'citation_reference_available': False, 'article_requested': command.articulo is not None}",
            "ActionEvidenceProvenance.RUNTIME_OBSERVATION",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "corpus.py",
            "registry_manual_id",
            "RegistryPreconditionCondition.MANUAL_ID_SUPPORTED",
            "{'manual_id_supported': False}",
            "ActionEvidenceProvenance.RUNTIME_OBSERVATION",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
        (
            "_corpus_manual_helpers.py",
            "manual_rule_kind",
            "RegistryPreconditionCondition.MANUAL_RULE_KIND_SUPPORTED",
            "{'manual_rule_kind_supported': False}",
            "ActionEvidenceProvenance.RUNTIME_OBSERVATION",
            "NoRecoveryOutcome.OPERATOR_DECISION",
        ),
    }


def test_registry_refusal_sources_do_not_construct_verdict_models_directly() -> None:
    direct_constructors: list[str] = []
    canonical_helper_calls: dict[str, int] = {}
    for path in (*_REFUSAL_SOURCES, _REGISTRY_ROOT / "errors.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id in {"ConditionEvidence", "PreconditionVerdict"}:
                direct_constructors.append(f"{path.name}:{node.lineno}:{node.func.id}")
            if node.func.id == "no_action_precondition_verdict":
                canonical_helper_calls[path.name] = canonical_helper_calls.get(path.name, 0) + 1

    assert direct_constructors == []
    assert canonical_helper_calls == {"errors.py": 1}
