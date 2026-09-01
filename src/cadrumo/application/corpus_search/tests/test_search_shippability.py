"""Licence/footprint shippability gate for the corpus-search surface.

Confirms the wheel ships the light, licence-clean data (the extracted
corpus triples the index builds from) and NOT the heavy model footprint:
no model weights, no onnxruntime, no caches, no precompiled index. Also
confirms the shipped retrieval surface carries no embedding runtime at all
and that the FTS index build is deterministic. Real-behavior only: no skips,
tmp_path SQLite, assertions on the packaged-data tree that SHIPS.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from ....core.directory_scan import DirectoryEntryKind, iter_directory, scan_directory
from ....core.resources.bundled_data import bundled_path
from ..lexical_index import build_lexical_index, iter_corpus_chunks
from ._corpus_fixture import build_sample_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

#: Third-party runtimes the shipped retrieval surface must never import: the
#: product carries no semantic runtime, so no model loader, no hub client, and
#: no vector maths may reach a production module.
_FORBIDDEN_RUNTIME_IMPORTS = frozenset({"model2vec", "huggingface_hub", "numpy", "onnxruntime", "torch"})

# Model-weight / runtime / cache artifacts that must never ship in the wheel.
_FORBIDDEN_SUFFIXES = frozenset(
    {
        ".onnx",
        ".safetensors",
        ".bin",
        ".pt",
        ".pth",
        ".ckpt",
        ".gguf",
        ".h5",
        ".msgpack",
        ".tflite",
        ".npy",
        ".npz",
        ".sqlite",
        ".db",
    }
)
_FORBIDDEN_DIR_NAMES = frozenset({"onnxruntime", "model2vec", ".cache", "__pycache__"})


def _iter_files(root: Path):
    yield from iter_directory(
        root,
        recursive=True,
        select=DirectoryEntryKind.FILES,
        prune_directories=("__pycache__",),
    )


def test_retrieval_surface_imports_on_a_bare_core_install() -> None:
    # The whole shipped retrieval surface must import with no optional stack;
    # a real import-machinery check, not a mock.
    for module in (
        "cadrumo.application.corpus_search.lexical_index",
        "cadrumo.application.corpus_search.citation_lookup",
        "cadrumo.application.corpus_search._retrieval",
        "cadrumo.application.corpus_search.runtime",
        "cadrumo.application.corpus_search",
        "cadrumo.application.command_search",
    ):
        assert importlib.import_module(module) is not None


def _production_search_modules() -> list[Path]:
    """Every shipped module of the two search packages (tests excluded)."""
    command_search_root = _PACKAGE_ROOT.parent / "command_search"
    modules = [
        path
        for root in (_PACKAGE_ROOT, command_search_root)
        for path in scan_directory(root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        if "tests" not in path.relative_to(root).parts
    ]
    # Anti-vacuity floor: an empty or collapsed walk would pass the import gate
    # below while checking nothing.
    assert len(modules) >= 8, f"expected the shipped search modules, walked only {len(modules)}"
    return modules


def _imported_root_packages(path: Path) -> set[str]:
    """Return the root package name of every import in ``path``, deferred ones included."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_shipped_search_surface_imports_no_embedding_runtime() -> None:
    # The product ships no semantic runtime: no production search module may
    # import a model loader, a hub client, or vector maths — including behind a
    # function-local or TYPE_CHECKING import, which an import-machinery probe
    # would miss. Reintroducing one fails here by name.
    offenders = {
        path.relative_to(_PACKAGE_ROOT.parent).as_posix(): sorted(forbidden)
        for path in _production_search_modules()
        if (forbidden := _imported_root_packages(path) & _FORBIDDEN_RUNTIME_IMPORTS)
    }
    assert not offenders, f"shipped search surface must import no embedding runtime, found: {offenders}"


def test_corpus_search_package_ships_no_model_artifacts() -> None:
    offenders = [
        path.relative_to(_PACKAGE_ROOT).as_posix()
        for path in _iter_files(_PACKAGE_ROOT)
        if path.suffix.lower() in _FORBIDDEN_SUFFIXES
    ]
    assert not offenders, f"corpus_search package must ship no weights/index artifacts, found: {offenders}"


def test_corpus_search_package_has_no_model_or_cache_dirs() -> None:
    offenders = [
        path.relative_to(_PACKAGE_ROOT).as_posix()
        for path in scan_directory(_PACKAGE_ROOT, recursive=True, select=DirectoryEntryKind.DIRECTORIES)
        if path.name in (_FORBIDDEN_DIR_NAMES - {"__pycache__"})
    ]
    assert not offenders, f"corpus_search package must ship no model/cache dirs, found: {offenders}"


def test_bundled_data_ships_no_model_weights() -> None:
    # The whole bundled _data tree must be free of model weights and
    # runtimes: only the light, licence-clean corpus text data ships.
    weight_suffixes = _FORBIDDEN_SUFFIXES - {".sqlite", ".db", ".npy", ".npz"}
    data_root = bundled_path()
    offenders = [
        path.relative_to(data_root).as_posix()
        for path in _iter_files(data_root)
        if path.suffix.lower() in weight_suffixes
    ]
    assert not offenders, f"bundled _data must ship no model weights, found: {offenders[:10]}"


def test_bundled_corpus_ships_extracted_triples() -> None:
    # The shippable LIGHT data the index builds from must be present.
    from ..lexical_index import bundled_corpus_html_root

    extracted = scan_directory(bundled_corpus_html_root(), pattern="*.html.extracted.json")
    assert len(extracted) > 100, f"expected the shipped extracted corpus triples, found {len(extracted)}"


def test_fts_chunk_ids_deterministic_across_builds(tmp_path: Path) -> None:
    corpus = build_sample_corpus(tmp_path / "corpus")
    chunk_ids = [chunk.chunk_id for chunk in iter_corpus_chunks(corpus)]

    first_db = tmp_path / "first.sqlite"
    second_db = tmp_path / "second.sqlite"
    build_lexical_index(first_db, iter_corpus_chunks(corpus))
    build_lexical_index(second_db, iter_corpus_chunks(corpus))

    assert _index_chunk_ids(first_db) == chunk_ids
    assert _index_chunk_ids(second_db) == chunk_ids


def _index_chunk_ids(database_path: Path) -> list[str]:
    import sqlite3

    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT chunk_id FROM chunks ORDER BY rowid").fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]
