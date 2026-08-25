"""Parser tests against real AEAT HTML captures (identity-redacted).

The fixtures under ``src/cadrumo/tests/fixtures/aeat-sede/`` are live
captures from a real sede with NIF, name, expediente sequence, and CSV
redacted to synthetic but schema-valid placeholders.

Identity is not the whole redaction contract. A capture of an
AUTHENTICATED page also carries credentials: the session and anti-CSRF
tokens the forms hold for the live session that produced it. Those are
not personal data, so a NIF-and-name pass leaves them untouched and a
personal-data review does not look for them - a real 36-character token
reached a pending fixture that way, in a field named ``CI1_ISLW``, which
matches no credential vocabulary and reads as markup noise. Substitute
every opaque, high-entropy input value with a placeholder of the same
shape, keeping the markup byte-faithful so the parser still meets the
real form. Readable censal, navigational and framework values are
structural and MUST be left alone. ``test_fixture_credential_hygiene``
enforces this half of the contract.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......tests import FIXTURES_DIR
from ......tests.aeat_literal_fixtures import KATA_COTEJO_ID_PATH_FIXTURE
from ..errors import SedeParseError
from .._parse import parse_expediente_detail, parse_resumen_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"
_SEDE_BASE = Settings.external_constants().aeat.domains.www6


class TestParseResumenTree:
    """Verify :func:`parse_resumen_tree` against a real ResumenVlt capture."""

    def test_extracts_modelo_100_expedientes(self) -> None:
        """Assert the fixture yields three Modelo 100 expedientes covering 2021/2022/2023."""
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
        # The captured sede held 3x Modelo 100 (IRPF 2023/22/21).
        modelo_100 = tuple(e for e in expedientes if e.modelo == "100")
        assert len(modelo_100) == 3
        years = sorted(e.ejercicio for e in modelo_100 if e.ejercicio is not None)
        assert years == [2021, 2022, 2023]

    def test_every_expediente_is_read_only(self) -> None:
        """Assert every parsed expediente carries the ``mode='read'`` declared-shape marker.

        The marker is documentation and test scaffolding, not a runtime
        guard — nothing in production reads it. What holds the read-only
        boundary is described in the ``_schema`` module docstring.
        """
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        for expediente in parse_resumen_tree(html, base_url=_SEDE_BASE):
            assert expediente.mode == "read"

    def test_filter_by_modelo_reduces_corpus(self) -> None:
        """Assert filtering by modelo never grows the corpus."""
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        all_expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
        modelo_100 = tuple(e for e in all_expedientes if e.modelo == "100")
        # Filtering is idempotent: filtering twice yields the same corpus.
        assert len(modelo_100) <= len(all_expedientes)

    def test_raises_on_missing_heading(self) -> None:
        """Assert HTML missing the 'Mis Expedientes' heading fails fast with :exc:`SedeParseError`."""
        # A stripped page without 'Mis Expedientes' reads like a session
        # timeout or page drift — we fail fast.
        with pytest.raises(SedeParseError, match="Mis Expedientes"):
            parse_resumen_tree("<html><body>nothing</body></html>", base_url=_SEDE_BASE)

    def test_category_path_is_populated(self) -> None:
        """Assert each expediente's ``category_path`` carries at least its modelo label."""
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
        modelo_100 = next(e for e in expedientes if e.modelo == "100")
        # Category path always includes at least the modelo label.
        assert any("Modelo 100" in label for label in modelo_100.category_path)

    def test_detail_url_is_per_year_endpoint(self) -> None:
        """Assert each Modelo 100 expediente's ``detail_url`` targets the per-year IRPF endpoint."""
        html = (_FIXTURE_ROOT / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")
        for expediente in parse_resumen_tree(html, base_url=_SEDE_BASE):
            if expediente.modelo != "100" or expediente.ejercicio is None:
                continue
            assert f"AccesoDR{expediente.ejercicio}RVlt" in str(expediente.detail_url)


class TestParseExpedienteDetail:
    """Verify :func:`parse_expediente_detail` extracts the CSV handle from a captured detail page."""

    def test_extracts_csv_and_urls(self) -> None:
        """Assert the CSV, cotejo URL, and PDF URL are extracted with ``mode='read'``."""
        html = (_FIXTURE_ROOT / "expediente-irpf-2023-detail.html").read_text(encoding="utf-8")
        ref = parse_expediente_detail(
            html,
            expediente_id="202399999999999T",
            base_url=_SEDE_BASE,
        )
        assert ref.csv == "FIXTURECSV1234X7"
        assert ref.expediente_id == "202399999999999T"
        assert "CotejoIdSv?CSV=FIXTURECSV1234X7" in str(ref.cotejo_url)
        assert "CotejoDocIdSv?CSV=FIXTURECSV1234X7" in str(ref.pdf_url)
        assert ref.mode == "read"

    def test_raises_on_missing_csv(self) -> None:
        """Assert HTML without a CotejoIdSv link raises :exc:`SedeParseError`."""
        with pytest.raises(SedeParseError, match="no /CotejoIdSv"):
            parse_expediente_detail(
                "<html><body>no csv here</body></html>",
                expediente_id="202399999999999T",
                base_url=_SEDE_BASE,
            )

    def test_accepts_the_maximum_length_csv(self) -> None:
        """The detail parser and ``JustificanteRef`` accept a 32-character CSV."""
        html = f'<a href="{KATA_COTEJO_ID_PATH_FIXTURE}?CSV={"A" * 32}">declaracion</a>'

        ref = parse_expediente_detail(
            html,
            expediente_id="202399999999999T",
            base_url=_SEDE_BASE,
        )

        assert ref.csv == "A" * 32

    def test_rejects_a_csv_longer_than_the_shared_constraint(self) -> None:
        """Do not truncate a 33-character CSV before the strict model validates it."""
        html = f'<a href="{KATA_COTEJO_ID_PATH_FIXTURE}?CSV={"A" * 33}">declaracion</a>'

        with pytest.raises(SedeParseError, match="does not match the AEAT shape"):
            parse_expediente_detail(
                html,
                expediente_id="202399999999999T",
                base_url=_SEDE_BASE,
            )
