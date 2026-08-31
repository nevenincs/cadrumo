"""Modelo 296's detail records hold every row, not just the first.

Four of modelo 296's five records are lists in AEAT's own design: the Tipo 2 perceptor
record and its intereses hoja are emitted once per payee, and the two valores-negociables
anexos are *relaciones*, one row per pago and one per certificado. All four were published
as single non-repeating records, so each could hold exactly ONE row -- a 296 with two payees
could not be expressed at all -- and their fields were header producers that nothing
resolved, so even the one row each could hold rendered blank.

Both halves are asserted against the SHIPPED layout, because both fail silently. A one-row
ceiling does not raise: it emits a structurally valid file that under-declares by however
many rows were dropped, which is exactly the failure mode this project forbids.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import override

import pytest

from ....core.filing_projection_ref import (
    M296AnexoCertificadoField,
    M296AnexoCertificadoProjectionRef,
    M296AnexoPagoField,
    M296AnexoPagoProjectionRef,
    M296PerceptorField,
    M296PerceptorInteresesField,
    M296PerceptorInteresesProjectionRef,
    M296PerceptorProjectionRef,
)
from ....core.modelo import Modelo
from ....core.payment_election import PaymentElection
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import bundled_authority
from .._m296_projection import build_m296_filing_projection_plan
from .._producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    Modelo296AnexoCertificadoRow,
    Modelo296AnexoPagoRow,
    Modelo296PerceptorInteresesRow,
    Modelo296PerceptorRow,
    Modelo296ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "296"
_REVISION = "2024-y-siguientes"

type _M296ProfileFactory = Callable[[tuple[str, ...]], Modelo296ProfileFacts]


@dataclass(frozen=True)
class _Family:
    """One repeated modelo 296 record and the row type that fills it."""

    record_id: str
    fields: type[StrEnum]
    profile: _M296ProfileFactory
    #: A field every row of this family carries, used to prove rows keep their own values.
    distinguishing_field: StrEnum

    @override
    def __str__(self) -> str:
        return self.record_id


_FAMILIES: tuple[_Family, ...] = (
    _Family(
        "m296-perceptor",
        M296PerceptorField,
        lambda values: Modelo296ProfileFacts(
            ejercicio="2024",
            nif_del_declarante="B12345678",
            apellidos_y_nombre_o_razon_social_del="EMPRESA PAGADORA SL",
            perceptor_rows=tuple(Modelo296PerceptorRow(nif_del_perceptor=value) for value in values),
        ),
        M296PerceptorField.NIF_DEL_PERCEPTOR,
    ),
    _Family(
        "m296-perceptor-intereses",
        M296PerceptorInteresesField,
        lambda values: Modelo296ProfileFacts(
            ejercicio="2024",
            nif_del_declarante="B12345678",
            apellidos_y_nombre_o_razon_social_del="EMPRESA PAGADORA SL",
            perceptor_intereses_rows=tuple(Modelo296PerceptorInteresesRow(nif_del_perceptor=value) for value in values),
        ),
        M296PerceptorInteresesField.NIF_DEL_PERCEPTOR,
    ),
    _Family(
        "m296-anexo-a-pagos",
        M296AnexoPagoField,
        lambda values: Modelo296ProfileFacts(
            ejercicio="2024",
            nif_del_declarante="B12345678",
            apellidos_y_nombre_o_razon_social_del="EMPRESA PAGADORA SL",
            anexo_pago_rows=tuple(Modelo296AnexoPagoRow(nif_del_contribuyente=value) for value in values),
        ),
        M296AnexoPagoField.NIF_DEL_CONTRIBUYENTE,
    ),
    _Family(
        "m296-anexo-b-certificados",
        M296AnexoCertificadoField,
        lambda values: Modelo296ProfileFacts(
            ejercicio="2024",
            nif_del_declarante="B12345678",
            apellidos_y_nombre_o_razon_social_del="EMPRESA PAGADORA SL",
            anexo_certificado_rows=tuple(
                Modelo296AnexoCertificadoRow(codigo_isin_del_certificado=value) for value in values
            ),
        ),
        M296AnexoCertificadoField.CODIGO_ISIN_DEL_CERTIFICADO,
    ),
)


def _snapshot_and_layout():
    """Resolve the shipped snapshot and layout the law selects for 296/2024/0A.

    Resolved from (modelo, filing_year, period), never from a stored revision id: which
    revision applies is a derived fact, and the id is only asserted equal to it.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=2024, period="0A", on=None)
    assert str(snapshot.revision.id) == _REVISION, (
        f"the law-determined revision for 296/2024/0A is {snapshot.revision.id}, not {_REVISION}"
    )
    return snapshot, snapshot.revision.export_layouts[0]


def _record(layout, family: _Family):
    return next(record for record in layout.records if str(record.id) == family.record_id)


def _producer_snapshot(profile: Modelo296ProfileFacts) -> FilingProducerSnapshot:
    """Build the canonical snapshot whose profile supplies the repeated rows."""
    return build_filing_producer_snapshot(
        modelo=Modelo.M296,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=profile,
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )


def _profile(family: _Family, count: int) -> Modelo296ProfileFacts:
    """A declarante carrying ``count`` distinguishable rows of one family."""
    values = tuple(f"ROW{index:05d}" for index in range(1, count + 1))
    return family.profile(values)


@pytest.mark.parametrize("family", _FAMILIES, ids=str)
def test_the_shipped_record_repeats_its_rows(family: _Family) -> None:
    """Without this the layout physically cannot express a second row."""
    _snapshot, layout = _snapshot_and_layout()
    assert _record(layout, family).repeat == "projection_rows", (
        f"the modelo 296 {family.record_id} record does not repeat, so the layout holds exactly "
        "one row and every row after the first is dropped from a filed return"
    )


@pytest.mark.parametrize("family", _FAMILIES, ids=str)
def test_every_field_is_a_projection_of_the_row(family: _Family) -> None:
    """No field of a repeated record may remain a header producer.

    A header producer on a per-row record reads a single declaration-wide value, which is
    either blank or the same wrong value repeated on every row.
    """
    _snapshot, layout = _snapshot_and_layout()
    record = _record(layout, family)
    header_fields = sorted(str(field.id) for field in record.fields if field.producer_key is not None)
    assert header_fields == [], f"{family}: fields still resolved as declaration headers: {header_fields}"

    projected = {field.projection_ref.field for field in record.fields if field.projection_ref is not None}
    assert projected == set(family.fields), (
        f"{family}: the shipped record does not project exactly its field set: "
        f"missing {sorted(f.value for f in set(family.fields) - projected)}, "
        f"extra {sorted(f.value for f in projected - set(family.fields))}"
    )


@pytest.mark.parametrize("family", _FAMILIES, ids=str)
@pytest.mark.parametrize("rows", [1, 2, 7])
def test_one_occurrence_is_emitted_per_row(family: _Family, rows: int) -> None:
    """Occurrence depth is the number of rows the filer has, with no ceiling anywhere."""
    snapshot, layout = _snapshot_and_layout()
    plan = build_m296_filing_projection_plan(
        registry_snapshot=snapshot,
        layout=layout,
        producer_snapshot=_producer_snapshot(_profile(family, rows)),
    )
    record = _record(layout, family)
    occurrences = sorted(context.occurrence for context in plan.contexts if context.record is record)
    assert occurrences == list(range(1, rows + 1))


@pytest.mark.parametrize("family", _FAMILIES, ids=str)
def test_each_row_keeps_its_own_values(family: _Family) -> None:
    """The anti-tautology half: an equal occurrence COUNT proves nothing on its own.

    A builder emitting N occurrences that all carry row one's values satisfies the count
    assertion above while still under-declaring every row after the first -- and the file it
    emits is structurally valid, so nothing downstream would object.
    """
    snapshot, layout = _snapshot_and_layout()
    plan = build_m296_filing_projection_plan(
        registry_snapshot=snapshot,
        layout=layout,
        producer_snapshot=_producer_snapshot(_profile(family, 3)),
    )
    record = _record(layout, family)
    by_occurrence = {
        value.occurrence: value.value
        for value in plan.values
        if value.record_id == record.id
        and isinstance(
            value.projection_ref,
            M296PerceptorProjectionRef
            | M296PerceptorInteresesProjectionRef
            | M296AnexoPagoProjectionRef
            | M296AnexoCertificadoProjectionRef,
        )
        and value.projection_ref.field is family.distinguishing_field
    }
    assert by_occurrence == {1: "ROW00001", 2: "ROW00002", 3: "ROW00003"}


@pytest.mark.parametrize("family", _FAMILIES, ids=str)
def test_a_family_with_no_rows_emits_no_record(family: _Family) -> None:
    """An absent row is not a blank row.

    Whether the absence is admissible is the record's own required flag, which is the
    renderer's question rather than the plan's.
    """
    snapshot, layout = _snapshot_and_layout()
    plan = build_m296_filing_projection_plan(
        registry_snapshot=snapshot,
        layout=layout,
        producer_snapshot=_producer_snapshot(_profile(family, 0)),
    )
    assert plan.contexts == ()
    assert plan.values == ()
