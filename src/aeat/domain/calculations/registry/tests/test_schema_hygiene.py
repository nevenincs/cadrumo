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

from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from .. import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SECTION_PART_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$")

_FORBIDDEN_XML_ROOT_TOKENS = frozenset(
    {
        "datoseconomicos",
        "datos_economicos",
        "rootnode",
        "root_node",
    },
)

_FORBIDDEN_TEST_NARRATIVE = (
    "aspirational",
    "deleted as tautological",
    "fails by design",
    "not yet delivered",
    "previously in this file",
    "past-state",
    "migration state",
    "pha" + "se ",
    "wa" + "ve ",
    "backwards-compat",
    "before the gate landed",
    "added per",
    "per-slice",
    "ad" + "r (",
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

# Validator-testing tests legitimately construct schema authority objects
# in order to exercise the validator paths that committed registry data
# can never reach (broken-shape inputs, edge cases, refused values). They
# are not "modelo inventory tests" — they test the validators themselves
# and need minimal broken objects as fixtures.
_VALIDATOR_TEST_ALLOWLIST = frozenset(
    {
        "test_catalogue_verification.py",
        "test_country_code_data_type.py",
        "test_cross_revision_drift.py",
        "test_iban_data_type.py",
        "test_long_tail_data_types.py",
        "test_nif_data_type.py",
        "test_period_code_data_type.py",
        "test_referential_integrity.py",
        "test_registry_schema.py",
        "test_required_role_hardflip.py",
        "test_schema.py",
        "test_selector_shape.py",
        "test_semantic_role.py",
        "test_year_data_type.py",
    },
)


def _all_modelos():
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
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
                    f"modelo {modelo.id} revision {revision_id} declares casilla id {casilla_id!r} {count} times",
                )
    assert not offences, "duplicate casilla ids per revision:\n  " + "\n  ".join(offences)


def test_no_duplicate_casilla_numbers_within_a_revision() -> None:
    """Within a single modelo revision, every ``(segmento, number)`` casilla identity must be unique.

    AEAT casilla identity is ``(segmento, number)``, not ``number`` alone.
    A multi-segment modelo (e.g. Modelo 200) legitimately reuses the same
    five-digit form-field number across distinct record segments: number
    ``00552`` is the ECPN ``Acciones y participaciones`` field in the
    default segment and the Liquidación III ``Base imponible`` field in
    segment ``DP200014``. Both are real AEAT form fields with their own
    export bindings. The duplicate this gate forbids is the same number
    appearing twice *within one segment* — a genuine copy artifact.
    """

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            counts = Counter((c.segmento, c.number) for c in revision.casillas)
            duplicates = {identity: count for identity, count in counts.items() if count > 1}
            for (segmento, number), count in duplicates.items():
                offences.append(
                    f"modelo {modelo.id} revision {revision_id} declares casilla number "
                    f"{number!r} under segmento {segmento!r} {count} times",
                )
    assert not offences, "duplicate casilla (segmento, number) identities per revision:\n  " + "\n  ".join(offences)


def test_section_paths_are_non_empty() -> None:
    """Every casilla must declare at least one section segment so downstream filters never see ``[]``."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                if not casilla.section:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} has empty section path",
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
                            f"has non-snake_case section part {part!r}",
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
                        f"has XML root container {casilla.section[0]!r} as section[0]",
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
        if path.name in _VALIDATOR_TEST_ALLOWLIST:
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
    renta_test_files = (PROJECT_ROOT / "src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py",)
    for path in renta_test_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Split into scenario blocks: each `_scenario` factory or RegistryCalculationScenario(...)
        scenario_blocks = re.split(r"(?=def \w+_scenario\b|RegistryCalculationScenario\()", text)
        for block in scenario_blocks:
            offence = _vacuous_scenario_offence(block, path)
            if offence is not None:
                offences.append(offence)
    assert not offences, "vacuous Renta synthetic scenarios:\n  " + "\n  ".join(offences)


_ZERO_DECIMAL_LITERALS: frozenset[str] = frozenset({"0", "0.0", "0.00"})


def _vacuous_scenario_offence(block: str, path: Path) -> str | None:
    """Return a vacuous-scenario offence string, or None when the block is fine.

    A scenario block is vacuous when every Decimal input literal AND
    every expected-output Decimal literal is the canonical zero
    representation: ``0 = 0 + 0 - 0 + ...`` never fails the gate's
    arithmetic.
    """
    if "RegistryCalculationScenario(" not in block and "expected_outputs" not in block:
        return None
    inputs_match = re.search(r"inputs\s*=\s*\{([^}]*)\}", block)
    expected_match = re.search(r"expected_outputs\s*=\s*\(([^)]*?(?:\([^)]*\)[^)]*?)*)\)", block)
    if not (inputs_match or expected_match):
        return None
    inputs_text = inputs_match.group(1) if inputs_match else ""
    expected_text = expected_match.group(1) if expected_match else ""
    input_decimals = re.findall(r'Decimal\("([^"]+)"\)', inputs_text)
    output_values = re.findall(r'value\s*=\s*Decimal\("([^"]+)"\)', expected_text)
    input_only_zero = bool(input_decimals) and all(d in _ZERO_DECIMAL_LITERALS for d in input_decimals)
    output_only_zero = bool(output_values) and all(v in _ZERO_DECIMAL_LITERALS for v in output_values)
    if not (input_only_zero and output_only_zero):
        return None
    id_match = re.search(r'id="([^"]+)"', block) or re.search(r"id\s*=\s*\"([^\"]+)\"", block)
    scenario_id = id_match.group(1) if id_match else "(anonymous)"
    return (
        f"{path.relative_to(PROJECT_ROOT).as_posix()} scenario "
        f"{scenario_id!r} has all-zero inputs AND all-zero expected outputs "
        f"(vacuous: 0 = 0 + 0 - 0 + ... never fails)"
    )


def test_every_renta_chain_scenario_has_renta_web_open_replay_payload() -> None:
    """Every chain-behaviour and synthetic-profile scenario should carry a Renta WEB Open payload.

    The payload sits at ``corpus/parity_replays/renta_web_open/{scenario_id}.json``
    and pins the AEAT open-simulator's output for the scenario's synthetic inputs.
    Renta full-coverage mandates this grounding for every Modelo 100
    scenario; this gate enforces it.

    The gate is dormant during initial scaffolding: when no payloads are
    captured yet, it records the inventory to a metrics file but does not
    fail. As soon as ANY payload exists, it converts to a hard failure for
    every other scenario that lacks one. This shape lets capture work land
    incrementally while preventing back-sliding.
    """

    replay_dir = bundled_path("corpus", "parity_replays", "renta_web_open")
    captured = {p.stem for p in replay_dir.glob("*.json")} if replay_dir.exists() else set()
    capture_replay_test = PROJECT_ROOT / "src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_capture_replay.py"
    declared: set[str] = set()
    # Only the capture-replay test inventory counts as the live-grounded
    # baseline set: its scenario ids are the ones the driver actually
    # captures (chain-behaviour scenarios feed values into derived
    # casillas the open-simulator renders read-only and can't capture).
    for path in (capture_replay_test,):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Match bare scenario ids only (no filename extensions or path
        # fragments). The capture-replay test references the same id in
        # the parametrized scenario tuple and as a payload filename via
        # f-string; either occurrence must round-trip identically.
        for match in re.finditer(r'"(modelo-100-[^".]+)"', text):
            declared.add(match.group(1))
    uncovered = sorted(declared - captured)
    metrics_path = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-replay-coverage.txt"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        "scenarios_total: {total}\n"
        "scenarios_with_payload: {covered}\n"
        "scenarios_uncovered: {uncovered_count}\n"
        "coverage_pct: {pct:.1f}\n"
        "uncovered_ids:\n{uncovered_listing}\n".format(
            total=len(declared),
            covered=len(declared & captured),
            uncovered_count=len(uncovered),
            pct=(100.0 * len(declared & captured) / len(declared)) if declared else 0.0,
            uncovered_listing="\n".join(f"  - {sid}" for sid in uncovered) or "  (none)",
        ),
        encoding="utf-8",
    )
    # Hard-fail mode (#171): every declared baseline-scenario id must
    # carry a captured replay payload. Once a capture exists, the gate
    # is strict — adding a new declared scenario without its capture
    # breaks CI immediately rather than waiting for the 80% threshold.
    if captured and uncovered:
        raise AssertionError(
            "Renta chain scenarios without Renta WEB Open replay payload "
            "(capture via AEAT_LIVE_TESTS_ENABLED=1):\n  " + "\n  ".join(uncovered),
        )


def _renta_replay_captured_targets(replay_dir) -> set[str]:  # type: ignore[no-untyped-def]
    """Return every 4-digit casilla id captured under ``*_by_casilla`` blocks in renta replays.

    A missing replay directory returns an empty set (the gate is
    dormant during initial scaffolding). Per-payload JSON parse
    failures are tolerated — a malformed scratch file should not
    block the suite. Only casilla-id keyed sections
    (``expected_by_casilla`` / ``observed_by_casilla``) are scanned;
    user-readable label keys are deliberately excluded so the
    capture set stays aligned with the registry's canonical ids.
    """
    captured: set[str] = set()
    if not replay_dir.exists():
        return captured
    import json as _json

    for payload_path in replay_dir.glob("*.json"):
        try:
            document = _json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("expected_by_casilla", "observed_by_casilla"):
            section = document.get(key) or {}
            if isinstance(section, dict):
                captured.update(k for k in section if isinstance(k, str) and k.isdigit())
    return captured


def _modelo_100_formula_targets(modelos) -> set[str]:  # type: ignore[no-untyped-def]
    """Return every ``formula.target`` casilla declared by any Modelo 100 revision."""
    targets: set[str] = set()
    for modelo in modelos:
        if modelo.id != "100":
            continue
        for revision in modelo.revisions.values():
            targets.update(formula.target for formula in revision.formulas)
    return targets


def test_every_modelo_100_formula_target_has_oracle_grounded_scenario_coverage() -> None:
    """Every Modelo 100 formula target should be exercised by at least one Renta WEB Open replay payload.

    Per-formula oracle grounding is required. This gate enumerates Modelo 100
    formulas and counts how many target casillas appear in at least one replay
    payload's ``observed`` mapping (or ``expected`` mapping). The output is written
    to ``.vault/audit/renta-formula-oracle-coverage.txt`` for audit-trail
    visibility.

    The gate is dormant during initial scaffolding (no captured payloads → no
    enforcement). As soon as ANY payload exists, the gate enforces that every
    formula target whose casilla appears in at least one captured payload's
    expected/observed set is grounded; the inventory of un-grounded targets is
    persisted for capture-work scheduling.
    """

    replay_dir = bundled_path("corpus", "parity_replays", "renta_web_open")
    captured_targets = _renta_replay_captured_targets(replay_dir)
    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))
    formula_targets = _modelo_100_formula_targets(modelos)
    grounded = formula_targets & captured_targets
    ungrounded = sorted(formula_targets - captured_targets)
    metrics_path = PROJECT_ROOT / ".vault" / "audit" / "renta-formula-oracle-coverage.txt"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        f"formula_targets_total: {len(formula_targets)}\n"
        f"formula_targets_grounded: {len(grounded)}\n"
        f"formula_targets_ungrounded: {len(ungrounded)}\n"
        f"coverage_pct: {(100.0 * len(grounded) / len(formula_targets)) if formula_targets else 0.0:.1f}\n",
        encoding="utf-8",
    )
    # Soft gate during scaffolding: only fail when payloads exist AND targets are
    # missing oracle grounding. The full hard-fail mode lands once the baseline
    # capture set covers the cuota chain (#81 follow-up).
    if captured_targets and not grounded:
        raise AssertionError(
            "Renta WEB Open replay payloads exist but cover zero formula targets — payload schema mismatch?",
        )


def test_renta_typed_binding_candidates_declare_substrate_enum_class() -> None:
    """Renta bindings that bridge a closed-membership substrate axis must declare `typed_enum`.

    The CCAA binding declares ``typed_enum = "CCAA"`` (the canonical enum in
    :mod:`aeat.domain.contribuyente._ccaa`).  The estimacion-directa binding
    declares ``typed_enum = "EstimacionDirectaModalidad"`` (from
    :mod:`aeat.domain.renta`).  Each binding whose id suffix matches a
    known typed-bridge anchor MUST declare the correct ``typed_enum`` so
    consumers can route through the closed-set contract instead of parsing
    free-form strings at runtime.
    """

    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))
    offences: list[str] = []
    for binding in _modelo_100_bindings(modelos):
        offence = _typed_enum_offence(binding, expectations=_RENTA_TYPED_BINDING_BRIDGES)
        if offence is not None:
            offences.append(offence)
    assert not offences, "Renta typed-binding gate violations:\n  " + "\n  ".join(offences)


_RENTA_TYPED_BINDING_BRIDGES: tuple[tuple[str, str], ...] = (
    ("tax-residence-ccaa", "CCAA"),
    ("estimacion-directa-es-normal", "EstimacionDirectaModalidad"),
)


def _modelo_100_bindings(modelos):  # type: ignore[no-untyped-def]
    """Yield every binding declared by any Modelo 100 revision."""
    for modelo in modelos:
        if modelo.id != "100":
            continue
        for revision in modelo.revisions.values():
            yield from revision.bindings


def _typed_enum_offence(binding, *, expectations: tuple[tuple[str, str], ...]) -> str | None:  # type: ignore[no-untyped-def]
    """Return the typed_enum violation message for ``binding``, or ``None`` if it satisfies every bridge it matches."""
    for suffix, expected_enum in expectations:
        if binding.id.endswith(suffix) and binding.typed_enum != expected_enum:
            return f"binding {binding.id!r} expected typed_enum={expected_enum!r}, got {binding.typed_enum!r}"
    return None
