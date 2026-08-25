"""Application-link closure validation helpers.

Validates that every application surface declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` is backed by a
matching application link, and that link combination rules are satisfied before
the revision is accepted by the registry validator.

See Also:
    :func:`cadrumo.domain.calculations.registry.validate_revision_closure._validate_revision_closure_sections`
        Revision-level closure runner that invokes these application-link
        checks.
    :func:`cadrumo.domain.calculations.registry.validate_surfaces.validate_application_link_section`
        Reference and evidence-tier validation for individual application-link
        declarations.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet

from ....core import Modelo, RegistryAuthorityGrade
from .schema import ModeloRevision

_COMMUNICATION_SURFACES = {"communication", "payer_delivery"}


_SIMPLE_APPLICATION_LINK_RULES: tuple[tuple[str, str, str], ...] = (
    # (revision_attribute, required_application_surface, failure_message)
    # Each rule fires when the revision declares the listed records but
    # the application-link bundle does not declare the matching surface.
    # Rules that require composite conditions (casillas, modelo-145
    # communication) stay inline in _application_link_surface_failures.
    ("formulas", "calculation", "formulas require a calculation application link"),
    ("extraction_profiles", "extractor", "extraction profiles require an extractor application link"),
    ("export_layouts", "export", "export layouts require an export application link"),
    ("live_cross_references", "portal", "live/static cross-references require a portal application link"),
    ("deadline_windows", "deadline", "deadline windows require a deadline application link"),
)


def validate_application_link_closure(
    scope: str,
    revision: ModeloRevision,
    *,
    modelo_id: str,
) -> list[str]:
    """Return application-link closure failures for one modelo revision.

    The supplied :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
    owns the declared application-link bundle and dependent surfaces. ``modelo_id``
    contributes the Modelo 145 communication-link rule because that workflow can
    use communication/payer-delivery surfaces in place of filing surfaces.
    """
    surfaces = {link.surface for link in revision.application_links}
    communication_surfaces = surfaces.intersection(_COMMUNICATION_SURFACES)
    modelo_requires_communication = modelo_id == Modelo.M145.value
    failures = _application_link_surface_failures(
        scope,
        revision,
        surfaces=surfaces,
        communication_surfaces=communication_surfaces,
        modelo_requires_communication=modelo_requires_communication,
    )
    if communication_surfaces or modelo_requires_communication:
        failures.extend(
            _application_link_communication_failures(
                scope,
                revision,
                surfaces=surfaces,
            ),
        )
    return failures


def _application_link_surface_failures(
    scope: str,
    revision: ModeloRevision,
    *,
    surfaces: AbstractSet[str],
    communication_surfaces: AbstractSet[str],
    modelo_requires_communication: bool,
) -> list[str]:
    failures: list[str] = []
    for revision_attribute, required_surface, message in _SIMPLE_APPLICATION_LINK_RULES:
        if getattr(revision, revision_attribute) and required_surface not in surfaces:
            failures.append(f"{scope}: {message}")
    extractor_owns_observation_casillas = (
        revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
        and bool(revision.extraction_profiles)
        and "extractor" in surfaces
    )
    casillas_have_lifecycle_link = (
        "filing" in surfaces
        or (modelo_requires_communication and bool(communication_surfaces))
        or extractor_owns_observation_casillas
    )
    if revision.casillas and not casillas_have_lifecycle_link:
        failures.append(f"{scope}: casillas require a filing or communication application link")
    if communication_surfaces and not modelo_requires_communication:
        failures.append(f"{scope}: communication application links are only valid for Modelo 145")
    if modelo_requires_communication and not communication_surfaces:
        failures.append(f"{scope}: Modelo 145 requires a communication application link")
    return failures


def _application_link_communication_failures(
    scope: str,
    revision: ModeloRevision,
    *,
    surfaces: AbstractSet[str],
) -> list[str]:
    failures: list[str] = []
    if "filing" in surfaces:
        failures.append(f"{scope}: communication application links must not be combined with filing")
    if "deadline" in surfaces or revision.deadline_windows:
        failures.append(f"{scope}: communication application links must not declare deadline surfaces")
    if "portal" in surfaces or revision.live_cross_references:
        failures.append(f"{scope}: communication application links must not declare live or portal surfaces")
    if revision.filing_schedules:
        failures.append(f"{scope}: communication application links must not declare filing schedules")
    return failures
