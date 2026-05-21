"""Extraction-profile artefact and parser validation helpers."""

from __future__ import annotations

from importlib import import_module

from ._schema import ExtractionProfileDefinition


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
