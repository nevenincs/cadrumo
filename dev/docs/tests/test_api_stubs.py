"""The API reference covers every module the declared exclusions admit.

The ``docs/api/*.rst`` stubs are generated at build time and never committed,
so no stub tree records which modules the published reference covers. What a
committed tree used to catch -- a change to the eligibility filter that
silently drops pages -- is caught here instead, by deriving the admitted module
population a second way and comparing it with the generator's.

The derivation is deliberately naive: a plain ``os.walk`` of the source package
that prunes whole directories and applies the generator's four declared
exclusions, read as data. It shares the declarations with
:class:`~dev.docs.apidocs.manager.ApiStubManager` and nothing else, so a defect
in the filter code (a substring match, a wrong prefix, a subtree test that
over-reaches) makes the two populations disagree. A change to the declarations
themselves is a visible edit to the manager, and the hand-written API overview
(``docs/api/index.md``) is checked as a second, authored statement of coverage:
every module page it links must still be generated.

Run via::

    uv run --no-sync pytest dev/docs/tests/test_api_stubs.py -q -m ""
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import override

import pytest

from dev._paths import REPO_ROOT

from ..apidocs.manager import (
    API_SOURCE_PACKAGE,
    EXCLUDED_FILENAME_PREFIXES,
    EXCLUDED_FILENAMES,
    EXCLUDED_PACKAGE_SEGMENTS,
    EXCLUDED_SUBTREES,
    ApiStubManager,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_SRC_PACKAGE = REPO_ROOT / "src" / API_SOURCE_PACKAGE
_API_OVERVIEW = REPO_ROOT / "docs" / "api" / "index.md"

#: A MyST ``{doc}`` role, with or without an explicit title; the target may
#: wrap onto the next line.
_DOC_ROLE = re.compile(r"\{doc\}`(?:[^`<]*<)?([^`>]+)>?`")

_Module = tuple[str, bool]


def _walked_modules(src_package: Path) -> set[_Module]:
    """Return ``(dotted name, is_package)`` for every admitted module, by plain walk.

    Directories are pruned before descent -- a declared segment anywhere, or a
    declared subtree at its package-relative position -- and files are admitted
    unless their name is declared or carries a declared test prefix.
    """
    admitted: set[_Module] = set()
    for directory, subdirectories, filenames in os.walk(src_package):
        relative = Path(directory).relative_to(src_package).parts
        subdirectories[:] = [
            name
            for name in subdirectories
            if name not in EXCLUDED_PACKAGE_SEGMENTS and (*relative, name) not in EXCLUDED_SUBTREES
        ]
        dotted_directory = ".".join((src_package.name, *relative))
        for filename in filenames:
            if not filename.endswith(".py") or filename in EXCLUDED_FILENAMES:
                continue
            if filename.startswith(EXCLUDED_FILENAME_PREFIXES):
                continue
            if filename == "__init__.py":
                admitted.add((dotted_directory, True))
            else:
                admitted.add((f"{dotted_directory}.{filename.removesuffix('.py')}", False))
    return admitted


def _population_findings(manager: ApiStubManager) -> list[str]:
    """Describe every way the generator's population differs from the plain walk."""
    walked = _walked_modules(manager.src_cadrumo)
    generated = set(manager.discover_modules())
    findings = [f"dropped by the generator: {name}" for name, _ in sorted(walked - generated)]
    findings += [
        f"admitted by the generator but excluded by declaration: {name}" for name, _ in sorted(generated - walked)
    ]
    return findings


def _unadmitted_overview_links(overview: str, modules: Iterable[_Module]) -> list[str]:
    """Return module pages the overview links that the population does not generate."""
    names = {name for name, _ in modules}
    targets = {match.strip() for match in _DOC_ROLE.findall(overview)}
    return sorted(target for target in targets if target.startswith(API_SOURCE_PACKAGE) and target not in names)


def test_the_generator_admits_exactly_the_walked_population() -> None:
    """The live generator and the plain walk agree on every module."""
    manager = ApiStubManager(src_cadrumo=_SRC_PACKAGE, docs_api=REPO_ROOT / "docs" / "api")
    walked = _walked_modules(_SRC_PACKAGE)
    # A walk that found nothing agrees with a generator that found nothing.
    assert any(is_package for _, is_package in walked), f"the walk of {_SRC_PACKAGE} admitted no package"
    assert any(not is_package for _, is_package in walked), f"the walk of {_SRC_PACKAGE} admitted no module"

    findings = _population_findings(manager)

    assert not findings, f"{len(findings)} module(s) disagree:\n  " + "\n  ".join(findings[:40])


def test_every_module_page_the_overview_links_is_generated() -> None:
    """The authored layer map and the generated population agree on which layers are documented."""
    manager = ApiStubManager(src_cadrumo=_SRC_PACKAGE, docs_api=REPO_ROOT / "docs" / "api")
    overview = _API_OVERVIEW.read_text(encoding="utf-8")
    assert _DOC_ROLE.search(overview), f"{_API_OVERVIEW} links no module page; this check read nothing"

    unadmitted = _unadmitted_overview_links(overview, set(manager.discover_modules()))

    assert not unadmitted, f"the API overview links module pages the build no longer generates: {unadmitted}"


def test_scaffolding_writes_a_stub_for_every_admitted_module(tmp_path: Path) -> None:
    """A scaffold into an empty tree yields one automodule stub per walked module and nothing else."""
    docs_api = tmp_path / "api"
    manager = ApiStubManager(src_cadrumo=_SRC_PACKAGE, docs_api=docs_api)

    result = manager.scaffold()

    walked = {name for name, _ in _walked_modules(_SRC_PACKAGE)}
    written = {path.stem for path in docs_api.glob("*.rst")}
    assert written == walked, (
        f"missing stubs: {sorted(walked - written)[:20]}; unexpected stubs: {sorted(written - walked)[:20]}"
    )
    assert result.written == len(walked)
    assert result.removed == 0
    unreferenced = [
        name
        for name in sorted(walked)
        if f".. automodule:: {name}\n" not in (docs_api / f"{name}.rst").read_text("utf-8")
    ]
    assert not unreferenced, f"stubs that do not document their own module: {unreferenced[:20]}"


# ── Detector teeth ───────────────────────────────────────────────────────────


def _fixture_source_tree(root: Path) -> Path:
    """Materialise a small package that exercises every declared exclusion and its near misses."""
    src_package = root / "src" / API_SOURCE_PACKAGE
    files = [
        "__init__.py",
        "conftest.py",
        "core/__init__.py",
        "core/errors.py",
        "core/_private.py",
        "core/contests.py",
        "core/test_inline.py",
        "core/_test_helper.py",
        "core/tests/__init__.py",
        "core/tests/test_errors.py",
        "core/_data/__init__.py",
        "core/_data/table.py",
        "domain/__init__.py",
        "domain/data_model.py",
        "domain/testing_tools.py",
        "entrypoints/__init__.py",
        "entrypoints/mcp.py",
        "entrypoints/cli/__init__.py",
        "entrypoints/cli/main.py",
        "entrypoints/client/__init__.py",
    ]
    for relative in files:
        path = src_package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('"""Fixture module."""\n', encoding="utf-8", newline="\n")
    return src_package


#: The fixture's admitted population, written out by hand from the declarations.
_FIXTURE_ADMITTED: frozenset[_Module] = frozenset(
    {
        (API_SOURCE_PACKAGE, True),
        (f"{API_SOURCE_PACKAGE}.core", True),
        (f"{API_SOURCE_PACKAGE}.core.errors", False),
        (f"{API_SOURCE_PACKAGE}.core._private", False),
        (f"{API_SOURCE_PACKAGE}.core.contests", False),
        (f"{API_SOURCE_PACKAGE}.domain", True),
        (f"{API_SOURCE_PACKAGE}.domain.data_model", False),
        (f"{API_SOURCE_PACKAGE}.domain.testing_tools", False),
        (f"{API_SOURCE_PACKAGE}.entrypoints", True),
        (f"{API_SOURCE_PACKAGE}.entrypoints.mcp", False),
        (f"{API_SOURCE_PACKAGE}.entrypoints.client", True),
    }
)


class _SubstringSegmentManager(ApiStubManager):
    """A filter defect: excluded segments matched as substrings of any path part."""

    @override
    def excludes_source(self, path: Path) -> bool:
        parts = path.relative_to(self.src_cadrumo).parts
        if any(segment in part for part in parts for segment in EXCLUDED_PACKAGE_SEGMENTS):
            return True
        return super().excludes_source(path)


class _BarePrefixManager(ApiStubManager):
    """A filter defect: any filename starting ``test`` is taken for a test module."""

    @override
    def excludes_source(self, path: Path) -> bool:
        return path.name.startswith("test") or super().excludes_source(path)


class _LoosePrefixSubtreeManager(ApiStubManager):
    """A filter defect: a subtree matched by string prefix, so ``cli`` swallows ``client``."""

    @override
    def excludes_source(self, path: Path) -> bool:
        posix = path.relative_to(self.src_cadrumo).as_posix()
        if any(posix.startswith("/".join(subtree)) for subtree in EXCLUDED_SUBTREES):
            return True
        return super().excludes_source(path)


class _WidenedManager(ApiStubManager):
    """An over-broad exclusion: one more top-level segment excluded than declared."""

    @override
    def excludes_source(self, path: Path) -> bool:
        return "core" in path.relative_to(self.src_cadrumo).parts or super().excludes_source(path)


class _ConftestAdmittingManager(ApiStubManager):
    """A filter defect in the other direction: the declared filename exclusion is lost."""

    @override
    def excludes_source(self, path: Path) -> bool:
        if path.name in EXCLUDED_FILENAMES:
            return False
        return super().excludes_source(path)


def test_the_walk_and_the_generator_agree_on_the_fixture(tmp_path: Path) -> None:
    """Both derivations reproduce the hand-written population, so the comparison has a known answer."""
    src_package = _fixture_source_tree(tmp_path)
    manager = ApiStubManager(src_cadrumo=src_package, docs_api=tmp_path / "api")

    assert _walked_modules(src_package) == _FIXTURE_ADMITTED
    assert set(manager.discover_modules()) == _FIXTURE_ADMITTED
    assert _population_findings(manager) == []


@pytest.mark.parametrize(
    ("defective", "expected_finding"),
    [
        pytest.param(
            _SubstringSegmentManager,
            f"dropped by the generator: {API_SOURCE_PACKAGE}.core.contests",
            id="substring-segment",
        ),
        pytest.param(
            _BarePrefixManager,
            f"dropped by the generator: {API_SOURCE_PACKAGE}.domain.testing_tools",
            id="bare-test-prefix",
        ),
        pytest.param(
            _LoosePrefixSubtreeManager,
            f"dropped by the generator: {API_SOURCE_PACKAGE}.entrypoints.client",
            id="loose-subtree-prefix",
        ),
        pytest.param(
            _WidenedManager,
            f"dropped by the generator: {API_SOURCE_PACKAGE}.core.errors",
            id="widened-exclusion",
        ),
        pytest.param(
            _ConftestAdmittingManager,
            f"admitted by the generator but excluded by declaration: {API_SOURCE_PACKAGE}.conftest",
            id="lost-filename-exclusion",
        ),
    ],
)
def test_a_filter_defect_is_named_by_the_comparison(
    tmp_path: Path,
    defective: type[ApiStubManager],
    expected_finding: str,
) -> None:
    """Each planted defect makes the populations disagree on the module it mishandles."""
    src_package = _fixture_source_tree(tmp_path)
    manager = defective(src_cadrumo=src_package, docs_api=tmp_path / "api")

    findings = _population_findings(manager)

    assert expected_finding in findings, findings


def test_a_dropped_layer_is_named_by_the_overview_check(tmp_path: Path) -> None:
    """An exclusion both derivations would share still fails against the authored overview."""
    src_package = _fixture_source_tree(tmp_path)
    widened = set(_WidenedManager(src_cadrumo=src_package, docs_api=tmp_path / "api").discover_modules())
    overview = (
        f"- {{doc}}`{API_SOURCE_PACKAGE}.core <{API_SOURCE_PACKAGE}.core>` owns the spine.\n"
        f"- {{doc}}`{API_SOURCE_PACKAGE}.domain` owns tax semantics.\n"
        f"The tree starts at the {{doc}}`package root\n<{API_SOURCE_PACKAGE}>`.\n"
    )

    assert _unadmitted_overview_links(overview, _FIXTURE_ADMITTED) == []
    assert _unadmitted_overview_links(overview, widened) == [f"{API_SOURCE_PACKAGE}.core"]
