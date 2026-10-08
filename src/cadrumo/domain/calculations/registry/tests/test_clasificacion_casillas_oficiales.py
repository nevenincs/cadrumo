"""Real bundled-registry proofs for the canonical official-box classifier."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from .....core.estado_casilla_oficial import EstadoCasillaOficial
from ...export_field_kind import CasillaFieldKind
from .. import export as owner
from ..export import clasificar_casillas_oficiales
from .published_authority import published_snapshot
from .registry_tree import bundled_modelo_components, bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_classifier_is_the_public_registry_identity() -> None:
    assert clasificar_casillas_oficiales is owner.clasificar_casillas_oficiales


def test_m720_binding_derived_design_distinguishes_declared_binding_representation() -> None:
    revision = bundled_modelo_components("720")[0].revisions["2013-y-siguientes"]

    # Generated records materialize the reviewed bindings alongside literal
    # record/model markers, draft headers, and reserved trailing padding.
    # None directly addresses a casilla, so classification must still honor
    # the explicitly declared binding representation.
    records = [record for layout in revision.export_layouts for record in layout.records]
    assert {record.binding_record for record in records} == {"type_1", "type_2"}
    assert all(field.casilla_id is None for record in records for field in record.fields)
    assert {
        (field.offset, field.length, field.literal)
        for record in records
        for field in record.fields
        if field.kind is CasillaFieldKind.LITERAL
    } == {(1, 1, "1"), (1, 1, "2"), (2, 3, "720")}
    assert {
        (field.offset, field.length)
        for record in records
        for field in record.fields
        if field.kind is CasillaFieldKind.FILLER
    } == {(181, 320), (481, 20)}
    assert all(
        any(field.kind is CasillaFieldKind.BINDING and field.binding is not None for field in record.fields)
        for record in records
    )

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses[validated_casilla_id("decl.ejercicio", surface="M720 filing year")] is (
        EstadoCasillaOficial.REPRESENTED_VIA_BINDING
    )
    assert statuses[validated_casilla_id("decl.tipo-declaracion", surface="M720 declaration type")] is (
        EstadoCasillaOficial.REPRESENTED_VIA_BINDING
    )
    assert statuses[validated_casilla_id("cuentas.valoracion", surface="M720 account valuation")] is (
        EstadoCasillaOficial.UNDEFINED
    )


def test_m349_binding_derived_rows_address_casillas_without_export_refs() -> None:
    revision = published_snapshot("349", filing_year=2026, period="1T").revision

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses[validated_casilla_id("decl.numero-operadores", surface="M349 declared operator count")] is (
        EstadoCasillaOficial.ADDRESSED
    )
    assert statuses[validated_casilla_id("op.codigo-pais", surface="M349 operator country code")] is (
        EstadoCasillaOficial.ADDRESSED
    )
    country_code = next(casilla for casilla in revision.casillas if str(casilla.id) == "op.codigo-pais")
    assert not country_code.export_refs


def _layoutless_revisions() -> list[tuple[str, str]]:
    """Every committed revision that declares no export layout at all."""
    return sorted(
        (str(modelo.id), revision_id)
        for modelo in bundled_registry_tree()[0]
        for revision_id, revision in modelo.revisions.items()
        if not revision.export_layouts
    )


def test_layoutless_revisions_are_explicitly_undefined() -> None:
    """A revision with no export layout classifies every casilla as UNDEFINED.

    This pinned modelo 130 as its layoutless subject. The subject later gained
    an export layout, so it stopped being layoutless and the case failed on its
    own premise rather than on the classifier -- a decayed premise, not a
    regression. The subject is now derived from the property it needs, so a
    revision leaves this gate exactly when it gains a layout.
    """
    layoutless = _layoutless_revisions()
    assert layoutless, "the bundled registry no longer declares a layoutless revision"
    failures: list[str] = []
    for modelo_id, revision_id in layoutless:
        identity = f"{modelo_id}/{revision_id}"
        try:
            revision = bundled_modelo_components(modelo_id)[0].revisions[revision_id]
            statuses = clasificar_casillas_oficiales(revision)
        except Exception as error:
            failures.append(f"{identity}: {type(error).__name__}: {error}")
            continue
        if not statuses:
            failures.append(f"{identity}: has no casillas to classify")
        elif set(statuses.values()) != {EstadoCasillaOficial.UNDEFINED}:
            failures.append(f"{identity}: expected only UNDEFINED statuses, got {set(statuses.values())!r}")
    assert not failures, "\n".join(failures)


def test_revision_with_a_layout_addresses_at_least_one_casilla() -> None:
    """The contrapositive, which cannot go vacuous as the registry gains layouts.

    The layoutless population shrinks by design as authoring proceeds and
    would eventually empty, silently retiring the check above. This asserts the
    other direction on a revision that HAS a layout, so classification stays
    covered no matter how far the authoring gets.
    """
    revision = published_snapshot("130", filing_year=2026, period="1T").revision

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses
    assert EstadoCasillaOficial.ADDRESSED in set(statuses.values())
