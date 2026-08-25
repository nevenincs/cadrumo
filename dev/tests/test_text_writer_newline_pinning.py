"""CI gate: every text writer pins its line terminator explicitly.

``Path.write_text`` and text-mode ``open`` default to ``newline=None``, which
translates every ``\\n`` to ``os.linesep`` on write. On Windows that is CRLF,
while the committed tree is ``eol=lf`` (see ``.gitattributes``). A writer
without an explicit terminator therefore rewrites whole files on disk while
``text=auto`` normalisation keeps ``git diff`` silent about it -- the drift is
invisible in review and surfaces only as an unexplained working-tree delta.

**The discriminator is the module kind, not the directory.** Only modules named
``test_*.py`` are out of scope; every other module is gated, including support
modules that happen to live under a ``tests/`` package. That choice is
deliberate and was paid for: an earlier sweep scoped by "under ``tests/``" and
so missed four SUPPORT modules that write COMMITTED artefacts -- the size-budget
baseline and three fixture sidecar generators -- which kept translating their
outputs. The honest discriminator is "does this writer target a tracked
artefact", which no static pass can decide; "is this a ``test_*.py`` module" is
the closest structural proxy that needs no hand-maintained include-list and so
cannot rot. Gating the residual ``tmp_path``-only support writers is the price,
and it is cheap: a pinned terminator is correct for a test fixture too.

Exemptions are keyed by ``(path, qualified function name)``, never by path
alone. A file-keyed exemption silently inherits: a new, unrelated writer added
to that same file later would be exempted too, and nobody would notice the gate
had stopped covering it. ``test_an_exemption_does_not_cover_the_rest_of_its_file``
is the standing proof that this cannot happen.
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Source roots scanned by this gate.
SCAN_ROOTS: tuple[str, ...] = ("dev", "src/cadrumo", "packaging")

#: Lowest plausible number of scanned modules. A green result below this floor
#: would mean "nothing was checked" rather than "nothing is wrong".
MIN_SCANNED_MODULES = 700

#: Writers that legitimately do not pin a terminator, keyed by
#: ``(repository-relative path, qualified function name)`` with a stated reason.
#: Keying by function is load-bearing -- see the module docstring.
EXEMPTIONS: dict[tuple[str, str], str] = {
    (
        "src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_writer.py",
        "write_sealed_archive",
    ): ("tarfile.open(mode='w:gz') is a BINARY archive handle, not a text stream. It takes no newline argument."),
    ("dev/locales/manager.py", "LocaleManager.allow_identical"): (
        "guard.write_text() is CatalogueWriteGuard.write_text, not Path.write_text -- the "
        "AST matcher keys on the attribute name alone. It delegates to atomic_write_text, "
        "which encodes the string to bytes in Python and writes them through a BINARY "
        "NamedTemporaryFile handle, so no newline argument applies and no translation occurs."
    ),
    ("dev/locales/manager.py", "_rewrite_locale_mapping"): (
        "Same guard.write_text() shape as LocaleManager.allow_identical above: a binary "
        "atomic-write handle underneath, immune to the CRLF-drift this gate guards against."
    ),
}


@dataclass(frozen=True)
class Finding:
    """One unpinned text write."""

    path: str
    line: int
    function: str
    call: str

    def format(self) -> str:
        return f"{self.path}:{self.line} in {self.function}() -- {self.call} has no explicit newline="


def _text_mode(node: ast.Call) -> str | None:
    """Return the mode string of an ``open``-shaped call, or None if not text-write."""
    func = node.func
    mode: object = None
    args = node.args
    if isinstance(func, ast.Name) and len(args) >= 2 and isinstance(args[1], ast.Constant):
        mode = args[1].value
    elif isinstance(func, ast.Attribute) and args and isinstance(args[0], ast.Constant):
        mode = args[0].value
    for keyword in node.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            mode = keyword.value.value
    if not isinstance(mode, str):
        return None
    if "b" in mode or not ("w" in mode or "a" in mode):
        return None
    return mode


def unpinned_writers(path: str, tree: ast.Module) -> list[Finding]:
    """Return every text write in *tree* that does not pin ``newline=``.

    Exposed as a pure function so the teeth tests below can drive it with
    synthetic sources instead of depending on the state of the real tree.
    """
    findings: list[Finding] = []

    def _record(call: ast.Call, scope: tuple[str, ...]) -> None:
        func = call.func
        keywords = {k.arg for k in call.keywords if k.arg}
        if isinstance(func, ast.Attribute) and func.attr == "write_text":
            description = "write_text(...)"
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = _text_mode(call)
            description = f"open(mode={mode!r})" if mode else ""
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            mode = _text_mode(call)
            description = f".open(mode={mode!r})" if mode else ""
        else:
            return
        if not description or "newline" in keywords:
            return
        function = ".".join(scope) if scope else "<module>"
        if (path, function) in EXEMPTIONS:
            return
        findings.append(Finding(path=path, line=call.lineno, function=function, call=description))

    # An explicit stack, not recursion: this walks every module in the tree and
    # a recursive descent overflows the smaller stack an xdist worker runs on.
    stack: list[tuple[ast.AST, tuple[str, ...]]] = [(tree, ())]
    while stack:
        node, scope = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                stack.append((child, (*scope, child.name)))
                continue
            if isinstance(child, ast.Call):
                _record(child, scope)
            stack.append((child, scope))
    return findings


def _qualified_function_names(tree: ast.Module) -> set[str]:
    """Return every function's dotted scope name, matching ``unpinned_writers``'s stack walk.

    A bare ``{node.name for node in ast.walk(tree) if isinstance(node, FunctionDef...)}``
    cannot distinguish a class method from a module-level function of the same
    name, and never produces the ``Class.method`` spelling ``unpinned_writers``
    keys its findings by. Reusing the identical scope-stack algorithm keeps the
    two name spaces from silently diverging.
    """
    names: set[str] = set()
    stack: list[tuple[ast.AST, tuple[str, ...]]] = [(tree, ())]
    while stack:
        node, scope = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                child_scope = (*scope, child.name)
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    names.add(".".join(child_scope))
                stack.append((child, child_scope))
                continue
            stack.append((child, scope))
    return names


def _tracked_python_modules() -> list[str]:
    """Return tracked, gated ``.py`` paths: everything but ``test_*.py`` modules."""
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no shell
        ["git", "ls-files", "--", *SCAN_ROOTS],  # noqa: S607 - fixed argv resolved by the platform PATH
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    modules: list[str] = []
    for name in completed.stdout.decode("utf-8").split("\n"):
        name = name.strip()
        if not name.endswith(".py") or Path(name).name.startswith("test_"):
            continue
        modules.append(name)
    return sorted(modules)


def _scan() -> tuple[list[Finding], int, list[str]]:
    findings: list[Finding] = []
    scanned = 0
    unparseable: list[str] = []
    for name in _tracked_python_modules():
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_bytes().decode("utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            # A peer mid-edit in this shared worktree must not red this gate;
            # the mass-skip case is caught by the corpus floor below.
            unparseable.append(name)
            continue
        scanned += 1
        findings.extend(unpinned_writers(name, tree))
    return findings, scanned, unparseable


def test_every_text_writer_pins_its_terminator() -> None:
    """No gated module may write text without an explicit newline."""
    findings, _, _ = _scan()
    assert not findings, "text writers without an explicit newline=:\n" + "\n".join(
        finding.format() for finding in sorted(findings, key=lambda f: (f.path, f.line))
    )


def test_the_scan_corpus_did_not_collapse() -> None:
    """A green gate above must mean 'checked', not 'scanned nothing'."""
    _, scanned, unparseable = _scan()
    assert scanned > MIN_SCANNED_MODULES, (
        f"newline gate scanned only {scanned} modules (floor {MIN_SCANNED_MODULES}); "
        "the scan corpus collapsed, so a green result means nothing was checked"
    )
    assert len(unparseable) < 20, (
        f"{len(unparseable)} modules failed to parse and were skipped: {unparseable[:10]}; "
        "that many skips hollows out the gate"
    )


def test_detector_flags_an_unpinned_writer() -> None:
    """The gate must have teeth: an unpinned writer is caught."""
    source = "from pathlib import Path\n\ndef save(p: Path) -> None:\n    p.write_text('x', encoding='utf-8')\n"
    findings = unpinned_writers("dev/synthetic.py", ast.parse(source))
    assert len(findings) == 1, findings
    assert findings[0].function == "save"
    assert findings[0].line == 4


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(
            "def save(p):\n    p.write_text('x', encoding='utf-8', newline='\\n')\n",
            id="write_text-pinned",
        ),
        pytest.param(
            "def save(p):\n    with open(p, 'w', encoding='utf-8', newline='\\n') as h:\n        h.write('x')\n",
            id="open-pinned",
        ),
        pytest.param(
            "def save(p, data):\n    p.write_bytes(data)\n",
            id="write_bytes-is-not-text",
        ),
        pytest.param(
            "def load(p):\n    with open(p, 'rb') as h:\n        return h.read()\n",
            id="binary-read",
        ),
        pytest.param(
            "def save(p, data):\n    with open(p, 'wb') as h:\n        h.write(data)\n",
            id="binary-write",
        ),
        pytest.param(
            "def load(p):\n    return p.read_text(encoding='utf-8')\n",
            id="read_text-is-not-a-write",
        ),
    ),
)
def test_detector_accepts_the_shapes_that_are_already_correct(source: str) -> None:
    """A positive control: the detector must not fire on correct or non-text code.

    Without this, a detector that flagged nothing at all would pass the gate
    above and look identical to a detector that works.
    """
    assert unpinned_writers("dev/synthetic.py", ast.parse(source)) == []


def test_an_exemption_does_not_cover_the_rest_of_its_file() -> None:
    """Exemptions are function-keyed: a new writer in an exempted file still reds.

    This is the regression a file-keyed allowlist would permit -- the exemption
    would inherit to the new writer silently. Uses a real exemption entry so the
    proof is against the shipped keying, not a synthetic stand-in.
    """
    path, function = next(iter(EXEMPTIONS))
    source = (
        f"def {function}(p):\n"
        "    with open('CONOUT$', 'w', encoding='utf-8') as h:\n"
        "        h.write('x')\n"
        "\n"
        "def a_new_unrelated_writer(p):\n"
        "    p.write_text('x', encoding='utf-8')\n"
    )
    findings = unpinned_writers(path, ast.parse(source))
    assert [f.function for f in findings] == ["a_new_unrelated_writer"], (
        f"exemption ({path}, {function}) leaked to another function in the same file: {findings}"
    )


def test_every_exemption_is_still_live() -> None:
    """A stale exemption must fail rather than linger.

    An exemption whose function no longer exists (renamed, deleted, or since
    pinned) is dead weight that would silently pre-authorise a future writer
    that happens to reuse the name.
    """
    stale: list[str] = []
    for (name, function), reason in EXEMPTIONS.items():
        assert reason.strip(), f"exemption ({name}, {function}) carries no reason"
        path = REPO_ROOT / name
        if not path.is_file():
            stale.append(f"{name} (file absent)")
            continue
        tree = ast.parse(path.read_bytes().decode("utf-8"))
        names = _qualified_function_names(tree)
        if function not in names:
            stale.append(f"{name}::{function} (function absent)")
            continue
        # The exemption must still be NEEDED: removing it must surface a finding.
        without = {key: value for key, value in EXEMPTIONS.items() if key != (name, function)}
        original = dict(EXEMPTIONS)
        EXEMPTIONS.clear()
        EXEMPTIONS.update(without)
        try:
            still_unpinned = any(f.function == function for f in unpinned_writers(name, tree))
        finally:
            EXEMPTIONS.clear()
            EXEMPTIONS.update(original)
        if not still_unpinned:
            stale.append(f"{name}::{function} (writer is now pinned; drop the exemption)")
    assert not stale, "stale exemptions:\n" + "\n".join(stale)
