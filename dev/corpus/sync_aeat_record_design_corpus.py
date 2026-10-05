"""Synchronise the supported AEAT record-design corpus from official indexes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Final, cast
from urllib.parse import urlparse

import httpx

_ROOT = Path(__file__).resolve().parents[2]

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if not __package__:
    __package__ = "dev.corpus"

from cadrumo.core.directory_scan import scan_directory  # noqa: E402
from dev.corpus.artifact_catalogue import (  # noqa: E402
    ArtifactCatalogue,
    ArtifactDiagnostic,
    ArtifactDiagnosticKind,
    ArtifactRole,
    SemanticAnnotation,
    compile_artifact_catalogue,
    record_design_manifest_identities,
)
from dev.corpus.record_design_inventory import (  # noqa: E402
    _CORRECTION_SUFFIX,
    _CURRENT_PAGE_KEYS,
    _DECLARATION_NAMES,
    _DERIVED_SUFFIXES,
    _EXTRACTION_SIDECAR_DERIVATIONS,
    _HISTORICAL_PAGE_KEYS,
    _MANIFEST_NAME,
    _PAGES,
    _REQUIRED,
    _RETRIEVED_AT,
    UNATTESTED_CORPUS_FILES,
    _RequiredArtifact,
)
from dev.packaging.hashing import sha256_path  # noqa: E402

from .record_design_acquisition import _pull_required_artifact, _sha256_bytes  # noqa: E402
from .record_design_index import _index_links, _raw_artifact_for_url, _supported_index_urls  # noqa: E402
from .record_design_manifests import (  # noqa: E402
    _Artifact,
    _artifact_urls,
    _HistoricalExclusions,
    _Manifest,
    _ModeloRow,
    _represented_urls,
    _root_aggregate,
    _RootAggregate,
)

_UTF_8: Final[str] = "utf-8"


_CORPUS = _ROOT / "src/cadrumo/_data/corpus/aeat_official/disenos_registro"


_HISTORICAL_EXCLUSIONS_PATH = _CORPUS / "historical_exclusions.json"


def _check_root_model_counts(root: _RootAggregate, expected_rows: list[_ModeloRow], failures: list[str]) -> None:
    """Check root model counts."""
    if root.get("modelos") != expected_rows:
        recorded_counts = {row["modelo"]: row["artefact_count"] for row in root.get("modelos") or []}
        expected_counts = {row["modelo"]: row["artefact_count"] for row in expected_rows}
        drifted = [
            f"{modelo} records {recorded_counts.get(modelo)} holds {expected_counts.get(modelo)}"
            for modelo in sorted(set(recorded_counts) | set(expected_counts))
            if recorded_counts.get(modelo) != expected_counts.get(modelo)
        ]
        failures.append("root manifest per-model counts are stale: " + "; ".join(drifted))


def _correction_annotations(corpus_root: Path) -> tuple[SemanticAnnotation, ...]:
    """Correction annotations."""
    annotations = tuple(
        SemanticAnnotation(
            path=PurePosixPath(path.relative_to(corpus_root).as_posix()),
            target_path=PurePosixPath(path.relative_to(corpus_root).as_posix().removesuffix(_CORRECTION_SUFFIX)),
        )
        for model_dir in scan_directory(corpus_root, pattern="modelo_*")
        for path in sorted(model_dir.rglob(f"*{_CORRECTION_SUFFIX}"))
        if path.is_file()
    )
    return annotations


def _check_required_urls(manifests: dict[str, _Manifest], failures: list[str]) -> None:
    """Check required urls."""
    for required in _REQUIRED:
        manifest = manifests.get(required.modelo)
        if manifest is None or not any(required.url in _artifact_urls(artifact) for artifact in manifest["artefacts"]):
            failures.append(f"missing official URL: M{required.modelo} {required.url}")


def _check_manifest_bytes(manifests: dict[str, _Manifest], failures: list[str]) -> None:
    """Check manifest bytes."""
    for modelo, manifest in manifests.items():
        model_dir = _CORPUS / f"modelo_{modelo}"
        for artifact in manifest["artefacts"]:
            path = model_dir / artifact["stored_path"]
            if not path.is_file():
                failures.append(f"missing artifact: {path}")
                continue
            if path.stat().st_size != artifact["bytes"]:
                failures.append(f"byte mismatch: {path}")
            if sha256_path(path) != artifact["sha256"]:
                failures.append(f"sha256 mismatch: {path}")


def _check_root_census(manifests: dict[str, _Manifest], failures: list[str]) -> None:
    """Check root census."""
    root = json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8))
    aggregate = _root_aggregate(manifests)
    expected_models = aggregate["supported_corpus_modelos"]
    expected_artifact_count = aggregate["artefact_count"]
    expected_rows = aggregate["modelos"]
    # Each staleness report names the observed and expected values. "is stale"
    # alone states that something drifted and withholds what, so the reader
    # cannot tell a one-artefact addition from a wholesale corpus change, and
    # the cheapest response to an unactionable verdict is to regenerate blindly.
    recorded_models = root.get("supported_corpus_modelos")
    if recorded_models != expected_models:
        missing = sorted(set(expected_models) - set(recorded_models or []))
        extra = sorted(set(recorded_models or []) - set(expected_models))
        failures.append(f"root manifest supported_corpus_modelos is stale: missing {missing}, unexpected {extra}")
    if root.get("model_count") != len(expected_models):
        failures.append(
            f"root manifest model_count is stale: records {root.get('model_count')}, "
            f"corpus holds {len(expected_models)}"
        )
    if root.get("artefact_count") != expected_artifact_count:
        failures.append(
            f"root manifest artefact_count is stale: records {root.get('artefact_count')}, "
            f"corpus holds {expected_artifact_count}"
        )
    _check_root_model_counts(root, expected_rows, failures)
    if any(failure.startswith("root manifest") for failure in failures):
        failures.append("repair the root manifest census offline with --regenerate-aggregate")


def _check_historical_exclusions(
    historical_exclusions: _HistoricalExclusions, manifests: dict[str, _Manifest], failures: list[str]
) -> list[str]:
    """Check historical exclusions."""
    exclusion_urls = historical_exclusions.get("urls", [])
    expected_historical_pages = [_PAGES[key] for key in _HISTORICAL_PAGE_KEYS]
    if historical_exclusions.get("schema_version") != 1:
        failures.append("historical exclusion schema_version is stale")
    if historical_exclusions.get("disposition") != "outside-supported-window-or-superseded":
        failures.append("historical exclusion disposition is stale")
    if historical_exclusions.get("source_pages") != expected_historical_pages:
        failures.append("historical exclusion source_pages are stale")
    if len(exclusion_urls) != len(set(exclusion_urls)):
        failures.append("historical exclusion URLs are not unique")
    represented_urls = _represented_urls(manifests)
    conflicting_exclusions = sorted(set(exclusion_urls) & represented_urls)
    if conflicting_exclusions:
        failures.append(f"historical exclusions are already represented: {conflicting_exclusions[:5]!r}")
    return exclusion_urls


def _check_unattested_files(catalogue: ArtifactCatalogue | None, failures: list[str]) -> None:
    """Check unattested files."""
    observed_unattested = (
        tuple(
            diagnostic.path.as_posix()
            for diagnostic in catalogue.diagnostics
            if diagnostic.kind is ArtifactDiagnosticKind.UNKNOWN_FILE and diagnostic.path is not None
        )
        if catalogue is not None
        else unattested_corpus_files(_CORPUS)
    )
    if observed_unattested != UNATTESTED_CORPUS_FILES:
        appeared = sorted(set(observed_unattested) - set(UNATTESTED_CORPUS_FILES))
        attested = sorted(set(UNATTESTED_CORPUS_FILES) - set(observed_unattested))
        failures.append(
            "corpus files carrying no manifest entry have changed: "
            f"newly unattested {appeared}, no longer unattested {attested}"
        )


def _check_required_exclusions(exclusion_urls: list[str], failures: list[str]) -> None:
    """Check required exclusions."""
    required_urls = {required.url for required in _REQUIRED}
    required_exclusions = sorted(set(exclusion_urls) & required_urls)
    if required_exclusions:
        failures.append(f"required URLs are classified as historical exclusions: {required_exclusions[:5]!r}")


def _load_manifests() -> dict[str, _Manifest]:
    manifests: dict[str, _Manifest] = {}
    for model_dir in scan_directory(_CORPUS, pattern="modelo_*"):
        path = model_dir / "manifest.json"
        if path.exists():
            manifests[model_dir.name.removeprefix("modelo_")] = json.loads(path.read_text(encoding=_UTF_8))
    return manifests


def _payload_paths(corpus_root: Path) -> tuple[PurePosixPath, ...]:
    """Return the bounded payload candidates owned by this synchronizer.

    Project declarations and extractor outputs are intentionally outside this
    acquisition boundary: the catalog compiler assigns payload roles here,
    while their disposition and derivation contracts remain with their owners
    until the later migration steps.  This function discovers candidates only;
    it does not decide whether they have an acceptable acquisition identity.
    """
    paths: list[PurePosixPath] = []
    for model_dir in scan_directory(corpus_root, pattern="modelo_*"):
        for candidate in sorted(model_dir.rglob("*")):
            if (
                not candidate.is_file()
                or candidate.name in _DECLARATION_NAMES
                or candidate.name.endswith(_DERIVED_SUFFIXES)
            ):
                continue
            paths.append(PurePosixPath(candidate.relative_to(corpus_root).as_posix()))
    return tuple(paths)


def _catalogue_diagnostic_message(diagnostic: ArtifactDiagnostic) -> str:
    """Render a typed catalog finding at this CLI's existing failure boundary."""
    path = "<unknown>" if diagnostic.path is None else diagnostic.path.as_posix()
    return f"artifact catalog {diagnostic.kind.value}: {path}: {diagnostic.message}"


def _record_design_catalogue(
    manifests: dict[str, _Manifest],
    corpus_root: Path,
) -> tuple[ArtifactCatalogue | None, list[str]]:
    """Compile payload identities and the targets of their correction annotations.

    The compiler owns the canonical path join and payload classification.  The
    synchronizer deliberately retains byte rehashing and retrieval checks;
    catalog compilation is an identity/role projection, not a replacement for
    either. Correction annotations must name a payload inside this boundary;
    their correction content is validated by the record-design reader.
    Production ``check`` always fails closed on an incomplete identity row.
    """
    derived_paths = {derivative.path for derivative in _EXTRACTION_SIDECAR_DERIVATIONS}
    identities = []
    failures: list[str] = []
    for modelo, manifest in sorted(manifests.items()):
        manifest_path = PurePosixPath(f"modelo_{modelo}/{_MANIFEST_NAME}")
        try:
            identities.extend(
                identity
                for identity in record_design_manifest_identities(manifest, manifest_path=manifest_path)
                if identity.path not in derived_paths
            )
        except (TypeError, ValueError) as error:
            failures.append(f"manifest acquisition identity is malformed: M{modelo}: {error}")
    if failures:
        return None, failures
    annotations = _correction_annotations(corpus_root)
    catalogue = compile_artifact_catalogue(
        known_paths=(*_payload_paths(corpus_root), *(annotation.path for annotation in annotations)),
        official_identities=identities,
        derived_artifacts=_EXTRACTION_SIDECAR_DERIVATIONS,
        semantic_annotations=annotations,
    )
    return catalogue, []


def unattested_corpus_files(corpus_root: Path) -> tuple[str, ...]:
    """Corpus files under ``corpus_root`` that no manifest declares.

    :func:`check` walks the manifests and confirms every declared artefact
    is on disk with the recorded size and digest. That direction cannot see
    a file the manifests do not mention, and the manifest has no way to say
    'present but not yet attested': an artefact is either a fully described
    entry or absent. So a run that writes payload bytes and stops before
    rewriting the manifests, or a partial revert of a bulk removal, leaves
    corpus content carrying no source URL, licence, digest or retrieval date
    while every count in every manifest still reconciles.

    Under-declaration of exactly this kind is silent, which is why the walk
    runs in both directions.

    Args:
        corpus_root: Directory holding the ``modelo_*`` corpus directories.

    Returns:
        Corpus-root-relative POSIX paths, sorted, of every present file that
        is neither a declaration, a known derivative, nor a declared artefact.
    """
    unattested: list[str] = []
    for model_dir in scan_directory(corpus_root, pattern="modelo_*"):
        manifest_path = model_dir / _MANIFEST_NAME
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding=_UTF_8))
        declared = {model_dir / artifact["stored_path"] for artifact in manifest["artefacts"]}
        for candidate in sorted(model_dir.rglob("*")):
            if not candidate.is_file() or candidate.name in _DECLARATION_NAMES:
                continue
            if candidate.name.endswith(_DERIVED_SUFFIXES):
                continue
            if candidate not in declared:
                unattested.append(candidate.relative_to(corpus_root).as_posix())
    return tuple(sorted(unattested))


def _load_historical_exclusions() -> _HistoricalExclusions:
    """Read the classified historical-URL exclusions.

    The exclusion ledger is intentionally URL-based.  A product support-year
    declaration belongs to the validated registry authority, while this file
    records the historical URLs that have been explicitly adjudicated as out of
    the synchronizer's acquisition set.  Keeping a second year window here would
    invite it to drift from the URL evidence (as the removed window did when
    ``DR714_2022.xls`` was bundled despite being outside that window).
    """
    # `json.loads` is typed `Any`; the cast states the shape this endpoint
    # is documented to return, in one place instead of at every use.
    return cast(
        "_HistoricalExclusions",
        json.loads(_HISTORICAL_EXCLUSIONS_PATH.read_text(encoding=_UTF_8)),
    )


def _write_root_manifest(root: dict[str, object]) -> None:
    (_CORPUS / "manifest.json").write_bytes((json.dumps(root, ensure_ascii=False, indent=2) + "\n").encode())


def _regenerate_root_aggregate() -> None:
    """Rewrite the root manifest's census from the per-modelo manifests, offline.

    The census is derived from files already on disk, so repairing it needs
    no network. Before this path existed the only writer was ``--pull``, and
    a purely local number could drift with no local way to correct it: it did,
    and the offline check stayed red against an unreachable repair.

    ``retrieved_at`` is deliberately NOT touched. Nothing was retrieved, and
    advancing a retrieval date to record a recount would assert a freshness
    this run did not establish.
    """
    manifests = _load_manifests()
    root = cast("dict[str, object]", json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8)))
    aggregate = _root_aggregate(manifests)
    drifted = sorted(field for field, value in aggregate.items() if root.get(field) != value)
    if not drifted:
        print("OK: root manifest census already agrees with the per-modelo manifests")
        return
    root.update(aggregate)
    _write_root_manifest(root)
    print(f"REGENERATED root manifest census: {', '.join(drifted)}")


def _write_manifests(manifests: dict[str, _Manifest]) -> None:
    for modelo, manifest in manifests.items():
        artifacts = manifest["artefacts"]
        manifest["artefact_count"] = len(artifacts)
        path = _CORPUS / f"modelo_{modelo}" / "manifest.json"
        path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

    root = cast("dict[str, object]", json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8)))
    root["retrieved_at"] = _RETRIEVED_AT
    root.update(_root_aggregate(manifests))
    _write_root_manifest(root)


def _pull() -> None:
    manifests = _load_manifests()
    with httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-hydration/1.0"},
    ) as client:
        for index, required in enumerate(_REQUIRED, 1):
            _pull_required_artifact(index, required, manifests, client, _CORPUS, len(_REQUIRED))
    _write_manifests(manifests)


def _authority_failures(
    manifests: dict[str, _Manifest],
    catalogue: ArtifactCatalogue | None = None,
) -> list[str]:
    """Report manifest artefacts that lack one official catalog identity.

    The catalog owns the complete immutable acquisition identity, including
    documents acquired from a non-AEAT publisher.  The synchronizer retains
    byte rehashing; catalogued derivatives retain their exact input identity.
    """
    failures: list[str] = []
    catalogue_is_local = catalogue is None
    if catalogue_is_local:
        catalogue = _local_artifact_catalogue(manifests, failures)
    if catalogue_is_local:
        failures.extend(_catalogue_diagnostic_message(diagnostic) for diagnostic in catalogue.diagnostics)
    for modelo, manifest in sorted(manifests.items()):
        for artifact in manifest["artefacts"]:
            _check_artifact_identity(artifact, modelo, catalogue, failures)
    return failures


def check() -> None:
    """Verify required official URLs, manifests, and local artifact bytes offline."""
    manifests = _load_manifests()
    historical_exclusions = _load_historical_exclusions()
    failures = []
    catalogue, catalogue_failures = _record_design_catalogue(manifests, _CORPUS)
    failures.extend(catalogue_failures)
    if catalogue is not None:
        failures.extend(
            _catalogue_diagnostic_message(diagnostic)
            for diagnostic in catalogue.diagnostics
            if diagnostic.kind is not ArtifactDiagnosticKind.UNKNOWN_FILE
        )
    _check_required_urls(manifests, failures)
    _check_manifest_bytes(manifests, failures)
    _check_root_census(manifests, failures)
    exclusion_urls = _check_historical_exclusions(historical_exclusions, manifests, failures)
    _check_unattested_files(catalogue, failures)
    _check_required_exclusions(exclusion_urls, failures)
    failures.extend(
        _authority_failures(
            manifests,
            catalogue,
        )
    )
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"OK: {len(_REQUIRED)} required official URLs and {len(manifests)} manifests")


#: Exit status for "the question could not be asked", as distinct from a pass or
#: a drift finding. AEAT republishes on its own schedule and its site is not
#: always reachable; a run that could not read the official pages has learned
#: NOTHING about staleness, and reporting that as either outcome would be a lie
#: in one direction or the other. Callers key on this status rather than parsing
#: the message.
LIVE_CHECK_UNAVAILABLE: Final[int] = 75


def _live_check() -> None:
    """Compare the captured corpus against the live official pages.

    Three outcomes, deliberately distinguished. The corpus matches; the corpus
    has drifted and the differences are named; or the official source could not
    be read at all, which is reported as a LIMITATION and never as either of the
    other two.
    """
    try:
        _live_check_against_official_pages()
    except (httpx.TransportError, httpx.HTTPStatusError) as unreachable:
        status = getattr(getattr(unreachable, "response", None), "status_code", None)
        if isinstance(unreachable, httpx.HTTPStatusError) and status is not None and status < 500:
            # A 4xx on a URL the corpus expects is a finding about the corpus,
            # not about the network: the official page stopped serving it.
            raise SystemExit(f"official URL no longer served ({status}): {unreachable.request.url}") from unreachable
        print(
            f"LIMITATION: the official source could not be read ({type(unreachable).__name__}); "
            f"staleness is UNKNOWN, not clean",
            file=sys.stderr,
        )
        raise SystemExit(LIVE_CHECK_UNAVAILABLE) from unreachable


def _live_check_against_official_pages() -> None:
    manifests = _load_manifests()
    historical_exclusions = _load_historical_exclusions()
    root = json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8))
    supported_modelos = {str(modelo) for modelo in root["supported_corpus_modelos"]}
    links_by_page: dict[str, dict[str, str]] = {}
    failures: list[str] = []

    with httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-currentness/1.0"},
    ) as client:
        for source_page in _PAGES.values():
            response = client.get(source_page)
            response.raise_for_status()
            links_by_page[source_page] = {url: title for title, url in _index_links(response.text, source_page)}

        # A declaration with no established index page cannot be asked whether
        # it is still indexed: there is no page to look on. Reporting that as a
        # pass would claim a check that did not run, and as a failure would
        # claim drift that was never observed, so it is counted and named.
        current_urls, historical_urls, unadjudicated = _compare_index_inventory(
            links_by_page, supported_modelos, manifests, historical_exclusions, failures
        )

        for url, modelo in sorted(current_urls.items()):
            _check_live_artifact_bytes(url, modelo, manifests, client, failures)

    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"OK live: {len(current_urls)} current raw URLs and {len(_REQUIRED) - len(unadjudicated)} "
        f"required indexed URLs plus {len(historical_urls)} classified historical URLs "
        f"across {len(_PAGES)} pages",
    )
    if unadjudicated:
        print(
            f"LIMITATION: {len(unadjudicated)} required URLs carry no established index page and were "
            f"not checked for continued indexing: "
            + ", ".join(f"M{required.modelo} {required.url}" for required in unadjudicated),
        )


def main() -> None:
    """Run the offline integrity check, optionally pulling official sources first."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pull", action="store_true")
    parser.add_argument(
        "--regenerate-aggregate",
        action="store_true",
        help="Recompute the root manifest census from the per-modelo manifests without fetching.",
    )
    parser.add_argument("--live-check", action="store_true")
    args = parser.parse_args()
    if args.pull:
        _pull()
    if args.regenerate_aggregate:
        _regenerate_root_aggregate()
    check()
    if args.live_check:
        _live_check()


def _check_artifact_identity(
    artifact: _Artifact, modelo: str, catalogue: ArtifactCatalogue, failures: list[str]
) -> None:
    """Check artifact identity."""
    path = f"modelo_{modelo}/{artifact['stored_path']}"
    catalog_role = catalogue.roles.get(PurePosixPath(path))
    if catalog_role is ArtifactRole.DERIVED_ARTIFACT:
        return
    catalog_identity = catalogue.identities.get(PurePosixPath(path))
    if catalog_identity is None or catalog_role is not ArtifactRole.OFFICIAL_ARTIFACT:
        failures.append(f"artefact does not bind an official catalog identity: M{modelo} {path}")
        return
    # A catalog identity proves provenance, but not reproducibility by
    # the acquisition writer: `_pull` names files from the response URL
    # extension. A divergent stored suffix therefore remains a failure.
    stored_suffix = PurePosixPath(artifact["stored_path"]).suffix.lower()
    url_suffix = PurePosixPath(urlparse(artifact["url"]).path).suffix.lower()
    if stored_suffix != url_suffix:
        failures.append(
            f"artefact is not reproducible from its declared URL: M{modelo} {path} "
            f"stored {stored_suffix or '<none>'} but {artifact['url']} serves {url_suffix or '<none>'}"
        )


def _check_live_artifact_bytes(
    url: str, modelo: str, manifests: dict[str, _Manifest], client: httpx.Client, failures: list[str]
) -> None:
    """Check live artifact bytes."""
    manifest = manifests[modelo]
    artifact = _raw_artifact_for_url(manifest, url)
    if artifact is None:
        failures.append(f"unrepresented current official URL: M{modelo} {url}")
        return
    response = client.get(url)
    response.raise_for_status()
    data = response.content
    if len(data) != artifact["bytes"] or _sha256_bytes(data) != artifact["sha256"]:
        failures.append(f"current official bytes drifted: M{modelo} {url}")


def _local_artifact_catalogue(manifests: dict[str, _Manifest], failures: list[str]) -> ArtifactCatalogue:
    """Compile the local identity boundary before comparing manifest roles."""
    derived_paths = {derivative.path for derivative in _EXTRACTION_SIDECAR_DERIVATIONS}
    identities = []
    for modelo, manifest in sorted(manifests.items()):
        try:
            identities.extend(
                identity
                for identity in record_design_manifest_identities(
                    manifest,
                    manifest_path=PurePosixPath(f"modelo_{modelo}/{_MANIFEST_NAME}"),
                )
                if identity.path not in derived_paths
            )
        except (TypeError, ValueError) as error:
            failures.append(f"manifest acquisition identity is malformed: M{modelo}: {error}")
    catalogue = compile_artifact_catalogue(
        known_paths=tuple(identity.path for identity in identities)
        + tuple(derivative.path for derivative in _EXTRACTION_SIDECAR_DERIVATIONS),
        official_identities=identities,
        derived_artifacts=_EXTRACTION_SIDECAR_DERIVATIONS,
    )
    return catalogue


def _compare_index_inventory(
    links_by_page: dict[str, dict[str, str]],
    supported_modelos: set[str],
    manifests: dict[str, _Manifest],
    historical_exclusions: _HistoricalExclusions,
    failures: list[str],
) -> tuple[dict[str, str], dict[str, str], list[_RequiredArtifact]]:
    """Compare required, current, and historical official index inventories."""
    unadjudicated = [required for required in _REQUIRED if required.source_page is None]
    for required in _REQUIRED:
        if required.source_page is None:
            continue
        if required.url not in links_by_page[required.source_page]:
            failures.append(f"required URL no longer indexed: M{required.modelo} {required.url}")

    current_urls = _supported_index_urls(links_by_page, _CURRENT_PAGE_KEYS, supported_modelos)
    historical_urls = _supported_index_urls(links_by_page, _HISTORICAL_PAGE_KEYS, supported_modelos)
    represented_urls = _represented_urls(manifests)
    expected_exclusions = set(historical_exclusions["urls"])
    actual_exclusions = set(historical_urls) - represented_urls
    for url in sorted(actual_exclusions - expected_exclusions):
        failures.append(f"unclassified historical official URL: M{historical_urls[url]} {url}")
    for url in sorted(expected_exclusions - actual_exclusions):
        failures.append(f"stale historical URL exclusion: {url}")

    return current_urls, historical_urls, unadjudicated


if __name__ == "__main__":
    main()
