"""Parametrized sidecar ground-truth roundtrip test for the justificante parser.

Each ``{modelo}/{ejercicio}-{period}.pdf`` in the committed corpus has a
matching ``{ejercicio}-{period}.json`` sanitiser manifest.  The manifest
records the synthetic values the sanitiser injected into the PDF, giving us
deterministic ground truth we did NOT derive by running the parser on its own
output.

The key ground-truth fields available from every manifest:

* ``tax_id``          — always ``Y0000001S`` (the standard sanitised NIE).
* ``csv``             — ``SANITIZED{modelo}{ejercicio}`` (the synthetic CSV
                        injected by the sanitiser, e.g. ``SANITIZED1302024``).
* ``modelo``          — encoded in the ``SANITIZED…`` token and the directory.
* ``ejercicio``       — encoded in the ``SANITIZED…`` token and the filename.
* ``period``          — derived from the filename with the same quirk-table used
                        by the existing ``TestRealCorpusParses``: M190, M390,
                        and M100/2023 print only the ejercicio in the PDF body,
                        so the parser's observed period equals the year string.

Any sidecar field that is null / absent is skipped — the test never fabricates
an expectation.

Regressions this test catches:
* Parser returning wrong modelo string (e.g. "130" → "100").
* Parser losing the CSV entirely or matching the wrong token.
* Parser swapping ejercicio with periodo (year/period confusion).
* Parser corrupting tax_id (NIF regex mismatch across layouts).
* Parser returning wrong ejercicio year (off-by-one or stale regex capture).
* Parser breaking the CSV shape constraint (not 8-24 uppercase alphanum).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pytest

from .....core import Period
from .....domain.justificante import Justificante
from .....tests import FIXTURES_DIR as _FIXTURES_ROOT
from .....tests._justificante_parse_cache import parse_committed_justificante_fixture
from .....tests.aeat_literal_fixtures import aeat_host

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_JUSTIFICANTES_DIR = _FIXTURES_ROOT / "justificantes"
_SEDE_HOST = aeat_host("sede")

# Sanitiser always injects "Y0000001S" as the synthetic NIE across the entire
# corpus.  This constant makes the assertion self-documenting.
_SYNTHETIC_TAX_ID = "Y0000001S"

# Pattern used to verify that the CSV token in the manifest is what we expect
# the parser to extract.  The sanitiser always uses SANITIZED{modelo}{year}.
_CSV_SYNTHETIC_RE = re.compile(r"^SANITIZED(\d{3})(\d{4})$")

# Fixtures where the PDF body prints only the ejercicio year as the period
# (no explicit "Período N" label) — the parser's observed period therefore
# equals the year string, not the filename period token.
_PERIOD_EQUALS_EJERCICIO: frozenset[tuple[str, str]] = frozenset(
    {
        # M190 Resumen anual 2024: positional layout prints only year.
        ("190", "2024-0A"),
        # M390 2021-0A: real multi-page PDF in English layout that omits
        # a labelled Período token; parser promotes ejercicio as period.
        # M390 2022-0A and 2023-0A are synthetic fixtures that print
        # "Periodo: 0A" explicitly — their period IS "0A", not the year.
        ("390", "2021-0A"),
        # M100 2023: newer layout omits labelled Período token.
        ("100", "2023-0A"),
        # M036: censal declaracion with event codes (alta/modificacion/baja),
        # no calendar Periodo label; parser falls back to ejercicio year.
        ("036", "2025-0A"),
        ("036", "2025-alta"),
        # M184, M232, M347, M720, M840: annual informativas with no Periodo
        # label; parser fallback returns the ejercicio year.
        ("184", "2024-0A"),
        ("232", "2016-0A"),
        ("232", "2018-0A"),
        ("347", "2024-0A"),
        ("720", "2024-0A"),
        ("840", "2024-0A"),
    },
)


@dataclass(frozen=True)
class _SidecarGroundTruth:
    """Fields we can reliably derive from the sanitiser manifest."""

    # Mandatory — always present in the sanitiser's replacements_applied list.
    expected_tax_id: str
    expected_csv: str
    expected_modelo: str
    expected_ejercicio: str
    expected_period: str


def _derive_expected_period(modelo: str, stem: str, ejercicio: str, filename_period: str) -> str:
    """Return the period token the parser is expected to emit for this fixture.

    Most fixtures emit the period verbatim from the PDF.  A small set of
    annual / resumen-anual layouts omit the labelled period and the parser
    promotes the ejercicio year instead.
    """
    if (modelo, stem) in _PERIOD_EQUALS_EJERCICIO:
        return ejercicio
    return filename_period


def _load_ground_truth(sidecar_path: Path, modelo: str, stem: str) -> _SidecarGroundTruth | None:
    """Parse the sanitiser manifest into a :class:`_SidecarGroundTruth`.

    Returns ``None`` when the sidecar does not contain the minimum set of
    synthetic replacement tokens needed to form a meaningful assertion (e.g. a
    partially sanitised or English-UI specimen that was excluded from the
    corpus).
    """
    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    replacements = data.get("replacements_applied", [])
    synthetics = {r["synthetic"] for r in replacements}

    # Locate the SANITIZED<modelo><year> token — it is the parser's expected CSV.
    csv_token: str | None = next(
        (s for s in synthetics if _CSV_SYNTHETIC_RE.match(s)),
        None,
    )
    if csv_token is None:
        return None

    m = _CSV_SYNTHETIC_RE.match(csv_token)
    assert m is not None  # narrowing — we just matched above
    sidecar_modelo = m.group(1)
    sidecar_ejercicio = m.group(2)

    # Verify the SANITIZED token encodes the same modelo and year as the path.
    ejercicio_from_stem, period_from_stem = stem.split("-", 1)
    if sidecar_modelo != modelo or sidecar_ejercicio != ejercicio_from_stem:
        # Inconsistent manifest — skip rather than assert garbage.
        return None  # pragma: no cover

    expected_period = _derive_expected_period(modelo, stem, sidecar_ejercicio, period_from_stem)

    return _SidecarGroundTruth(
        expected_tax_id=_SYNTHETIC_TAX_ID,
        expected_csv=csv_token,
        expected_modelo=modelo,
        expected_ejercicio=sidecar_ejercicio,
        expected_period=expected_period,
    )


def _collect_sidecar_pairs() -> list[tuple[Path, _SidecarGroundTruth]]:
    """Walk the justificantes fixture tree and collect every valid PDF+sidecar pair."""
    pairs: list[tuple[Path, _SidecarGroundTruth]] = []
    for modelo_dir in sorted(p for p in _JUSTIFICANTES_DIR.iterdir() if p.is_dir()):
        modelo = modelo_dir.name
        for pdf in sorted(modelo_dir.glob("*.pdf")):
            sidecar = pdf.with_suffix(".json")
            if not sidecar.is_file():
                continue  # no sidecar — skip
            ground_truth = _load_ground_truth(sidecar, modelo, pdf.stem)
            if ground_truth is None:
                continue  # partial/English manifest — skip
            pairs.append((pdf, ground_truth))
    return pairs


_CORPUS_PAIRS = _collect_sidecar_pairs()


class TestCorpusSidecarRoundtrip:
    """Parser output matches sanitiser-manifest ground truth for every fixture.

    Each case is independent: the parametrize decorator creates one test item
    per (modelo, period) pair discovered at collection time.  Adding a new
    fixture PDF+sidecar to ``tests/fixtures/justificantes/{modelo}/`` is
    sufficient to extend coverage — no test code changes needed.
    """

    @pytest.mark.parametrize(
        "pdf_path,ground_truth",
        _CORPUS_PAIRS,
        ids=lambda v: f"{v[0].parent.name}/{v[0].stem}" if isinstance(v, tuple) else "",
    )
    def test_sidecar_fields_match_parsed_output(
        self,
        pdf_path: Path,
        ground_truth: _SidecarGroundTruth,
    ) -> None:
        record: Justificante = parse_committed_justificante_fixture(pdf_path)

        # --- mandatory fields derivable from every sidecar ---

        assert record.modelo == ground_truth.expected_modelo, (
            f"modelo mismatch for {pdf_path.parent.name}/{pdf_path.stem}: "
            f"got {record.modelo!r}, expected {ground_truth.expected_modelo!r}"
        )
        assert record.ejercicio == ground_truth.expected_ejercicio, (
            f"ejercicio mismatch for {pdf_path.parent.name}/{pdf_path.stem}: "
            f"got {record.ejercicio!r}, expected {ground_truth.expected_ejercicio!r}"
        )
        assert record.period == _expected_period(
            ground_truth.expected_ejercicio,
            ground_truth.expected_period,
        ), (
            f"period mismatch for {pdf_path.parent.name}/{pdf_path.stem}: "
            f"got {record.period!r}, expected {ground_truth.expected_period!r}"
        )
        assert record.tax_id == ground_truth.expected_tax_id, (
            f"tax_id mismatch for {pdf_path.parent.name}/{pdf_path.stem}: "
            f"got {record.tax_id!r}, expected {ground_truth.expected_tax_id!r}"
        )

        # The CSV injected by the sanitiser is the token the parser must extract.
        # A regression that returns any other token (e.g. a noisy match) will
        # fail here because only SANITIZED{modelo}{year} appears in the PDF.
        assert record.csv == ground_truth.expected_csv, (
            f"csv mismatch for {pdf_path.parent.name}/{pdf_path.stem}: "
            f"got {record.csv!r}, expected {ground_truth.expected_csv!r}"
        )

        # CSV shape invariant — must survive even if the SANITIZED token pattern
        # happened to match a noise string that is not alphanumeric-uppercase.
        assert record.csv.isalnum() and record.csv.isupper(), (
            f"csv shape violation for {pdf_path.parent.name}/{pdf_path.stem}: {record.csv!r}"
        )
        assert 8 <= len(record.csv) <= 24, (
            f"csv length violation for {pdf_path.parent.name}/{pdf_path.stem}: {record.csv!r}"
        )

        # presented_at must always be a real datetime across every layout.
        assert record.presented_at is not None, f"presented_at missing for {pdf_path.parent.name}/{pdf_path.stem}"

        # source_pdf_sha256 populated and correct length.
        assert record.source_pdf_sha256, f"source_pdf_sha256 missing for {pdf_path.parent.name}/{pdf_path.stem}"
        assert len(record.source_pdf_sha256) == 64, (
            f"source_pdf_sha256 wrong length for {pdf_path.parent.name}/{pdf_path.stem}"
        )

        # verification_url must point at the AEAT cotejo surface.
        assert urlparse(str(record.verification_url)).hostname == _SEDE_HOST, (
            f"verification_url wrong for {pdf_path.parent.name}/{pdf_path.stem}: {record.verification_url}"
        )

    def test_corpus_pair_count(self) -> None:
        """Guard that the fixture discovery covers a known minimum corpus size.

        If the collection shrinks unexpectedly (e.g. a fixture directory is
        accidentally deleted) this test fails loudly rather than silently
        reducing coverage.  Update the minimum when new fixtures are added.
        """
        assert len(_CORPUS_PAIRS) >= 55, (
            f"Expected at least 55 corpus pairs; found {len(_CORPUS_PAIRS)}. "
            "Was a fixture directory deleted or a sidecar removed?"
        )


def _expected_period(ejercicio: str, observed_period: str) -> Period:
    code = "0A" if observed_period == ejercicio else observed_period
    return Period.from_year_and_code(int(ejercicio), code)
