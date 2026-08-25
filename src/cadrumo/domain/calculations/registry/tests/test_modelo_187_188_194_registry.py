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

from datetime import date

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.hashing import hash_file
from .....core.resources import bundled_path
from .._corpus_catalogue import resolve_record_design_binary
from .._errors import NoRevisionForPeriodError
from .._temporal import select_revision
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = ("187", "188", "194")
_REVISION_BY_MODELO = {"187": "2022-y-siguientes", "188": "2023-y-siguientes", "194": "2024"}
_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")

_M194_DESIGN_ERAS = (
    (2019, "aeat-dr-194-2019", "orden-hac-1276-2019:art-primero", "orden-hac-1276-2019:df-unica"),
    (2023, "aeat-dr-194-2023", "orden-hfp-1284-2023:art-6", "orden-hfp-1284-2023:df-unica"),
    (2024, "aeat-dr-194-2024", "orden-hac-1504-2024:art-primero", "orden-hac-1504-2024:df-unica"),
)


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


def test_modelo_187_selects_only_the_2022_design_era() -> None:
    """The current record design cannot be backdated to the unevidenced years."""
    modelo, catalogues = _committed_modelo("187")
    revision = modelo.revisions["2022-y-siguientes"]

    assert revision.authority_grade.value == "applicability"
    assert revision.valid_from == date(2022, 1, 1)
    assert revision.period_selector.year_from == 2022
    assert {ref for ref in revision.source_refs if ref.startswith("aeat-dr-187-")} == {"aeat-dr-187-2022"}
    design = catalogues.sources["aeat-dr-187-2022"]
    assert design.applies_from == date(2022, 1, 1)
    assert design.applies_to is None

    assert select_revision(modelo, filing_year=2022, period="0A", on=date(2022, 12, 31)) == revision
    for filing_year in range(2019, 2022):
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))


def test_modelo_188_selects_only_the_2023_design_era() -> None:
    """The sole hash-pinned 2023 design cannot establish earlier years."""
    modelo, catalogues = _committed_modelo("188")
    revision = modelo.revisions["2023-y-siguientes"]

    assert revision.authority_grade.value == "applicability"
    assert revision.valid_from == date(2023, 1, 1)
    assert revision.period_selector.year_from == 2023
    assert {ref for ref in revision.source_refs if ref.startswith("aeat-dr-188-")} == {"aeat-dr-188-2023"}
    assert catalogues.sources["aeat-dr-188-2023"].applies_from == date(2023, 1, 1)
    assert select_revision(modelo, filing_year=2023, period="0A", on=date(2023, 12, 31)) == revision
    for filing_year in range(2019, 2023):
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))


def test_modelo_194_selects_only_its_three_hash_pinned_design_eras() -> None:
    """Each declared Modelo 194 year resolves to its own official binary."""
    modelo, catalogues = _committed_modelo("194")

    assert set(modelo.revisions) == {"2019", "2023", "2024"}
    for filing_year, source_ref, amendment_ref, commencement_ref in _M194_DESIGN_ERAS:
        revision = modelo.revisions[str(filing_year)]
        source = catalogues.sources[source_ref]

        assert revision.authority_grade.value == "applicability"
        assert revision.valid_from == date(filing_year, 1, 1)
        assert revision.valid_to == date(filing_year, 12, 31)
        assert revision.period_selector.year_from == filing_year
        assert revision.period_selector.year_to == filing_year
        assert {ref for ref in revision.source_refs if ref.startswith("aeat-dr-194-")} == {source_ref}
        assert {amendment_ref, commencement_ref} <= set(revision.legal_refs)
        assert revision.export_layouts == ()

        assert source.record_design_epoch == str(filing_year)
        assert source.applies_from == date(filing_year, 1, 1)
        assert source.applies_to == date(filing_year, 12, 31)
        assert select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31)) == revision

        resolved = resolve_record_design_binary(
            bundled_path(),
            catalogues.sources,
            source_ref=source_ref,
            filing_year=filing_year,
            design_epoch=str(filing_year),
        )
        assert resolved.source == source
        assert hash_file(resolved.path) == (source.sha256, source.bytes)

    for filing_year in (2020, 2021, 2022, 2025, 2026):
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))


def test_modelo_194_refuses_a_mutated_2024_selector_past_its_source_window() -> None:
    """A selector expansion cannot turn the 2024 source into 2025 authority."""
    modelo, catalogues = _committed_modelo("194")
    revision = modelo.revisions["2024"]
    expanded = revision.model_copy(
        update={
            "valid_to": date(2025, 12, 31),
            "period_selector": revision.period_selector.model_copy(update={"year_to": 2025}),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, "2024": expanded}})

    with pytest.raises(RegistryValidationError, match="aeat-dr-194-2024"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_modelo_194_refuses_a_mutated_record_design_hash() -> None:
    """The exact era selector also verifies the bytes of its named source."""
    _modelo, catalogues = _committed_modelo("194")
    source_ref = "aeat-dr-194-2024"
    sources = dict(catalogues.sources)
    sources[source_ref] = sources[source_ref].model_copy(update={"sha256": "0" * 64})
    mutated_catalogues = catalogues.model_copy(update={"sources": sources})

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            mutated_catalogues.sources,
            source_ref=source_ref,
            filing_year=2024,
            design_epoch="2024",
        )


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
