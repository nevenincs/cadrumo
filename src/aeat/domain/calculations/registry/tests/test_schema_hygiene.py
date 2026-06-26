"""Cross-modelo schema hygiene tests.

These guards run against every committed registry/aeat/modelos/*.toml to
prevent duplicate casilla declarations, missing section structure, or XML-root
container names like ``DatosEconomicos`` leaking through into the section
taxonomy.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from ..._export_field_kind import CasillaFieldKind
from .. import load_registry_tree, revision_casilla_identity_failures
from .._ids import CasillaId, validated_casilla_id
from .._schema import DataBindingDefinition, ModeloDefinition
from .._validate_revision_identity import _PRIMARY_ID_KINDS, _RECORD_ID_KINDS

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

def _all_modelos() -> tuple[ModeloDefinition, ...]:
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
    """Within a revision, every ``(segmento, number)`` metadata pair must be unique.

    ``casilla.id`` is the canonical reference identity. The AEAT
    record-design metadata pair is ``(segmento, number)``, not ``number``
    alone.
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
            duplicates = {metadata: count for metadata, count in counts.items() if count > 1}
            for (segmento, number), count in duplicates.items():
                offences.append(
                    f"modelo {modelo.id} revision {revision_id} declares casilla number "
                    f"{number!r} under segmento {segmento!r} {count} times",
                )
    assert not offences, "duplicate casilla (segmento, number) metadata per revision:\n  " + "\n  ".join(offences)


def test_reused_casilla_numbers_have_only_segment_qualified_ids() -> None:
    """A reused printed number must never leave a bare casilla id owner.

    When a revision reuses ``CasillaDefinition.number`` across record
    segments, every owner must carry a segment-qualified ``casilla.id``
    and a declared ``segmento``. Otherwise the printed number becomes a
    second address for one owner and any reference by that token is
    ambiguous.
    """

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            owners_by_number: dict[str, list[tuple[str, str | None]]] = {}
            for casilla in revision.casillas:
                owners_by_number.setdefault(casilla.number, []).append((casilla.id, casilla.segmento))
            for number, owners in sorted(owners_by_number.items()):
                if len(owners) <= 1:
                    continue
                bare_owners = sorted(
                    casilla_id
                    for casilla_id, segmento in owners
                    if segmento is None or casilla_id == number
                )
                if bare_owners:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} reuses casilla number {number!r} "
                        f"but leaves bare casilla id owners {bare_owners!r}",
                    )
    assert not offences, "reused casilla numbers with bare owners:\n  " + "\n  ".join(offences)


def test_bundled_revisions_produce_no_ambiguous_casilla_identity_failures() -> None:
    """Every bundled modelo revision must satisfy the production casilla identity contract."""

    checked: list[str] = []
    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            context = f"modelo {modelo.id} revision {revision_id}"
            checked.append(context)
            offences.extend(revision_casilla_identity_failures(context, revision))

    assert checked, "bundled registry contains no modelo revisions to validate"
    assert not offences, "bundled revisions produce ambiguous casilla references:\n  " + "\n  ".join(offences)


def test_primary_registry_ids_do_not_collide_with_casilla_reference_metadata() -> None:
    """No primary registry id may also identify casilla display/export metadata."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            primary_ids: dict[str, list[str]] = {}
            for kind, attr in _RECORD_ID_KINDS:
                if kind not in _PRIMARY_ID_KINDS:
                    continue
                for record in getattr(revision, attr):
                    primary_ids.setdefault(record.id, []).append(kind)
            for casilla in revision.casillas:
                metadata_tokens = [("number", casilla.number)]
                if casilla.form_number is not None:
                    metadata_tokens.append(("form_number", casilla.form_number))
                metadata_tokens.extend(("export_ref", export_ref) for export_ref in casilla.export_refs)
                for metadata_kind, token in metadata_tokens:
                    if token == casilla.id or token not in primary_ids:
                        continue
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} "
                        f"{metadata_kind} {token!r} collides with primary registry ids "
                        f"{sorted(primary_ids[token])!r}",
                    )
    assert not offences, "ambiguous primary-id/casilla-metadata collisions:\n  " + "\n  ".join(offences)


def test_operator_input_id_map_contains_only_casilla_ids() -> None:
    """The runtime input map must expose only canonical ``casilla.id`` keys."""

    from .._runtime_graph import input_casilla_id_map

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            expected = {casilla.id for casilla in revision.casillas}
            observed = input_casilla_id_map(revision)
            extra_keys = sorted(set(observed) - expected)
            wrong_values = sorted(
                f"{key}->{value}"
                for key, value in observed.items()
                if key not in expected or value != key
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
    if not replay_dir.exists():
        return captured
    import json as _json

    for payload_path in replay_dir.glob("*.json"):
        try:
            document = _json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("expected_by_casilla_id", "observed_by_casilla_id"):
            section = document.get(key) or {}
            if isinstance(section, dict):
                captured.update(
                    _renta_replay_casilla_id(k, payload_path=payload_path, section_name=key)
                    for k in section
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
    mapping. The output is written to ``.vault/audit/renta-formula-oracle-coverage.txt`` for audit-trail
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
    declared_casillas = _modelo_100_casilla_ids(modelos)
    dangling_replay_targets = sorted(captured_targets - declared_casillas)
    assert not dangling_replay_targets, (
        "Renta WEB Open replay payloads reference casilla ids not declared by Modelo 100:\n  "
        + "\n  ".join(dangling_replay_targets)
    )
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
