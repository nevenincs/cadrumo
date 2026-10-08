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

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import tr
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....tests.cli_envelope import require_error_document
from ....tests.cli_envelope import unwrap_cli_result as _json
from ....tests.fixtures.borrador.generate import corpus_casilla_values, corpus_years, render_borrador_pdf
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _fixture_year() -> int:
    """The latest committed borrador fixture year the published authority supports."""
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return max(year for year in corpus_years() if year in support.years)


_FIXTURE_YEAR = _fixture_year()
_FIXTURE_PDF = (
    bundled_path().resolve().parents[0] / "tests" / "fixtures" / "borrador" / f"modelo_100_{_FIXTURE_YEAR}.pdf"
)

# The borrador extraction profile declares these five target casillas at
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


def _invoke(profile: NativeCliProfileFixture, *command: str, json_output: bool = True) -> Result:
    """Use one real authenticated worker connection for a synthetic profile."""
    if profile.label is None:
        raise AssertionError("native Borrador profile was not registered")
    close_active_bucket_session()
    output_args = ("--format", "json" if json_output else "text")
    result = invoke_cached_cli(
        (*output_args, "--language", "en", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def _import(profile: NativeCliProfileFixture, pdf: Path, *, filing_year: int = _FIXTURE_YEAR) -> Result:
    return _invoke(
        profile,
        "app",
        "live",
        "borrador",
        "100",
        "import",
        "--file",
        str(pdf),
        "--filing-year",
        str(filing_year),
    )


def test_import_persists_a_snapshot_the_read_verbs_retrieve(tmp_path: Path) -> None:
    """A committed PDF crosses the worker and all snapshot readers see its encrypted capture."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-borrador-import", facts={})

        empty = _json(_invoke(profile, "app", "live", "borrador", "100", "list"))
        assert empty["rows"] == []
        empty_latest = _json(
            _invoke(profile, "app", "live", "borrador", "100", "latest", "--filing-year", str(_FIXTURE_YEAR)),
        )
        assert empty_latest["snapshot_id"] is None
        assert empty_latest["state"] is None

        imported = _import(profile, _FIXTURE_PDF)
        assert imported.exit_code == 0, imported.output
        payload = _json(imported)

        snapshot_id = payload["snapshot_id"]
        # The envelope redacts the bucket id before transport; assert the
        # redaction contract rather than the raw identifier.
        assert payload["bucket_id"] == "<bucket-id>"
        assert payload["filing_year"] == _FIXTURE_YEAR
        assert payload["extraction_profile_id"] == "modelo-100-borrador-pdf"
        assert Decimal(str(payload["extraction_coverage"])) == Decimal("1")
        assert payload["artefact_kind"] == "BORRADOR"
        assert payload["binding_count"] == len(_PROFILE_TARGET_CASILLAS)
        assert payload["blank_casillas"] == []
        digest = hashlib.sha256(_FIXTURE_PDF.read_bytes()).hexdigest()
        assert payload["source_pdf_sha256"] == digest
        assert payload["source_url"] == f"file-import:sha256:{digest}"
        assert "warnings" in payload and isinstance(payload["warnings"], list)
        assert str(_FIXTURE_PDF) not in imported.output

        # A second worker import creates the next active capture and exercises
        # the public lifecycle filters across both persisted encrypted rows.
        replacement = _import(profile, _FIXTURE_PDF)
        assert replacement.exit_code == 0, replacement.output
        replacement_payload = _json(replacement)
        replacement_id = replacement_payload["snapshot_id"]
        assert replacement_id != snapshot_id

        active_rows = _json(_invoke(profile, "app", "live", "borrador", "100", "list"))["rows"]
        assert [row["snapshot_id"] for row in active_rows] == [replacement_id]
        assert active_rows[0]["state"] == "active"

        all_rows = _json(_invoke(profile, "app", "live", "borrador", "100", "list", "--state", "all"))["rows"]
        assert {row["snapshot_id"] for row in all_rows} == {snapshot_id, replacement_id}
        assert {row["snapshot_id"]: row["state"] for row in all_rows} == {
            snapshot_id: "superseded",
            replacement_id: "active",
        }
        superseded_rows = _json(
            _invoke(profile, "app", "live", "borrador", "100", "list", "--state", "superseded"),
        )["rows"]
        assert [row["snapshot_id"] for row in superseded_rows] == [snapshot_id]
        discarded_rows = _json(
            _invoke(profile, "app", "live", "borrador", "100", "list", "--state", "discarded"),
        )["rows"]
        assert discarded_rows == []

        viewed = _invoke(profile, "app", "live", "borrador", "100", "view", str(snapshot_id)[:12])
        assert viewed.exit_code == 0, viewed.output
        view_payload = _json(viewed)
        binding_values = view_payload["binding_values"]
        assert view_payload["source_url"] == payload["source_url"]
        assert view_payload["state"] == "superseded"
        assert str(_FIXTURE_PDF) not in str(view_payload)
        assert sorted(binding_values) == [f"casilla.{casilla}" for casilla in _PROFILE_TARGET_CASILLAS]
        # Values survive as the amounts printed on the PDF, not as zeros.
        printed = corpus_casilla_values(_FIXTURE_YEAR)
        assert {casilla: Decimal(binding_values[f"casilla.{casilla}"]) for casilla in _PROFILE_TARGET_CASILLAS} == {
            casilla: printed[validated_casilla_id(casilla, surface="test.printed")]
            for casilla in _PROFILE_TARGET_CASILLAS
        }

        latest = _json(
            _invoke(profile, "app", "live", "borrador", "100", "latest", "--filing-year", str(_FIXTURE_YEAR)),
        )
        assert latest["snapshot_id"] == replacement_id
        assert latest["state"] == "active"
        text_view = _invoke(
            profile,
            "app",
            "live",
            "borrador",
            "100",
            "view",
            str(replacement_id),
            json_output=False,
        )
        assert text_view.exit_code == 0, text_view.output
        assert "binding_count\t5" in text_view.output
        assert "state\tactive" in text_view.output

        refused = _invoke(profile, "app", "live", "borrador", "100", "view", "no-such-id")
        assert refused.exit_code != 0
        unknown_state = _invoke(profile, "app", "live", "borrador", "100", "list", "--state", "old")
        assert unknown_state.exit_code != 0


def test_import_stores_a_digest_reference_and_never_the_operator_path(tmp_path: Path) -> None:
    """The stored reference contains the PDF digest, never its input path."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-borrador-path", facts={})
        imported = _import(profile, _FIXTURE_PDF)
        assert imported.exit_code == 0, imported.output
        payload = _json(imported)

        source_url = str(payload["source_url"])
        assert source_url == f"file-import:sha256:{payload['source_pdf_sha256']}"
        assert str(_FIXTURE_PDF) not in source_url
        assert str(_FIXTURE_PDF) not in imported.output

        viewed_result = _invoke(
            profile,
            "app",
            "live",
            "borrador",
            "100",
            "view",
            str(payload["snapshot_id"]),
        )
        viewed = _json(viewed_result)
        assert str(tmp_path) not in str(viewed)
        assert str(_FIXTURE_PDF) not in str(viewed)
        assert viewed["source_url"] == source_url


def test_import_refuses_a_pdf_below_the_profile_coverage_minimum(tmp_path: Path) -> None:
    """DETECTOR TEETH: a PDF missing target casillas refuses and persists nothing.

    The borrador profile declares ``min_coverage = 1`` over five target
    casillas. This renders a real borrador PDF carrying only two of them, so
    coverage is 0.4. The import must refuse; the three missing casillas are
    absent, not zero, and no partial snapshot may reach the store.
    """
    printed = corpus_casilla_values(_FIXTURE_YEAR)
    kept = tuple(validated_casilla_id(casilla, surface="test.below_minimum") for casilla in ("0505", "0545"))
    partial_pdf = tmp_path / "below-minimum.pdf"
    partial_pdf.write_bytes(
        render_borrador_pdf(year=_FIXTURE_YEAR, casilla_values={casilla: printed[casilla] for casilla in kept})
    )

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-borrador-coverage", facts={})
        refused = _import(profile, partial_pdf)
        assert refused.exit_code != 0, refused.output
        error = require_error_document(refused.output)["error"]
        assert error["code"] == "FAIL_BORRADOR_PARSE"
        assert error["context"]["reason"] == "FAIL_BORRADOR_PARSE"
        assert error["context"]["effect"] == "none"

        listed = _invoke(profile, "app", "live", "borrador", "100", "list", "--state", "all")
        assert listed.exit_code == 0, listed.output
        assert _json(listed)["rows"] == [], "a refused import must not persist a partial snapshot"


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("key", _NEW_TRANSLATION_KEYS)
def test_import_translation_keys_resolve_in_every_supported_locale(key: str, locale: str) -> None:
    """Every key the import verb introduces carries real prose in each locale."""
    rendered = tr(key, locale=locale)
    assert rendered, f"locale={locale!r} key={key!r}: empty translation"
    assert rendered != key, f"locale={locale!r} key={key!r}: tr() returned the key, catalogue entry missing"
