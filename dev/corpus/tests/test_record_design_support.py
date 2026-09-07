"""Integrity gate for the supported AEAT record-design corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..sync_aeat_record_design_corpus import (
    _HISTORICAL_EXCLUSIONS_PATH,
    _REQUIRED,
    _UNATTESTED_CORPUS_FILES,
    check,
    unattested_corpus_files,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_supported_record_design_corpus_is_complete_and_current() -> None:
    """The captured official matrix and every manifested source rehash cleanly."""
    check()


def test_modelos_308_and_309_historical_designs_are_required_not_excluded() -> None:
    """The six AEAT historical IVA designs stay in the canonical sync inventory.

    The corpus checker proves their persisted bytes and exclusion partition.  This
    explicit cohort prevents a future inventory edit from silently returning the
    claimed-year evidence to the historical exclusion ledger.
    """
    expected = {
        "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_300_399/archivos/dr308.xls": (
            "308",
            "308 - Orden EHA/1033/2011 (Ejercicios 2009 a 2011- julio)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr308_2011.pdf"
        ): (
            "308",
            "308 - Orden EHA/1033/2011 (Ejercicios 2011 - julio - a 2015)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr308e16v12.xls"
        ): (
            "308",
            "308 - Orden EHA/1033/2011 (Ejercicios 2016 hasta 2018)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr309_2004.pdf"
        ): (
            "309",
            "309 - Orden EHA/3212/2004 (Ejercicios hasta 2015)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr309e16v10.xls"
        ): (
            "309",
            "309 - Orden EHA/3212/2004 (Ejercicios 2016 y 2017)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "DR_300_399/archivos_17/dr309e17v13.xls"
        ): (
            "309",
            "309 - Orden EHA/3212/2004 (Ejercicios 2018 y posteriores)",
        ),
    }
    required = {artifact.url: (artifact.modelo, artifact.title) for artifact in _REQUIRED}
    exclusions = set(json.loads(_HISTORICAL_EXCLUSIONS_PATH.read_text(encoding="utf-8"))["urls"])

    assert {url: required[url] for url in expected} == expected
    assert exclusions.isdisjoint(expected)


def test_modelo_353_historical_designs_are_required_not_excluded() -> None:
    """The five historical M353 designs remain canonical source evidence.

    These sources deliberately remain unjoined while the current 2008--2025
    selector is over-broad.  Keeping their exact official URLs in the inventory
    is what makes a later era split evidence-backed rather than a backdate of
    the 2021 layout.
    """
    expected = {
        "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_300_399/archivos/dr353.pdf": (
            "353",
            "353 - Orden EHA/3434/2007",
        ),
        "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_300_399/archivos/dr353v13.pdf": (
            "353",
            "353 - Orden EHA/3786/2008",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/DR353e16v19.xls"
        ): (
            "353",
            "353 - Orden HAP/1222/2014 (Ejercicios 2015 y 2016)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/DR353e17v20.xlsx"
        ): (
            "353",
            "353 - Orden HAP/1222/2014 (Ejercicios 2017, 2108 y 2019)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/DR353e17v20.xls"
        ): (
            "353",
            "353 -Orden EHA/3434/2007 (Ejercicio 2020)",
        ),
    }
    required = {artifact.url: (artifact.modelo, artifact.title) for artifact in _REQUIRED}
    exclusions = set(json.loads(_HISTORICAL_EXCLUSIONS_PATH.read_text(encoding="utf-8"))["urls"])

    assert {url: required[url] for url in expected} == expected
    assert exclusions.isdisjoint(expected)


def _model_tree(root: Path, modelo: str, stored: tuple[str, ...]) -> Path:
    """Build one attested model directory: payloads plus the manifest naming them."""
    model_dir = root / f"modelo_{modelo}"
    (model_dir / "files").mkdir(parents=True)
    for relative in stored:
        (model_dir / relative).write_bytes(b"payload")
    (model_dir / "manifest.json").write_text(
        json.dumps(
            {
                "modelo": modelo,
                "artefact_count": len(stored),
                "artefacts": [{"stored_path": relative} for relative in stored],
            }
        ),
        encoding="utf-8",
    )
    return model_dir


def test_a_payload_no_manifest_names_is_reported_as_unattested(tmp_path: Path) -> None:
    """The direction the manifest walk cannot see.

    ``check`` confirms every declared artefact is on disk at the recorded size
    and digest. Nothing confirmed the converse, and the manifest cannot express
    'present but not attested': an artefact is a complete entry or it is absent.
    So a pull that writes payload bytes and stops before rewriting the manifests,
    or a partial revert of a bulk removal, leaves corpus content with no source
    URL, licence, digest or retrieval date while every declared count still
    reconciles and the gate reads green.

    Built on a temporary tree, never the committed corpus.
    """
    root = tmp_path / "disenos_registro"
    root.mkdir()
    model_dir = _model_tree(root, "999", ("files/01-declared.pdf",))

    assert unattested_corpus_files(root) == (), "a fully attested corpus must report nothing"

    # Derivatives and project declarations sit beside payloads and are not
    # artefacts; they must not be mistaken for unattested content.
    (model_dir / "files" / "01-declared.pdf.extracted.md").write_text("text", encoding="utf-8")
    (model_dir / "files" / "01-declared.pdf.extracted.json").write_text("{}", encoding="utf-8")
    (model_dir / "files" / "01-declared.pdf.record-design-correction.json").write_text("{}", encoding="utf-8")
    (model_dir / "declared-non-record-sheets.json").write_text("{}", encoding="utf-8")
    assert unattested_corpus_files(root) == ()

    # The defect: bytes restored, manifest entry not.
    (model_dir / "files" / "02-restored.xlsx").write_bytes(b"evidence")
    assert unattested_corpus_files(root) == ("modelo_999/files/02-restored.xlsx",)

    # Attesting it closes the finding through the same predicate.
    manifest_path = model_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artefacts"].append({"stored_path": "files/02-restored.xlsx"})
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert unattested_corpus_files(root) == ()


def test_the_recorded_unattested_census_is_a_named_debt_not_a_blanket() -> None:
    """The recorded set is one file, named, and it is not an ignore rule.

    ``check`` compares the observed unattested set against this one for EQUALITY,
    so a second unattested file fails and so does attesting this one while it is
    still listed. A census that only grows silently would be the same silence it
    was written to end.
    """
    assert _UNATTESTED_CORPUS_FILES == ("modelo_200/files/01-200-ejercicio-2025-10-9-mb-xls.xlsx",)
