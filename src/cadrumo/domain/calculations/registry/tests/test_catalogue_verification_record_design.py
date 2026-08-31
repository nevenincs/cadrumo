"""Record-design and Renta-manual catalogue verification tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.external_constants import PDF_EXTENSION, XLS_EXTENSION, XLSM_EXTENSION, XLSX_EXTENSION
from .....core.record_design_epoch import RECORD_DESIGN_EPOCH_RE
from .....core.resources.bundled_data import bundled_path
from .....tests import REPO_ROOT
from ..corpus_catalogue import verify_source_file
from ._catalogue_verification_support import _catalogues, _registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_aeat_record_design_sources_match_corpus_manifests() -> None:
    catalogues = _catalogues()
    checked: list[str] = []

    for source in catalogues.sources.values():
        path = Path(source.corpus_path)
        parts = path.parts
        if len(parts) < 5 or parts[:3] != ("corpus", "aeat_official", "disenos_registro"):
            continue
        # corpus_path is stored relative to the bundled corpus root
        # (src/cadrumo/_data/), so resolve via bundled_path rather than
        # REPO_ROOT to find the on-disk manifest.
        modelo_dir = bundled_path(*parts[:4])
        manifest_path = modelo_dir / "manifest.json"
        assert manifest_path.is_file(), f"{source.id} missing corpus manifest {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored_path = Path(*parts[4:]).as_posix()
        artefact = next(
            (item for item in manifest["artefacts"] if item["stored_path"] == stored_path),
            None,
        )

        assert artefact is not None, f"{source.id} missing manifest artefact for {stored_path}"
        assert source.sha256 == artefact["sha256"], source.id
        assert source.bytes == artefact["bytes"], source.id
        assert source.source_url == artefact["url"], source.id
        checked.append(source.id)

    assert checked


#: The SAME extension set the schema's own ``kind == "record_design"`` validator
#: accepts (``_schema_references.py``), reused rather than redeclared. A source
#: NOT kind-``record_design`` whose bundled file carries one of these binary
#: extensions AND lives under the AEAT ``disenos_registro/`` tree is exactly the
#: shape the schema's forward check cannot see: nothing constrains what a
#: ``form_spec`` (or other) kind may point at, so a real Diseño de Registro
#: binary can sit mislabelled indefinitely with no gate noticing.
_BINARY_RECORD_DESIGN_EXTENSIONS = (PDF_EXTENSION, XLS_EXTENSION, XLSX_EXTENSION, XLSM_EXTENSION)


def test_no_non_record_design_source_points_at_a_binary_design_under_disenos_registro() -> None:
    """A ``form_spec`` (or other) kind may not point at a real AEAT design binary.

    Deliberately extension-scoped, not path-scoped: a bare "non-record_design
    under disenos_registro/" rule would ALSO flag the 12 ``dictionary`` and 6
    ``xsd`` companion files Modelo 100 correctly declares under its own kind --
    those are a real, distinct evidence type living beside the design, not a
    misclassified design. The binary-extension discriminator is what keeps this
    check anchored on the PROPERTY (this file IS a design workbook by its own
    extension) rather than a hand-list of which paths are exempt today, which
    would go stale silently after the next rename or reclassification.

    KNOWN BLIND SPOT, found and confirmed by inspection while building this
    check, not by this check itself: Modelo 123 declares two ``form_spec``
    sources whose ``corpus_path`` ends in ``.txt``
    (``aeat-dr-123-2024-v20-form-text``, ``aeat-dr-123-2019-2023-v13-form-text``).
    Reading the bundled files confirms they are row-by-row plain-text
    TRANSCRIPTIONS of the exact same posición/longitud/tipo/descripción Diseño
    de Registro content a bundled binary would carry -- genuine record-design
    evidence, not a landing page or procedure note -- but their ``source_url``
    already names the real ``.xls`` AEAT publishes. A binary-extension
    discriminator cannot see this: ``.txt`` is not a design extension, and the
    schema's own ``record_design`` kind validator would refuse a ``.txt``
    corpus_path if this were reclassified as-is (only .pdf/.xls/.xlsx/.xlsm are
    accepted). Closing this specific gap means re-bundling the real ``.xls``
    binary AEAT already publishes at the recorded ``source_url``, not widening
    the schema to accept a derived transcription -- the same "never ground on a
    derived artefact" posture this registry already takes for
    ``.html.extracted.md`` normatives citations. Reported here rather than
    silently passed: this test's own binary-extension scope cannot catch it,
    so it must not be allowed to look covered.
    """
    catalogues = _catalogues()
    offending: list[str] = []
    for source in catalogues.sources.values():
        if source.kind == "record_design":
            continue
        path = Path(source.corpus_path)
        if "disenos_registro" not in path.parts:
            continue
        suffix = source.corpus_path.rsplit(".", 1)
        extension = "." + suffix[1].lower() if len(suffix) == 2 else ""
        if extension in _BINARY_RECORD_DESIGN_EXTENSIONS:
            offending.append(
                f"{source.id!r} declares kind={source.kind!r} but its corpus_path "
                f"{source.corpus_path!r} is a {extension} binary under disenos_registro/ -- "
                "reclassify as kind='record_design' with a record_design_epoch, or confirm "
                "by content that it is genuinely NOT the AEAT design (e.g. a companion "
                "dictionary/xsd correctly modelled under its own kind, which never carries "
                "a design-binary extension)",
            )

    assert offending == [], (
        "non-record_design source(s) point at what their own extension declares is a "
        "binary AEAT design under disenos_registro/ -- the same misclassification tier5's "
        "M210/M280/M345 sweep found and corrected, reported here as a set so a NEW instance "
        "is caught rather than silently joining a stale allowlist:\n  " + "\n  ".join(sorted(offending))
    )


def _record_design_modelo(corpus_path: str) -> str | None:
    """Return the modelo a design's bundled corpus path sits under."""
    parts = Path(corpus_path).parts
    for part in parts:
        if part.startswith("modelo_"):
            return part.removeprefix("modelo_")
    return None


def test_every_record_design_source_declares_a_unique_well_formed_epoch() -> None:
    """A design binary no generator can select is an invisible under-declaration.

    ``resolve_record_design_binary`` refuses a ``record_design`` source that
    declares no ``record_design_epoch``, so the omission is not benign: it makes
    the bundled, hash-pinned, reviewed binary unreachable by the export-fragment
    generator. Nothing surfaced that until a generator was pointed at the modelo,
    which for an unauthored export layout is never -- so the sibling
    misclassification check above could demand "reclassify as kind='record_design'
    with a record_design_epoch" while 60 of the catalogue's 121 design sources
    carried no epoch at all.

    Epochs are also asserted UNIQUE per modelo, because the epoch is the key the
    generator's semantic-map and render-profile trees are addressed by
    (the authored registry mapping tree). Two designs for one modelo
    sharing an epoch cannot both be mapped, and AEAT does re-lay a form out
    mid-ejercicio -- which is exactly what the grammar's optional sub-year label
    ("2024-early", "2024-late") exists to distinguish.

    The pending set below is deliberately reason-bearing and fails when stale: an
    entry that acquires an epoch, or disappears, must leave this map rather than
    sit here looking cleared.
    """
    pending: dict[str, str] = {
        # Two same-ejercicio re-layout PAIRS. A bare year would collide, so each
        # pair needs the sub-year label ruling (which half is early/late, on
        # AEAT's own edition boundary) from the campaign that owns the M303
        # epoch vocabulary -- the same ruling that produced 2024-early/2024-late.
        "aeat-dr-303-2018": "same-ejercicio pair with aeat-dr-303-2018-salvo-ultimo-periodo",
        "aeat-dr-303-2018-salvo-ultimo-periodo": "same-ejercicio pair with aeat-dr-303-2018",
        "aeat-dr-303-2021-hasta-periodo-06": "same-ejercicio pair with aeat-dr-303-2021-desde-periodo-07",
        "aeat-dr-303-2021-desde-periodo-07": "same-ejercicio pair with aeat-dr-303-2021-hasta-periodo-06",
        # Mechanically derivable, but these sit in trees another campaign holds
        # open (the M303/M390 generator-authority work and the designless-modelo
        # adjudication). Declared here rather than swept, so the omission stays
        # visible and attributed instead of racing a peer's edit.
        "aeat-dr-303-2014": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-303-2015-2016": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-303-2017": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-303-2019-2020": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-390-2015": "held by the in-flight M390 generator-authority campaign",
        "aeat-dr-390-2016": "held by the in-flight M390 generator-authority campaign",
        # Every official manifest artefact is registered so the corpus and
        # catalogue agree, but this map does not invent selection windows. These source
        # titles describe versions/updates (or an ATF translation), not a
        # non-conflicting filing period relative to the actively selected
        # design. The source rows deliberately remain resolver-unreachable
        # until the temporal-design owner supplies that authority.
        "aeat-dr-036-v40": "AEAT's 2023 update to the 2021-y-siguientes design has no selection boundary",
        "aeat-dr-036-v35": "AEAT's 2021 update has no selection boundary against v40",
        "aeat-dr-202-2025-mar-update": "AEAT's March 2026 update has no selection boundary against the active 2025 design",
        "aeat-dr-202-2019-september-update": "AEAT's September 2019 update has no selection boundary against the active 2019 design",
        "aeat-dr-202-2012-v32": "the official version label does not establish a filing-period window",
        "aeat-dr-202-2013-v33": "the official version label does not establish the boundary before the 3P 2013 design",
        "aeat-dr-202-2010-v13": "the official version label does not establish a filing-period window",
        "aeat-dr-345-2023-archive": "the archive's 2023 design conflicts with the selected 2023 edition absent an effective boundary",
        "aeat-dr-349-2002": "the historical order title does not establish a bounded filing window",
        "aeat-dr-604-atf-spanish": "the Spanish ATF appendix is a translated logical design, not an independently dated epoch",
        "aeat-dr-604-atf-english": "the English ATF appendix is a translated logical design, not an independently dated epoch",
        # The modelo 184 ejercicio-2023 pair. Its revision cites BOTH the AEAT
        # diseno de registro and the BOE publication of the orden that
        # established it, so a bare "2023" would collide with the epoch
        # aeat-dr-184-2023-2024 already holds. Which of the two is the
        # selectable LAYOUT and which is merely the establishing instrument is
        # the temporal-design owner's ruling, not a sub-year label: they are the
        # same layout, not an AEAT mid-ejercicio re-lay.
        "boe-dr-184-2023-2024": "same-ejercicio pair with aeat-dr-184-2023-2024, which already holds epoch 2023",
        # The four older raw BOE ordenes for modelo 184. These carry NO epoch by
        # adjudication, not by omission: test_modelo_184_registry's
        # raw-BOE-design-eras regression asserts `record_design_epoch is None`
        # for exactly these four, on the ruling that a raw BOE design is
        # provenance and not a surrogate for a later AEAT map. Its parser
        # refusal is deliberate and load-bearing. Declaring an epoch here to
        # satisfy this gate contradicts that contract -- which is precisely what
        # happened before this entry existed.
        "boe-dr-184-2015": "raw BOE orden, adjudicated provenance rather than a mapped design",
        "boe-dr-184-2016-2018": "raw BOE orden, adjudicated provenance rather than a mapped design",
        "boe-dr-184-2019-2021": "raw BOE orden, adjudicated provenance rather than a mapped design",
        "boe-dr-184-2022": "raw BOE orden, adjudicated provenance rather than a mapped design",
        # Historical modelo 353 ordenes, registered so corpus and catalogue
        # agree. Neither declares applies_from/applies_to, and no modelo 353
        # revision cites either -- the modelo's revisions begin at 2021. There is
        # therefore no filing period to derive an epoch from, and inventing one
        # would assert a selection window nothing evidences.
        "aeat-dr-353-2007-orden": "the historical orden declares no filing window and no revision cites it",
        "aeat-dr-353-2008-orden": "the historical orden declares no filing window and no revision cites it",
    }

    modelos, catalogues = _registry_tree()
    designs = [source for source in catalogues.sources.values() if source.kind == "record_design"]
    assert designs, "the catalogue must declare record-design sources for this gate to mean anything"

    cited = {source_ref for modelo in modelos for source_ref in modelo.source_refs}
    cited |= {
        source_ref
        for modelo in modelos
        for revision in modelo.revisions.values()
        for source_ref in revision.source_refs
    }

    undeclared = {source.id for source in designs if source.record_design_epoch is None}

    malformed = sorted(
        f"{source.id!r} declares epoch {source.record_design_epoch!r}"
        for source in designs
        if source.record_design_epoch is not None and not RECORD_DESIGN_EPOCH_RE.fullmatch(source.record_design_epoch)
    )
    assert malformed == [], (
        "record-design epoch(s) do not match the shared epoch grammar (a four-digit ejercicio "
        "with an optional lower-case sub-year label):\n  " + "\n  ".join(malformed)
    )

    stale = sorted(source_id for source_id in pending if source_id not in undeclared)
    assert stale == [], (
        "pending record-design epoch entr(ies) are stale -- the source now declares an epoch, or no "
        "longer exists. Remove them from the pending map:\n  " + "\n  ".join(stale)
    )
    newly_undeclared = sorted(undeclared - set(pending))
    assert newly_undeclared == [], (
        "record-design source(s) declare no record_design_epoch, so resolve_record_design_binary "
        "refuses them and no export-fragment generator can reach their bundled binary. Declare the "
        "ejercicio the design governs:\n  " + "\n  ".join(newly_undeclared)
    )

    by_modelo_epoch: dict[tuple[str, str], list[str]] = {}
    for source in designs:
        if source.record_design_epoch is None:
            continue
        modelo = _record_design_modelo(source.corpus_path)
        if modelo is None:
            continue
        by_modelo_epoch.setdefault((modelo, source.record_design_epoch), []).append(source.id)
    collisions = sorted(
        f"modelo {modelo} epoch {epoch!r}: {', '.join(sorted(source_ids))}"
        for (modelo, epoch), source_ids in by_modelo_epoch.items()
        if len(source_ids) > 1
    )
    assert collisions == [], (
        "two record-design sources for one modelo share an epoch, so they address the same "
        "generator mapping directory and cannot both be authored. Distinguish them with the "
        "grammar's sub-year label:\n  " + "\n  ".join(collisions)
    )


def test_modelo_202_active_record_design_is_latest_manifested_revision() -> None:
    catalogues = _catalogues()
    source = catalogues.sources["aeat-dr-202-2025"]
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_202", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = [
        artefact
        for artefact in manifest["artefacts"]
        if artefact["original_filename"] == "DR202e25.xlsx" and "2025 y siguientes" in artefact["title"]
    ]
    latest = max(candidates, key=lambda artefact: artefact["retrieved_at"])

    assert source.corpus_path.endswith(latest["stored_path"])
    assert source.sha256 == latest["sha256"]
    assert source.bytes == latest["bytes"]
    assert source.source_url == latest["url"]


def test_modelo_100_record_design_sources_match_manifest() -> None:
    catalogues = _catalogues()
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources_by_path = {source.corpus_path: source for source in catalogues.sources.values()}
    checked: list[str] = []

    for artefact in manifest["artefacts"]:
        title = artefact["title"]
        if not (
            "Diccionario declaración individual" in title
            or "Diccionario declaración individual (toma de datos)" in title
            or "Esquema XSD Ejercicio" in title
        ):
            continue
        corpus_path = f"corpus/aeat_official/disenos_registro/modelo_100/{artefact['stored_path']}"
        source = sources_by_path.get(corpus_path)

        assert source is not None, f"Modelo 100 corpus artefact has no registry source: {corpus_path}"
        assert source.sha256 == artefact["sha256"]
        assert source.bytes == artefact["bytes"]
        assert source.source_url == artefact["url"]
        assert source.evidence_tier == "layout_authority"
        assert source.kind in {"dictionary", "xsd"}
        verify_source_file(REPO_ROOT, source)
        checked.append(source.id)

    assert len(checked) == 18


def _source_path(corpus_path: str) -> Path:
    return bundled_path(*corpus_path.split("/"))


def _record_design_label(corpus_path: str, casilla_id: str) -> str:
    marker = f"[{casilla_id}]"
    for line in _source_path(corpus_path).read_text(encoding="cp1252").splitlines():
        if marker not in line:
            continue
        label = line.split(marker, 1)[1].strip()
        assert label.startswith("[") and label.endswith("]"), line
        return label[1:-1]
    raise AssertionError(f"source {corpus_path} has no label for casilla {casilla_id}")


def _manual_extracted_text(corpus_path: str) -> str:
    extracted_path = Path(f"{_source_path(corpus_path)}.extracted.json")
    raw_payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert isinstance(raw_payload, dict)
    raw_units = raw_payload.get("units")
    assert isinstance(raw_units, list)
    texts: list[str] = []
    for raw_unit in raw_units:
        assert isinstance(raw_unit, dict)
        text = raw_unit.get("text")
        assert isinstance(text, str)
        texts.append(text)
    return "\n".join(texts)


def test_modelo_100_2021_deportistas_0489_is_grounded_in_dictionary_and_manual() -> None:
    modelos, catalogues = _registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "100")
    revision = modelo.revisions["2021"]
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0489")
    dictionary = catalogues.sources["aeat-dr-100-2021-dictionary"]
    manual = catalogues.sources["aeat-renta-2021-manual-parte1"]

    assert dictionary.evidence_tier == "layout_authority"
    assert manual.evidence_tier == "official_source_guidance"
    assert casilla.label == _record_design_label(dictionary.corpus_path, "0489")
    assert "aeat-renta-2021-manual-parte1" in casilla.source_refs
    assert casilla.semantic_role == "irpf_red_deportistas_aportaciones_contribuciones"

    manual_text = " ".join(_manual_extracted_text(manual.corpus_path).split())
    assert "casillas [0488] y [0489]" in manual_text
    assert "aportaciones y contribuciones realizadas en 2021" in manual_text


def test_modelo_100_2021_forestal_0302_prefers_manual_year_over_dictionary_drift() -> None:
    modelos, catalogues = _registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "100")
    revision = modelo.revisions["2021"]
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0302")
    dictionary = catalogues.sources["aeat-dr-100-2021-dictionary"]
    manual = catalogues.sources["aeat-renta-2021-manual-parte1"]

    expected_label = (
        "Ganancias patrimoniales obtenidas por los vecinos en 2021 como consecuencia de "
        "aprovechamientos forestales en montes públicos"
    )

    assert _record_design_label(dictionary.corpus_path, "0302") == expected_label.replace("2021", "2020")
    assert casilla.label == expected_label
    assert "aeat-renta-2021-manual-parte1" in casilla.source_refs

    manual_text = " ".join(_manual_extracted_text(manual.corpus_path).split())
    assert expected_label in manual_text
    assert "Esta ganancia patrimonial ha estado sujeta en 2021 a la retención del 19 por 100" in manual_text


def test_renta_manual_sources_match_manifest() -> None:
    catalogues = _catalogues()
    sources_by_path = {source.corpus_path: source for source in catalogues.sources.values()}
    renta_root = bundled_path("corpus", "manuals", "renta")
    manifest_paths = sorted(
        renta_root.glob("*/*/manifest.json"),
        key=lambda path: path.relative_to(renta_root).as_posix(),
    )
    checked: list[str] = []

    assert manifest_paths
    for manifest_path in manifest_paths:
        root = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pdf_path = root / manifest["relative_pdf_path"]
        # corpus_path on registry sources is bundled-corpus-relative
        # (i.e. begins with ``corpus/...``), so relativise against the
        # bundle root rather than REPO_ROOT.
        corpus_path = pdf_path.relative_to(bundled_path()).as_posix()
        source = sources_by_path.get(corpus_path)

        assert manifest["synthetic"] is False, f"Renta manual manifest must cite a real PDF: {manifest_path}"
        assert pdf_path.is_file(), f"Renta manual manifest points at a missing PDF: {pdf_path}"
        assert source is not None, f"Renta manual corpus artefact has no registry source: {corpus_path}"
        assert source.sha256 == manifest["sha256"]
        assert source.bytes == manifest["content_length"]
        assert source.source_url == manifest["source_pdf_url"]
        assert source.evidence_tier == "official_source_guidance"
        assert source.kind == "manual_pdf"
        verify_source_file(REPO_ROOT, source)
        checked.append(source.id)

    assert checked == [
        "aeat-renta-2020-manual-parte1",
        "aeat-renta-2021-manual-parte1",
        "aeat-renta-2022-manual-parte1",
        "aeat-renta-2023-manual-parte1",
        "aeat-renta-2024-manual-parte1",
        "aeat-renta-2024-manual-deducciones-autonomicas",
        "aeat-renta-2025-manual-parte1",
        "aeat-renta-2025-manual-deducciones-autonomicas",
    ]
