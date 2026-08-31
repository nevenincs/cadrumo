"""Cross-modelo schema hygiene tests.

These guards run against every committed registry/aeat/modelos/*.toml to
prevent duplicate casilla declarations, missing section structure, or XML-root
container names like ``DatosEconomicos`` leaking through into the section
taxonomy.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from functools import cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingTypedEnumKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.directory_scan import scan_directory
from .....core.resources.bundled_data import bundled_path
from ...export_field_kind import CasillaFieldKind
from ..authority import bundled_authority
from ..schema import DataBindingDefinition, ModeloDefinition
from ..validate_revision_identity import revision_reference_identity_failures

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


@cache
def _all_modelos() -> tuple[ModeloDefinition, ...]:
    return bundled_authority().modelos


def test_bundled_revisions_produce_no_ambiguous_reference_identity_failures() -> None:
    """Every bundled modelo revision must satisfy the production reference identity contract."""

    checked: list[str] = []
    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            context = f"modelo {modelo.id} revision {revision_id}"
            checked.append(context)
            offences.extend(revision_reference_identity_failures(context, revision))

    assert checked, "bundled registry contains no modelo revisions to validate"
    assert not offences, "bundled revisions produce ambiguous reference identities:\n  " + "\n  ".join(offences)


def test_operator_input_id_map_contains_only_casilla_ids() -> None:
    """The runtime input map must expose only canonical ``casilla.id`` keys."""

    from ..runtime_graph import input_casilla_id_map

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            expected = {casilla.id for casilla in revision.casillas}
            observed = input_casilla_id_map(revision)
            extra_keys = sorted(set(observed) - expected)
            wrong_values = sorted(
                f"{key}->{value}" for key, value in observed.items() if key not in expected or value != key
            )
            if extra_keys or wrong_values:
                offences.append(
                    f"modelo {modelo.id} revision {revision_id} exposes non-id input references "
                    f"extra_keys={extra_keys!r} wrong_values={wrong_values!r}",
                )
    assert not offences, "operator input map exposes non-canonical casilla references:\n  " + "\n  ".join(offences)


def test_export_casilla_fields_reference_only_casilla_ids() -> None:
    """Export fields must reference declared ``casilla.id`` values directly."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            casilla_ids = {casilla.id for casilla in revision.casillas}
            for layout in revision.export_layouts:
                for record in layout.records:
                    for field in record.fields:
                        if field.kind is not CasillaFieldKind.CASILLA or field.casilla_id is None:
                            continue
                        if field.casilla_id not in casilla_ids:
                            offences.append(
                                f"modelo {modelo.id} revision {revision_id} export field {field.id!r} "
                                f"references {field.casilla_id!r}, which is not a casilla.id",
                            )
    assert not offences, "export fields reference non-canonical casilla ids:\n  " + "\n  ".join(offences)


def test_completeness_manifests_reference_only_canonical_casilla_ids() -> None:
    """Completeness manifests must resolve by canonical ``casilla.id`` only."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            manifest = revision.completeness_manifest
            if manifest is None:
                continue
            casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
            for entry in manifest.casillas:
                casilla = casillas_by_id.get(entry.casilla_id)
                if casilla is None:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} completeness manifest "
                        f"references {entry.casilla_id!r}, which is not a casilla.id",
                    )
                    continue
                if (casilla.segmento, casilla.number) != entry.record_design_metadata():
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} completeness manifest "
                        f"entry {entry.casilla_id!r} carries metadata {entry.record_design_metadata()!r} "
                        f"but the registry casilla declares {(casilla.segmento, casilla.number)!r}",
                    )
    assert not offences, "completeness manifests reference non-canonical or mismatched casillas:\n  " + "\n  ".join(
        offences,
    )


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


def _renta_replay_casilla_id(value: object, *, payload_path: Path, section_name: str) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(
            f"{payload_path.name} {section_name} key {value!r} is not a canonical casilla.id",
        ) from exc


def _renta_replay_captured_targets(replay_dir: Path) -> set[CasillaId]:
    """Return every 4-digit casilla id captured under ``*_by_casilla_id`` blocks in renta replays.

    A missing replay directory returns an empty set (the gate is
    dormant during initial scaffolding). Per-payload JSON parse
    failures are tolerated — a malformed scratch file should not
    block the suite. Only casilla-id keyed sections
    (``expected_by_casilla_id`` / ``observed_by_casilla_id``) are scanned;
    user-readable label keys are deliberately excluded so the
    capture set stays aligned with the registry's canonical ids.
    """
    captured: set[CasillaId] = set()
    import json as _json

    for payload_path in scan_directory(replay_dir, pattern="*.json"):
        try:
            document = _json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("expected_by_casilla_id", "observed_by_casilla_id"):
            section = document.get(key) or {}
            if isinstance(section, dict):
                captured.update(
                    _renta_replay_casilla_id(k, payload_path=payload_path, section_name=key) for k in section
                )
    return captured


def _modelo_100_formula_targets(modelos: Iterable[ModeloDefinition]) -> set[CasillaId]:
    """Return every ``formula.target_casilla_id`` casilla declared by any Modelo 100 revision."""
    targets: set[CasillaId] = set()
    for modelo in modelos:
        if modelo.id != "100":
            continue
        for revision in modelo.revisions.values():
            targets.update(formula.target_casilla_id for formula in revision.formulas)
    return targets


def _modelo_100_casilla_ids(modelos: Iterable[ModeloDefinition]) -> set[CasillaId]:
    casilla_ids: set[CasillaId] = set()
    for modelo in modelos:
        if modelo.id != "100":
            continue
        for revision in modelo.revisions.values():
            casilla_ids.update(casilla.id for casilla in revision.casillas)
    return casilla_ids


def test_every_modelo_100_formula_target_has_oracle_grounded_scenario_coverage() -> None:
    """Every Modelo 100 formula target should be exercised by at least one Renta WEB Open replay payload.

    Per-formula oracle grounding is required. This gate enumerates Modelo 100
    formulas and counts how many target casillas appear in at least one replay
    payload's canonical ``expected_by_casilla_id`` or ``observed_by_casilla_id``
    mapping.

    Replay payloads must only reference casillas Modelo 100 actually declares.
    Beyond that the gate is dormant while no payload has been captured; as soon
    as ANY payload exists it enforces that the captured set grounds at least one
    formula target, which catches a payload-schema mismatch.
    """

    replay_dir = bundled_path("corpus", "parity_replays", "renta_web_open")
    captured_targets = _renta_replay_captured_targets(replay_dir)
    modelos = _all_modelos()
    declared_casillas = _modelo_100_casilla_ids(modelos)
    dangling_replay_targets = sorted(captured_targets - declared_casillas)
    assert not dangling_replay_targets, (
        "Renta WEB Open replay payloads reference casilla ids not declared by Modelo 100:\n  "
        + "\n  ".join(dangling_replay_targets)
    )
    formula_targets = _modelo_100_formula_targets(modelos)
    grounded = formula_targets & captured_targets
    if captured_targets and not grounded:
        raise AssertionError(
            "Renta WEB Open replay payloads exist but cover zero formula targets — payload schema mismatch?",
        )


def test_renta_typed_binding_candidates_declare_substrate_enum_class() -> None:
    """Renta bindings that bridge a closed-membership substrate axis must declare `typed_enum`.

    The CCAA binding declares ``typed_enum = "CCAA"`` (the canonical enum in
    :mod:`cadrumo.domain.contribuyente.ccaa`).  The estimacion-directa binding
    declares ``typed_enum = "EstimacionDirectaModalidad"`` (from
    :mod:`cadrumo.domain.renta`).  Each binding whose id suffix matches a
    known typed-bridge anchor MUST declare the correct ``typed_enum`` so
    consumers can route through the closed-set contract instead of parsing
    free-form strings at runtime.
    """

    modelos = _all_modelos()
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


def test_declared_typed_enum_hydrates_to_binding_typed_enum_kind() -> None:
    """F8: every binding's ``typed_enum`` is the narrowed enum member, not a bare str.

    The field was a stringly-typed pointer; F8 narrowed it to
    :class:`~cadrumo.core.aggregation.BindingTypedEnumKind`. The loader coerces the
    raw TOML token to its member at the boundary, so every committed binding that
    declares a ``typed_enum`` exposes a member (which still equals its string
    value, keeping the ``str`` consumers byte-compatible).
    """
    modelos = _all_modelos()
    seen: set[BindingTypedEnumKind] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                if binding.typed_enum is None:
                    continue
                assert isinstance(binding.typed_enum, BindingTypedEnumKind), (
                    f"binding {binding.id!r} typed_enum {binding.typed_enum!r} is not a BindingTypedEnumKind"
                )
                assert binding.typed_enum == binding.typed_enum.value
                seen.add(binding.typed_enum)
    # The four substrate-bridge annotations are all exercised by the committed tree.
    assert seen == set(BindingTypedEnumKind), f"committed bindings cover only {seen!r} of the typed-enum set"


def test_unknown_typed_enum_token_is_rejected_at_construction() -> None:
    """Anti-tautology: an unknown ``typed_enum`` token is refused at the boundary.

    If this ever passes with an arbitrary token, the F8 narrowing is broken and
    the ``isinstance`` assertion above is vacuous.
    """
    with pytest.raises(ValidationError):
        DataBindingDefinition.model_validate(
            {
                "id": "bad-typed-enum",
                "source": "profile",
                "selector": {"profile_key": "censo.status"},
                "typed_enum": "NotARealSubstrateEnum",
                "legal_refs": ("rd-1065-2007:art-9",),
                "source_refs": ("aeat-modelo-036-procedure",),
            },
        )


def _modelo_100_bindings(modelos: Iterable[ModeloDefinition]) -> Iterator[DataBindingDefinition]:
    """Yield every binding declared by any Modelo 100 revision."""
    for modelo in modelos:
        if modelo.id != "100":
            continue
        for revision in modelo.revisions.values():
            yield from revision.bindings


def _typed_enum_offence(
    binding: DataBindingDefinition,
    *,
    expectations: tuple[tuple[str, str], ...],
) -> str | None:
    """Return the typed_enum violation message for ``binding``, or ``None`` if it satisfies every bridge it matches."""
    for suffix, expected_enum in expectations:
        if binding.id.endswith(suffix) and binding.typed_enum != expected_enum:
            return f"binding {binding.id!r} expected typed_enum={expected_enum!r}, got {binding.typed_enum!r}"
    return None
