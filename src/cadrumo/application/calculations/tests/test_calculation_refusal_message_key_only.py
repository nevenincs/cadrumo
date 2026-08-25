"""No calculation refusal authors its own sentence; every one renders as its key.

Two independent proofs, because either alone is escapable.

The AST proof walks every module in the calculations package and refuses any
construction of a registered refusal this package raises that supplies message
text at all -- positionally or through ``message=``. That shape is the specific
defect this guard exists for: an authored sentence passed *alongside* a
registered ``translated_message`` key hides from every key-and-context
assertion, because resolution prefers the key, while ``str(exc)`` prefers the
positional argument and carries the English into tracebacks, structured logs and
every direct rendering, in every locale. A key-and-context assertion therefore
cannot detect it; only an absence check can.

The scan covers CONSTRUCTIONS, not raises: a refusal built by a helper and
returned to its caller to raise carries the same defect, and a raise-only walk
would not see it.

The runtime proof constructs each refusal family the way production does and
asserts the *absence* directly: ``str(exc)`` equals the locale key. A refusal
that starts smuggling prose fails here even if it is raised from a module the
AST walk has not been taught about.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import NoRecoveryOutcome
from ....core.directory_scan import scan_directory
from ..errors import (
    BindingPrefillTypeError,
    CalculationRefusalPrecondition,
    ObservationCasillaReferenceError,
    ObservationEvidenceDisplacementError,
    ObservationKeyError,
    calculation_no_recovery_verdict,
)
from .._m303_carry_ingress import M303CarryIngressError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CALCULATIONS_PACKAGE = Path(__file__).resolve().parent.parent

#: Registered refusal classes this package raises at an operator-facing
#: boundary. Classes owned elsewhere but constructed here are included, because
#: the authored sentence is written at THIS call site and is this package's to
#: remove. Bare ``ValueError`` / ``RuntimeError`` are deliberately absent: they
#: are pydantic-validator contracts and developer invariants, not registered
#: refusals, and they carry no locale key to render.
_CALCULATION_REFUSALS: frozenset[str] = frozenset(
    {
        "BindingPrefillTypeError",
        "IvaCompensationCasillaReferenceError",
        "IvaCompensationModeloError",
        "IvaCompensationReconciliationInputError",
        "M303CarryIngressError",
        "ModeloApplicabilityFilterError",
        "ObservationCasillaReferenceError",
        "ObservationEvidenceDisplacementError",
        "ObservationKeyError",
        "RegistryValidationError",
        "RentaValidationError",
    }
)

#: The enrollment-authorization gate is a developer-facing test gate with no
#: production caller: its refusals instruct whoever wrote the enrolling test
#: what evidence to record. It carries no operator boundary and therefore no
#: locale key, so it is excluded rather than migrated to prose no operator reads.
_DEVELOPER_GATE_ERRORS: frozenset[str] = frozenset({"EnrollmentEvidenceError"})


def _calculation_modules() -> tuple[Path, ...]:
    return scan_directory(_CALCULATIONS_PACKAGE, pattern="*.py")


def _authored_message_sites(path: Path) -> list[tuple[str, int]]:
    """Return every refusal construction in ``path`` that supplies message text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name not in _CALCULATION_REFUSALS:
            continue
        authors = bool(node.args) or any(keyword.arg == "message" for keyword in node.keywords)
        if authors:
            offenders.append((name, node.lineno))
    return offenders


def test_the_refusal_roster_still_names_classes_this_package_constructs() -> None:
    """Keep the roster honest: every named class must still be constructed here.

    Without this anchor a rename would silently shrink the scan's reach and the
    gate would pass vacuously on the class it stopped seeing.
    """
    constructed: set[str] = set()
    for path in _calculation_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                constructed.add(node.func.id)

    missing = sorted(_CALCULATION_REFUSALS - constructed)
    assert missing == [], f"the roster names refusals this package no longer constructs: {missing}"


def test_the_developer_gate_exclusion_still_names_a_declared_class() -> None:
    """A stale exclusion must not silently widen into a hole in the scan."""
    declared: set[str] = set()
    for path in _calculation_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        declared.update(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

    assert declared >= _DEVELOPER_GATE_ERRORS, (
        f"the developer-gate exclusion names classes this package no longer declares: "
        f"{sorted(_DEVELOPER_GATE_ERRORS - declared)}"
    )
    assert not (_DEVELOPER_GATE_ERRORS & _CALCULATION_REFUSALS), "a class cannot be both scanned and excluded"


def test_no_calculation_module_refusal_authors_its_own_message() -> None:
    modules = _calculation_modules()
    assert modules, "the calculations package scan found no modules to check"

    offenders = {path.name: sites for path in modules if (sites := _authored_message_sites(path))}
    assert offenders == {}, f"calculation refusals must carry a locale key, never authored text: {offenders}"


def test_the_authored_message_scan_detects_the_defect_it_guards_against(tmp_path: Path) -> None:
    """Prove the AST scan bites on all three reachable shapes of the defect."""
    positional = tmp_path / "positional.py"
    positional.write_text(
        "raise M303CarryIngressError(\n"
        '    "Modelo 303 carry history received a non-Modelo 303 observation envelope",\n'
        '    translated_message="application.calculations.m303_carry.errors.non_m303_envelope",\n'
        ")\n",
        encoding="utf-8",
    )
    keyword = tmp_path / "keyword.py"
    keyword.write_text(
        "raise M303CarryIngressError(\n"
        '    message="Modelo 303 carry history received a non-Modelo 303 observation envelope",\n'
        '    translated_message="application.calculations.m303_carry.errors.non_m303_envelope",\n'
        ")\n",
        encoding="utf-8",
    )
    constructed_and_returned = tmp_path / "returned.py"
    constructed_and_returned.write_text(
        "def refusal():\n"
        "    return RegistryValidationError(\n"
        '        "row-set assembly failed",\n'
        '        translated_message="application.calculations.row_set.errors.row_assembly_failed",\n'
        "    )\n",
        encoding="utf-8",
    )
    clean = tmp_path / "clean.py"
    clean.write_text(
        "raise M303CarryIngressError(\n"
        '    translated_message="application.calculations.m303_carry.errors.non_m303_envelope",\n'
        ")\n",
        encoding="utf-8",
    )

    assert _authored_message_sites(positional) == [("M303CarryIngressError", 1)]
    assert _authored_message_sites(keyword) == [("M303CarryIngressError", 1)]
    assert _authored_message_sites(constructed_and_returned) == [("RegistryValidationError", 2)]
    assert _authored_message_sites(clean) == []


def test_no_calculation_refusal_class_defaults_its_message_to_prose() -> None:
    """The third defect shape: English living on the constructor's own default.

    A default cannot be seen by any raise-site scan, because every call site
    then looks argument-free while ``args`` still carries the sentence. The only
    way to detect it is to construct the class with no arguments and look.
    """
    for refusal in (
        BindingPrefillTypeError,
        M303CarryIngressError,
        ObservationCasillaReferenceError,
        ObservationEvidenceDisplacementError,
        ObservationKeyError,
    ):
        constructed = refusal()
        assert str(constructed) == "", f"{refusal.__name__} defaults its message to prose: {str(constructed)!r}"
        assert constructed.args == (), f"{refusal.__name__} carries default args: {constructed.args!r}"


@pytest.mark.parametrize(
    "key",
    [
        "application.calculations.m303_carry.errors.non_m303_envelope",
        "application.calculations.m303_carry.errors.disposition_resultado_sign_incompatible",
        "application.calculations.observations.errors.filing_year_out_of_range",
        "application.calculations.row_set.errors.row_assembly_failed",
    ],
)
def test_calculation_refusal_renders_as_its_key_and_never_as_prose(key: str) -> None:
    error = M303CarryIngressError(translated_message=key, context={"probe": True})

    assert str(error) == key
    assert error.translated_message == key
    assert error.args == (key,)


def test_observation_key_refusal_renders_as_its_key() -> None:
    from .._observations_repository import observation_key_for_token

    with pytest.raises(ObservationKeyError) as excinfo:
        observation_key_for_token("303", 1999, "1T")

    assert str(excinfo.value) == "application.calculations.observations.errors.filing_year_out_of_range"


def test_row_set_grouping_refusal_renders_as_its_key() -> None:
    from ....core.resources import resources
    from ....domain.calculations.registry import RegistryValidationError
    from .._row_set_assembly import assemble_observations_for_grouping

    revision = resources().modelos.authority.snapshot("190", filing_year=2025, period="0A").revision

    with pytest.raises(RegistryValidationError) as excinfo:
        assemble_observations_for_grouping("no-such-grouping", (), revision, filing_year=2025)

    assert str(excinfo.value) == "application.calculations.row_set.errors.grouping_has_no_assembler"


def test_official_evidence_displacement_carries_an_explicit_safety_disposition() -> None:
    """Displacing captured AEAT evidence states no-recovery, and binds no action."""
    verdict = calculation_no_recovery_verdict(
        CalculationRefusalPrecondition.OFFICIAL_EVIDENCE_PRESERVED,
        facts={"existing_source_kind": "aeat_sede_justificante", "incoming_source_kind": "app_filing"},
    )
    error = ObservationEvidenceDisplacementError(
        translated_message="application.calculations.errors.observation_displaces_official_evidence_app_filing",
        context={"modelo": "303"},
        precondition_verdict=verdict,
    )

    assert error.terminal_precondition_verdict is verdict
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.failed_condition_id == "calculations.observations.official_evidence_preserved"


def test_a_calculation_refusal_without_a_safety_disposition_carries_no_verdict() -> None:
    error = M303CarryIngressError(
        translated_message="application.calculations.m303_carry.errors.resultado_casilla_required",
    )

    assert error.terminal_precondition_verdict is None
