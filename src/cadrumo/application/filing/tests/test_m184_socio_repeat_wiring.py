"""Real-byte proof that the modelo 184 socio record repeats per member (S289).

Before this fix, the socio export record carried every field as a scalar
``kind = 'casilla'`` value with no ``repeat`` marker, so a real attribution
entity with several members always exported exactly one member's data no
matter how many were declared -- while the ATRIBUCION_MEMBER row bindings
computing every member's correct value already existed, enrolled, and were
simply discarded at the export boundary. This drives a real multi-member
attribution through the production resolver and the production renderer and
proves the fichero carries one occurrence PER MEMBER, with the RIGHT value in
each occurrence rather than merely the right count.

This exercises the socio record's own rendering in isolation (the sibling
declarante/entidad records on the same layout have their own, unrelated,
pre-existing required-input surface that a full ``export_draft`` round trip
would additionally demand); ``render_layout_records`` is the exact production
renderer ``export_draft`` itself calls, so nothing about the fix under test is
stood in for.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    resolve_atribucion_binding_row_values,
)
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef

from ....core import Modelo, Period, PriorDomiciliationElection
from ....domain.filing import ModeloDraft, compute_modelo_draft_id
from ....domain.submission import ModeloDraftStatus
from .. import GeneralFilingProfileFacts, build_filing_producer_snapshot
from .._export_producer import filing_producer_values
from .._projection import FilingProjectionPlan
from .._record_renderer import render_layout_records
from ._export_support import _schema_provider, _typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MEMBERS = (
    AtributionMemberObservation(
        source_id="member-1",
        member_tax_id="11111111H",
        member_legal_name="Miembro Uno",
        country_code="ES",
        transaction_date=date(2025, 1, 1),
        share_percentage=Decimal("50"),
        base_imponible_assigned=Decimal("1000.00"),
    ),
    AtributionMemberObservation(
        source_id="member-2",
        member_tax_id="22222222J",
        member_legal_name="Miembro Dos",
        country_code="ES",
        transaction_date=date(2025, 1, 1),
        share_percentage=Decimal("30"),
        base_imponible_assigned=Decimal("600.50"),
    ),
    AtributionMemberObservation(
        source_id="member-3",
        member_tax_id="33333333P",
        member_legal_name="Miembro Tres",
        country_code="ES",
        transaction_date=date(2025, 1, 1),
        share_percentage=Decimal("20"),
        base_imponible_assigned=Decimal("400.25"),
    ),
)


def _m184_producer_snapshot():
    base = _typed_producer_snapshot()
    return build_filing_producer_snapshot(
        modelo=Modelo.M184,
        taxpayer_tax_id=base.taxpayer_tax_id,
        taxpayer_identity=base.taxpayer_identity,
        presenter=base.presenter,
        model_profile=GeneralFilingProfileFacts(),
        elections=base.elections,
        amendment_evidence=base.amendment_evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )


def _binding_values_for(
    observations: tuple[AtributionMemberObservation, ...],
) -> dict[tuple[BindingId, int | None], object]:
    """Resolve real per-row member bindings through the production resolver."""
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("184",))
    revision = provider.get_snapshot("184").revision
    resolved = resolve_atribucion_binding_row_values(revision, observations)
    assert resolved, "the atribucion_member bindings must actually resolve rows"
    return {(binding_id, row_index): value for (binding_id, row_index), value in resolved.items()}


def _minimal_draft() -> ModeloDraft:
    """A minimal, real ``ModeloDraft`` carrying only what the renderer reads.

    The renderer only consults ``draft.modelo``/``draft.period`` for M369 and
    complementaria markers, neither of which apply to modelo 184; every other
    completeness concern (the sibling records' own required scalar casillas)
    is orthogonal to the socio-record repeat fix this test proves.
    """
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("184",))
    subview = provider.get_subview("184")
    period = Period.from_year_and_code(2025, "0A")
    snapshot_ref = RegistrySnapshotRef(
        modelo=subview.modelo_id,
        revision_id=subview.revision_id,
        modelo_year=2025,
        period="0A",
    )
    draft_id = compute_modelo_draft_id(
        modelo="184",
        period=period,
        profile_tax_id="12345678Z",
        snapshot_ref=snapshot_ref,
        values=(),
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ModeloDraft(
        draft_id=draft_id,
        modelo="184",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=now,
        updated_at=now,
        schema_version=subview.schema_version,
    )


def _socio_record_occurrences(observations: tuple[AtributionMemberObservation, ...]):
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("184",))
    snapshot = provider.get_snapshot("184")
    layout = snapshot.revision.export_layouts[0]
    producer_snapshot = _m184_producer_snapshot()
    headers = filing_producer_values(producer_snapshot)
    occurrences = render_layout_records(
        layout,
        registry_snapshot=snapshot,
        draft=_minimal_draft(),
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        casilla_values={},
        binding_values=_binding_values_for(observations),
        projection_plan=FilingProjectionPlan(contexts=(), values=()),
        projection_values={},
    )
    return tuple(occurrence for occurrence in occurrences if occurrence.record_id == "m184-socio")


def _decode(payload: bytes, *, offset: int, length: int) -> str:
    return payload[offset - 1 : offset - 1 + length].decode("latin-1").strip()


def test_export_emits_one_socio_occurrence_per_declared_member() -> None:
    occurrences = _socio_record_occurrences(_MEMBERS)

    # One occurrence per declared member, not one occurrence total.
    assert len(occurrences) == 3

    nifs = [_decode(occ.payload, offset=18, length=9) for occ in occurrences]
    names = [_decode(occ.payload, offset=36, length=40) for occ in occurrences]

    # The resolver's own deterministic sort is (country_code, member_tax_id),
    # so the three members render in tax-id order -- and each occurrence
    # carries THAT member's own values, not a repeated first row.
    assert nifs == ["11111111H", "22222222J", "33333333P"]
    assert names == ["Miembro Uno", "Miembro Dos", "Miembro Tres"]


def test_a_single_declared_member_still_exports_exactly_one_occurrence() -> None:
    """A count-only assertion would also pass a broken renderer emitting N identical rows.

    This complements the multi-member proof: the fix must not turn a
    single-member filing into spurious repeats either.
    """
    occurrences = _socio_record_occurrences(_MEMBERS[:1])
    assert len(occurrences) == 1
    assert _decode(occurrences[0].payload, offset=18, length=9) == "11111111H"


def test_socio_record_declares_repeating_binding_rows_not_a_scalar_slot() -> None:
    """Pin the registry declaration itself, independent of a live export run."""
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("184",))
    layout = provider.get_snapshot("184").revision.export_layouts[0]
    socio = next(record for record in layout.records if record.record_type == "socio")
    assert socio.repeat == "binding_rows"
    binding_fields = [field for field in socio.fields if field.kind == CasillaFieldKind.BINDING]
    assert {field.binding for field in binding_fields} == {
        "modelo-184-member-row-nif",
        "modelo-184-member-row-name",
        "modelo-184-member-row-share",
        "modelo-184-member-row-base-assigned",
    }


def test_occurrence_order_is_a_pure_function_of_content_not_of_supply_order() -> None:
    """A row's fichero occurrence number carries no meaning of its own (S292).

    ``resolve_atribucion_binding_row_values`` sorts its observations by
    ``(country_code, member_tax_id)`` before assigning row indices, so the
    occurrence a member lands on is a deterministic function of that member's
    own content -- never of the order the caller happened to supply
    observations in. Rendering the SAME three members via the production
    renderer in two unrelated supply orders proves the fichero bytes are
    byte-for-byte identical, not merely that some downstream id agrees: there
    is no operator-visible "declared order" for AEAT to lose or for a
    MOVE_ROW intent to preserve.
    """
    forward = _socio_record_occurrences(_MEMBERS)
    reversed_supply = _socio_record_occurrences(tuple(reversed(_MEMBERS)))
    shuffled_supply = _socio_record_occurrences((_MEMBERS[1], _MEMBERS[2], _MEMBERS[0]))

    forward_payloads = tuple(occ.payload for occ in forward)
    assert forward_payloads == tuple(occ.payload for occ in reversed_supply)
    assert forward_payloads == tuple(occ.payload for occ in shuffled_supply)
