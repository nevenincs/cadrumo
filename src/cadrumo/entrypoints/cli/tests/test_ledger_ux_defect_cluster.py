"""Real-behavior regressions for ledger category and taxonomy UX."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....domain.categories.spending_category import SpendingCategory
from ._ledger_ux_support import _imported_transaction_id, _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]


def test_categories_command_lists_the_canonical_spending_taxonomy(
    tmp_path: Path,
) -> None:
    """`ledger categories` enumerates every SpendingCategory id."""
    result = _invoke(["--format", "json", "app", "ledger", "categories"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    listed = set(payload["category_ids"])
    expected = {category.value for category in SpendingCategory}
    assert listed == expected
    grouped = {category_id for family in payload["families"] for category_id in family["category_ids"]}
    assert grouped == expected
    assert "actividad_economica" in payload["irpf_category_ids"]
    assert "arrendamiento_local" in payload["irpf_category_ids"]
    activity_category = next(item for item in payload["irpf_categories"] if item["id"] == "actividad_economica")
    assert activity_category["net_paid_invoice"] is True
    assert activity_category["directions"] == ["INCOMING", "OUTGOING"]
    assert activity_category["related_category_ids"] == [
        "asesoria_contable",
        "asesoria_fiscal",
        "asesoria_juridica",
    ]
    rent_category = next(item for item in payload["irpf_categories"] if item["id"] == "arrendamiento_local")
    assert rent_category["net_paid_invoice"] is True
    assert rent_category["related_category_ids"] == ["arrendamiento_local"]


def test_ledger_status_text_names_active_profile_without_storage_id(tmp_path: Path) -> None:
    """Status presents the operator label; the storage UUID is not useful text UX."""
    result = _invoke(["--language", "en", "app", "ledger", "status"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0] == "Profile\ttester"
    assert "9e0f3a2b-5d1c-4a77-9b2d-27ed6d6c7f10" not in result.output
    assert "<profile-id>" not in result.output


def test_classify_rejects_an_invented_category_id(tmp_path: Path) -> None:
    """An id outside the closed taxonomy is refused, not silently kept."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--category-id",
            "ventas_actividad",
        ],
    )
    assert result.exit_code != 0
    assert "ventas_actividad" in result.output
    assert "ledger categories" in result.output


def test_classify_accepts_a_canonical_category_id(tmp_path: Path) -> None:
    """A real SpendingCategory id still classifies successfully."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--category-id",
            SpendingCategory.MATERIAL_OFICINA.value,
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["category_id"] == SpendingCategory.MATERIAL_OFICINA.value


def test_classify_reaffirm_json_output_is_a_single_envelope(tmp_path: Path) -> None:
    """`--reaffirm` must not print a plain-text notice before JSON output."""
    txn = _imported_transaction_id(tmp_path)
    first = _invoke(
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
        ],
    )
    assert first.exit_code == 0, first.output

    reaffirmed = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--reaffirm",
        ],
    )

    assert reaffirmed.exit_code == 0, reaffirmed.output
    assert reaffirmed.output.lstrip().startswith("{")
    payload = json.loads(reaffirmed.output)
    assert payload["command"] == "ledger.classify"
    assert payload["result"]["transaction"]["business_classification"] == "BUSINESS"
    assert payload["result"]["transaction"]["taxable_base"] == "100"


def test_categories_output_names_the_category_id_column(tmp_path: Path) -> None:
    """The catalogue makes exact category flag values unmistakable."""
    result = _invoke(["app", "ledger", "categories"])
    assert result.exit_code == 0, result.output
    output = result.output
    assert "category-id" in output
    assert "--category-id" in output
    assert SpendingCategory.MATERIAL_OFICINA.value in output
    assert "irpf-category" in output
    assert "--irpf-category arrendamiento_local" in output
    assert "actividad_economica" in output


def test_classify_help_points_irpf_category_to_categories_catalogue(
    tmp_path: Path,
) -> None:
    """`--help` names accepted ids and the royalty activity/capital distinction."""
    result = _invoke(["app", "ledger", "classify", "--help"], env={"COLUMNS": "160"})
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "aeat app ledger categories" in flat
    assert "actividad_economica" in flat
    assert "arrendamiento_local" in flat
    assert "Royalties" in flat
    normalized = flat.casefold()
    assert "lirpf" in normalized and "27" in normalized
    assert "25.4" in normalized
    assert "capital mobiliario" in flat
    assert any(
        author_phrase in normalized
        for author_phrase in ("not the author", "no es el autor", "no es l'autor", "nem a szerzo")
    )


def test_invalid_category_error_shows_a_concrete_valid_example(
    tmp_path: Path,
) -> None:
    """A rejected `--category-id` names one concrete valid id."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--category-id",
            "office:material_oficina",
        ],
    )
    assert result.exit_code != 0
    valid_ids = {category.value for category in SpendingCategory}
    assert any(category_id in result.output for category_id in valid_ids)
    assert "ledger categories" in result.output
