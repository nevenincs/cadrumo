"""Registry-boundary tests for Modelo 303 and Modelo 390 filing paths.

Modelo 303 (IVA autoliquidación) and Modelo 390 (IVA resumen anual)
are registry-backed: their registry fragments carry full casilla and
revision definitions. ``build_draft`` must therefore project a
``ModeloDraft`` for both, sourcing its schema from the calculation
registry rather than refusing at the registry boundary. The
genuinely-unsupported-modelo refusal path is covered separately by
``test_testing_registry.test_unsupported_modelo_fails_at_registry_boundary``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.filing import FilingExportError
from ....domain.submission import ModeloDraftStatus
from .. import ModeloInputs, build_draft, build_runtime_schema_provider, export_draft
from ..testing import ModeloTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M303_REPERCUTIDO_GENERAL_BASE_CASILLA: CasillaId = validated_casilla_id(
    "07",
    surface="_M303_REPERCUTIDO_GENERAL_BASE_CASILLA",
)
_M303_SOPORTADO_INTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.soportado.interiores",
    surface="_M303_SOPORTADO_INTERIORES_CASILLA",
)
_M390_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio", surface="_M390_EJERCICIO_CASILLA")


def _profile() -> ModeloTestProfile:
    return ModeloTestProfile(
        tax_id="12345678Z",
        display_name="Registry boundary IVA test",
    )


@pytest.mark.parametrize(
    ("modelo", "period", "inputs"),
    [
        (
            "303",
            Period.from_year_and_code(2025, "1T"),
            {
                _M303_REPERCUTIDO_GENERAL_BASE_CASILLA: Decimal("10000.00"),
                _M303_SOPORTADO_INTERIORES_CASILLA: Decimal("200.00"),
                "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
            },
        ),
        (
            "390",
            Period.from_year_and_code(2025, "0A"),
            {
                _M390_EJERCICIO_CASILLA: 2025,
                "modelo-390-iva-repercutido-general-cuota": Decimal("0"),
                "modelo-390-iva-repercutido-reducido-cuota": Decimal("0"),
                "modelo-390-iva-repercutido-super-reducido-cuota": Decimal("0"),
                "modelo-390-iva-soportado-interiores-cuota": Decimal("0"),
                "modelo-390-iva-autorepercutido-intracomunitaria-cuota": Decimal("0"),
                "modelo-390-prev-303-cuota-devengada-total": Decimal("0"),
                "modelo-390-prev-303-cuota-deducible-total": Decimal("0"),
                "modelo-390-prev-303-resultado-regimen-general": Decimal("0"),
                "modelo-390-prev-303-compensacion-ultimo-periodo": Decimal("0"),
                "modelo-390-prev-303-compensacion-generada-ejercicio-no-97": Decimal("0"),
            },
        ),
    ],
)
def test_modelo_build_draft_projects_registry_backed_draft(
    modelo: str,
    period: Period,
    inputs: ModeloInputs,
) -> None:
    """``build_draft`` projects a registry-backed draft for 303 / 390."""
    draft = build_draft(
        modelo=modelo,
        period=period,
        profile=_profile(),
        inputs=inputs,
        schema_provider=build_runtime_schema_provider(modelos=("303", "390")),
    )

    assert draft.modelo == modelo
    assert draft.period == period
    assert draft.profile_tax_id == "12345678Z"


def test_modelo_390_export_refuses_missing_boe_layout_from_real_registry(tmp_path: Path) -> None:
    provider = build_runtime_schema_provider(modelos=("390",))
    subview = provider.get_subview("390")
    assert subview.export_layout_ids == ()
    assert subview.export_layouts == ()
    draft = build_draft(
        modelo="390",
        period=Period.from_year_and_code(2025, "0A"),
        profile=_profile(),
        inputs={
            _M390_EJERCICIO_CASILLA: 2025,
            "modelo-390-iva-repercutido-general-cuota": Decimal("0"),
            "modelo-390-iva-repercutido-reducido-cuota": Decimal("0"),
            "modelo-390-iva-repercutido-super-reducido-cuota": Decimal("0"),
            "modelo-390-iva-soportado-interiores-cuota": Decimal("0"),
            "modelo-390-iva-autorepercutido-intracomunitaria-cuota": Decimal("0"),
            "modelo-390-prev-303-cuota-devengada-total": Decimal("0"),
            "modelo-390-prev-303-cuota-deducible-total": Decimal("0"),
            "modelo-390-prev-303-resultado-regimen-general": Decimal("0"),
            "modelo-390-prev-303-compensacion-ultimo-periodo": Decimal("0"),
            "modelo-390-prev-303-compensacion-generada-ejercicio-no-97": Decimal("0"),
        },
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output_path = tmp_path / "modelo-390.txt"

    with pytest.raises(FilingExportError) as exc_info:
        export_draft(draft, output_path=output_path, headers={}, schema_provider=provider)

    message = str(exc_info.value)
    assert "modelo '390' fichero-BOE export is unsupported" in message
    assert "registry snapshot has no complete export_layouts definition" in message
    assert "calculation, verification, and local filing surfaces may exist" in message.lower()
    assert "cannot produce a BOE export file" in message
    assert "does not certify legal correctness" in message
    assert not output_path.exists()
