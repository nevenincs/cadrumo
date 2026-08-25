"""Tests for the committed Modelo 187/188/194 registry foundations.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Bundled-registry loader used to validate the promoted definitions.
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_snapshot`
        Snapshot fixture used for committed-form arithmetic tests.
    :class:`~domain.calculations.registry.RegistryValidator`
        Registry integrity gate proving each promoted TOML tree is loadable.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Formula runtime entry point used for official form arithmetic.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision carrier whose construct-owned formulas are asserted.
    :class:`~domain.calculations.registry.CasillaId`
        Typed casilla identifier used for the copied-total assertion.
"""

from __future__ import annotations

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = ("187", "188", "194")
_REVISION_BY_MODELO = {"187": "2022-y-siguientes", "188": "2019-y-siguientes", "194": "2019-y-siguientes"}
_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_modelo_187_188_194_validators_accept_committed_definitions(modelo_id: str) -> None:
    modelo, catalogues = _committed_modelo(modelo_id)
    assert modelo.id == modelo_id
    assert modelo.revisions, f"{modelo_id} must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_modelo_187_188_194_declare_no_formula(modelo_id: str) -> None:
    """These hoja-resumen forms compute nothing, so no formula may be declared.

    **Correcting what this module asserted.** It required a
    ``modelo-NNN-total`` owned by a construct, and a companion test asserted
    "casilla 05 equals casilla 04 per each AEAT form's own printed total row".
    Reading the printed annexes disproved that appeal:

    * Orden HAP/1608/2014 ANEXO I numbers modelo 187 boxes 01 to 04 and prints
      NO box 05 at all; box 03 is "importe total de las enajenaciones", not a
      base.
    * The 1999 ordenes' ANEXO IV (188) and ANEXO VIII (194) number 01 to 05 in
      two rows split by sign of the base, where 03 is the retenciones and 05 is
      the NEGATIVE-base figure -- an input, not a total of anything.

    So the "total" was an identity ``add`` over one casilla, writing to a box
    that either did not exist or held a different declared figure. Every box on
    these three sheets is operator input; the formulas were deleted and the
    absence is the contract now.
    """
    modelo, _ = _committed_modelo(modelo_id)
    revision = modelo.revisions[_REVISION_BY_MODELO[modelo_id]]

    assert revision.formulas == (), (
        f"modelo {modelo_id} declares {len(revision.formulas)} formula(s); its printed "
        "hoja-resumen computes none of its boxes"
    )
    assert not any(construct.formulas for construct in revision.constructs)


def test_modelo_187_preserves_both_article_2_filer_population_limbs() -> None:
    """The retained withholding selector must not erase Article 42 RGAT filers."""
    modelo, catalogues = _committed_modelo("187")
    revision = modelo.revisions["2022-y-siguientes"]
    (rule,) = revision.applicability

    assert rule.required_payer_fact == "pays_capital_income_with_retencion"
    assert "orden-hac-1417-2018:art-primero" in rule.legal_refs
    assert "articulo 42 RGAT" in rule.applicable_reason
    assert "permanece sin resolver" in rule.not_applicable_reason

    article_2 = catalogues.legal["orden-hac-1417-2018:art-primero"]
    assert "Asimismo, se encuentran también obligadas a presentar el modelo 187" in article_2.required_text


@pytest.mark.parametrize(
    ("modelo_id", "expected"),
    [
        ("187", ("01", "02", "03", "04")),
        ("188", ("01", "02", "03", "04", "05")),
        ("194", ("01", "02", "03", "04", "05")),
    ],
)
def test_modelo_187_188_194_casilla_set_is_the_printed_box_set(modelo_id: str, expected: tuple[str, ...]) -> None:
    """The declared casillas are the boxes the approving orden's annex prints."""
    modelo, _ = _committed_modelo(modelo_id)
    revision = modelo.revisions[_REVISION_BY_MODELO[modelo_id]]

    assert tuple(str(casilla.id) for casilla in revision.casillas) == expected
    assert all(casilla.input_kind.value == "manual" for casilla in revision.casillas), (
        "every box on these hoja-resumen forms is declarante input"
    )
