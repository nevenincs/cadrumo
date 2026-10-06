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

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.hashing import hash_file
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import NoRevisionForPeriodError, RegistryValidationError
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..conformance.registry_schema_support import committed_modelo as _committed_modelo
from ..maintenance_support import resolve_record_design_binary
from .authored_edition_support import legal_text_match, source_first_exercise, source_with_sha256
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_MODELOS = ("187", "188", "194")
_REVISION_BY_MODELO = {"187": "2022-y-siguientes", "188": "2023-y-siguientes", "194": "2024"}
# The first exercise each hash-pinned official design evidences, read from its
# applicability, and the Modelo 194 edition that Orden HAC/1504/2024 supersedes: the
# one before the exercise the Orden first applies to.
_M187_DESIGN_EXERCISE = source_first_exercise(
    source_with_sha256("c7a21c1feb9619380bb0da3e73066fa3c58c628f430bf85ed9dbea15b1308eb1")
)
_M188_DESIGN_EXERCISE = source_first_exercise(
    source_with_sha256("30ced236b558de21383c3eba6339cb720fc9a704d38eaa574dd9be55cf90f9e3")
)
_M194_SUPERSEDED_EDITION = (
    int(
        legal_text_match(
            "orden-hac-1504-2024:df-unica",
            r"aplicable, por primera vez, a las declaraciones informativas correspondientes al ejercicio (\d{4})",
        ).group(1)
    )
    - 1
)
_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")

# (first ejercicio, LAST ejercicio or None for an open era, design, amending art, df unica).
# The end dates are NOT "first year again": each amending orden's df unica applies its
# edition "por primera vez" to its first ejercicio, which OPENS a continuing window, and
# BOE's consolidated Referencias posteriores for BOE-A-1999-22309 (read 2026-08-30) is
# what closes each one -- anexo X is amended in 2019, 2023 and 2024 and NOWHERE between
# 2020 and 2022, and not at all after 2024. So 2019 runs to 2022, 2023 is a single year
# because 2024 amends it, and 2024 is open.
_M194_DESIGN_ERAS = (
    (2019, 2022, "aeat-dr-194-2019", "orden-hac-1276-2019:art-primero", "orden-hac-1276-2019:df-unica"),
    (2023, 2023, "aeat-dr-194-2023", "orden-hfp-1284-2023:art-6", "orden-hfp-1284-2023:df-unica"),
    (2024, None, "aeat-dr-194-2024", "orden-hac-1504-2024:art-primero", "orden-hac-1504-2024:df-unica"),
)


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_modelo_187_188_194_validators_accept_committed_definitions(modelo_id: str) -> None:
    modelo, catalogues = _committed_modelo(modelo_id)
    assert modelo.id == modelo_id
    assert modelo.revisions, f"{modelo_id} must declare at least one revision"
    committed_registry_validator(catalogues).validate_modelo(modelo)


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


def test_modelo_187_selects_only_its_evidenced_design_era() -> None:
    """The current record design cannot be backdated to the unevidenced years."""
    modelo, catalogues = _committed_modelo("187")
    revision = modelo.revisions[_REVISION_BY_MODELO["187"]]
    first = _M187_DESIGN_EXERCISE

    assert revision.authority_grade is not None
    assert revision.authority_grade.value == "applicability"
    assert revision.valid_from == date(first, 1, 1)
    assert revision.period_selector.year_from == first
    assert {ref for ref in revision.source_refs if ref.startswith("aeat-dr-187-")} == {f"aeat-dr-187-{first}"}
    design = catalogues.sources[f"aeat-dr-187-{first}"]
    assert design.applies_from == date(first, 1, 1)
    assert design.applies_to is None

    assert select_revision(modelo, filing_year=first, period="0A", on=date(first, 12, 31)) == revision
    # The three exercises before the design, which no official design evidences.
    for filing_year in range(first - 3, first):
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))


def test_modelo_188_selects_only_its_evidenced_design_era() -> None:
    """The sole hash-pinned design cannot establish earlier years."""
    modelo, catalogues = _committed_modelo("188")
    revision = modelo.revisions[_REVISION_BY_MODELO["188"]]
    first = _M188_DESIGN_EXERCISE

    assert revision.authority_grade is not None
    assert revision.authority_grade.value == "applicability"
    assert revision.valid_from == date(first, 1, 1)
    assert revision.period_selector.year_from == first
    assert {ref for ref in revision.source_refs if ref.startswith("aeat-dr-188-")} == {f"aeat-dr-188-{first}"}
    assert catalogues.sources[f"aeat-dr-188-{first}"].applies_from == date(first, 1, 1)
    assert select_revision(modelo, filing_year=first, period="0A", on=date(first, 12, 31)) == revision
    # Earlier ejercicios are served by their own edition, never by this design.
    for earlier_id, earlier in modelo.revisions.items():
        if earlier_id == revision.id:
            continue
        year = earlier.period_selector.year_from
        assert year is not None and year < first
        assert select_revision(modelo, filing_year=year, period="0A", on=date(year, 12, 31)) == earlier


def test_modelo_194_selects_only_its_three_hash_pinned_design_eras() -> None:
    """Each declared Modelo 194 year resolves to its own official binary."""
    modelo, catalogues = _committed_modelo("194")

    assert set(modelo.revisions) == {"2019", "2023", "2024"}
    for filing_year, last_year, source_ref, amendment_ref, commencement_ref in _M194_DESIGN_ERAS:
        revision = modelo.revisions[str(filing_year)]
        source = catalogues.sources[source_ref]

        assert revision.authority_grade is not None
        assert revision.authority_grade.value == "applicability"
        era_end = date(last_year, 12, 31) if last_year is not None else None
        assert revision.valid_from == date(filing_year, 1, 1)
        assert revision.valid_to == era_end
        assert revision.period_selector.year_from == filing_year
        assert revision.period_selector.year_to == last_year
        assert {ref for ref in revision.source_refs if ref.startswith("aeat-dr-194-")} == {source_ref}
        assert {amendment_ref, commencement_ref} <= set(revision.legal_refs)
        assert revision.export_layouts == ()

        assert source.record_design_epoch == str(filing_year)
        assert source.applies_from == date(filing_year, 1, 1)
        # The design's window must MATCH the era it grounds; a design capped shorter than
        # its revision would let the revision cite authority the source disclaims.
        assert source.applies_to == era_end
        assert select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31)) == revision
        # Every year the era spans resolves to it -- the 2020-2022 interval is the point.
        for covered in range(filing_year, (last_year or filing_year) + 1):
            assert select_revision(modelo, filing_year=covered, period="0A", on=date(covered, 6, 30)) == revision

        resolved = resolve_record_design_binary(
            bundled_path(),
            catalogues.sources,
            source_ref=source_ref,
            filing_year=filing_year,
            design_epoch=str(filing_year),
        )
        assert resolved.source == source
        assert hash_file(resolved.path) == (source.sha256, source.bytes)

    # Refused BELOW the first declared era only. 2020-2022 and 2025+ used to be refused
    # here; both refusals were holes, not conservatism -- BOE's amendment list for
    # BOE-A-1999-22309 puts no amendment between 2020 and 2022 and none after 2024, so
    # those years are governed by the 2019 and 2024 editions respectively.
    for filing_year in (2016, 2017, 2018):
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))
    for filing_year in (2025, 2026):
        carried = select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))
        assert carried.id == "2024"


def test_modelo_194_refuses_a_mutated_superseded_selector_past_its_source_window() -> None:
    """A selector expansion cannot turn the superseded edition's source into its successor's authority.

    This guard used to be aimed at the 2024 edition reaching into 2025. That is no
    longer a boundary: BOE's consolidated amendment list for BOE-A-1999-22309 records
    no amendment to anexo X after HAC/1504/2024, so the 2024 edition legitimately
    governs 2025 and there is nothing there to refuse. The guard is re-aimed rather
    than dropped -- 2023/2024 IS still a real closed boundary, because HAC/1504/2024
    supersedes the 2023 edition, so the same over-reach is still provably refused.
    """
    modelo, catalogues = _committed_modelo("194")
    superseded_id = str(_M194_SUPERSEDED_EDITION)
    successor = _M194_SUPERSEDED_EDITION + 1
    revision = modelo.revisions[superseded_id]
    expanded = revision.model_copy(
        update={
            "valid_to": date(successor, 12, 31),
            "period_selector": revision.period_selector.model_copy(update={"year_to": successor}),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, superseded_id: expanded}})
    selected = select_revision(
        mutated_modelo, filing_year=successor, period="0A", on=date(successor, 12, 31), revision_id=superseded_id
    )
    (source_ref,) = (ref for ref in selected.source_refs if ref.startswith("aeat-dr-194-"))

    with pytest.raises(RegistryValidationError, match=f"does not apply to filing year {successor}"):
        resolve_record_design_binary(
            bundled_path(),
            catalogues.sources,
            source_ref=source_ref,
            filing_year=successor,
            design_epoch=superseded_id,
        )


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
def test_modelo_187_188_194_summary_is_the_printed_box_set(modelo_id: str, expected: tuple[str, ...]) -> None:
    """Summary boxes remain distinct from the separately authored recipient detail."""
    modelo, _ = _committed_modelo(modelo_id)
    revision = modelo.revisions[_REVISION_BY_MODELO[modelo_id]]

    summary = tuple(casilla for casilla in revision.casillas if modelo_id != "188" or casilla.section == ("resumen",))
    assert tuple(str(casilla.id) for casilla in summary) == expected
    assert all(casilla.input_kind.value == "manual" for casilla in summary), (
        "every box on these hoja-resumen forms is declarante input"
    )
