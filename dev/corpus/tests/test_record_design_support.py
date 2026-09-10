"""Integrity gate for the supported AEAT record-design corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..sync_aeat_record_design_corpus import (
    _CORPUS,
    _EXTRACTION_SIDECAR_ARTEFACTS,
    _HISTORICAL_EXCLUSIONS_PATH,
    _PAGES,
    _REQUIRED,
    _STATIC,
    _UNATTESTED_CORPUS_FILES,
    _Artifact,
    _authority_failures,
    _load_manifests,
    _load_off_host_sources,
    _Manifest,
    _OffHostSources,
    _root_aggregate,
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


def _artefact(stored_path: str, url: str) -> _Artifact:
    """One fully-formed manifest artefact; only path and URL vary per case."""
    return {
        "modelo": "999",
        "title": "fixture",
        "source_page": _PAGES["100"],
        "url": url,
        "stored_path": stored_path,
        "original_filename": stored_path.rsplit("/", 1)[-1],
        "content_type": "application/pdf",
        "bytes": 8,
        "sha256": "0" * 64,
        "retrieved_at": "2026-01-01",
    }


def _manifest(recorded_count: int, stored_paths: tuple[str, ...]) -> _Manifest:
    """A manifest whose recorded count is stated independently of its artefact list."""
    return {
        "source": "fixture",
        "modelo": "999",
        "retrieved_at": "2026-01-01",
        "source_pages": [_PAGES["100"]],
        "artefact_count": recorded_count,
        "artefacts": [_artefact(path, f"{_STATIC}/DR_900/archivos/{Path(path).name}") for path in stored_paths],
    }


def test_the_root_census_is_derived_from_the_artefact_lists_not_the_recorded_counts() -> None:
    """A per-modelo manifest whose own count lies does not corrupt the root census.

    The root census exists to be checked against reality, so it must be derived
    from what the manifests HOLD rather than from what they CLAIM. Reading the
    recorded ``artefact_count`` would make the aggregate agree with a lying
    manifest and the gate would pass on a corpus that is under-declared.
    """
    # Each recorded `artefact_count` disagrees with the list beside it.
    manifests: dict[str, _Manifest] = {
        "111": _manifest(99, ("files/01.pdf",)),
        "303": _manifest(0, ("files/a.pdf", "files/b.pdf")),
        "999": _manifest(7, ()),
    }

    aggregate = _root_aggregate(manifests)

    assert aggregate["artefact_count"] == 3
    assert aggregate["model_count"] == 3
    assert aggregate["supported_corpus_modelos"] == ["111", "303", "999"]
    assert aggregate["modelos"] == [
        {"modelo": "111", "artefact_count": 1},
        {"modelo": "303", "artefact_count": 2},
        {"modelo": "999", "artefact_count": 0},
    ]


def test_the_shipped_root_census_agrees_with_the_shipped_manifests() -> None:
    """The committed root manifest carries the census its per-modelo manifests imply.

    ``check`` reports this drift as four separate staleness findings; this states
    the invariant behind them in one place, and is the assertion the offline
    ``--regenerate-aggregate`` repair path is written to restore.
    """
    root = json.loads((_CORPUS / "manifest.json").read_text(encoding="utf-8"))

    for field, expected in _root_aggregate(_load_manifests()).items():
        assert root[field] == expected, f"root manifest {field} disagrees with the per-modelo manifests"


def _corpus_fixture(tmp_path: Path) -> tuple[dict[str, _Manifest], _OffHostSources]:
    """A two-artefact corpus where each artefact resolves to one authority."""
    (tmp_path / "modelo_999" / "files").mkdir(parents=True)
    (tmp_path / "modelo_999" / "files" / "02-orden.pdf").write_bytes(b"%PDF-1.4")
    manifests: dict[str, _Manifest] = {
        "999": {
            "source": "fixture",
            "modelo": "999",
            "retrieved_at": "2026-01-01",
            "source_pages": [_PAGES["100"]],
            "artefact_count": 2,
            "artefacts": [
                _artefact("files/01-design.pdf", f"{_STATIC}/DR_900/archivos/dr999.pdf"),
                _artefact("files/02-orden.pdf", "https://www.boe.es/boe/dias/2020/01/01/pdfs/X.pdf"),
            ],
        }
    }
    off_host: _OffHostSources = {
        "schema_version": 1,
        "authority": "boe",
        "disposition": "official-authority-published-by-boe-not-indexed-by-aeat",
        "reason": "fixture",
        "artefacts": [
            {
                "modelo": "999",
                "title": "Orden",
                "url": "https://www.boe.es/boe/dias/2020/01/01/pdfs/X.pdf",
                "stored_path": "modelo_999/files/02-orden.pdf",
                "kind": "record_design",
                "registry_declaration": "aeat/legal/modelo-999.toml",
            }
        ],
    }
    return manifests, off_host


def test_an_artefact_with_no_declared_authority_is_refused(tmp_path: Path) -> None:
    """The planted defect: corpus content nothing states the origin of.

    This is the state the corpus was actually in - 168 of 248 artefacts named by
    no declaration - and every other check passed throughout, because they all
    walk from the declarations outward or from the bytes to their own digest.
    """
    manifests, off_host = _corpus_fixture(tmp_path)
    required = {f"{_STATIC}/DR_900/archivos/dr999.pdf"}
    census: tuple[str, ...] = ()

    assert _authority_failures(manifests, required, off_host, tmp_path, census) == []

    # The defect: an artefact arrives carrying a URL no declaration names.
    manifests["999"]["artefacts"].append(
        _artefact("files/03-undeclared.pdf", f"{_STATIC}/DR_900/archivos/stowaway.pdf")
    )
    failures = _authority_failures(manifests, required, off_host, tmp_path, census)

    assert len(failures) == 1
    assert "resolves to no declared authority" in failures[0]
    assert "modelo_999/files/03-undeclared.pdf" in failures[0]


def test_an_artefact_claimed_by_two_declarations_is_refused(tmp_path: Path) -> None:
    """Two authorities is a defect, not redundancy: the acquisition path forks."""
    manifests, off_host = _corpus_fixture(tmp_path)
    # The off-host entry and a required row both claim the BOE artefact.
    required = {f"{_STATIC}/DR_900/archivos/dr999.pdf", "https://www.boe.es/boe/dias/2020/01/01/pdfs/X.pdf"}

    failures = _authority_failures(manifests, required, off_host, tmp_path, ())

    assert any("resolves to 2 authorities" in failure for failure in failures)


def test_an_off_host_entry_naming_an_aeat_url_or_an_absent_file_is_refused(tmp_path: Path) -> None:
    """The off-host locus exists for what the required set CANNOT express.

    An AEAT-hosted URL is expressible as a required row, so admitting one here
    would make the same artefact declarable in two places, and the reproducibility
    invariant would be satisfied by whichever the author happened to pick.
    """
    manifests, off_host = _corpus_fixture(tmp_path)
    off_host["artefacts"][0]["url"] = f"{_STATIC}/DR_900/archivos/dr999.pdf"
    off_host["artefacts"][0]["stored_path"] = "modelo_999/files/99-absent.pdf"
    required = {f"{_STATIC}/DR_900/archivos/dr999.pdf"}

    failures = _authority_failures(manifests, required, off_host, tmp_path, ())

    assert any("belongs in the required set" in failure for failure in failures)
    assert any("names an absent artefact" in failure for failure in failures)


def test_the_extraction_sidecar_census_is_an_equality_not_a_suffix_rule(tmp_path: Path) -> None:
    """A third sidecar fails, and so does retiring one while it is still listed."""
    manifests, off_host = _corpus_fixture(tmp_path)
    required = {f"{_STATIC}/DR_900/archivos/dr999.pdf"}
    # The .txt carries the .xls URL it was extracted from, so a required row
    # matches it; the census is what says the match is spurious.
    manifests["999"]["artefacts"].append(_artefact("files/01-design.txt", f"{_STATIC}/DR_900/archivos/dr999.pdf"))
    sidecar = "modelo_999/files/01-design.txt"

    assert _authority_failures(manifests, required, off_host, tmp_path, (sidecar,)) == []

    # Present but not censused. The URL match alone would excuse it, so the
    # reproducibility check is what catches it: the URL serves the .pdf.
    unlisted = _authority_failures(manifests, required, off_host, tmp_path, ())
    assert any("not reproducible from its declared URL" in failure for failure in unlisted)

    # Censused but no longer present.
    manifests["999"]["artefacts"].pop()
    retired = _authority_failures(manifests, required, off_host, tmp_path, (sidecar,))
    assert any("no longer present" in failure for failure in retired)


def test_the_shipped_extraction_sidecar_census_is_the_two_known_rows() -> None:
    """Named debt, not a suffix exemption that would swallow a genuine text artefact."""
    assert _EXTRACTION_SIDECAR_ARTEFACTS == (
        "modelo_123/files/01-123-orden-eha-3435-2007-ejercicio-2024-y-siguientes-190-kb-xls.txt",
        "modelo_123/files/02-123-eha-3435-2007-ejercicios-2019-2023-169-kb-xls.txt",
    )


def test_every_off_host_artefact_is_registered_on_the_registry_side() -> None:
    """The declaration names where the artefact is registered, and that file exists.

    A corpus declaration that pointed at nothing would restore the very asymmetry
    it closes: the registry knowing about an artefact the acquisition path does not.
    """
    registry_root = Path(__file__).resolve().parents[3] / "src/cadrumo/_data/registry"

    for entry in _load_off_host_sources()["artefacts"]:
        declaration = registry_root / entry["registry_declaration"]
        assert declaration.is_file(), f"{entry['stored_path']} names a missing declaration"
        assert entry["stored_path"].rsplit("/", 1)[-1] in declaration.read_text(encoding="utf-8"), (
            f"{entry['registry_declaration']} does not reference {entry['stored_path']}"
        )
