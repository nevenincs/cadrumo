"""Generate and check the package's third-party notices page from what assembly staged.

The page lists every third-party component a target's package installs: the
Python interpreter, the native programs and runtime libraries beside it, the
Node.js runtimes, the Python distributions and the agent runtime's JavaScript
packages, each with its version, its declared licence and where the package
carries the licence text. Package assembly calls :func:`require_current_notices`
on the assembled candidate, writes the fresh page into the build tree, and
refuses the package while the committed page differs, while a component's
licence text is missing, while a program file is attributed to no component, or
while any component declares the GNU General Public License or the GNU Affero
General Public License.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import Distribution
from pathlib import Path, PurePosixPath
from typing import Any, cast

from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev.paths import REPO_ROOT

from .agent_runtime import STAGED_RECEIPT_NAME
from .assembly_identity import installed_distributions
from .msvc_redist import REQUIRED_LIBRARIES

_UTF_8 = "utf-8"
_FIRST_PARTY = frozenset({*PRODUCT_IDENTITY.cohort_distributions, "cadrumo-agent"})
_CLASSIFIER_PREFIX = "License :: "
_SHORT_LICENCE_FIELD = 100
_STRONG_COPYLEFT = re.compile(r"(?<!L)GPL|GNU (Affero )?General Public License")
_LLAMA_FILE = re.compile(r"(lib)?(llama|ggml|mtmd)([-_.][\w.-]*)?")
_OPENMP_FILE = re.compile(r"lib(g|i)?omp[\w.-]*")
_MSVC_VERSION = re.compile(r"/MSVC/(\d+\.\d+\.\d+)/")
_NOTICES_DIRECTORY = "notices"


@dataclass(frozen=True)
class Notice:
    """One listed component: what it is, its version, its declared licence and its licence text in the package."""

    component: str
    version: str
    licence: str
    text: str | None


def target_path(target: str, repo_root: Path = REPO_ROOT) -> Path:
    """Return the committed notices page for one package target."""
    return repo_root / "docs" / "reference" / f"third-party-notices-{target}.md"


def build_render_path(binary_dir: Path, target: str) -> Path:
    """Return where assembly writes the page it would accept, inside the build tree."""
    return binary_dir / _NOTICES_DIRECTORY / f"third-party-notices-{target}.md"


def declared_licence(distribution: Distribution) -> str:
    """Return the licence a distribution's metadata declares, preferring its SPDX expression."""
    metadata = distribution.metadata
    expression = str(metadata.get("License-Expression") or "").strip()
    if expression:
        return expression
    classifiers = sorted(
        {
            str(value).removeprefix(_CLASSIFIER_PREFIX).split(" :: ")[-1]
            for value in metadata.get_all("Classifier") or ()
            if str(value).startswith(_CLASSIFIER_PREFIX)
        }
    )
    if classifiers:
        return " / ".join(classifiers)
    return _free_text_licence(metadata)


def _free_text_licence(metadata: Any) -> str:
    """The licence a distribution states in its ``License`` field when short, else by its licence files."""
    field = str(metadata.get("License") or "").strip()
    if field and "\n" not in field and len(field) <= _SHORT_LICENCE_FIELD:
        return field
    files = sorted(str(name) for name in metadata.get_all("License-File") or ())
    if files:
        return "stated in " + ", ".join(files)
    return "not declared"


def _distribution_statements(distribution: Distribution) -> str:
    metadata = distribution.metadata
    return "\n".join(
        str(value)
        for value in (
            metadata.get("License-Expression") or "",
            *(metadata.get_all("Classifier") or ()),
            metadata.get("License") or "",
        )
    )


def _third_party(distributions: Iterable[Distribution]) -> list[Distribution]:
    return sorted(
        (d for d in distributions if canonicalize_name(d.metadata["Name"]) not in _FIRST_PARTY),
        key=lambda d: canonicalize_name(d.metadata["Name"]),
    )


def _metadata_directory(distribution: Distribution, packages: str) -> str | None:
    for member in distribution.files or ():
        top = PurePosixPath(str(member).replace("\\", "/")).parts[0]
        if top.endswith(".dist-info"):
            return f"{packages}/{top}"
    return None


def python_notices(distributions: Iterable[Distribution], packages: str) -> list[Notice]:
    """List each third-party Python distribution with the licence its metadata declares."""
    return [
        Notice(
            canonicalize_name(d.metadata["Name"]),
            d.version,
            declared_licence(d),
            _metadata_directory(d, packages),
        )
        for d in _third_party(distributions)
    ]


def javascript_notices(runtime: Path, runtime_prefix: str) -> list[Notice]:
    """List each JavaScript package the agent runtime installed, from its lockfile, as installed on disk."""
    lock = runtime / "package-lock.json"
    if not lock.is_file():
        return []
    packages = cast(Mapping[str, Mapping[str, Any]], json.loads(lock.read_text(encoding=_UTF_8))["packages"])
    notices = []
    for key, entry in sorted(packages.items()):
        if not key or entry.get("dev") or not (runtime / key).is_dir():
            continue
        name = key.rsplit("node_modules/", 1)[-1]
        notices.append(
            Notice(
                name,
                str(entry.get("version", "")),
                str(entry.get("license") or "not declared"),
                f"{runtime_prefix}/{key}",
            )
        )
    return notices


def _partition_program_files(names: Sequence[str]) -> tuple[list[str], list[str], list[str]]:
    """Split program files into the OpenMP and Visual C++ runtime libraries and those no component owns."""
    programs = [name for name in names if _LLAMA_FILE.fullmatch(name)]
    openmp = [name for name in names if _OPENMP_FILE.fullmatch(name)]
    runtime = [name for name in names if name in REQUIRED_LIBRARIES]
    unattributed = [name for name in names if name not in {*programs, *openmp, *runtime}]
    return openmp, runtime, unattributed


def _llama_notices(
    root: Path, layout: Mapping[str, str], inputs: Mapping[str, Any], tag: str
) -> tuple[list[Notice], list[str]]:
    """List llama.cpp, its OpenMP and Visual C++ runtime libraries; name each program file no component owns."""
    licences = f"{layout['docs']}/licenses/llama.cpp"
    names = sorted(path.name for path in (root / layout["llama_server"]).iterdir() if path.is_file())
    openmp, runtime, unattributed = _partition_program_files(names)
    notices = [
        Notice("llama.cpp: llama-server and the llama, ggml and mtmd libraries", tag, "MIT", f"{licences}/LICENSE")
    ]
    if openmp:
        notices.append(_openmp_notice(tag, licences, openmp))
    if runtime:
        notices.append(_msvc_runtime_notice(inputs, runtime))
    return notices, unattributed


def _openmp_notice(tag: str, licences: str, openmp: Sequence[str]) -> Notice:
    return Notice(
        f"LLVM OpenMP runtime ({', '.join(openmp)}) from the llama.cpp release",
        tag,
        "Apache-2.0 WITH LLVM-exception",
        f"{licences}/LICENSE-LLVM-OpenMP",
    )


def _msvc_runtime_notice(inputs: Mapping[str, Any], runtime: Sequence[str]) -> Notice:
    toolchain = cast(Mapping[str, Any], inputs.get("build_toolchain", {}))
    redist = cast(Mapping[str, Any], toolchain.get("msvc_redist", {}))
    version = _MSVC_VERSION.search(str(redist.get("directory", "")))
    return Notice(
        f"Microsoft Visual C++ runtime ({', '.join(runtime)})",
        version.group(1) if version else "not recorded",
        "Microsoft Visual C++ Redistributable terms",
        None,
    )


def _native_notices(
    root: Path,
    layout: Mapping[str, str],
    files: Mapping[str, str],
    manifest: Mapping[str, Any],
    distributions: Mapping[str, str],
) -> tuple[list[Notice], list[str]]:
    """List the interpreter, the programs beside it and the Node.js runtimes; name each unattributed program file."""
    notices = [
        Notice(
            "CPython, with the libraries of its build",
            str(manifest["python"]),
            "PSF-2.0, with the notices of the libraries it bundles",
            files["python_license"],
        )
    ]
    unattributed: list[str] = []
    inputs = cast(Mapping[str, Any], manifest.get("inputs", {}))
    llama = cast(Mapping[str, Any] | None, inputs.get("llama_server"))
    if llama is not None:
        found, unattributed = _llama_notices(root, layout, inputs, str(llama["tag"]))
        notices.extend(found)
    packages = PurePosixPath(layout["packages"])
    receipt = root / packages.parent / STAGED_RECEIPT_NAME
    if receipt.is_file():
        node = str(json.loads(receipt.read_text(encoding=_UTF_8))["node_version"])
        notices.append(Notice("Node.js, the agent runtime", node, "MIT", f"{packages.parent}/node/LICENSE"))
    if "playwright" in distributions:
        notices.append(
            Notice(
                "Node.js, the Playwright driver",
                f"as shipped in playwright {distributions['playwright']}",
                "MIT",
                f"{packages}/playwright/driver/LICENSE",
            )
        )
    return notices, unattributed


def _cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


def _table(notices: Sequence[Notice], heading: str) -> str:
    rows = "\n".join(
        f"| {_cell(n.component)} | {_cell(n.version)} | {_cell(n.licence)} | "
        f"{'none shipped' if n.text is None else '`' + n.text + '`'} |"
        for n in notices
    )
    header = "| Component | Version | Licence | Licence text in the package |\n| --- | --- | --- | --- |"
    return f"## {heading}\n\n{header}\n{rows}\n"


@dataclass(frozen=True)
class PackageNotices:
    """Everything one assembled package lists, and what it cannot list."""

    native: list[Notice]
    python: list[Notice]
    javascript: list[Notice]
    unattributed: list[str]

    def render(self, target: str) -> str:
        """Render the notices page."""
        sections = [
            _table(self.native, "Interpreter, programs and runtimes"),
            _table(self.python, "Python distributions"),
        ]
        if self.javascript:
            sections.append(_table(self.javascript, "JavaScript packages of the agent runtime"))
        return (
            "<!-- GENERATED FILE - DO NOT EDIT.\n"
            f"Regenerate with: uv run --no-sync python -m dev.packaging.native.third_party_notices --target {target} "
            "--build <the CMake binary directory>\n"
            "Source of truth: the package the assembly stages -->\n\n"
            f"# Third-party notices ({target})\n\n"
            f"This page lists every third-party component the {target} package installs,\n"
            "with its version, the licence it declares and where the package carries the\n"
            "licence text. Package assembly refuses to build while this page differs from\n"
            "what it stages, while a listed licence text is missing, and while any\n"
            "component declares the GNU General Public License or the GNU Affero General\n"
            "Public License.\n\n" + "\n".join(sections)
        )

    def every(self) -> list[Notice]:
        """Return every listed component."""
        return [*self.native, *self.python, *self.javascript]


def collect_notices(root: Path, layout: Mapping[str, str], files: Mapping[str, str]) -> PackageNotices:
    """Read what an assembled package root holds."""
    manifest = cast(Mapping[str, Any], json.loads((root / files["package_manifest"]).read_text(encoding=_UTF_8)))
    distributions = installed_distributions(root / layout["packages"])
    versions = {str(canonicalize_name(d.metadata["Name"])): d.version for d in distributions}
    native, unattributed = _native_notices(root, layout, files, manifest, versions)
    packages = PurePosixPath(layout["packages"])
    return PackageNotices(
        native,
        python_notices(distributions, layout["packages"]),
        javascript_notices(root / packages.parent, str(packages.parent)),
        unattributed,
    )


def strong_copyleft(notices: PackageNotices, distributions: Iterable[Distribution] = ()) -> list[str]:
    """Name each component whose declared licence is the GPL or AGPL."""
    named = [n.component for n in notices.every() if _STRONG_COPYLEFT.search(n.licence)]
    named.extend(
        canonicalize_name(d.metadata["Name"])
        for d in _third_party(distributions)
        if _STRONG_COPYLEFT.search(_distribution_statements(d))
    )
    return sorted(set(named))


def package_refusals(root: Path, notices: PackageNotices, distributions: Iterable[Distribution]) -> list[str]:
    """Return why this package may not ship, independent of the committed page."""
    refusals = []
    copyleft = strong_copyleft(notices, distributions)
    if copyleft:
        refusals.append(
            f"GPL- or AGPL-licensed components: {', '.join(copyleft)}; "
            "the installer carries no strong-copyleft component"
        )
    missing = sorted(n.text for n in notices.native if n.text is not None and not (root / n.text).exists())
    if missing:
        refusals.append(f"licence texts the package does not carry: {', '.join(missing)}")
    if notices.unattributed:
        refusals.append(f"program files attributed to no listed component: {', '.join(notices.unattributed)}")
    return refusals


def require_current_notices(
    target: str,
    root: Path,
    layout: Mapping[str, str],
    files: Mapping[str, str],
    binary_dir: Path,
    repo_root: Path = REPO_ROOT,
) -> None:
    """Write the fresh page into the build tree, then refuse a package that may not ship or a stale page."""
    notices = collect_notices(root, layout, files)
    fresh = notices.render(target).encode(_UTF_8)
    rendered = build_render_path(binary_dir, target)
    rendered.parent.mkdir(parents=True, exist_ok=True)
    rendered.write_bytes(fresh)
    refusals = package_refusals(root, notices, installed_distributions(root / layout["packages"]))
    if refusals:
        raise ValueError("The package may not ship: " + "; ".join(refusals))
    page = target_path(target, repo_root)
    if not page.is_file() or page.read_bytes() != fresh:
        raise ValueError(
            f"{page} does not list what this package stages. Review {rendered}, then run "
            f"python -m dev.packaging.native.third_party_notices --target {target} --build {binary_dir} "
            "and commit the page."
        )


def main(argv: list[str] | None = None) -> int:
    """Copy the page the last assembly rendered into the docs, or verify it with ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="The package target, such as windows-x86-64")
    parser.add_argument("--build", type=Path, required=True, help="The CMake binary directory that assembled it")
    parser.add_argument("--check", action="store_true", help="Exit 1 when the committed page is stale.")
    args = parser.parse_args(argv)
    rendered, page = build_render_path(args.build, args.target), target_path(args.target)
    if not rendered.is_file():
        print(f"REFUSED: {rendered} does not exist; assemble the package first", file=sys.stderr)
        return 1
    if args.check:
        if not page.is_file() or page.read_bytes() != rendered.read_bytes():
            print(f"DRIFT: {page} differs from {rendered}", file=sys.stderr)
            return 1
        print(f"OK: {page} is fresh.")
        return 0
    page.write_bytes(rendered.read_bytes())
    print(f"Wrote {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
