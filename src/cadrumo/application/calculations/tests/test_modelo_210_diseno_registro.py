"""Modelo 210 diseño-de-registro structural + formula-wiring parity.

Grounds the complete numbered liquidación casilla schema against the bundled
AEAT layout authority ``boe-modelo-210-diseno-registro-2011`` (record identifier
T21001, version 1.1, 15/02/2012). The official form enumerates numbered boxes
[4]-[31] on the "Determinación de la base imponible" (210 I/R/H/G) and
"Liquidación" segments; the remaining fixed-width positions are
identification/domicile/property/banking segments, out of scope for the numbered
casilla schema.

Two contracts are asserted, both non-tautological (this tests the form's
declared STRUCTURE and inter-casilla arithmetic WIRING, not a rate oracle):

* Structure: every official numbered box [4]-[31] is present in the revision's
  declared casilla numbering, and the layout-authority corpus artefact resolves
  on disk.
* Wiring: the real registry engine (no mocks) evaluates the form's declared
  formula chain end-to-end. The rates it applies (0.19 EU/EEA, 0.24 general)
  come from the registry TRLIRNR parameter table, not from the test author; the
  assertions check that the declared boxes fold into one another as the official
  diseño-de-registro states: [8]=[5]-[6]-[7], [17]=[12]+[16], [22]=base×[21],
  [24]=[22]-[23], [28]=clamped convenio reduction, [31]=[28]-[29]±[30].
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import validated_casilla_id
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "210"
_YEAR = 2025
_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"
_DR_SOURCE = "boe-modelo-210-diseno-registro-2011"

# The official numbered liquidación boxes on record T21001, page 2.
_OFFICIAL_NUMBERS = tuple(str(n) for n in range(4, 32))


def _calculate(
    *,
    tipo_renta: str,
    country_code: str,
    casilla_inputs: Mapping[str, str],
) -> Mapping[str, Decimal]:
    """Drive the REAL M210 engine and return values keyed by official number."""
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code} if country_code else {}
    text_inputs = {validated_casilla_id("tipo_renta", surface="diseno_registro_test"): tipo_renta}
    casilla_values = {
        validated_casilla_id(k, surface="diseno_registro_test"): Decimal(v) for k, v in casilla_inputs.items()
    }
    bound = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs={**bound, **casilla_values},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        text_inputs=text_inputs,
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )
    numbers_by_id = {c.id: c.number for c in snapshot.revision.casillas}
    return {numbers_by_id[cid]: value for cid, value in result.values.items()}


def test_official_numbered_boxes_4_to_31_are_all_declared() -> None:
    """Every official diseño-de-registro numbered box [4]-[31] is present."""
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    declared = {c.number for c in snapshot.revision.casillas}
    missing = [n for n in _OFFICIAL_NUMBERS if n not in declared]
    assert not missing, f"official M210 casilla numbers absent from the schema: {missing!r}"


def test_layout_authority_corpus_artefact_resolves() -> None:
    """The bundled diseño-de-registro PDF is registered and present on disk."""
    catalogues = bundled_authority().catalogues
    source = catalogues.sources[_DR_SOURCE]
    assert source.evidence_tier == "layout_authority"
    assert source.corpus_path == "corpus/aeat_official/disenos_registro/modelo_210/dr210_2011.pdf"
    assert source.sha256 == "41875d015c809fc303a399581d6a437255f3235f8727515fe7e47606772a45e3"
    assert source.bytes == 48190
    assert (bundled_path() / source.corpus_path).is_file()


def test_type_r_base_and_liquidacion_chain_evaluates_end_to_end(tmp_path: Path) -> None:
    """No-convenio 210 R chain: [8]=[5]-[6]-[7] → [22] → [24] → [28] → [31].

    Worked input mirrors the AEAT spec example ([5]=1000, [6]=0, [7]=100 →
    [8]=900). The EU/EEA reduced rate 0.19 (casilla [21]) is read from the
    registry parameter table. The liquidación chain collapses to the
    pre-slice-C cuota_integra − retenciones result when no convenio, donativos
    or complementaria prior-result apply.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        v = _calculate(
            tipo_renta="ue_residente",
            country_code="",
            casilla_inputs={
                "rendimientos_integros": "1000.00",
                "exencion_dividendos": "0",
                "gastos_deducibles": "100.00",
                "retencion_practicada": "0",
            },
        )

    assert v["8"] == Decimal("900.00")  # [8] = [5] - [6] - [7]
    assert v["21"] == Decimal("0.19")  # EU/EEA reduced rate (registry parameter)
    assert v["22"] == Decimal("171.00")  # [22] = base × [21]
    assert v["24"] == Decimal("171.00")  # [24] = [22] - [23], donativos 0
    assert v["27"] == Decimal("0.00")  # [27] reducción convenio = 0 (no convenio)
    assert v["28"] == Decimal("171.00")  # [28] = [24] - [27]
    assert v["31"] == Decimal("171.00")  # [31] = [28] - [29] - [30]


def test_convenio_limit_clamps_the_reduced_cuota(tmp_path: Path) -> None:
    """A declared límite convenio [26] caps the reduced cuota: [28]=min([24],[26]).

    With [24]=171 and [26]=150, the treaty cap applies: [28]=150 and the
    reducción [27]=[24]-[26]=21, matching the official (24)-(26)/(24)-(27) rule.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        v = _calculate(
            tipo_renta="ue_residente",
            country_code="",
            casilla_inputs={
                "rendimientos_integros": "1000.00",
                "gastos_deducibles": "100.00",
                "convenio_indicador": "1",
                "limite_convenio": "150.00",
            },
        )

    assert v["24"] == Decimal("171.00")
    assert v["27"] == Decimal("21.00")  # [27] = [24] - [26]
    assert v["28"] == Decimal("150.00")  # [28] = clamped to the convenio limit
    assert v["31"] == Decimal("150.00")


def test_ganancias_base_folds_adquisicion_and_mejora(tmp_path: Path) -> None:
    """210 H ganancias base [17] = [12] + [16] (adquisición + mejora ganancia)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        v = _calculate(
            tipo_renta="general",
            country_code="GB",
            casilla_inputs={"ganancia_importe": "5000.00", "mejora_ganancia": "2000.00"},
        )

    assert v["17"] == Decimal("7000.00")  # [17] = [12] + [16]


def test_donativos_and_complementaria_prior_result_flow_to_resultado(tmp_path: Path) -> None:
    """Donativos [23] and complementaria prior-result [30] fold into [24] and [31].

    [22]=240 (general 24% × 1000), [24]=[22]-[23]=190, [28]=190 (no convenio),
    [31]=[28]-[29]-[30]=190-10-30=150.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        v = _calculate(
            tipo_renta="general",
            country_code="GB",
            casilla_inputs={
                "rendimientos_integros": "1000.00",
                "deduccion_donativos": "50.00",
                "retencion_practicada": "10.00",
                "ingreso_devolucion_anterior": "30.00",
            },
        )

    assert v["22"] == Decimal("240.00")
    assert v["24"] == Decimal("190.00")  # [24] = [22] - [23]
    assert v["28"] == Decimal("190.00")
    assert v["31"] == Decimal("150.00")  # [31] = [28] - [29] - [30]
