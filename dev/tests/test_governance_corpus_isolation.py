"""Governance-corpus isolation gate: ``src/`` knows nothing of the scaffolding.

The decision corpus, the agent harness and the development tooling tree are
removable scaffolding layered over the product. By operator ruling the
direction is one-way and ABSOLUTE: nothing under ``src/`` -- shipped module,
test module, or shipped data -- may reference them, as an import, a path
literal, or prose.

What this gate owns, and what it does not
-----------------------------------------
``test_dev_path_isolation`` already closes the tooling tree for PYTHON modules
(imports, constructed paths, prose) and is proven. This gate closes the two
gaps beside it, and the division is deliberately non-overlapping so no site is
judged twice:

* the governance trees ``.vault`` and ``.vaultspec`` in Python modules; and
* all three trees in every NON-Python file under ``src/``.

The second is the gap that actually bled. ``src/cadrumo/_data/`` ships inside
the wheel, and a census row there naming a scanner in the development tree
hands the installed user a locator into a tree they never received -- a
reference to this project's own development backlog, shipped as product data.
An AST scan cannot see a TOML file at all, so a green Python-only boundary
gate reported clean while those rows accumulated. The coupling reached the
size it did because nothing was watching, which is the argument for a ratchet
rather than a one-time sweep.

No allowlist
------------
There is deliberately no exemption table. An allowlist is where the judgement
moves, and the ruling here admits no judgement: there is no legitimate reason
for a file under ``src/`` to name the scaffolding. A site that seems to need
one is a site whose logic belongs under ``dev/``, and that is the fix.

Anti-tautology coverage
-----------------------
Every check below is proven to BITE: a deliberate violation is planted under
an injectable root and the shared detector is asserted to return it. Every
detected form carries its own firing proof, and every near-miss the detector
must stay silent on carries its own silence proof -- the product's own
``cadrumo-vault/`` Drive folder, the ``vault_folder_name`` error keys, a
``.vaults`` sibling, and the POSIX device nodes. A firing proof alone cannot
tell a precise detector from one that fires on everything, and the near-misses
here are not hypothetical: all of them are live in this tree.

Vacuity floors on both populations keep an empty scan from reading as a clean
one, and a root-liveness assertion keeps the gate from passing because the
trees it names were renamed away.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT
from ..quality.governance_corpus_scan import (
    GOVERNANCE_TREE_ROOTS,
    GovernanceRefForm,
    find_governance_path_violations,
    find_governance_prose_violations,
    find_scaffolding_data_references,
    live_governance_roots,
    scannable_data_files,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT: Final[Path] = REPO_ROOT / "src"
_PKG_ROOT: Final[Path] = _SRC_ROOT / "cadrumo"

_UTF_8: Final[str] = "utf-8"

# Floors below which a hard-zero result is refused as a collapsed scan rather
# than accepted as a clean tree. Both are set well under the live counts so
# ordinary growth and deletion never touch them.
_MODULE_VACUITY_FLOOR: Final[int] = 4_000
_DATA_VACUITY_FLOOR: Final[int] = 10_000


# ---------------------------------------------------------------------------
# Live-tree inputs
# ---------------------------------------------------------------------------


def _live_modules() -> list[Path]:
    """Return every ``.py`` module in the product package."""
    return list(scan_directory(_PKG_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)))


def _planted(root: Path, rel: str, body: str) -> Path:
    """Write ``body`` at ``root/rel`` and return the path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding=_UTF_8)
    return path


# ---------------------------------------------------------------------------
# The gate's own subject must exist
# ---------------------------------------------------------------------------


def test_the_governance_roots_this_gate_names_exist() -> None:
    """Both declared roots are real directories, so the scan names something.

    A gate whose subject was renamed away reports exactly what a clean tree
    reports. This is the tripwire for that.
    """
    assert live_governance_roots() == set(GOVERNANCE_TREE_ROOTS), (
        "a declared governance root is not a live directory at the repository root; "
        "the scan patterns below would then be searching for nothing and passing vacuously"
    )


# ---------------------------------------------------------------------------
# Hard-zero live assertions
# ---------------------------------------------------------------------------


def test_no_src_module_builds_a_governance_corpus_path() -> None:
    """No module under ``src/`` constructs a path into ``.vault`` or ``.vaultspec``."""
    modules = _live_modules()
    assert len(modules) >= _MODULE_VACUITY_FLOOR, (
        f"vacuity check: fewer than {_MODULE_VACUITY_FLOOR} modules were found under {_SRC_ROOT}; "
        "a hard-zero result from a collapsed scan reads as clean without being one"
    )
    offenders = find_governance_path_violations(modules, src_root=_SRC_ROOT)
    assert offenders == [], (
        "modules under src/ build paths into the governance corpus (absolute one-way boundary):\n"
        + "\n".join(f"  [{v.form}] {v.module_path}:{v.lineno} -> {v.detail!r}" for v in offenders)
    )


def test_no_src_prose_names_the_governance_corpus() -> None:
    """No comment, docstring or multi-line string under ``src/`` cites the corpus."""
    modules = _live_modules()
    assert len(modules) >= _MODULE_VACUITY_FLOOR, "vacuity check: the module scan collapsed"
    offenders = find_governance_prose_violations(modules, src_root=_SRC_ROOT)
    assert offenders == [], (
        "prose under src/ names the governance corpus (awareness in any form is a violation):\n"
        + "\n".join(f"  [{v.source_kind}] {v.module_path}:{v.lineno} -> {v.detail!r}" for v in offenders)
    )


def test_no_shipped_data_file_names_removable_scaffolding() -> None:
    """No non-Python file under ``src/`` names a tree the installed user lacks.

    This is the family that closes the wheel-shipped data hole: an AST scan
    cannot read a TOML row, so nothing previously watched this population.
    """
    data_files = scannable_data_files(_SRC_ROOT)
    assert len(data_files) >= _DATA_VACUITY_FLOOR, (
        f"vacuity check: fewer than {_DATA_VACUITY_FLOOR} non-Python files were found under {_SRC_ROOT}; "
        "a hard-zero result from a collapsed scan reads as clean without being one"
    )
    offenders = find_scaffolding_data_references(data_files, src_root=_SRC_ROOT)
    assert offenders == [], (
        "non-Python files under src/ name removable scaffolding; _data/** ships in the wheel, "
        "so these locators reach a tree the installed user never received:\n"
        + "\n".join(f"  [{r.tree}] {r.file_path}:{r.lineno} -> {r.detail!r}" for r in offenders)
    )


# ---------------------------------------------------------------------------
# Firing proofs: the Python path family
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "form"),
    [
        pytest.param('CORPUS = ".vault/adr/2026-01-01-thing-adr.md"\n', GovernanceRefForm.LITERAL, id="literal"),
        pytest.param('RULES = "./.vaultspec/rules/a.md"\n', GovernanceRefForm.LITERAL, id="relative-literal"),
        # Planted as a RAW literal, which is how a Windows path is actually
        # written in source. A non-raw form would make ``\r`` a carriage
        # return, and a value spanning lines is prose by rule, not a path --
        # so the non-raw fixture would prove nothing about path detection.
        pytest.param(r'RULES = r"..\.vaultspec\rules\a.md"' "\n", GovernanceRefForm.LITERAL, id="windows-literal"),
        pytest.param(
            'from pathlib import Path\nX = Path(root) / ".vault" / "adr"\n',
            GovernanceRefForm.PATH_JOIN,
            id="path-join",
        ),
        pytest.param(
            'from pathlib import Path\nX = ".vault" / root\n',
            GovernanceRefForm.PATH_JOIN,
            id="reversed-join-operand",
        ),
        pytest.param('import os\nX = os.path.join(root, ".vault", "adr")\n', GovernanceRefForm.CALL_JOIN, id="os-join"),
        pytest.param(
            'from pathlib import Path\nX = Path(root, ".vaultspec")\n', GovernanceRefForm.CALL_JOIN, id="factory"
        ),
        pytest.param('X = f"{root}/.vault/adr/x.md"\n', GovernanceRefForm.FSTRING, id="fstring"),
    ],
)
def test_path_scanner_catches_every_planted_form(tmp_path: Path, body: str, form: GovernanceRefForm) -> None:
    path = _planted(tmp_path, "cadrumo/core/_planted.py", body)
    violations = find_governance_path_violations([path], src_root=tmp_path)
    assert any(v.form is form for v in violations), (
        f"the {form} form was planted and the scanner stayed silent: {violations!r}"
    )


def test_path_scanner_catches_a_planted_test_module(tmp_path: Path) -> None:
    """The boundary is awareness, not installed-user breakage: test modules count too."""
    path = _planted(tmp_path, "cadrumo/tests/test_planted.py", 'CORPUS = ".vault/audit/x.md"\n')
    violations = find_governance_path_violations([path], src_root=tmp_path)
    assert [v.root for v in violations] == [".vault"]


# ---------------------------------------------------------------------------
# Silence proofs: the near-misses this tree really contains
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "why"),
    [
        pytest.param(
            'KEY = "adapters.outbound.storage.google_drive.errors.vault_folder_name_blank"\n',
            "a dotted attribute path ending in a vault_* error key is product vocabulary",
            id="dotted-error-key",
        ),
        pytest.param(
            'FOLDER = "cadrumo-vault/calc-sheets/303-1T-2026"\n',
            "the operator's encrypted Drive folder is the product's own store",
            id="drive-folder",
        ),
        pytest.param(
            'OWNERSHIP_KEY = "cadrumo_vault_app"\n',
            "the Drive ownership marker is product vocabulary",
            id="ownership-marker",
        ),
        pytest.param('NAME = "vault"\n', "a bare word carries no path identity", id="bare-word"),
        pytest.param('X = ".vaults/elsewhere.md"\n', "a longer segment is a different directory", id="longer-segment"),
        pytest.param(
            'import sys\nT = "CONOUT$" if sys.platform == "win32" else "/dev/tty"\n',
            "a POSIX device node is not a repository tree",
            id="device-node",
        ),
    ],
)
def test_path_scanner_stays_silent_on_live_near_misses(tmp_path: Path, body: str, why: str) -> None:
    path = _planted(tmp_path, "cadrumo/core/_planted.py", body)
    violations = find_governance_path_violations([path], src_root=tmp_path)
    assert violations == [], f"the scanner fired where it must stay silent ({why}): {violations!r}"


# ---------------------------------------------------------------------------
# Firing and silence proofs: the prose family
# ---------------------------------------------------------------------------


def test_prose_scanner_catches_a_comment_citing_a_decision_record(tmp_path: Path) -> None:
    path = _planted(tmp_path, "cadrumo/core/_planted.py", "# Ruled in .vault/adr/2026-01-01-thing-adr.md.\nX = 1\n")
    violations = find_governance_prose_violations([path], src_root=tmp_path)
    assert [v.source_kind for v in violations] == ["comment"]
    assert violations[0].root == ".vault"


def test_prose_scanner_catches_a_one_line_docstring_citing_the_harness(tmp_path: Path) -> None:
    path = _planted(tmp_path, "cadrumo/core/_planted.py", '"""Mirrors .vaultspec/rules/naming.md."""\nX = 1\n')
    violations = find_governance_prose_violations([path], src_root=tmp_path)
    assert [v.source_kind for v in violations] == ["string"]
    assert violations[0].root == ".vaultspec"


def test_prose_scanner_catches_a_backtick_wrapped_citation(tmp_path: Path) -> None:
    """Wrapping punctuation must not hide a citation, which is how they are usually written."""
    path = _planted(
        tmp_path, "cadrumo/core/_planted.py", '"""See ``.vault/audit/x-audit.md`` for the ruling.\n\nMore.\n"""\n'
    )
    violations = find_governance_prose_violations([path], src_root=tmp_path)
    assert [v.root for v in violations] == [".vault"]


def test_prose_scanner_stays_silent_on_product_vault_vocabulary(tmp_path: Path) -> None:
    path = _planted(
        tmp_path,
        "cadrumo/core/_planted.py",
        '"""Resolves the cadrumo-vault/ Drive folder and its cadrumo_vault_app marker.\n\n'
        'Raises on a blank storage.google_drive.vault_folder_name.\n"""\n',
    )
    violations = find_governance_prose_violations([path], src_root=tmp_path)
    assert violations == [], f"the product's own vault vocabulary must stay silent: {violations!r}"


# ---------------------------------------------------------------------------
# Firing and silence proofs: the shipped-data family
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "line", "tree"),
    [
        pytest.param("census.toml", 'reference = "dev/source_connectivity/discovery.py"', "dev", id="toml-dev-locator"),
        pytest.param("census.toml", 'reference = ".vault/adr/x-adr.md"', ".vault", id="toml-vault-locator"),
        pytest.param("manifest.json", '{"rules": ".vaultspec/rules/a.md"}', ".vaultspec", id="json-harness-locator"),
        pytest.param("notes.md", "Grounded in dev/registry/pipeline.py today.", "dev", id="markdown-prose"),
        pytest.param("config.yml", "baseline: ./dev/quality/baseline.json", "dev", id="yaml-relative"),
    ],
)
def test_data_scanner_catches_a_planted_locator(tmp_path: Path, name: str, line: str, tree: str) -> None:
    path = _planted(tmp_path, f"cadrumo/_data/{name}", f"# heading\n{line}\n")
    references = find_scaffolding_data_references([path], src_root=tmp_path)
    assert [(r.tree, r.lineno) for r in references] == [(tree, 2)]


@pytest.mark.parametrize(
    ("line", "why"),
    [
        pytest.param('sink = "/dev/null"', "a POSIX device node is not a repository tree", id="dev-null"),
        pytest.param('tty = "/dev/tty"', "a POSIX device node is not a repository tree", id="dev-tty"),
        pytest.param('scratch = "sandbox/dev/notes.json"', "another tree's nested directory", id="nested-elsewhere"),
        pytest.param('folder = "cadrumo-vault/calc-sheets"', "the product's own Drive folder", id="drive-folder"),
        pytest.param('key = "storage.google_drive.vault_folder_name"', "a dotted product key", id="dotted-key"),
        pytest.param('marker = "cadrumo_vault_app"', "the Drive ownership marker", id="ownership-marker"),
        pytest.param('summary = "The taxpayer\'s development costs are deducted."', "an English word", id="english"),
        pytest.param('note = "Handles devengada and devolucion stems."', "Spanish stems", id="spanish-stems"),
    ],
)
def test_data_scanner_stays_silent_on_near_misses(tmp_path: Path, line: str, why: str) -> None:
    path = _planted(tmp_path, "cadrumo/_data/census.toml", f"{line}\n")
    references = find_scaffolding_data_references([path], src_root=tmp_path)
    assert references == [], f"the data scanner fired where it must stay silent ({why}): {references!r}"


def test_data_scanner_skips_python_and_binaries(tmp_path: Path) -> None:
    """The data population excludes modules (owned by the AST families) and binaries."""
    _planted(tmp_path, "cadrumo/core/mod.py", 'X = "dev/thing.py"\n')
    _planted(tmp_path, "cadrumo/_data/doc.pdf", "dev/thing.py\n")
    _planted(tmp_path, "cadrumo/_data/rows.toml", 'x = "dev/thing.py"\n')
    selected = [p.name for p in scannable_data_files(tmp_path)]
    assert selected == ["rows.toml"], f"the data population must exclude modules and binaries: {selected!r}"
