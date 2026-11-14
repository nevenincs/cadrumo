"""The Modelo 840 Anexo reads the premises where the declared activity is exercised.

A local afecto indirectamente belongs to Apartado V, not to the Anexo "Relación de
locales"; one Modelo 840 declares one activity, so exercised premises naming two
activities are refused rather than mixed onto one Anexo.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.contribuyente.iae_local_facts import IAE_LOCAL_SECTION
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...filing.producer_snapshot_m840 import Modelo840LocalRow
from ..action_errors import ModeloProfileReadinessError
from ..m840_anexo_profile import modelo_840_profile_facts

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "840"
_PERIOD = "0A"
_BUCKET_ID = "m840-anexo-profile"


def _work_unit() -> WorkUnit:
    snapshot = published_snapshot(_MODELO, filing_year=filing_year_envelope().horizon, period=_PERIOD)
    year = snapshot.snapshot_ref.modelo_year
    period = Period.from_year_and_code(year, _PERIOD)
    stamp = datetime(year, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=_MODELO, filing_year=year, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="m840-anexo",
        created_at=stamp,
        updated_at=stamp,
    )


def _local(row: int, **leaves: str) -> dict[str, object]:
    return {f"{IAE_LOCAL_SECTION}.{row}.{leaf}": value for leaf, value in leaves.items()}


def test_only_exercised_premises_fill_the_anexo_in_stored_order() -> None:
    path_values = (
        _local(4, actividad="0", afectacion="ejercicio", via_nombre="CALLE MAYOR", numero="7", superficie_total="120")
        | _local(1, actividad="0", afectacion="indirecta", via_nombre="ALMACEN NORTE")
        | _local(2, actividad="0", afectacion="ejercicio", postcode="50001", municipality_name="ZARAGOZA")
    )

    facts = modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert facts.local_rows == (
        Modelo840LocalRow(codigo_postal="50001", municipio_nombre="ZARAGOZA"),
        Modelo840LocalRow(nombre_via="CALLE MAYOR", numero="7", total=120),
    )


def test_a_profile_without_premises_lists_none() -> None:
    assert modelo_840_profile_facts(work_unit=_work_unit(), path_values={}).local_rows == ()


def test_exercised_premises_of_two_activities_are_refused() -> None:
    path_values = _local(1, actividad="0", afectacion="ejercicio") | _local(2, actividad="1", afectacion="ejercicio")

    with pytest.raises(ModeloProfileReadinessError) as refused:
        modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert refused.value.translated_message == "application.modelo.errors.m840_anexo_activities_ambiguous"
    assert (refused.value.context or {})["activities"] == "0, 1"
