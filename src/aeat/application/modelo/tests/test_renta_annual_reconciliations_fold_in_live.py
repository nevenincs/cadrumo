"""M180/M190/M193 renta annual reconciliations fold LIVE.

Three cross-modelo annual reconciliations are proven end-to-end on the
LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`).
Each annual summary modelo derives its declarante totals by folding the four
quarterly source filings (1T-4T) through the enrolled
:class:`RelationPrefillSourceResolver`:

* **Modelo 180** (revision ``2023-y-siguientes``) folds **Modelo 115** quarterly
  retención-de-alquileres filings. Source casilla ids ``01`` (perceptores),
  ``02`` (base), ``03`` (retenciones) → target casillas
  ``decl.total-perceptores`` / ``decl.base-total`` / ``decl.retenciones-total``
  via the ``copy``-from-relation formulas.
* **Modelo 190** (revision ``2024-y-siguientes``) folds **Modelo 111** quarterly
  retención-rendimientos-del-trabajo filings. Nine percepciones-count source
  casilla ids sum into ``decl.total-percepciones``, nine importe casilla ids into
  ``decl.percepciones-total``, and output ``28`` copies into
  ``decl.retenciones-total``.
* **Modelo 193** (revision ``2024-y-siguientes``) folds **Modelo 123** quarterly
  retención-capital-mobiliario filings. Source casilla ids ``03`` (perceptores),
  ``06`` (base), ``09`` (retenciones) → the same three declarante casillas.

Each source quarter is seeded as a filed observation through the production
observation-persistence API
(:meth:`CalculationObservationRepository.save_observation`, the same write path
the local-file carry flow uses), stamped with the non-official ``app_filing``
source_kind, over a real encrypted-SQLite object store
(:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider` via
:func:`isolated_runtime_profile`). No mocks, stubs, skips, or xfail.

The aggregation assertions (annual casilla == sum of the four DISTINCT seeded
quarterly inputs) are fold-WIRING invariants, not tautologies: the seeded
per-quarter values are distinct non-equal known Decimals, so an off-by-quarter,
a single-quarter copy, a silent blank, or a coincidental sum cannot satisfy the
assertion. The test does not recompute any registry IRPF formula — it proves
the enrolled relation resolver wires the four prior periodic filings through to
each annual declarante casilla.

Both M190 and M193 additionally declare ``source = "withholding"`` per-perceptor
detalle bindings (the tipo-2 row producers) that are deferred with advisory:
no resolver is enrolled, so the live calculate's ``source_diagnostics`` carries
an ``unhandled_binding_source`` advisory naming ``withholding``. That advisory
is EXPECTED and is asserted present alongside the clean relation fold — M190/M193
are deliberately NOT the empty-diagnostics shape that M180 (relation-only) is.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-renta-annual-fold"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2024
_ANNUAL_PERIOD = "0A"
_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_RELATION_PREFILL_SOURCE = "relation_prefill"
_WITHHOLDING_SOURCE = "withholding"

# Declarante summary casilla ids shared by the M180 / M193 copy-from-relation
# reconciliations (M180 2023 and M193 2024 both expose these three).
_DECL_PERCEPTORES: CasillaId = validated_casilla_id("decl.total-perceptores", surface="_DECL_PERCEPTORES")
_DECL_BASE: CasillaId = validated_casilla_id("decl.base-total", surface="_DECL_BASE")
_DECL_RETENCIONES: CasillaId = validated_casilla_id("decl.retenciones-total", surface="_DECL_RETENCIONES")
# M190 declarante summary casilla ids (percepciones rather than perceptores).
_DECL_PERCEPCIONES_COUNT: CasillaId = validated_casilla_id(
    "decl.total-percepciones",
    surface="_DECL_PERCEPCIONES_COUNT",
)
_DECL_PERCEPCIONES_AMOUNT: CasillaId = validated_casilla_id(
    "decl.percepciones-total",
    surface="_DECL_PERCEPCIONES_AMOUNT",
)
_M115_PERCEPTORES_OUTPUT: CasillaId = validated_casilla_id("01", surface="_M115_PERCEPTORES_OUTPUT")
_M115_BASE_OUTPUT: CasillaId = validated_casilla_id("02", surface="_M115_BASE_OUTPUT")
_M115_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("03", surface="_M115_RETENCIONES_OUTPUT")
_M123_PERCEPTORES_OUTPUT: CasillaId = validated_casilla_id("03", surface="_M123_PERCEPTORES_OUTPUT")
_M123_BASE_OUTPUT: CasillaId = validated_casilla_id("06", surface="_M123_BASE_OUTPUT")
_M123_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("09", surface="_M123_RETENCIONES_OUTPUT")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_quarterly_filing(
    *,
    obs_repo: CalculationObservationRepository,
    source_modelo: str,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    """Persist one filed source-modelo quarter carrying every needed source casilla id.

    The relation resolver requires exactly ONE observation per
    ``(source_modelo, filing_year, period)`` carrying every source casilla id the
    annual relations consume, so each quarter is written as a single
    :class:`RegistryModeloObservation` whose ``observations`` tuple covers all
    outputs. Persisted through the production
    :meth:`CalculationObservationRepository.save_observation` write path with the
    non-official ``app_filing`` source_kind.
    """
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=source_modelo,
            filing_year=_YEAR,
            period=period,
            observations=registry_grounded_observations(
                modelo=source_modelo,
                filing_year=_YEAR,
                period=period,
                casilla_values=casilla_values,
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _calculate_annual(
    secure_objects: SecureObjectRepository,
    *,
    modelo: str,
) -> BucketAggregationCalculationResult:
    """Run the live annual calculate for ``modelo`` / ``_YEAR`` / ``0A``.

    These annual summary modelos declare no ``profile`` bindings and no caller
    inputs other than the relation-folded values; the only bindings are the
    ``relation_prefill`` reconciliations (folded by the enrolled resolver from
    the seeded source store) and, for M190/M193, the deferred ``withholding``
    detalle bindings. No ``binding_values`` are supplied so the live mesh is the
    sole value source.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=_YEAR, period=_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def _assert_distinct_positive(values: dict[str, Decimal]) -> Decimal:
    """Return the sum of ``values`` after asserting they are distinct and positive.

    Distinct non-equal positive values make the downstream fold assertion
    non-tautological: a silent blank (0), a single-quarter copy, or an
    off-by-quarter wiring cannot reproduce the strictly-positive sum of four
    distinct quarters.
    """
    assert len(set(values.values())) == len(values), f"seeded quarters must be distinct; got {values}"
    total = sum(values.values(), Decimal("0"))
    assert total > Decimal("0")
    return total


# ---------------------------------------------------------------------------
# Modelo 180 <- Modelo 115 (perceptores / base / retenciones), relation-only.
# ---------------------------------------------------------------------------

# Four DISTINCT non-equal quarterly values per M115 output. M115 c01 is an
# integer perceptor count; c02 (base) and c03 (retenciones) are money.
_M115_C01_PERCEPTORES = {"1T": Decimal("1"), "2T": Decimal("2"), "3T": Decimal("3"), "4T": Decimal("4")}
_M115_C02_BASE = {
    "1T": Decimal("1000.00"),
    "2T": Decimal("2500.50"),
    "3T": Decimal("750.25"),
    "4T": Decimal("3000.00"),
}
_M115_C03_RETENCIONES = {
    "1T": Decimal("190.00"),
    "2T": Decimal("475.10"),
    "3T": Decimal("142.55"),
    "4T": Decimal("570.00"),
}


def test_m180_folds_in_four_m115_quarters_on_live_calculate(secure_objects: SecureObjectRepository) -> None:
    """E2E: four filed M115 quarters fold into the M180 annual declarante totals.

    Each M180 declarante casilla is a ``copy`` of its annual_summary relation,
    whose ``sum`` aggregation folds the four seeded M115 quarters. The three
    annual casillas equal the per-output four-quarter sums. M180 declares only
    ``relation_prefill`` bindings, so the live resolution is clean — no
    ``source_diagnostics`` at all.
    """
    obs_repo = CalculationObservationRepository()
    expected_perceptores = _assert_distinct_positive(_M115_C01_PERCEPTORES)
    expected_base = _assert_distinct_positive(_M115_C02_BASE)
    expected_retenciones = _assert_distinct_positive(_M115_C03_RETENCIONES)
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="115",
            period=period,
            casilla_values={
                _M115_PERCEPTORES_OUTPUT: _M115_C01_PERCEPTORES[period],
                _M115_BASE_OUTPUT: _M115_C02_BASE[period],
                _M115_RETENCIONES_OUTPUT: _M115_C03_RETENCIONES[period],
            },
        )

    result = _calculate_annual(secure_objects, modelo="180")

    values = result.revision.casilla_values
    assert Decimal(values[_DECL_PERCEPTORES]) == expected_perceptores, (
        f"M180 {_DECL_PERCEPTORES} must fold the four M115 c01 quarters "
        f"(sum {expected_perceptores}); got {values[_DECL_PERCEPTORES]}"
    )
    assert Decimal(values[_DECL_BASE]) == expected_base, (
        f"M180 {_DECL_BASE} must fold the four M115 c02 quarters (sum {expected_base}); got {values[_DECL_BASE]}"
    )
    assert Decimal(values[_DECL_RETENCIONES]) == expected_retenciones, (
        f"M180 {_DECL_RETENCIONES} must fold the four M115 c03 quarters "
        f"(sum {expected_retenciones}); got {values[_DECL_RETENCIONES]}"
    )

    # relation_prefill is a claimed source: no diagnostic names it.
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    # M180 has no withholding detalle bindings, so the whole resolution is clean.
    assert result.source_diagnostics == (), (
        f"M180 source_diagnostics must be clean (relation-only); got {result.source_diagnostics}"
    )


# ---------------------------------------------------------------------------
# Modelo 190 <- Modelo 111 (percepciones counts / importes / retenciones),
# relation fold + deferred withholding detalle advisory.
# ---------------------------------------------------------------------------

# The nine percepciones-count source casilla ids (M111 c01,04,07,10,13,16,19,22,25)
# sum into decl.total-percepciones. Distinct integers across outputs AND
# quarters so the 36-term fold is unmistakable.
_M190_PERCEPCION_OUTPUTS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(value, surface="_M190_PERCEPCION_OUTPUTS")
    for value in ("01", "04", "07", "10", "13", "16", "19", "22", "25")
)
# The nine importe source casilla ids (M111 c02,05,08,11,14,17,20,23,26) sum into
# decl.percepciones-total.
_M190_IMPORTE_OUTPUTS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(value, surface="_M190_IMPORTE_OUTPUTS")
    for value in ("02", "05", "08", "11", "14", "17", "20", "23", "26")
)
# Output 28 (M111 retenciones total) copies into decl.retenciones-total via the
# retenciones relation (still summed over the four quarters per the binding).
_M190_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("28", surface="_M190_RETENCIONES_OUTPUT")


def _m190_seed_value(output: CasillaId, period: str) -> Decimal:
    """Return a distinct seed for one M111 output in one quarter.

    Encodes the output index and the quarter index into the integer/decimal so
    every (output, quarter) pair carries a unique value — a wrong-output or
    wrong-quarter fold cannot reproduce the per-casilla expected sum.
    """
    quarter_index = _QUARTERS.index(period) + 1
    # Percepción counts are integers; importe / retenciones are money. Both axes
    # are distinct per (output, quarter); the leading digit is the output index
    # and the trailing the quarter index.
    base = (int(output) * 100) + quarter_index
    if output in _M190_PERCEPCION_OUTPUTS:
        return Decimal(base)
    return Decimal(base) + Decimal("0.50")


def test_m190_folds_in_four_m111_quarters_with_withholding_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: four filed M111 quarters fold into M190 annual totals; withholding advisory present.

    The nine percepciones-count relations sum into ``decl.total-percepciones``,
    the nine importe relations into ``decl.percepciones-total``, and the
    retenciones relation (output ``28``) into ``decl.retenciones-total``. Each
    annual casilla equals the exact 36-term (9 outputs x 4 quarters) or 4-term
    (retenciones) sum of the distinct seeded inputs. Because M190 also declares
    the deferred ``withholding`` per-perceptor detalle bindings, the live
    calculate carries an ``unhandled_binding_source`` advisory for
    ``withholding`` — asserted present (NOT empty diagnostics).
    """
    obs_repo = CalculationObservationRepository()
    all_outputs = (*_M190_PERCEPCION_OUTPUTS, *_M190_IMPORTE_OUTPUTS, _M190_RETENCIONES_OUTPUT)
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="111",
            period=period,
            casilla_values={output: _m190_seed_value(output, period) for output in all_outputs},
        )

    expected_percepciones_count = sum(
        (_m190_seed_value(output, period) for output in _M190_PERCEPCION_OUTPUTS for period in _QUARTERS),
        Decimal("0"),
    )
    expected_percepciones_amount = sum(
        (_m190_seed_value(output, period) for output in _M190_IMPORTE_OUTPUTS for period in _QUARTERS),
        Decimal("0"),
    )
    expected_retenciones = sum(
        (_m190_seed_value(_M190_RETENCIONES_OUTPUT, period) for period in _QUARTERS),
        Decimal("0"),
    )
    # Sanity: the three expected totals are strictly positive and mutually
    # distinct, so a cross-wired fold (perceptores summed into importe, etc.)
    # would red the per-casilla assertions below.
    assert expected_percepciones_count > Decimal("0")
    assert expected_percepciones_amount > Decimal("0")
    assert expected_retenciones > Decimal("0")
    assert len({expected_percepciones_count, expected_percepciones_amount, expected_retenciones}) == 3

    result = _calculate_annual(secure_objects, modelo="190")

    values = result.revision.casilla_values
    assert Decimal(values[_DECL_PERCEPCIONES_COUNT]) == expected_percepciones_count, (
        f"M190 {_DECL_PERCEPCIONES_COUNT} must fold the nine percepciones-count outputs over four quarters "
        f"(sum {expected_percepciones_count}); got {values[_DECL_PERCEPCIONES_COUNT]}"
    )
    assert Decimal(values[_DECL_PERCEPCIONES_AMOUNT]) == expected_percepciones_amount, (
        f"M190 {_DECL_PERCEPCIONES_AMOUNT} must fold the nine importe outputs over four quarters "
        f"(sum {expected_percepciones_amount}); got {values[_DECL_PERCEPCIONES_AMOUNT]}"
    )
    assert Decimal(values[_DECL_RETENCIONES]) == expected_retenciones, (
        f"M190 {_DECL_RETENCIONES} must fold the retenciones output (28) over four quarters "
        f"(sum {expected_retenciones}); got {values[_DECL_RETENCIONES]}"
    )

    # The relation fold is clean (claimed source, no diagnostic names it)...
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    # ...but the deferred withholding detalle bindings MUST surface the
    # advisory (NOT empty diagnostics — that is the M180 relation-only case).
    withholding_advisories = [
        diag
        for diag in result.source_diagnostics
        if diag.source_kind == _WITHHOLDING_SOURCE and diag.reason == "unhandled_binding_source"
    ]
    assert withholding_advisories, (
        "M190 must surface an 'unhandled_binding_source' advisory for the deferred 'withholding' "
        f"detalle bindings; source_diagnostics: {result.source_diagnostics}"
    )
    assert all(diag.binding_id for diag in withholding_advisories)
    assert all(_WITHHOLDING_SOURCE in diag.message for diag in withholding_advisories)


# ---------------------------------------------------------------------------
# Modelo 193 <- Modelo 123 (perceptores / base / retenciones),
# relation fold + deferred withholding detalle advisory.
# ---------------------------------------------------------------------------

# Four DISTINCT non-equal quarterly values per M123 output. M123 c03 is an
# integer perceptor count; c06 (base) and c09 (retenciones) are money.
_M123_C03_PERCEPTORES = {"1T": Decimal("5"), "2T": Decimal("7"), "3T": Decimal("11"), "4T": Decimal("13")}
_M123_C06_BASE = {
    "1T": Decimal("4000.00"),
    "2T": Decimal("1250.75"),
    "3T": Decimal("9000.20"),
    "4T": Decimal("333.05"),
}
_M123_C09_RETENCIONES = {
    "1T": Decimal("760.00"),
    "2T": Decimal("237.64"),
    "3T": Decimal("1710.04"),
    "4T": Decimal("63.28"),
}


def test_m193_folds_in_four_m123_quarters_with_withholding_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: four filed M123 quarters fold into M193 annual totals; withholding advisory present.

    Each M193 declarante casilla is a ``copy`` of its annual_summary relation,
    whose ``sum`` aggregation folds the four seeded M123 quarters (output ``03``
    perceptores, ``06`` base, ``09`` retenciones). Because M193 also declares the
    deferred ``withholding`` tipo-2 detalle bindings, the live calculate carries
    an ``unhandled_binding_source`` advisory for ``withholding`` — asserted
    present alongside the clean relation fold (NOT empty diagnostics).
    """
    obs_repo = CalculationObservationRepository()
    expected_perceptores = _assert_distinct_positive(_M123_C03_PERCEPTORES)
    expected_base = _assert_distinct_positive(_M123_C06_BASE)
    expected_retenciones = _assert_distinct_positive(_M123_C09_RETENCIONES)
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="123",
            period=period,
            casilla_values={
                _M123_PERCEPTORES_OUTPUT: _M123_C03_PERCEPTORES[period],
                _M123_BASE_OUTPUT: _M123_C06_BASE[period],
                _M123_RETENCIONES_OUTPUT: _M123_C09_RETENCIONES[period],
            },
        )

    result = _calculate_annual(secure_objects, modelo="193")

    values = result.revision.casilla_values
    assert Decimal(values[_DECL_PERCEPTORES]) == expected_perceptores, (
        f"M193 {_DECL_PERCEPTORES} must fold the four M123 c03 quarters "
        f"(sum {expected_perceptores}); got {values[_DECL_PERCEPTORES]}"
    )
    assert Decimal(values[_DECL_BASE]) == expected_base, (
        f"M193 {_DECL_BASE} must fold the four M123 c06 quarters (sum {expected_base}); got {values[_DECL_BASE]}"
    )
    assert Decimal(values[_DECL_RETENCIONES]) == expected_retenciones, (
        f"M193 {_DECL_RETENCIONES} must fold the four M123 c09 quarters "
        f"(sum {expected_retenciones}); got {values[_DECL_RETENCIONES]}"
    )

    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    withholding_advisories = [
        diag
        for diag in result.source_diagnostics
        if diag.source_kind == _WITHHOLDING_SOURCE and diag.reason == "unhandled_binding_source"
    ]
    assert withholding_advisories, (
        "M193 must surface an 'unhandled_binding_source' advisory for the deferred 'withholding' "
        f"detalle bindings; source_diagnostics: {result.source_diagnostics}"
    )
    assert all(diag.binding_id for diag in withholding_advisories)
    assert all(_WITHHOLDING_SOURCE in diag.message for diag in withholding_advisories)
