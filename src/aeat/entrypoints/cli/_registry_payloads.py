"""Typed ``--json`` payload schemas for registry CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every registry command surface this module covers.

Field sets match the production payload dicts constructed in ``registry.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


@register_schema("registry.inspect")
class RegistryInspectResult(OutputSchema):
    """JSON envelope for ``aeat app registry inspect``."""

    modelo_count: int
    revision_count: int
    legal_reference_count: int
    source_reference_count: int
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: list[str] = []
    modelos: list[str] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.verify")
class RegistryVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry verify``."""

    verified: bool
    modelo_count: int
    revision_count: int
    legal_reference_count: int
    source_reference_count: int
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: list[str] = []
    modelos: list[str] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]
