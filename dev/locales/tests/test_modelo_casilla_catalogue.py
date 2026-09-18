"""The delta-keyed casilla catalogue: findings, lossless collapse, and its limits.

Synthetic chains stand in for the published authority so each rule is exercised
in isolation; the resolution rule itself is the runtime one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ..modelo_casilla_catalogue import (
    CasillaOccurrence,
    CollapseVerificationError,
    ModeloCasillaCatalogue,
    _segments,
    load_casilla_values,
    resume_install,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OCC_2023 = "modelo.schema.999.revision.2023.casilla.01.label"
_OCC_2024 = "modelo.schema.999.revision.2024.casilla.01.label"
_LINEAGE = "modelo.schema.999.casilla.continuidad.base.label"


def _occurrence(revision: str, chain: tuple[str, ...], *, inherited_from: str | None = None) -> CasillaOccurrence:
    return CasillaOccurrence(
        modelo="999",
        revision=revision,
        casilla="01",
        number="1",
        continuidad_id="base",
        inherited_from=inherited_from,
        label_chain=chain,
    )


def _chains() -> tuple[CasillaOccurrence, ...]:
    return (
        _occurrence("2023", (_OCC_2023, _LINEAGE)),
        _occurrence("2024", (_OCC_2024, _OCC_2023, _LINEAGE), inherited_from="2023"),
    )


def _catalogue(values: dict[str, dict[str, str | None]]) -> ModeloCasillaCatalogue:
    return ModeloCasillaCatalogue(_chains(), {locale: dict(values.get(locale, {})) for locale in ("es", "en")})


def _applied(catalogue: ModeloCasillaCatalogue) -> dict[str, dict[str, str | None]]:
    result = catalogue.collapse_plan()
    return result.working


def test_a_restated_inherited_value_is_removed_without_changing_any_resolution() -> None:
    catalogue = _catalogue({"es": {_OCC_2023: "Base imponible", _OCC_2024: "Base imponible"}})
    before = catalogue.resolution()

    working = _applied(catalogue)

    assert _OCC_2024 not in working["es"]
    assert catalogue.resolution(working) == before


def test_text_every_edition_agrees_on_lands_once_on_the_lineage_key() -> None:
    catalogue = _catalogue(
        {
            "es": {_OCC_2023: "Base imponible", _OCC_2024: "Base imponible"},
            "en": {_OCC_2023: "Tax base", _OCC_2024: "Tax base"},
        }
    )
    before = catalogue.resolution()

    working = _applied(catalogue)

    assert working["es"] == {_LINEAGE: "Base imponible"}
    assert working["en"] == {_LINEAGE: "Tax base"}
    assert catalogue.resolution(working) == before


def test_an_edition_specific_text_is_kept_and_its_translation_is_not_lifted_past_it() -> None:
    catalogue = _catalogue(
        {
            "es": {_OCC_2023: "Base imponible", _OCC_2024: "Base imponible ajustada"},
            "en": {_OCC_2023: "Tax base", _OCC_2024: "Adjusted tax base"},
        }
    )
    before = catalogue.resolution()

    working = _applied(catalogue)

    assert working["es"][_OCC_2024] == "Base imponible ajustada"
    assert working["en"][_OCC_2024] == "Adjusted tax base"
    assert catalogue.resolution(working) == before


def test_null_leaves_orphans_and_derived_help_are_delete_targets() -> None:
    orphan = "modelo.schema.999.revision.2023.casilla.99.label"
    derived = "modelo.schema.999.revision.2023.casilla.01.help"
    catalogue = _catalogue(
        {
            "es": {
                _OCC_2023: "Base imponible",
                _OCC_2024: None,
                orphan: "Nadie la lee",
                derived: "Indique o revise «Base imponible» para completar esta autoliquidación.",
            },
        }
    )

    findings = catalogue.findings()
    plan = catalogue.collapse_plan().plan

    assert findings.null_leaves["es"] == (_OCC_2024,)
    assert findings.orphan_keys["es"] == (orphan,)
    assert findings.derived_help["es"] == (derived,)
    assert {_OCC_2024, orphan, derived} <= plan.removals["es"].keys()
    assert not findings.pure


def test_a_placeholder_is_reported_and_a_clean_surface_is_pure() -> None:
    placeholder = _catalogue({"es": {_OCC_2023: "Casilla 01: base imponible"}})
    clean = _catalogue({"es": {_LINEAGE: "Base imponible"}, "en": {_LINEAGE: "Tax base"}})

    assert placeholder.findings().placeholders["es"] == (_OCC_2023,)
    assert clean.findings().pure


@pytest.mark.parametrize(
    ("values", "family", "locale"),
    [
        (
            {"es": {_LINEAGE: "Base imponible"}, "en": {_LINEAGE: "Base Aplicado in esta return"}},
            "glossary_artifacts",
            "en",
        ),
        ({"es": {_LINEAGE: "Base imponible de las rentas obtenidas en el ejercici..."}}, "truncated_text", "es"),
        ({"es": {_LINEAGE: "Base  imponible"}}, "irregular_whitespace", "es"),
        ({"es": {_LINEAGE: "Base imponible "}}, "irregular_whitespace", "es"),
    ],
)
def test_content_defects_are_reported_and_make_the_surface_impure(
    values: dict[str, dict[str, str | None]], family: str, locale: str
) -> None:
    findings = _catalogue(values).findings()

    assert {code for code, keys in getattr(findings, family).items() if _LINEAGE in keys} == {locale}
    assert not findings.pure


def test_a_missing_translation_is_counted_not_invented() -> None:
    catalogue = _catalogue({"es": {_LINEAGE: "Base imponible"}})

    findings = catalogue.findings()
    working = _applied(catalogue)

    assert findings.untranslated["en"] == 2
    assert working["en"] == {}


def _write_catalogue(root: Path, values: dict[str, dict[str, str | None]]) -> None:
    for locale, leaves in values.items():
        tree: dict[str, object] = {}
        for dotted, value in leaves.items():
            node = tree
            *parents, leaf = dotted.split(".")
            for part in parents:
                child = node.setdefault(part, {})
                assert isinstance(child, dict)
                node = child
            node[leaf] = value
        shard = root / locale / "modelo" / "schema" / "999.yml"
        shard.parent.mkdir(parents=True, exist_ok=True)
        shard.write_text(yaml.safe_dump(tree, allow_unicode=True), encoding="utf-8")


def test_an_applied_collapse_is_installed_only_as_proven_and_is_idempotent(tmp_path: Path) -> None:
    locales = tmp_path / "locales"
    pending = tmp_path / "pending"
    _write_catalogue(
        locales,
        {
            "es": {_OCC_2023: "Base imponible", _OCC_2024: "Base imponible"},
            "en": {_OCC_2023: "Tax base", _OCC_2024: "Tax base"},
        },
    )
    catalogue = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales))
    before = catalogue.resolution()

    catalogue.apply(catalogue.collapse_plan(), locales, pending)

    installed = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales))
    assert installed.resolution() == before
    assert installed.values["es"] == {_LINEAGE: "Base imponible"}
    assert not pending.exists()
    assert not installed.collapse_plan().plan.reasons


def test_a_pending_install_blocks_a_new_plan_until_resumed(tmp_path: Path) -> None:
    locales = tmp_path / "locales"
    pending = tmp_path / "pending"
    _write_catalogue(locales, {"es": {_OCC_2023: "Base imponible"}, "en": {}})
    (pending / "locales").mkdir(parents=True)
    catalogue = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales))

    with pytest.raises(CollapseVerificationError, match="pending"):
        catalogue.apply(catalogue.collapse_plan(), locales, pending)

    resume_install(locales, pending)
    assert not pending.exists()


def test_an_interrupted_install_is_finished_from_its_staged_catalogue(tmp_path: Path) -> None:
    """A staged, verified catalogue left behind by a crash installs on resume.

    The install copies shard by shard, so a crash can leave the catalogue half
    written. Recovery replays the staged copy rather than re-planning against a
    half-installed baseline, whose resolution is nobody's intended state.
    """
    locales = tmp_path / "locales"
    pending = tmp_path / "pending"
    _write_catalogue(locales, {"es": {_OCC_2023: "Base imponible", _OCC_2024: "Base imponible"}, "en": {}})
    _write_catalogue(pending / "locales", {"es": {_LINEAGE: "Base imponible"}, "en": {}})
    before = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales)).resolution()

    resume_install(locales, pending)

    installed = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales))
    assert installed.resolution() == before
    assert installed.values["es"] == {_LINEAGE: "Base imponible"}
    assert not pending.exists()
    with pytest.raises(CollapseVerificationError, match="no install is pending"):
        resume_install(locales, pending)


def test_authored_values_install_only_when_they_serve_every_change(tmp_path: Path) -> None:
    locales = tmp_path / "locales"
    pending = tmp_path / "pending"
    _write_catalogue(locales, {"es": {_LINEAGE: "Base imponible"}, "en": {}})
    catalogue = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales))

    changed = catalogue.author({"en": {_LINEAGE: "Tax base"}}, locales, pending)

    assert changed == {"en": 2}
    assert load_casilla_values(locales)["en"] == {_LINEAGE: "Tax base"}
    with pytest.raises(CollapseVerificationError, match="no casilla chain reads"):
        catalogue.author({"en": {"modelo.schema.999.revision.1999.casilla.77.label": "Nothing"}}, locales, pending)
    assert not pending.exists()


def test_an_authored_removal_falls_back_and_an_edition_split_is_refused(tmp_path: Path) -> None:
    locales = tmp_path / "locales"
    pending = tmp_path / "pending"
    _write_catalogue(locales, {"es": {_LINEAGE: "Base imponible", _OCC_2024: "Base imponible del ejercicio"}, "en": {}})
    catalogue = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales))

    changed = catalogue.author({"es": {_OCC_2024: None, _LINEAGE: "Base imponible"}}, locales, pending)

    assert changed == {"es": 1, "en": 1}
    assert load_casilla_values(locales)["es"] == {_LINEAGE: "Base imponible"}
    agreeing = ModeloCasillaCatalogue(_chains(), load_casilla_values(locales))
    with pytest.raises(CollapseVerificationError, match="continuity evolution"):
        agreeing.author({"es": {_OCC_2024: "Base imponible del ejercicio"}}, locales, pending)
    assert not pending.exists()


@pytest.mark.parametrize(
    ("spanish", "english", "dropped"),
    [
        ("Reducción del 25 por 100", "Reduction of 25%", False),
        ("Disposición transitoria 6ª", "Sixth transitional provision", False),
        ("Compensación en los 4 ejercicios siguientes", "Offset over the next four tax years", False),
        ("Rendimientos superiores a 60.000 euros", "Income above 60,000 euros", False),
        ("Discapacidad ≥33%", "Disability >=33%", False),
        ("Actividad iniciada desde el 1-1-2024", "Activity started on 2024-01-01", False),
        ("Importe de las casillas [0430] y [0430]", "Amount from box [0430]", False),
        ("Aportaciones [interno]", "Contributions [internal]", False),
        ("Actividad iniciada desde el 1-1-2024", "Activity started on 2023-01-01", True),
        ("Deducción con un máximo de 500 euros", "Deduction", True),
        ("Traslade el importe de la casilla [0421]", "Transfer the amount", True),
    ],
)
def test_a_translation_keeps_the_content_the_spanish_states(spanish: str, english: str, dropped: bool) -> None:
    """Numbers, box references and comparisons are compared across rendering differences."""
    catalogue = _catalogue({"es": {_LINEAGE: spanish}, "en": {_LINEAGE: english}})

    assert bool(catalogue.dropped_source_content("en")) is dropped


def test_keys_under_an_undeclared_revision_are_a_rename_never_an_orphan() -> None:
    renamed = "modelo.schema.999.revision.2019.casilla.01.label"
    removed = "modelo.schema.999.revision.2023.casilla.02.label"
    catalogue = _catalogue({"es": {_OCC_2023: "Base imponible", renamed: "Base imponible", removed: "Retirada"}})

    findings = catalogue.findings()
    plan = catalogue.collapse_plan().plan

    assert findings.undeclared_revision_keys["es"] == (renamed,)
    assert findings.orphan_keys["es"] == (removed,)
    assert renamed not in plan.removals["es"]
    assert plan.removals["es"][removed] == "orphan"


def test_a_translation_that_ignored_a_spanish_change_is_stale() -> None:
    catalogue = _catalogue(
        {
            "es": {_OCC_2023: "Base imponible", _OCC_2024: "Base imponible ajustada"},
            "en": {_OCC_2023: "Tax base", _OCC_2024: "Tax base"},
        }
    )
    faithful = _catalogue(
        {
            "es": {_OCC_2023: "Base imponible", _OCC_2024: "Base Imponible."},
            "en": {_OCC_2023: "Tax base", _OCC_2024: "Tax base"},
        }
    )

    assert catalogue.stale_translations("en") == ("999/base",)
    assert faithful.stale_translations("en") == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Deducciones - Ejercicio 2024 - Pendiente",
            ("Deducciones", "Ejercicio 2024", "Pendiente"),
        ),
        ("Rendimiento neto ( [1577] - [1578] - [1579])", ("Rendimiento neto ( [1577] - [1578] - [1579])",)),
        ("Si la diferencia ([0418] - [0419]) es negativa", ("Si la diferencia ([0418] - [0419]) es negativa",)),
        ("Base imponible", ("Base imponible",)),
        ("Resultado - [0670]", ("Resultado - [0670]",)),
    ],
)
def test_a_label_splits_into_segments_only_where_it_composes_them(text: str, expected: tuple[str, ...]) -> None:
    """Subtraction of one box from another is arithmetic, not a composed segment."""
    assert _segments(text) == expected


def test_one_spanish_segment_rendered_two_ways_is_reported() -> None:
    """A segment repeated across labels keeps one rendering, as one meaning keeps one key."""
    catalogue = _catalogue(
        {
            "es": {
                _OCC_2023: "Resultado de conversión: Abono - Navarra",
                _OCC_2024: "Resultado de conversión: Abono - Estado",
                _LINEAGE: "Base imponible",
            },
            "en": {
                _OCC_2023: "Conversion result: Credit - Navarre",
                _OCC_2024: "Conversion result: Payment - State",
                _LINEAGE: "Tax base",
            },
        }
    )

    drift = catalogue.segment_drift("en")

    assert drift == {"Resultado de conversión: Abono": ("Conversion result: Credit", "Conversion result: Payment")}
    assert catalogue.findings().segment_drift["en"] == ("Resultado de conversión: Abono",)


def test_one_rendering_standing_for_two_spanish_segments_is_reported() -> None:
    """A rendering may cover two wordings of one segment, but not two segments."""
    catalogue = _catalogue(
        {
            "es": {
                _OCC_2023: "Tributación conjunta - Concierto económico - Bizkaia",
                _OCC_2024: "Tributación conjunta - Convenio económico - Navarra",
                _LINEAGE: "Base imponible",
            },
            "en": {
                _OCC_2023: "Joint taxation - Economic Agreement - Bizkaia",
                _OCC_2024: "Joint taxation - Economic Agreement - Navarre",
                _LINEAGE: "Taxable base",
            },
        }
    )

    assert catalogue.shared_segments("en") == {"Economic Agreement": ("Concierto económico", "Convenio económico")}


@pytest.mark.parametrize(
    ("spanish", "abbreviated"),
    [
        ("IVA deducible en importaciones de bienes corrientes", "IVA deducible importaciones bienes corrientes"),
        ("Resultado de la cuenta de pérdidas y ganancias", "Resultado cuenta pérdidas y ganancias"),
    ],
)
def test_an_abbreviated_official_wording_may_share_one_rendering(spanish: str, abbreviated: str) -> None:
    """AEAT shortens a label by dropping its prepositions, which states the same thing."""
    catalogue = _catalogue(
        {
            "es": {_OCC_2023: f"Casilla - {spanish}", _OCC_2024: f"Casilla - {abbreviated}"},
            "en": {_OCC_2023: "Box - Deductible VAT", _OCC_2024: "Box - Deductible VAT"},
        }
    )

    assert catalogue.shared_segments("en") == {}


@pytest.mark.parametrize("field_name", ["label", "help"])
def test_a_dropped_box_reference_is_reported_in_either_field(field_name: str) -> None:
    """Help states the same legal content a label does, so it is read the same way."""
    other = "help" if field_name == "label" else "label"
    catalogue = _catalogue(
        {
            "es": {
                f"{_LINEAGE[: -len('label')]}{field_name}": "Traslade el importe de la casilla [0421]",
                f"{_LINEAGE[: -len('label')]}{other}": "Base imponible",
            },
            "en": {
                f"{_LINEAGE[: -len('label')]}{field_name}": "Transfer the amount",
                f"{_LINEAGE[: -len('label')]}{other}": "Taxable base",
            },
        }
    )

    assert catalogue.dropped_source_content("en") == {f"{_LINEAGE[: -len('label')]}{field_name}": ("[0421]",)}
