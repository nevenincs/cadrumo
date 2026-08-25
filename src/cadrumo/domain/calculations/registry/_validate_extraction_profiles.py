"""Extraction-profile artefact and parser validation helpers."""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.schema_extraction import (
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
)

from ....core.directory_scan import iter_directory


def validate_provisional_declaracion_pdf_evidence_state(
    scope: str,
    profile: ExtractionProfileDefinition,
) -> list[str]:
    """Reject evidence claims that contradict a provisional declaration profile.

    ``provisional_pending_specimen`` is an explicit acknowledgement that the
    profile has not been checked against a real declaration PDF.  It therefore
    cannot simultaneously claim the strict confidence or corpus round-trip
    evidence that such a specimen would supply.  This is intentionally a
    registry-build invariant, independent of whether an authoring corpus root
    happens to be available to the current process.
    """
    if profile.surface != "declaracion_pdf" or not profile.provisional_pending_specimen:
        return []

    failures: list[str] = []
    if profile.confidence != "review_required":
        failures.append(
            f"{scope}: provisional declaracion_pdf profile {profile.id!r} must set "
            f"confidence='review_required', not {profile.confidence!r}",
        )
    if profile.corpus_round_trip_verified:
        failures.append(
            f"{scope}: provisional declaracion_pdf profile {profile.id!r} cannot set "
            "corpus_round_trip_verified=true because a profile awaiting a specimen "
            "has no real corpus round-trip proof",
        )
    return failures


def validate_declaracion_pdf_specimen_gate(
    scope: str,
    modelo_id: str,
    profile: ExtractionProfileDefinition,
    corpus_root: Path,
) -> list[str]:
    """Enforce that a declaracion_pdf profile without a corpus specimen is explicitly acknowledged.

    A ``declaracion_pdf`` profile whose ``label_pattern`` values were derived from
    the registry's own casilla ``label_es`` fields — rather than verified against a
    real printed PDF — is a silently-provisional profile.  Any such profile that is
    NOT marked ``provisional_pending_specimen = True`` must fail the snapshot-build
    gate, because the patterns have not been round-trip verified against a corpus
    PDF and silent extraction failure is the probable result.

    If a corpus fixture directory exists at ``corpus_root / <modelo_id>`` containing
    at least one ``.pdf`` file, the profile is considered grounded and the field
    default (``False``) is correct.  If no fixture exists, the author MUST either
    acquire a specimen or explicitly mark the profile ``provisional_pending_specimen =
    true`` to acknowledge the open risk.
    """
    if profile.surface != "declaracion_pdf":
        return []
    if profile.provisional_pending_specimen:
        return []
    fixture_dir = corpus_root / modelo_id
    if any(iter_directory(fixture_dir, pattern="*.pdf")):
        return []
    return [
        f"{scope}: extraction profile {profile.id!r} is surface='declaracion_pdf' but no corpus "
        f"fixture PDF exists at '{fixture_dir}' and provisional_pending_specimen is not set; "
        f"either add a specimen PDF or set provisional_pending_specimen = true to acknowledge "
        f"that label_patterns are unverified against a real printed form",
    ]


def validate_declaracion_pdf_round_trip_gate(
    scope: str,
    modelo_id: str,
    profile: ExtractionProfileDefinition,
    corpus_root: Path,
) -> list[str]:
    """Enforce that a declaracion_pdf profile with a corpus fixture has a real round-trip test.

    The ``validate_declaracion_pdf_specimen_gate`` already handles the no-fixture case.
    This gate handles the complementary case: fixture EXISTS but neither
    ``corpus_round_trip_verified`` nor ``provisional_pending_specimen`` is set.

    A profile in that state has real corpus PDFs but no confirmed round-trip test,
    which is the exact silent-failure class the M111/M130 audit surfaced — fixture
    presence gave a false signal of extraction correctness.

    Gate logic:
    - surface != declaracion_pdf → dormant
    - provisional_pending_specimen → dormant (explicit opt-out, no check)
    - corpus_round_trip_verified → dormant (author asserts verified)
    - no corpus fixture → dormant (specimen gate handles this case)
    - fixture EXISTS, neither flag set → FAIL
    """
    if profile.surface != "declaracion_pdf":
        return []
    if profile.provisional_pending_specimen:
        return []
    if profile.corpus_round_trip_verified:
        if profile.verification_source is None:
            return [
                f"{scope}: extraction profile {profile.id!r} sets corpus_round_trip_verified = true "
                f"but verification_source is not set; set verification_source to one of "
                f"'real_aeat_corpus_pdf', 'synthetic_from_aeat_published_text', "
                f"'historical_suppression', or 'not_applicable' to document provenance explicitly",
            ]
        return []
    fixture_dir = corpus_root / modelo_id
    if not any(iter_directory(fixture_dir, pattern="*.pdf")):
        return []
    return [
        f"{scope}: extraction profile {profile.id!r} has corpus fixture at '{fixture_dir}' "
        f"but corpus_round_trip_verified is False and provisional_pending_specimen is False; "
        f"either set corpus_round_trip_verified = true once a parametrized real-corpus "
        f"round-trip test exists, or set provisional_pending_specimen = true to acknowledge "
        f"unverified status",
    ]


def validate_bbox_anchor_consistency(
    scope: str,
    target: ExtractionTargetDefinition,
) -> list[str]:
    """Registry-level defense-in-depth for bbox_anchor field/strategy consistency.

    The
    :class:`~domain.calculations.registry._schema_extraction.ExtractionTargetDefinition`
    model validator enforces this at construction time; this function provides
    an additional snapshot-build check so that targets loaded from TOML that
    somehow bypass the in-memory validator (e.g. via future schema migration
    tools) are caught at registry validation.
    """
    if target.match_strategy == "bbox_anchored" and target.bbox_anchor is None:
        return [
            f"{scope}: target {target.casilla_id!r} uses match_strategy='bbox_anchored' "
            f"but bbox_anchor is None; bbox_anchor is required for bbox_anchored targets",
        ]
    if target.match_strategy != "bbox_anchored" and target.bbox_anchor is not None:
        return [
            f"{scope}: target {target.casilla_id!r} uses match_strategy={target.match_strategy!r} "
            f"but bbox_anchor is set; bbox_anchor must be None for non-bbox_anchored strategies",
        ]
    return []


def validate_extraction_profile_artefacts(
    scope: str,
    profile: ExtractionProfileDefinition,
) -> list[str]:
    expected_by_surface = {
        "borrador_pdf": {"declaration_pdf"},
        "declaracion_pdf": {"declaration_pdf"},
        "justificante_pdf": {"justificante_pdf"},
        "export_record": {"submitted_file"},
        "official_workbook": {"official_workbook"},
    }
    expected = expected_by_surface[profile.surface]
    accepted = set(profile.accepted_artefact_kinds)
    failures: list[str] = []
    if accepted != expected:
        failures.append(
            f"{scope}: extraction profile {profile.id!r} accepts {sorted(accepted)!r}, "
            f"but surface {profile.surface!r} requires {sorted(expected)!r}",
        )
    if profile.surface == "justificante_pdf" and profile.target_casillas:
        failures.append(f"{scope}: extraction profile {profile.id!r} cannot use justificante PDFs as casilla data")
    return failures


def validate_dotted_callable(scope: str, owner: str, dotted_path: str) -> list[str]:
    """Validate that ``dotted_path`` is well-formed as a ``module.attribute`` path.

    Structural shape only: the domain registry validation must not name or import
    the adapter parser modules. Resolution — the allowed-authority prefix,
    importability, and callability of the target — is enforced by the
    adapter-legal CI gate ``test_extraction_parser_paths_resolve``, so this
    validator stays free of any ``adapters`` coupling (static or dynamic).
    """
    module_name, separator, attribute = dotted_path.rpartition(".")
    if not separator or not module_name or not attribute:
        return [f"{scope}: {owner} parser {dotted_path!r} must be a dotted callable path"]
    return []
