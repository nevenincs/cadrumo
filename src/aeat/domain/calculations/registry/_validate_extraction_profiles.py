"""Extraction-profile artefact and parser validation helpers."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from ._schema import ExtractionProfileDefinition


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
    if fixture_dir.is_dir() and any(fixture_dir.glob("*.pdf")):
        return []
    return [
        f"{scope}: extraction profile {profile.id!r} is surface='declaracion_pdf' but no corpus "
        f"fixture PDF exists at '{fixture_dir}' and provisional_pending_specimen is not set; "
        f"either add a specimen PDF or set provisional_pending_specimen = true to acknowledge "
        f"that label_patterns are unverified against a real printed form"
    ]


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
            f"but surface {profile.surface!r} requires {sorted(expected)!r}"
        )
    if profile.surface == "justificante_pdf" and profile.target_casillas:
        failures.append(f"{scope}: extraction profile {profile.id!r} cannot use justificante PDFs as casilla data")
    return failures


def validate_dotted_callable(scope: str, owner: str, dotted_path: str) -> list[str]:
    module_name, separator, attribute = dotted_path.rpartition(".")
    if not separator or not module_name or not attribute:
        return [f"{scope}: {owner} parser {dotted_path!r} must be a dotted callable path"]
    try:
        module = import_module(module_name)
    except (ImportError, ValueError, SyntaxError) as exc:
        return [f"{scope}: {owner} parser {dotted_path!r} cannot import module {module_name!r}: {exc}"]
    try:
        resolved = getattr(module, attribute)
    except AttributeError as exc:
        return [f"{scope}: {owner} parser {dotted_path!r} does not resolve attribute {attribute!r}: {exc}"]
    if not callable(resolved):
        return [f"{scope}: {owner} parser {dotted_path!r} is not callable"]
    return []
