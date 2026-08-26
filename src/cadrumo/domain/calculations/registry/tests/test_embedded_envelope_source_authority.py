"""Embedded envelope provenance must remain a live catalogue claim.

Filing envelopes and auxiliary page-zero headers are generated declarations that
restate a source identity and digest.  This suite exercises both real shipped
shapes through ``build_snapshot``: a pass proves registry composition accepts
the authoritative declaration, while each mutation proves the build boundary
cannot preserve a missing, rebound, mismatched, or stale source claim.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import RegistryCatalogues
from cadrumo.domain.calculations.registry.snapshot import build_snapshot

from .....core.resources import bundled_path
from .._validate_exports import _validate_embedded_envelope_source_authority
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ZERO_DIGEST = "0" * 64


@pytest.fixture(params=(("303", 2025, "1T", "filing_envelope"), ("232", 2024, "0A", "auxiliary_envelope_header")))
def embedded_envelope_case(request: pytest.FixtureRequest) -> tuple[str, int, str, str]:
    """Return one real filing-envelope and one real auxiliary-header case."""
    return request.param


def _embedded_declaration(layout, declaration_name: str):  # type: ignore[no-untyped-def]  # reason: the narrow test-only selector returns either of the two typed declarations, and spelling the union repeats the production protocol without improving assertions
    declaration = getattr(layout, declaration_name)
    assert declaration is not None, f"layout {layout.id!r} has no {declaration_name} declaration"
    return declaration


def _case_modelo_and_revision(
    embedded_envelope_case: tuple[str, int, str, str],
):  # type: ignore[no-untyped-def]  # reason: test-local tuple unpacking preserves the concrete registry model types at every mutation site
    modelo_id, _filing_year, _period, declaration_name = embedded_envelope_case
    modelos, catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == modelo_id)
    revision = next(
        candidate
        for candidate in modelo.revisions.values()
        if any(getattr(layout, declaration_name) is not None for layout in candidate.export_layouts)
    )
    layout = next(layout for layout in revision.export_layouts if getattr(layout, declaration_name) is not None)
    return modelo, revision, layout, catalogues


def _modelo_with_layout(modelo, revision, layout, replacement):  # type: ignore[no-untyped-def]  # reason: model_copy preserves strict production schemas while these test-only transformations each target a different concrete envelope declaration
    updated_revision = revision.model_copy(
        update={
            "export_layouts": tuple(
                replacement if candidate.id == layout.id else candidate for candidate in revision.export_layouts
            ),
        },
    )
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: updated_revision}})


def _catalogues_with(catalogues: RegistryCatalogues, source_ref: str, source) -> RegistryCatalogues:  # type: ignore[no-untyped-def]  # reason: SourceReference is inferred from the real catalogue entry and never constructed synthetically
    return catalogues.model_copy(update={"sources": {**catalogues.sources, source_ref: source}})


def _build(modelo, catalogues: RegistryCatalogues, *, filing_year: int, period: str):  # type: ignore[no-untyped-def]  # reason: the helper returns a snapshot only for the pass proof; refusal tests consume its raised validation error
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    )


def test_real_embedded_envelopes_build_from_their_live_catalogue_authority(
    embedded_envelope_case: tuple[str, int, str, str],
) -> None:
    """Both shipped envelope shapes compose only after their source is re-hashed."""
    modelo, _revision, layout, catalogues = _case_modelo_and_revision(embedded_envelope_case)
    _modelo_id, filing_year, period, declaration_name = embedded_envelope_case
    declaration = _embedded_declaration(layout, declaration_name)

    snapshot = _build(modelo, catalogues, filing_year=filing_year, period=period)

    source = catalogues.sources[declaration.source_ref]
    assert source.id == declaration.source_ref
    assert source.sha256 == declaration.source_sha256
    assert snapshot.revision.id in modelo.revisions


def test_embedded_envelope_refuses_a_missing_canonical_source_identity(
    embedded_envelope_case: tuple[str, int, str, str],
) -> None:
    """A layout cannot retain an envelope declaration after its catalogue row disappears."""
    modelo, _revision, layout, catalogues = _case_modelo_and_revision(embedded_envelope_case)
    _modelo_id, filing_year, period, declaration_name = embedded_envelope_case
    declaration = _embedded_declaration(layout, declaration_name)
    missing_catalogues = catalogues.model_copy(
        update={"sources": {key: value for key, value in catalogues.sources.items() if key != declaration.source_ref}},
    )

    with pytest.raises(RegistryValidationError, match="is absent from the canonical source catalogue"):
        _build(modelo, missing_catalogues, filing_year=filing_year, period=period)


def test_embedded_envelope_refuses_a_rebound_catalogue_identity(
    embedded_envelope_case: tuple[str, int, str, str],
) -> None:
    """A catalogue key may not silently point at a differently identified source row."""
    modelo, _revision, layout, catalogues = _case_modelo_and_revision(embedded_envelope_case)
    _modelo_id, filing_year, period, declaration_name = embedded_envelope_case
    declaration = _embedded_declaration(layout, declaration_name)
    source = catalogues.sources[declaration.source_ref]
    alternate_identity = next(key for key in catalogues.sources if key != declaration.source_ref)
    rebound_catalogues = _catalogues_with(
        catalogues,
        declaration.source_ref,
        source.model_copy(update={"id": alternate_identity}),
    )

    with pytest.raises(
        RegistryValidationError, match="embedded source identity must equal its canonical catalogue key"
    ):
        _build(modelo, rebound_catalogues, filing_year=filing_year, period=period)


def test_embedded_envelope_refuses_a_catalogue_source_that_is_not_a_record_design(
    embedded_envelope_case: tuple[str, int, str, str],
) -> None:
    """An embedded envelope may not treat a non-design source as layout authority."""
    modelo, _revision, layout, catalogues = _case_modelo_and_revision(embedded_envelope_case)
    _modelo_id, filing_year, period, declaration_name = embedded_envelope_case
    declaration = _embedded_declaration(layout, declaration_name)
    source = catalogues.sources[declaration.source_ref]
    non_design_catalogues = _catalogues_with(
        catalogues,
        declaration.source_ref,
        source.model_copy(update={"kind": "manual_pdf"}),
    )

    with pytest.raises(RegistryValidationError, match="not a record-design source"):
        _build(modelo, non_design_catalogues, filing_year=filing_year, period=period)


def test_embedded_envelope_source_kind_guard_reports_each_non_design_catalogue_source(
    embedded_envelope_case: tuple[str, int, str, str],
) -> None:
    """The envelope-specific guard must identify the wrong catalogue kind itself."""
    modelo, revision, layout, catalogues = _case_modelo_and_revision(embedded_envelope_case)
    _modelo_id, _filing_year, _period, declaration_name = embedded_envelope_case
    declaration = _embedded_declaration(layout, declaration_name)
    source = catalogues.sources[declaration.source_ref]
    non_design_catalogues = _catalogues_with(
        catalogues,
        declaration.source_ref,
        source.model_copy(update={"kind": "manual_pdf"}),
    )
    failures: list[str] = []

    _validate_embedded_envelope_source_authority(
        failures,
        prefix=f"modelo {modelo.id} revision {revision.id}",
        layout=layout,
        source_refs=non_design_catalogues.sources,
        source_root=bundled_path(),
    )

    assert any(declaration.source_ref in failure and "not a record-design source" in failure for failure in failures)


def test_embedded_envelope_refuses_a_digest_that_disagrees_with_its_catalogue(
    embedded_envelope_case: tuple[str, int, str, str],
) -> None:
    """The generated declaration's digest cannot drift while its source id remains valid."""
    modelo, revision, layout, catalogues = _case_modelo_and_revision(embedded_envelope_case)
    _modelo_id, filing_year, period, declaration_name = embedded_envelope_case
    declaration = _embedded_declaration(layout, declaration_name)
    updated_layout = layout.model_copy(
        update={declaration_name: declaration.model_copy(update={"source_sha256": _ZERO_DIGEST})},
    )
    mutated_modelo = _modelo_with_layout(modelo, revision, layout, updated_layout)

    with pytest.raises(RegistryValidationError, match="does not match canonical catalogue digest"):
        _build(mutated_modelo, catalogues, filing_year=filing_year, period=period)


def test_embedded_envelope_refuses_a_stale_catalogue_digest_after_live_rehash(
    embedded_envelope_case: tuple[str, int, str, str],
) -> None:
    """Matching zero digests still fail because the build re-hashes the real source bytes."""
    modelo, revision, layout, catalogues = _case_modelo_and_revision(embedded_envelope_case)
    _modelo_id, filing_year, period, declaration_name = embedded_envelope_case
    declaration = _embedded_declaration(layout, declaration_name)
    source = catalogues.sources[declaration.source_ref]
    zero_catalogues = _catalogues_with(
        catalogues,
        declaration.source_ref,
        source.model_copy(update={"sha256": _ZERO_DIGEST}),
    )
    updated_layout = layout.model_copy(
        update={declaration_name: declaration.model_copy(update={"source_sha256": _ZERO_DIGEST})},
    )
    mutated_modelo = _modelo_with_layout(modelo, revision, layout, updated_layout)

    with pytest.raises(RegistryValidationError, match="fails live canonical re-hash"):
        _build(mutated_modelo, zero_catalogues, filing_year=filing_year, period=period)
