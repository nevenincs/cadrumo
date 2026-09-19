"""The enrollment candidate derives rows from capture records and installs nothing.

An unregistered design under ``corpus/aeat_official/disenos_registro/`` is
invisible: nothing hash-pins it, nothing resolves it, and the sources catalogue
cannot see it exists. The candidate answers what closing that would take, and
the two properties worth pinning are what it refuses to invent and what it
refuses to touch.

The fixtures are synthetic trees rather than the bundled corpus, so the
assertions stay about the derivation rather than about whichever designs happen
to be unregistered today.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..analysis.record_design_enrollment import DerivedSourceRow, derive_enrollment_candidate
from ..conformance.loader_directory_mode_support import write_minimal_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_DIR = "modelo_999"
_REGISTERED_DIGEST = "a" * 64
_CAPTURED_DIGEST = "b" * 64
_UNCAPTURED_DIGEST = "c" * 64

_SOURCES_TOML = f"""\
[sources."aeat-dr-999-2019"]
evidence_tier = "layout_authority"
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/aeat_official/disenos_registro/{_MODELO_DIR}/files/01-999-ejercicio-2019.xlsx"
sha256 = "{_REGISTERED_DIGEST}"
bytes = 11
retrieved_at = 2026-05-03
source_url = "https://sede.agenciatributaria.gob.es/static_files/999/DR999v01.xlsx"
review_status = "pending_review"
"""


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    """Materialise a bundle root holding one registered, one captured, one uncaptured design."""
    bundle_root = tmp_path / "bundle"
    registry_root = bundle_root / "registry" / "aeat"
    write_minimal_shared_catalogues(registry_root / "legal")
    (registry_root / "legal" / "designs.toml").write_text(_SOURCES_TOML, encoding="utf-8", newline="\n")
    # The loader walks the modelo sources even when the question is only about
    # the sources catalogue; a tree with no modelos directory is not a tree.
    (registry_root / "modelos").mkdir(parents=True)

    design_root = bundle_root / "corpus" / "aeat_official" / "disenos_registro" / _MODELO_DIR
    files = design_root / "files"
    files.mkdir(parents=True)
    for name in ("01-999-ejercicio-2019.xlsx", "02-999-ejercicio-2020.xlsx", "03-999-sin-captura.xlsx"):
        (files / name).write_text("not a workbook", encoding="utf-8", newline="\n")
    # The ingest harness writes one capture row per artefact it retrieved. The
    # third file deliberately has none, which is the state the derivation must
    # keep separate rather than enrol from nothing.
    (design_root / "manifest.json").write_text(
        json.dumps(
            {
                "artefacts": [
                    {
                        "stored_path": "files/01-999-ejercicio-2019.xlsx",
                        "sha256": _REGISTERED_DIGEST,
                        "bytes": 11,
                        "retrieved_at": "2026-05-03",
                        "url": "https://sede.agenciatributaria.gob.es/static_files/999/DR999v01.xlsx",
                        "title": "Diseño de registro del modelo 999. Ejercicio 2019",
                    },
                    {
                        "stored_path": "files/02-999-ejercicio-2020.xlsx",
                        "sha256": _CAPTURED_DIGEST,
                        "bytes": 14,
                        "retrieved_at": "2026-05-04",
                        "url": "https://sede.agenciatributaria.gob.es/static_files/999/DR999v02.xlsx",
                        "title": "Diseño de registro del modelo 999. Ejercicio 2020 y siguientes",
                    },
                ],
            },
        ),
        encoding="utf-8",
        newline="\n",
    )
    return bundle_root, registry_root


def _derive(tmp_path: Path) -> tuple[tuple[DerivedSourceRow, ...], tuple[str, ...], Path]:
    bundle_root, registry_root = _bundle(tmp_path)
    rows, uncaptured = derive_enrollment_candidate(registry_root, bundle_root=bundle_root)
    return rows, uncaptured, bundle_root


def test_only_the_unregistered_captured_design_becomes_a_candidate_row(tmp_path: Path) -> None:
    """A design the catalogue already names is not owed a second row."""
    rows, _uncaptured, _bundle_root = _derive(tmp_path)

    assert [row.corpus_path for row in rows] == [
        f"corpus/aeat_official/disenos_registro/{_MODELO_DIR}/files/02-999-ejercicio-2020.xlsx",
    ]


def test_a_candidate_row_carries_the_capture_record_verbatim(tmp_path: Path) -> None:
    """Every evidential field comes off the capture row, not off the filename."""
    rows, _uncaptured, _bundle_root = _derive(tmp_path)
    row = rows[0]

    assert row.sha256 == _CAPTURED_DIGEST
    assert row.bytes == 14
    assert row.retrieved_at == "2026-05-04"
    assert row.source_url.endswith("DR999v02.xlsx")
    assert row.owning_toml.endswith("legal/designs.toml")


def test_the_identifier_takes_the_exercise_the_listing_title_states(tmp_path: Path) -> None:
    """The title's ejercicio names the row; it is a key, and nothing resolves law from it."""
    rows, _uncaptured, _bundle_root = _derive(tmp_path)

    assert rows[0].source_id == "aeat-dr-999-2020"


def test_a_candidate_declares_no_window_and_no_epoch(tmp_path: Path) -> None:
    """The one inference the module refuses: a listing title is not a legal scope.

    ``applies_from``, ``applies_to`` and ``record_design_epoch`` are the fields
    that decide which filing year a design is compared against, and the only
    thing on disk suggesting them is AEAT's own listing title. Reading a window
    out of one would put a filing year under a layout the design never claimed.
    """
    rows, _uncaptured, _bundle_root = _derive(tmp_path)
    rendered = rows[0].as_toml()

    assert "applies_from" not in rendered.partition("#")[0]
    assert "applies_to" not in rendered.partition("#")[0]
    assert "record_design_epoch" not in rendered.partition("#")[0]
    assert 'review_status = "pending_review"' in rendered


def test_a_design_with_no_capture_record_is_reported_apart_from_the_candidate(tmp_path: Path) -> None:
    """Enrolling it would assert a retrieval nobody recorded, so it is never batched with the rest."""
    rows, uncaptured, _bundle_root = _derive(tmp_path)

    assert uncaptured == (f"corpus/aeat_official/disenos_registro/{_MODELO_DIR}/files/03-999-sin-captura.xlsx",)
    assert all(row.corpus_path not in uncaptured for row in rows)


def test_deriving_the_candidate_writes_nothing(tmp_path: Path) -> None:
    """The boundary the module states in its own first line: it installs nothing."""
    bundle_root, registry_root = _bundle(tmp_path)
    before = {path: path.read_bytes() for path in sorted(bundle_root.rglob("*")) if path.is_file()}

    derive_enrollment_candidate(registry_root, bundle_root=bundle_root)

    after = {path: path.read_bytes() for path in sorted(bundle_root.rglob("*")) if path.is_file()}
    assert after == before
