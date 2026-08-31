"""Provenance gate for the AEAT-published manual annex specimens.

The sibling ``justificantes/`` corpus declares ``real_corpus`` (a sanitised real
taxpayer filing) or ``synthetic_generated`` (output of this project's fixture
generator), cross-checked against the physical ``/Producer`` DocInfo by
``test_verification_source_fixture_metadata.py``. The annex specimens are
neither, so they live here under their own provenance value rather than being
mislabelled into that tree.

An AEAT manual annex is the official form filled with AEAT's own worked-example
figures, authored and rendered by AEAT's *publication* toolchain (Adobe
InDesign, PDF/X-4). It is not a filing: it carries no NIF, no CSV and no
presentador, so it physically cannot be parsed as a justificante. Declaring it
``real_corpus`` would report that the modelo has real specimens and show the
audit gap closed while the actual gap - no sede-rendered justificante - stayed
open; declaring it ``synthetic_generated`` would be factually false.

The cross-check here is conjunctive, and deliberately stronger than the binary
producer test the justificante gate applies: a specimen must NOT carry the
fixture generator's signature AND must NOT yield an extractable NIF. Both halves
are physical properties of the bytes, so the declaration stays falsifiable rather
than becoming an honour-system third option.

See Also:
    :mod:`~domain.calculations.registry.tests.test_verification_source_fixture_metadata`
        The sibling gate over the ``justificantes/`` corpus.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pdfplumber
import pytest

from .....adapters.inbound.declaracion._parser import _extract_tax_id
from .....adapters.inbound.declaracion.errors import DeclaracionParseError
from .....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_ANNEX_ROOT = Path(__file__).resolve().parents[1]
_SYNTHETIC_PRODUCER_SIGNATURE = "aeat-test-fixture-generator"
_EXPECTED_PROVENANCE = "aeat_published_facsimile"
_EXPECTED_ROLE = "casilla_value_oracle"

_REQUIRED_SIDECAR_FIELDS = (
    "provenance",
    "role",
    "modelo",
    "filing_year",
    "raw_evidence_locator",
    "source_pdf_url",
    "output_sha256",
    "notes",
)


def _annex_pdfs() -> list[Path]:
    """Every committed specimen, excluding this package's own test directory.

    The exclusion is computed against the path RELATIVE to the annex root: the
    absolute path already contains a ``tests`` segment (``src/cadrumo/tests/``),
    so filtering on the absolute parts would discard the whole corpus.
    """
    return sorted(
        p
        for p in scan_directory(_ANNEX_ROOT, pattern="*.pdf", recursive=True)
        if "tests" not in p.relative_to(_ANNEX_ROOT).parts
    )


_PDFS = _annex_pdfs()
_IDS = [f"{p.parent.name}-{p.stem}" for p in _PDFS]


def test_annex_corpus_is_not_empty() -> None:
    """A dormant gate is worse than no gate: fail if the corpus vanished."""
    assert _PDFS, f"no annex specimens found under {_ANNEX_ROOT}; the provenance gate would be dormant"


@pytest.mark.parametrize("pdf_path", _PDFS, ids=_IDS)
def test_sidecar_declares_annex_provenance_and_role(pdf_path: Path) -> None:
    """Every specimen self-declares its provenance, role and evidence locator."""
    sidecar = pdf_path.with_suffix(".json")
    assert sidecar.is_file(), f"{pdf_path.name}: missing sidecar {sidecar.name}"

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    missing = [field for field in _REQUIRED_SIDECAR_FIELDS if not payload.get(field)]
    assert not missing, f"{pdf_path.name}: sidecar omits required field(s) {missing}"

    assert payload["provenance"] == _EXPECTED_PROVENANCE, (
        f"{pdf_path.name}: provenance {payload['provenance']!r} is not {_EXPECTED_PROVENANCE!r}; "
        "this tree is exclusively for AEAT-published facsimiles"
    )
    assert payload["role"] == _EXPECTED_ROLE, (
        f"{pdf_path.name}: role {payload['role']!r} is not {_EXPECTED_ROLE!r}; these specimens ground "
        "casilla values and cannot anchor the justificante parser"
    )
    assert payload["modelo"] == pdf_path.parent.name, (
        f"{pdf_path.name}: sidecar modelo {payload['modelo']!r} does not match its directory {pdf_path.parent.name!r}"
    )


@pytest.mark.parametrize("pdf_path", _PDFS, ids=_IDS)
def test_declared_digest_matches_the_committed_bytes(pdf_path: Path) -> None:
    """The sidecar digest must describe the file actually committed beside it."""
    payload = json.loads(pdf_path.with_suffix(".json").read_text(encoding="utf-8"))
    actual = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    assert payload["output_sha256"] == actual, (
        f"{pdf_path.name}: sidecar output_sha256 {payload['output_sha256']!r} does not match the "
        f"committed bytes {actual!r}"
    )


@pytest.mark.parametrize("pdf_path", _PDFS, ids=_IDS)
def test_specimen_carries_no_fixture_generator_signature(pdf_path: Path) -> None:
    """First half of the conjunctive check: these bytes are not generator output."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        producer = str((pdf.metadata or {}).get("Producer") or "")
    assert _SYNTHETIC_PRODUCER_SIGNATURE not in producer.lower(), (
        f"{pdf_path.name}: /Producer={producer!r} carries the fixture-generator signature, so this file is "
        f"synthetic_generated and does not belong in the {_EXPECTED_PROVENANCE} tree"
    )


@pytest.mark.parametrize("pdf_path", _PDFS, ids=_IDS)
def test_specimen_yields_no_extractable_nif(pdf_path: Path) -> None:
    """Second half: a facsimile carries no taxpayer identity, so it is not a filing.

    This is what separates an AEAT-published facsimile from a sanitised real
    filing. Every fixture in the ``justificantes/`` tree, real and synthetic
    alike, yields a NIF (the sanitiser substitutes one rather than removing it);
    a facsimile has none to substitute. A specimen that DID yield a NIF would be
    a filing mis-filed here, and this assertion is what catches that.
    """
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    with pytest.raises(DeclaracionParseError):
        extracted = _extract_tax_id(text)
        pytest.fail(
            f"{pdf_path.name}: extracted NIF {extracted!r}; a specimen carrying a taxpayer identity is a "
            f"filing, not an {_EXPECTED_PROVENANCE}, and belongs in the justificantes corpus instead",
        )
