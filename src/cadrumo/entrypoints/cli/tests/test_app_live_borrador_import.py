"""End-to-end gate for the local Modelo 100 borrador PDF import verb.

The ``app live borrador 100 import`` verb is the only producer for the
:class:`Borrador100Snapshot` store that ``list`` / ``view`` / ``latest``
read. This module drives that whole path with real objects: a real synthetic
borrador PDF, the live Click command tree, the validated registry authority,
the real extraction profile, and the encrypted snapshot repository.

Three contracts are pinned here:

- The happy path persists a snapshot the existing read verbs can retrieve.
- The registry profile's ``min_coverage`` refuses a PDF that does not carry
  enough target casillas, and persists nothing when it does.
- The operator's filesystem path never reaches the persisted snapshot; the
  stored source reference is derived from the PDF digest.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ....core.resources.bundled_data import bundled_path
from ....tests.fixtures.borrador.generate import render_borrador_pdf
from ._cli_surface_support import (
    _active_bucket_id,
    _invoke,
    _json,
    create_cli_surface_profile,
    isolated_cli_surface_backend,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FIXTURE_YEAR = 2023
_FIXTURE_PDF = bundled_path().resolve().parents[0] / "tests" / "fixtures" / "borrador" / "modelo_100_2023.pdf"

# The 2023 borrador extraction profile declares these five target casillas at
# min_coverage = 1, so every one of them must be read for the import to stand.
_PROFILE_TARGET_CASILLAS = ("0505", "0545", "0546", "0585", "0586")

_NEW_TRANSLATION_KEYS = (
    "cli.app.live.borrador.import_coverage_absent",
    "cli.app.live.borrador.import_ejercicio_mismatch",
    "cli.app.live.borrador.import_file_help",
    "cli.app.live.borrador.import_help",
    "cli.app.live.borrador.import_period_help",
    "cli.app.live.borrador.import_period_invalid",
    "cli.app.live.borrador.import_profile_unresolved",
)


def _import(pdf: Path, *, filing_year: int = _FIXTURE_YEAR):
    return _invoke(
        ["--format", "json", "app", "live", "borrador", "100", "import", "--file", str(pdf), "--filing-year", str(filing_year)]
    )


def test_import_persists_a_snapshot_the_read_verbs_retrieve(tmp_path: Path) -> None:
    """A committed borrador PDF imports, persists, and is readable through list and view."""
    with isolated_cli_surface_backend(tmp_path):
        create_cli_surface_profile()
        bucket_id = _active_bucket_id()

        imported = _import(_FIXTURE_PDF)
        assert imported.exit_code == 0, imported.output
        payload = _json(imported)

        snapshot_id = payload["snapshot_id"]
        assert payload["bucket_id"] == bucket_id
        assert payload["filing_year"] == _FIXTURE_YEAR
        assert payload["extraction_profile_id"] == "modelo-100-2023-borrador-pdf"
        assert Decimal(str(payload["extraction_coverage"])) == Decimal("1")
        assert payload["artefact_kind"] == "BORRADOR"
        assert payload["binding_count"] == len(_PROFILE_TARGET_CASILLAS)
        assert payload["blank_casillas"] == []

        listed = _invoke(["--format", "json", "app", "live", "borrador", "100", "list"])
        assert listed.exit_code == 0, listed.output
        rows = _json(listed)["rows"]
        assert [row["snapshot_id"] for row in rows] == [snapshot_id]

        viewed = _invoke(["--format", "json", "app", "live", "borrador", "100", "view", str(snapshot_id)])
        assert viewed.exit_code == 0, viewed.output
        binding_values = _json(viewed)["binding_values"]
        assert sorted(binding_values) == [f"casilla.{casilla}" for casilla in _PROFILE_TARGET_CASILLAS]
        # Values survive as the amounts printed on the PDF, not as zeros.
        assert Decimal(binding_values["casilla.0505"]) == Decimal("30000.00")
        assert Decimal(binding_values["casilla.0545"]) == Decimal("3582.75")


def test_import_stores_a_digest_reference_and_never_the_operator_path(tmp_path: Path) -> None:
    """The persisted source reference is digest-derived; the local path is not retained."""
    with isolated_cli_surface_backend(tmp_path):
        create_cli_surface_profile()
        staged = tmp_path / "operator-download" / "mi-borrador.pdf"
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(_FIXTURE_PDF.read_bytes())

        imported = _import(staged)
        assert imported.exit_code == 0, imported.output
        payload = _json(imported)

        source_url = str(payload["source_url"])
        assert source_url == f"file-import:sha256:{payload['source_pdf_sha256']}"
        assert "operator-download" not in source_url
        assert "mi-borrador" not in source_url
        assert str(tmp_path) not in source_url

        viewed = _json(_invoke(["--format", "json", "app", "live", "borrador", "100", "view", str(payload["snapshot_id"])]))
        assert str(tmp_path) not in str(viewed)
        assert viewed["source_url"] == source_url


def test_import_refuses_a_pdf_below_the_profile_coverage_minimum(tmp_path: Path) -> None:
    """DETECTOR TEETH: a PDF missing target casillas refuses and persists nothing.

    The 2023 borrador profile declares ``min_coverage = 1`` over five target
    casillas. This renders a real borrador PDF carrying only two of them, so
    coverage is 0.4. The import must refuse; the three missing casillas are
    absent, not zero, and no partial snapshot may reach the store.
    """
    partial_pdf = tmp_path / "below-minimum.pdf"
    partial_pdf.write_bytes(
        render_borrador_pdf(
            year=_FIXTURE_YEAR,
            casilla_values={
                validated_casilla_id("0505", surface="test.below_minimum"): Decimal("30000.00"),
                validated_casilla_id("0545", surface="test.below_minimum"): Decimal("3582.75"),
            },
        )
    )

    with isolated_cli_surface_backend(tmp_path):
        create_cli_surface_profile()

        refused = _import(partial_pdf)
        assert refused.exit_code != 0, refused.output

        listed = _invoke(["--format", "json", "app", "live", "borrador", "100", "list"])
        assert listed.exit_code == 0, listed.output
        assert _json(listed)["rows"] == [], "a refused import must not persist a partial snapshot"


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("key", _NEW_TRANSLATION_KEYS)
def test_import_translation_keys_resolve_in_every_supported_locale(key: str, locale: str) -> None:
    """Every key the import verb introduces carries real prose in each locale."""
    rendered = tr(key, locale=locale)
    assert rendered, f"locale={locale!r} key={key!r}: empty translation"
    assert rendered != key, f"locale={locale!r} key={key!r}: tr() returned the key, catalogue entry missing"
