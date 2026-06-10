"""Build only documentation pages affected by local source changes."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_ROOT_FOR_DIRECT_INVOCATION = Path(__file__).resolve().parents[2]
if str(_ROOT_FOR_DIRECT_INVOCATION) not in sys.path:
    sys.path.insert(0, str(_ROOT_FOR_DIRECT_INVOCATION))

from dev.docs.apidocs import ApiStubManager
from dev.docs.cli_reference import generate_cli_reference

DOC_SUFFIXES = {".md", ".rst"}
PY_SUFFIX = ".py"


@dataclass(frozen=True)
class DocBuildPlan:
    """Selected documentation sources and generated surfaces needed to build them."""

    targets: list[Path]
    full_build_required: bool
    api_scaffold_required: bool = False
    cli_reference_required: bool = False


def _repo_root() -> Path:
    """Return the repository root for this script."""
    return Path(__file__).resolve().parents[2]


def _executable(name: str) -> str:
    """Resolve an executable name from PATH or abort with a clear error."""
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"Required executable not found on PATH: {name}")
    return resolved


def _run_git(args: list[str], repo_root: Path) -> list[Path]:
    """Run a git path query and return repository-relative paths.

    Args:
        args: Arguments after ``git``.
        repo_root: Repository root used as the process working directory.

    Returns:
        Unique paths listed by git, in output order.
    """
    result = subprocess.run(  # noqa: S603
        [_executable("git"), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    seen: set[Path] = set()
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = Path(line.strip())
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def changed_paths(repo_root: Path, base: str) -> list[Path]:
    """Return changed tracked and untracked paths relevant to the worktree.

    Args:
        repo_root: Repository root.
        base: Git revision used for committed branch changes.

    Returns:
        Deduplicated repository-relative paths.
    """
    queries = [
        ["diff", "--name-only", "--diff-filter=ACMRD", f"{base}...HEAD"],
        ["diff", "--cached", "--name-only", "--diff-filter=ACMRD"],
        ["diff", "--name-only", "--diff-filter=ACMRD"],
        ["ls-files", "--others", "--exclude-standard"],
    ]
    seen: set[Path] = set()
    paths: list[Path] = []
    for query in queries:
        for path in _run_git(query, repo_root):
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def _is_documentable_source(rel_path: Path) -> bool:
    """Return whether a changed Python path participates in API stubs."""
    parts = rel_path.parts
    if len(parts) < 3 or parts[:2] != ("src", "aeat"):
        return False
    package_parts = parts[2:]
    if not package_parts or rel_path.suffix != PY_SUFFIX:
        return False
    if rel_path.name in {"conftest.py"}:
        return False
    if rel_path.name.startswith(("test_", "_test_")):
        return False
    if package_parts[0] in {"tests", "_data"}:
        return False
    return package_parts[:2] != ("entrypoints", "cli")


def _module_name_for_source(rel_path: Path) -> str:
    """Map a repository-relative Python path under ``src/`` to a dotted module."""
    rel_module = rel_path.relative_to("src").with_suffix("")
    parts = list(rel_module.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _api_stub_targets(module_name: str, docs_api: Path, *, include_parents: bool) -> list[Path]:
    """Return the module stub and package-parent stubs that may be affected."""
    modules = [module_name]
    if include_parents:
        parts = module_name.split(".")
        modules = [".".join(parts[:idx]) for idx in range(1, len(parts) + 1)]
    return [docs_api / f"{name}.rst" for name in modules]


def planned_doc_targets(repo_root: Path, paths: list[Path]) -> DocBuildPlan:
    """Plan Sphinx file targets for changed docs/source paths.

    Args:
        repo_root: Repository root.
        paths: Repository-relative changed paths.

    Returns:
        A documentation build plan. Targets are absolute paths under ``docs/``.
    """
    docs_root = repo_root / "docs"
    docs_api = docs_root / "api"
    targets: list[Path] = []
    full_build_required = False
    api_scaffold_required = False
    source_modules: list[tuple[str, bool]] = []
    cli_reference_required = False

    for rel_path in paths:
        absolute = repo_root / rel_path
        if rel_path == Path("docs/conf.py"):
            full_build_required = True
        elif rel_path.parts[:1] == ("docs",) and rel_path.suffix in DOC_SUFFIXES and absolute.is_file():
            targets.append(absolute)
        elif _is_documentable_source(rel_path):
            api_scaffold_required = True
            include_parents = rel_path.name == "__init__.py" or not (repo_root / rel_path).is_file()
            source_modules.append((_module_name_for_source(rel_path), include_parents))
        elif (
            rel_path.parts[:3] == ("src", "aeat", "entrypoints")
            and len(rel_path.parts) > 3
            and rel_path.parts[3] == "cli"
            and rel_path.suffix == PY_SUFFIX
        ):
            cli_reference_required = True

    if api_scaffold_required:
        for module_name, include_parents in source_modules:
            targets.extend(_api_stub_targets(module_name, docs_api, include_parents=include_parents))
    if cli_reference_required:
        targets.extend(
            target
            for target in (
                docs_root / "cli" / "index.rst",
                docs_root / "cli" / "app.rst",
                docs_root / "cli" / "config.rst",
                docs_root / "cli" / "automation.rst",
                docs_root / "cli" / "schemas.rst",
                docs_root / "cli" / "retired.rst",
            )
            if target.is_file()
        )

    seen: set[Path] = set()
    unique_targets: list[Path] = []
    for target in targets:
        resolved = target.resolve()
        planned_api_stub = api_scaffold_required and target.parent == docs_api and target.suffix == ".rst"
        if resolved not in seen and (resolved.is_file() or planned_api_stub):
            seen.add(resolved)
            unique_targets.append(resolved)
    return DocBuildPlan(
        targets=unique_targets,
        full_build_required=full_build_required,
        api_scaffold_required=api_scaffold_required,
        cli_reference_required=cli_reference_required,
    )


def _single_page_source_set(docs_root: Path, targets: list[Path]) -> list[str]:
    """Return source files needed to resolve links for a canonical page build.

    A canonical single-page build writes only the requested output page, but it
    still needs the non-API documentation graph available so MyST links and
    toctrees resolve like the real handbook. The generated API tree is
    intentionally excluded because importing autodoc modules is the expensive
    and fragile part this mode avoids.

    Args:
        docs_root: Documentation source root.
        targets: Absolute source files requested for output.

    Returns:
        POSIX-style paths relative to ``docs_root`` for the allowed source set.
    """
    excluded_roots = {
        (docs_root / "api").resolve(),
        (docs_root / "_build").resolve(),
        (docs_root / "_inventories").resolve(),
    }
    sources: list[str] = []
    for source in sorted(docs_root.rglob("*")):
        if source.suffix not in DOC_SUFFIXES:
            continue
        resolved = source.resolve()
        if any(resolved == root or root in resolved.parents for root in excluded_roots):
            continue
        sources.append(source.relative_to(docs_root).as_posix())
    for target in targets:
        relative = target.relative_to(docs_root).as_posix()
        if relative not in sources:
            sources.append(relative)
    return sources


def _is_generated_doc(docs_root: Path, target: Path) -> bool:
    """Return whether a documentation target belongs to a generated docs tree."""
    try:
        relative = target.relative_to(docs_root)
    except ValueError:
        return False
    return bool(relative.parts) and relative.parts[0] in {"api", "cli"}


def _copy_docs_source(docs_root: Path, target: Path) -> None:
    """Copy documentation sources without repository-local build artifacts."""
    shutil.copytree(docs_root, target, ignore=shutil.ignore_patterns("_build"))


def remove_noncanonical_build_entries(docs_root: Path) -> None:
    """Remove stale noncanonical entries directly under ``docs/_build``."""
    build_root = docs_root / "_build"
    if not build_root.exists():
        return
    allowed = (build_root / "html").resolve()
    for entry in build_root.iterdir():
        resolved = entry.resolve()
        if resolved == allowed:
            continue
        if build_root.resolve() not in resolved.parents:
            raise SystemExit(f"Refusing to remove docs build entry outside docs/_build: {entry}")
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _targets_for_docs_root(original_docs_root: Path, copied_docs_root: Path, targets: list[Path]) -> list[Path]:
    """Map repository documentation targets into a copied documentation root."""
    mapped: list[Path] = []
    for target in targets:
        try:
            relative = target.relative_to(original_docs_root)
        except ValueError:
            continue
        copied = copied_docs_root / relative
        if copied.is_file():
            mapped.append(copied)
    return mapped


def build_docs(repo_root: Path, plan: DocBuildPlan, *, strict: bool, single_page: bool = False) -> None:
    """Run Sphinx against the selected targets.

    Full builds write the actual documentation output under ``docs/_build/html``.
    Targeted changed-page checks copy ``docs/`` to an OS temporary source tree
    and write temporary output there, so generated API/CLI sources and preview
    artifacts never pollute the repository. Single-page builds are an explicit
    exception: they write the requested page into the canonical HTML output
    directory while excluding generated API/CLI/autodoc surfaces.
    """
    docs_root = repo_root / "docs"
    targets = plan.targets
    command = [sys.executable, "-m", "sphinx", "-b", "html", "-j", "auto"]
    env = {**os.environ, "AEAT_DOCS_PROJECT_ROOT": str(repo_root)}
    if strict:
        command.extend(["-n", "-W"])
        env["AEAT_DOCS_OFFLINE"] = "1"
        if (docs_root / "_build" / "html" / "objects.inv").is_file():
            env["AEAT_DOCS_SELF_INVENTORY"] = "1"
    if not plan.full_build_required:
        env["AEAT_DOCS_OFFLINE"] = "1"
        if single_page:
            relative_sources = _single_page_source_set(docs_root, targets)
            master_source = "index.md"
        else:
            relative_sources = [target.relative_to(docs_root).as_posix() for target in targets]
            master_source = relative_sources[0]
        env["AEAT_DOCS_ONLY"] = os.pathsep.join(relative_sources)
        env["AEAT_DOCS_MASTER_DOC"] = Path(master_source).with_suffix("").as_posix()
        if single_page:
            env["AEAT_DOCS_SINGLE_PAGE"] = "1"

    if plan.full_build_required:
        remove_noncanonical_build_entries(docs_root)
        out_dir = docs_root / "_build" / "html"
        command.extend(
            [
                str(docs_root),
                str(out_dir),
            ]
        )
        result = subprocess.run(command, cwd=repo_root, env=env, check=False)  # noqa: S603
    elif single_page:
        remove_noncanonical_build_entries(docs_root)
        with tempfile.TemporaryDirectory(prefix="aeat-docs-doctrees-") as tmp:
            out_dir = docs_root / "_build" / "html"
            command.extend(
                [
                    "-d",
                    str(Path(tmp) / "doctrees"),
                    str(docs_root),
                    str(out_dir),
                    *(target.relative_to(repo_root).as_posix() for target in targets),
                ]
            )
            result = subprocess.run(command, cwd=repo_root, env=env, check=False)  # noqa: S603
    else:
        with tempfile.TemporaryDirectory(prefix="aeat-docs-changed-") as tmp:
            temp_root = Path(tmp)
            temp_docs_root = temp_root / "docs-source"
            _copy_docs_source(docs_root, temp_docs_root)
            if plan.api_scaffold_required:
                ApiStubManager(src_aeat=repo_root / "src" / "aeat", docs_api=temp_docs_root / "api").scaffold()
            if plan.cli_reference_required:
                generate_cli_reference(temp_docs_root)
            temp_targets = _targets_for_docs_root(docs_root, temp_docs_root, targets)
            if not temp_targets:
                print("No existing documentation targets remained after temporary generation.", flush=True)
                return
            out_dir = temp_root / "html"
            specific_command = [*command, str(temp_docs_root), str(out_dir), *(str(target) for target in temp_targets)]
            result = subprocess.run(specific_command, cwd=repo_root, env=env, check=False)  # noqa: S603
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def update_rag_index(repo_root: Path) -> None:
    """Refresh the resident vaultspec-rag service index after docs changes."""
    rag = _executable("vaultspec-rag")
    status = subprocess.run(  # noqa: S603
        [rag, "server", "service", "status"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0 or "stopped" in (status.stdout + status.stderr).lower():
        start = subprocess.run([rag, "server", "service", "start"], cwd=repo_root, check=False)  # noqa: S603
        if start.returncode != 0:
            raise SystemExit(start.returncode)
    indexed = subprocess.run([rag, "index", "--type", "all", "--port", "8766"], cwd=repo_root, check=False)  # noqa: S603
    if indexed.returncode != 0:
        raise SystemExit(indexed.returncode)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for changed-document builds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional repository-relative paths to build instead of scanning git changes.",
    )
    parser.add_argument("--base", default="HEAD", help="Git revision used for committed branch changes.")
    parser.add_argument("--strict", action="store_true", help="Use nitpicky warnings-as-errors mode.")
    parser.add_argument(
        "--rag-index", action="store_true", help="Refresh the service-backed RAG index after a clean build."
    )
    parser.add_argument(
        "--single-page",
        metavar="PATH",
        help=("Build one documentation source into docs/_build/html without rebuilding generated API/autodoc pages."),
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    if args.single_page and args.paths:
        raise SystemExit("--single-page cannot be combined with positional paths")
    paths = (
        [Path(args.single_page)]
        if args.single_page
        else ([Path(path) for path in args.paths] if args.paths else changed_paths(repo_root, args.base))
    )
    plan = planned_doc_targets(repo_root, paths)
    if args.single_page and (plan.full_build_required or len(plan.targets) != 1):
        raise SystemExit(f"--single-page requires one existing docs source file: {args.single_page}")
    if args.single_page and _is_generated_doc(repo_root / "docs", plan.targets[0]):
        raise SystemExit(
            "--single-page does not support generated API/CLI pages; use the explicit generator or full docs build."
        )
    if not plan.full_build_required and not plan.targets:
        print("No changed documentation targets detected.", flush=True)
        if args.rag_index:
            update_rag_index(repo_root)
        return 0

    if plan.full_build_required:
        print("Configuration changed; running an incremental full Sphinx build.", flush=True)
    elif args.single_page:
        print("Building canonical documentation page:", flush=True)
        print(f"  {plan.targets[0].relative_to(repo_root)}", flush=True)
    else:
        print("Building changed documentation targets:", flush=True)
        for target in plan.targets:
            print(f"  {target.relative_to(repo_root)}", flush=True)
    build_docs(repo_root, plan, strict=args.strict, single_page=bool(args.single_page))
    if args.rag_index:
        update_rag_index(repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
