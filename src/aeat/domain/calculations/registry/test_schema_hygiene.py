"""Cross-modelo schema hygiene tests.

These guards run against every committed registry/aeat/modelos/*.toml to
prevent duplicate casilla declarations, missing section structure, or XML-root
container names like ``DatosEconomicos`` leaking through into the section
taxonomy.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_SECTION_PART_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$")

_FORBIDDEN_XML_ROOT_TOKENS = frozenset(
    {
        "datoseconomicos",
        "datos_economicos",
        "rootnode",
        "root_node",
    }
)

_FORBIDDEN_TEST_NARRATIVE = (
    "aspirational",
    "deleted as tautological",
    "fails by design",
    "not yet delivered",
    "previously in this file",
    "past-state",
    "migration state",
    "phase ",
    "wave ",
    "compatibility shim",
    "xfail",
)

_FORBIDDEN_TEST_SCHEMA_CONSTRUCTORS = (
    "ApplicationLinkDefinition",
    "CasillaDefinition",
    "DataBindingDefinition",
    "FormulaDefinition",
    "LegalReference",
    "ModeloDefinition",
    "ModeloRevision",
    "ParameterDefinition",
    "RegistryCatalogues",
    "SourceReference",
)


def _all_modelos():
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return modelos


def test_no_duplicate_casilla_ids_within_a_revision() -> None:
    """Within a single modelo revision, every casilla id must be unique."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            counts = Counter(c.id for c in revision.casillas)
            duplicates = {casilla_id: count for casilla_id, count in counts.items() if count > 1}
            for casilla_id, count in duplicates.items():
                offences.append(
                    f"modelo {modelo.id} revision {revision_id} declares casilla id {casilla_id!r} {count} times"
                )
    assert not offences, "duplicate casilla ids per revision:\n  " + "\n  ".join(offences)


def test_no_duplicate_casilla_numbers_within_a_revision() -> None:
    """Within a single modelo revision, every casilla number must be unique."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            counts = Counter(c.number for c in revision.casillas)
            duplicates = {number: count for number, count in counts.items() if count > 1}
            for number, count in duplicates.items():
                offences.append(
                    f"modelo {modelo.id} revision {revision_id} declares casilla number {number!r} {count} times"
                )
    assert not offences, "duplicate casilla numbers per revision:\n  " + "\n  ".join(offences)


def test_section_paths_are_non_empty() -> None:
    """Every casilla must declare at least one section segment so downstream filters never see ``[]``."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                if not casilla.section:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} has empty section path"
                    )
    assert not offences, "empty section paths:\n  " + "\n  ".join(offences)


def test_section_parts_are_snake_case() -> None:
    """Section parts must be lowercase, digits, and underscores only -- no CamelCase XPath leakage."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                for part in casilla.section:
                    if not _SECTION_PART_PATTERN.match(part):
                        offences.append(
                            f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} "
                            f"has non-snake_case section part {part!r}"
                        )
    assert not offences, "non-snake_case section parts:\n  " + "\n  ".join(offences)


def test_section_paths_do_not_leak_xml_root_containers() -> None:
    """Section[0] must not be an AEAT XML container name (DatosEconomicos, etc.)."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                if casilla.section and casilla.section[0] in _FORBIDDEN_XML_ROOT_TOKENS:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} "
                        f"has XML root container {casilla.section[0]!r} as section[0]"
                    )
    assert not offences, "XML root containers leaked into section paths:\n  " + "\n  ".join(offences)


def test_registry_tests_describe_current_behaviour_not_removed_work() -> None:
    """Calculation-registry tests must describe executable behaviour, not old development states."""

    offences: list[str] = []
    root = PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry"
    for path in sorted(root.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in _FORBIDDEN_TEST_NARRATIVE:
            if phrase in text:
                offences.append(f"{path.relative_to(PROJECT_ROOT).as_posix()} contains {phrase!r}")
    assert not offences, "registry tests contain past-state narratives:\n  " + "\n  ".join(offences)


def test_registry_tests_do_not_define_schema_authority_objects() -> None:
    """Registry tests must derive modelo/casilla authority objects from committed registry data."""

    offences: list[str] = []
    root = PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry"
    for path in sorted(root.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        for constructor in _FORBIDDEN_TEST_SCHEMA_CONSTRUCTORS:
            if f"{constructor}(" in text:
                offences.append(f"{path.relative_to(PROJECT_ROOT).as_posix()} constructs {constructor}")
    assert not offences, "registry tests define schema authority objects:\n  " + "\n  ".join(offences)


def test_renta_synthetic_scenarios_do_not_pass_with_pure_zero_inputs_to_zero_outputs() -> None:
    """Renta synthetic-profile scenarios must not be all-zero-input to all-zero-output.

    A scenario where every input is 0 and every expected output is 0 computes
    0 = 0 + 0 - 0 + ... and never fails — false coverage. Each Renta synthetic
    scenario must either provide at least one non-zero input or assert at
    least one non-zero expected output. Scenarios that intentionally test
    the zero-input boundary case must declare a single non-trivial assertion
    (e.g. that a specific casilla evaluates to a specific non-zero parameter
    bound) so the math actually has to hold.
    """

    offences: list[str] = []
    renta_test_files = (
        PROJECT_ROOT / "src/aeat/domain/calculations/registry/test_renta_2025_synthetic_profile.py",
        PROJECT_ROOT / "src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py",
    )
    for path in renta_test_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Split into scenario blocks: each `_scenario` factory or RegistryCalculationScenario(...)
        scenario_blocks = re.split(r"(?=def \w+_scenario\b|RegistryCalculationScenario\()", text)
        for idx, block in enumerate(scenario_blocks):
            if "RegistryCalculationScenario(" not in block and "expected_outputs" not in block:
                continue
            # Extract inputs section and expected_outputs section
            inputs_match = re.search(r"inputs\s*=\s*\{([^}]*)\}", block)
            expected_match = re.search(r"expected_outputs\s*=\s*\(([^)]*?(?:\([^)]*\)[^)]*?)*)\)", block)
            if not (inputs_match or expected_match):
                continue
            inputs_text = inputs_match.group(1) if inputs_match else ""
            expected_text = expected_match.group(1) if expected_match else ""
            # Detect zero-only patterns
            input_decimals = re.findall(r'Decimal\("([^"]+)"\)', inputs_text)
            output_values = re.findall(r'value\s*=\s*Decimal\("([^"]+)"\)', expected_text)
            input_only_zero = bool(input_decimals) and all(
                d in ("0", "0.0", "0.00") for d in input_decimals
            )
            output_only_zero = bool(output_values) and all(
                v in ("0", "0.0", "0.00") for v in output_values
            )
            # A scenario is vacuous if BOTH all inputs are zero AND all expected outputs are zero
            if input_only_zero and output_only_zero:
                # Try to extract scenario id for the offence message
                id_match = re.search(r'id="([^"]+)"', block) or re.search(r"id\s*=\s*\"([^\"]+)\"", block)
                scenario_id = id_match.group(1) if id_match else "(anonymous)"
                offences.append(
                    f"{path.relative_to(PROJECT_ROOT).as_posix()} scenario "
                    f"{scenario_id!r} has all-zero inputs AND all-zero expected outputs "
                    f"(vacuous: 0 = 0 + 0 - 0 + ... never fails)"
                )
    assert not offences, "vacuous Renta synthetic scenarios:\n  " + "\n  ".join(offences)


def test_renta_typed_binding_candidates_declare_substrate_enum_class() -> None:
    """Renta bindings that bridge a closed-membership substrate axis must declare `typed_enum`.

    The Renta substrate enums (`RentaCCAA`, `EstimacionDirectaModalidad`,
    `RentaIncomeType`) live in :mod:`aeat.domain.renta`. Each binding whose
    id suffix matches a known typed-bridge anchor (e.g. `-tax-residence-ccaa`,
    `-estimacion-directa-es-normal`) MUST declare a `typed_enum` field naming
    the substrate enum class so consumers can route through the closed-set
    contract instead of parsing free-form strings at runtime.
    """

    bridges_by_suffix = {
        "tax-residence-ccaa": "RentaCCAA",
        "estimacion-directa-es-normal": "EstimacionDirectaModalidad",
    }
    modelos, _ = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    offences: list[str] = []
    for modelo in modelos:
        if modelo.id != "100":
            continue
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                for suffix, expected_enum in bridges_by_suffix.items():
                    if binding.id.endswith(suffix):
                        if binding.typed_enum != expected_enum:
                            offences.append(
                                f"binding {binding.id!r} expected typed_enum={expected_enum!r}, "
                                f"got {binding.typed_enum!r}"
                            )
    assert not offences, "Renta typed-binding gate violations:\n  " + "\n  ".join(offences)
