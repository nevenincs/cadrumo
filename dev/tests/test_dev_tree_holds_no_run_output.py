"""`dev/` holds the harness, never the harness's output.

A development command produces two unrelated kinds of file, and the difference
is not visible from the write call. One is a CURATED SOURCE: a ledger of
rulings, a pinned matrix, a reviewed queue. It is read on the next run, its
diff is what a reviewer looks at, and losing it loses work. The other is RUN
OUTPUT: a coverage report, a findings dump, a captured stderr. It is written by
a run and read back by nothing, and losing it costs one re-run.

Run output has one home in this repository -- `.logs/<family>/<date>/<run>/`,
allocated by `dev.test_runs.paths.allocate_run_directory` and reclaimed whole
by the next `just clean-apply`. Output that lands beside its own harness under
`dev/` instead gets none of that: no clean reclaims it, no run identity
separates two measurements of the same tree, and it has to be hidden behind a
`.gitignore` entry to stay out of commits. That happened here. The terminology
coverage report was written to `dev/docs/terminology/evaluation/`, its recipe
called it "committed" while `.gitignore` hid it, and the contradiction survived
because nothing was checking.

So a dev-internal destination is DECLARED, not merely written. Every path under
`dev/` that a production module resolves is discovered from the parsed source
and matched against :data:`_CURATED_DEV_DESTINATIONS`; an undeclared one fails
this gate naming the module, the line and the path. The declaration is cheap
and the thought it forces is the point: writing the reason down is where an
author notices they are about to persist run output inside the harness.

What the discovery can see is stated rather than implied. It resolves a
destination only where the whole path is literal -- `Path(__file__)`, the
repository root, `.parent`, `.parents[n]`, `.with_name("x")` and `/ "segment"`
-- following module-level constants and zero-argument module functions up to a
small depth. A path assembled from a runtime value (an operator's `--work-dir`,
an `argparse` root, an interpolated name) is outside it and is left to the
refusals at those call sites. That boundary is narrower than the rule, and it
is the same boundary the `mkdtemp` prefix gate and the `var/` mint-site gate
draw around their own subjects: a gate that guessed at the unresolvable half
would report a population it never assembled.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT, UTF_8

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEV_ROOT: Final[Path] = REPO_ROOT / "dev"

#: Attribute calls that persist bytes or create a directory at their receiver.
_WRITE_ATTRIBUTES: Final[frozenset[str]] = frozenset({"mkdir", "touch", "write_bytes", "write_text"})

#: Names that mean the repository root when a module does not bind them itself.
_REPOSITORY_ROOT_NAMES: Final[frozenset[str]] = frozenset(
    {"REPOSITORY_ROOT", "REPO_ROOT", "ROOT", "_REPOSITORY_ROOT", "_REPO_ROOT", "_ROOT"},
)

#: How far a destination is followed through constants and zero-argument
#: functions before the expression is declared unresolvable. Deep enough for
#: the real chains (a constant built from a constant built from the root),
#: shallow enough that a cyclic binding cannot hang the gate.
_RESOLUTION_DEPTH: Final[int] = 6

#: Every path under `dev/` that a production module resolves, with the reason it
#: is a source rather than run output. A path here is read, or is a reviewed
#: file whose diff is the artefact; NONE of them is a measurement a run mints.
#: Adding a run's output to this mapping is the mistake the gate exists to stop
#: -- send it to `.logs/` through `allocate_run_directory` instead.
_CURATED_DEV_DESTINATIONS: Final[dict[str, str]] = {
    "dev/ci/python-runtime-matrix.json": "the pinned interpreter matrix the runtime gates read",
    "dev/docs/terminology/evaluation/held-out-queries.json": "the committed query set a sweep is measured against",
    "dev/docs/terminology/ratification/synonym-candidates.json": "the reviewed synonym queue; mining preserves review",
    "dev/docs/terminology/relevance/relevance.json": "the committed mapping coverage is measured against",
    "dev/quality/import_checker.py": "the module the import gate spawns; read, never written",
    "dev/quality/import_load_worker.py": "the module the load probe spawns; read, never written",
    "dev/quality/secure_store_write_path.toml": "the declared write paths the gate checks source against",
    "dev/registry/analysis/casilla_lineage_ledger.toml": "the reviewed lineage ledger; its diff is the artefact",
    "dev/registry/analysis/casilla_lineage_rulings.toml": "the authored rulings the lineage seed resolves against",
    "dev/registry/analysis/facts_iva_retirement.toml": "the authored retirement ledger the facts screen reads",
    "dev/registry/analysis/legal_citation_period_ledger.toml": "authored citation exceptions, each with a reason",
    "dev/registry/analysis/regulatory_prose_parser_channel.toml": (
        "the authored channel ledger; its diff is the artefact"
    ),
    "dev/registry/conformance_vectors/modelo_200_2025_y_siguientes.toml": (
        "a pinned vector the export proof compares against"
    ),
    "dev/registry/pipeline/generated_export_bootstrap_targets.toml": "the authored targets candidate staging reads",
    "dev/registry/pipeline/generated_tree_dispositions.toml": "the authored dispositions the tree screens read",
    "dev/release/burned_versions.json": "the release ledger of burned versions; durable state",
}


class _UnresolvableError(Exception):
    """The expression is not a literal path chain, so this gate does not judge it."""


def _module_bindings(tree: ast.Module) -> tuple[dict[str, ast.expr], dict[str, ast.expr]]:
    """Return module-level name bindings and zero-argument function results.

    Both are followed because a destination is routinely named once and used
    elsewhere: a `Final` constant at module scope, or a small accessor whose
    single `return` is the path. A function taking arguments is skipped -- its
    result depends on a caller this gate cannot see.
    """
    names: dict[str, ast.expr] = {}
    functions: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            names[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            names[node.target.id] = node.value
        elif isinstance(node, ast.FunctionDef):
            returned = [
                child.value for child in ast.walk(node) if isinstance(child, ast.Return) and child.value is not None
            ]
            takes_arguments = bool(node.args.args or node.args.posonlyargs or node.args.kwonlyargs)
            if len(returned) == 1 and not takes_arguments:
                functions[node.name] = returned[0]
    return names, functions


def _resolve(
    expression: ast.expr,
    module: Path,
    names: dict[str, ast.expr],
    functions: dict[str, ast.expr],
    depth: int = 0,
) -> Path:
    """Resolve a literal path expression to the file it names, or refuse.

    Raises:
        _UnresolvableError: When any link in the chain is not a literal this gate
            can evaluate, including when the depth ceiling is reached.
    """
    if depth > _RESOLUTION_DEPTH:
        raise _UnresolvableError
    step = depth + 1
    match expression:
        case ast.Call(func=ast.Name(id="Path"), args=[ast.Name(id="__file__")]):
            return module
        case ast.Name(id=name) if name in names:
            return _resolve(names[name], module, names, functions, step)
        case ast.Name(id=name) if name in _REPOSITORY_ROOT_NAMES:
            return REPO_ROOT
        case ast.Call(func=ast.Name(id=name), args=[]) if name in functions:
            return _resolve(functions[name], module, names, functions, step)
        case ast.BinOp(op=ast.Div(), left=left, right=ast.Constant(value=str() as segment)):
            return _resolve(left, module, names, functions, step) / segment
        case ast.Attribute(value=value, attr="parent"):
            return _resolve(value, module, names, functions, step).parent
        case ast.Call(func=ast.Attribute(value=value, attr="resolve")):
            return _resolve(value, module, names, functions, step)
        case ast.Call(func=ast.Attribute(value=value, attr="with_name"), args=[ast.Constant(value=str() as name)]):
            return _resolve(value, module, names, functions, step).with_name(name)
        case ast.Subscript(value=ast.Attribute(value=value, attr="parents"), slice=ast.Constant(value=int() as index)):
            parents = _resolve(value, module, names, functions, step).parents
            if index >= len(parents):
                raise _UnresolvableError
            return parents[index]
        case _:
            raise _UnresolvableError


def _production_modules() -> list[Path]:
    """Return every `dev/` module that is not itself a test."""
    return [
        path
        for path in sorted(_DEV_ROOT.rglob("*.py"))
        if "tests" not in path.relative_to(REPO_ROOT).parts and "__pycache__" not in path.parts
    ]


def _dev_destinations(module: Path, source: str) -> list[tuple[int, str]]:
    """Return every `dev/`-internal path this module resolves, as (line, relative path).

    Two shapes are discovered, because the defect appears as either. A WRITE
    SITE is a persist call on a resolvable receiver, which is the direct form.
    A PATH PRODUCER is a constant or accessor whose value is a dev-internal
    file, which is the form the terminology coverage report took: the write
    happened one module away, on a local whose value came through a ternary,
    and only the producer was resolvable.

    A producer is judged only when it names a FILE. Resolving a directory is
    how a module reaches its own package -- the source root it globs, the
    sibling tree it hashes -- and those are reads, not destinations. A write
    site is judged whatever it resolves to, so ``mkdir`` on a directory inside
    ``dev/`` is still a finding.
    """
    tree = ast.parse(source)
    names, functions = _module_bindings(tree)
    found: dict[tuple[int, str], None] = {}

    def record(node_line: int, expression: ast.expr, *, files_only: bool) -> None:
        try:
            destination = _resolve(expression, module, names, functions)
        except _UnresolvableError:
            return
        if _DEV_ROOT not in destination.parents:
            return
        if files_only and not destination.suffix:
            return
        found[(node_line, destination.relative_to(REPO_ROOT).as_posix())] = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _WRITE_ATTRIBUTES:
            record(node.lineno, node.func.value, files_only=False)
    for expression in (*names.values(), *functions.values()):
        if isinstance(expression, ast.Constant):
            continue
        record(getattr(expression, "lineno", 0), expression, files_only=True)

    return sorted(found)


def test_every_dev_internal_destination_is_a_declared_source() -> None:
    """A `dev/`-internal path is a declared curated source, or this fails naming it.

    The failure is not "you wrote a file". It is "you resolved a path inside
    the harness and did not say why it is a source". If the answer is that it
    is a measurement, the fix is `allocate_run_directory` and `.logs/`, not a
    new line in the mapping.
    """
    undeclared: list[str] = []
    for module in _production_modules():
        source = module.read_text(encoding=UTF_8)
        relative_module = module.relative_to(REPO_ROOT).as_posix()
        for line, destination in _dev_destinations(module, source):
            if destination not in _CURATED_DEV_DESTINATIONS:
                undeclared.append(f"{relative_module}:{line} -> {destination}")

    assert not undeclared, (
        "undeclared path inside dev/. Run output belongs in .logs/ through "
        "dev.test_runs.paths.allocate_run_directory; a curated source belongs in "
        "_CURATED_DEV_DESTINATIONS with the reason it is a source:\n  " + "\n  ".join(undeclared)
    )


def test_every_declared_destination_still_exists() -> None:
    """A declaration for a path nothing holds is an exception that reads as coverage.

    The mapping's whole value is that each entry states why a real file is a
    source. An entry outliving its file leaves the next reader believing a
    dev-internal destination was considered and approved, when what happened is
    that it was deleted and the declaration was not.
    """
    missing = [path for path in _CURATED_DEV_DESTINATIONS if not (REPO_ROOT / path).exists()]
    assert not missing, f"declared curated dev sources no longer exist: {missing}"


def test_the_discovery_reports_run_output_written_beside_its_harness(tmp_path: Path) -> None:
    """The defect this gate was written for is detected, in both of its shapes.

    The fixture reproduces the terminology coverage report as it stood: an
    accessor returning a path beside the harness, and a write through it. Both
    the producer and the write site must be reported, because the real defect
    offered only one of them -- the write happened in a sibling module.
    """
    module = _DEV_ROOT / "docs" / "terminology" / "_synthetic_regression_probe.py"
    source = (
        "from pathlib import Path\n"
        "\n"
        "def coverage_report_path() -> Path:\n"
        '    return Path(__file__).resolve().parent / "evaluation" / "coverage-report.json"\n'
        "\n"
        "def write(payload: str) -> None:\n"
        "    coverage_report_path().write_text(payload)\n"
    )
    del tmp_path

    destinations = _dev_destinations(module, source)

    reported = {destination for _line, destination in destinations}
    assert reported == {"dev/docs/terminology/evaluation/coverage-report.json"}
    assert len(destinations) == 2, f"expected the producer and the write site, got {destinations}"
    assert all(destination not in _CURATED_DEV_DESTINATIONS for _line, destination in destinations), (
        "the probe's destination must not be declared, or the gate proves nothing"
    )
