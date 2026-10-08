"""Required review copy resolves in one locale or refuses missing wording."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from .....core.external_constants import OutputLanguage
from .....core.i18n.render import MissingTranslationError, override_locales_root
from ..records import TabName
from ..review_labels import _REVIEW_LABEL_KEYS, ReviewWorkbookLabels
from ..review_workbook import build_review_workbook
from .review_fixture import review_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("locale", "text"),
    (
        (OutputLanguage.EN, "Your review notes"),
        (OutputLanguage.ES, "Tus notas de revisión"),
        (OutputLanguage.CA, "Les teves notes de revisió"),
        (OutputLanguage.HU, "Áttekintési jegyzeteid"),
    ),
)
def test_label_uses_exact_selected_catalogue(locale: OutputLanguage, text: str, tmp_path: Path) -> None:
    (tmp_path / f"{locale.value}.yml").write_text(
        "application:\n  storage:\n    calc_sheets:\n      review:\n        labels:\n          review: '"
        + text
        + "'\n",
        encoding="utf-8",
    )
    with override_locales_root(tmp_path):
        assert ReviewWorkbookLabels(locale)("review") == text


@pytest.mark.parametrize("raw_value", ("null", "''", "'application.storage.calc_sheets.review.labels.review'"))
def test_missing_blank_and_key_echo_copy_refuse_instead_of_humanising(raw_value: str, tmp_path: Path) -> None:
    (tmp_path / "es.yml").write_text(
        "application:\n  storage:\n    calc_sheets:\n      review:\n        labels:\n          review: "
        + raw_value
        + "\n",
        encoding="utf-8",
    )
    with override_locales_root(tmp_path), pytest.raises(MissingTranslationError):
        ReviewWorkbookLabels(OutputLanguage.ES)("review")


def test_absent_key_refuses_even_with_another_locale_authored(tmp_path: Path) -> None:
    (tmp_path / "es.yml").write_text("application: {}\n", encoding="utf-8")
    (tmp_path / "en.yml").write_text(
        "application:\n  storage:\n    calc_sheets:\n      review:\n        labels:\n          review: 'Your review notes'\n",
        encoding="utf-8",
    )
    with override_locales_root(tmp_path), pytest.raises(MissingTranslationError):
        ReviewWorkbookLabels(OutputLanguage.ES)("review")


def test_unknown_semantic_label_is_not_a_dynamic_catalogue_route() -> None:
    with pytest.raises(KeyError):
        ReviewWorkbookLabels(OutputLanguage.EN)("arbitrary_key")


@pytest.mark.parametrize("locale", tuple(OutputLanguage))
def test_all_required_review_labels_are_authored_in_packaged_catalogue(locale: OutputLanguage) -> None:
    """The real installed catalogue must resolve every consumer-declared label."""
    labels = ReviewWorkbookLabels(locale)
    for semantic_key, catalogue_key in _REVIEW_LABEL_KEYS.items():
        rendered = labels(semantic_key)
        assert rendered.strip()
        assert rendered != catalogue_key
        assert not rendered.startswith("application.storage.calc_sheets.review.")


@pytest.mark.parametrize(
    ("locale", "overview", "review", "provisional", "missing"),
    (
        (OutputLanguage.EN, "Review overview", "Your review notes", "Provisional", "Missing historical payload"),
        (
            OutputLanguage.ES,
            "Resumen de la revisión",
            "Tus notas de revisión",
            "Provisional",
            "Archivo histórico ausente",
        ),
        (
            OutputLanguage.CA,
            "Resum de la revisió",
            "Les teves notes de revisió",
            "Provisional",
            "Fitxer històric absent",
        ),
        (
            OutputLanguage.HU,
            "Az áttekintés összefoglalója",
            "Áttekintési jegyzeteid",
            "Előzetes",
            "Hiányzó korábbi fájl",
        ),
    ),
)
@pytest.mark.parametrize("ledger_only", (False, True))
def test_packaged_catalogues_render_real_calculation_and_ledger_plans(
    locale: OutputLanguage, overview: str, review: str, provisional: str, missing: str, ledger_only: bool
) -> None:
    """Resolve real product copy and preserve the independently captured baseline."""
    labels = ReviewWorkbookLabels(locale)
    plan = build_review_workbook(
        review_snapshot(ledger_only=ledger_only),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=labels,
    )
    cells = {cell.address.qualified(): cell.value for cell in plan.value_cells}
    if ledger_only:
        assert plan.metadata.title == labels("ledger") + " · aaaaaaaaaaaa"
    else:
        assert plan.metadata.title == "Modelo 303 · 2026 · 1T · " + labels("not_captured") + " · cccccccccccc"
    assert cells["'Guía'!A1"] == overview
    assert cells["'Guía'!B6"] == provisional
    assert cells["'Entradas'!A1"] == review
    assert cells["'Entradas'!B5"] is None
    assert cells["'Evidencia'!C5"] == "missing"
    assert cells["'Evidencia'!H5"] == missing
    assert cells["'Detalle'!K5"] == '=IMPORTXML("https://example.invalid", "x")'
    assert cells["'Detalle'!Y5"] == "law"
    assert cells["'Detalle'!Z5"] == "official-source"
    assert labels("not_captured") == cells["'Detalle'!G5"]
    assert not plan.formula_cells
    assert not plan.protected_ranges
    if ledger_only:
        assert TabName.CALCULOS not in plan.tabs
        assert cells["'Detalle'!AA5"] == labels("unattributed")
    else:
        assert cells["'Cálculos'!D5"] == Decimal("25.20")
        assert cells["'Cálculos'!E5"] == "25.20"
        assert cells["'Cálculos'!I5"] == "'Procedencia'!A5"
        assert cells["'Detalle'!AA5"] == "'Cálculos'!A5"
