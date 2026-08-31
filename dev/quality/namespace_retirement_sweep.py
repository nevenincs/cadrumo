"""Sweep the references a module rename leaves behind, in one pass.

Renaming a module -- most often making a private one public -- moves the
import edges the tooling can see and silently strands the ones it cannot.
Five kinds go stale, and each fails in a different place:

1. A relative import whose dot depth no longer matches the file's depth.
   It parses and lints; it fails only when something imports it.
2. A module imported as an OBJECT by its old name, then used as
   ``old.thing`` in the body. Both have to move together.
3. A gate pinning its scan target by full source path. A pin naming a file
   that does not exist makes the gate scan nothing and PASS.
4. The same, pinned by bare ``_module.py`` basename.
5. A ruff per-file ignore in pyproject, which simply stops applying.

Classes 3 and 4 are the dangerous ones: they turn a gate green rather than
red, so nothing announces them. They are also the easiest to miss, because a
pin can sit inside the source of a subprocess a test spawns, where a plain AST
walk of the parent sees one opaque string. Every string that itself parses as
Python is re-walked for that reason.

One literal is never rewritten. ``assert not (pkg / "_x.py").exists()``
asserts the OLD module is gone, so repointing it at the public name inverts
the test into asserting the live module does not exist. A ``_x.py`` string
means one of two opposite things and only its surrounding line says which.

Run with no arguments to report, ``--apply`` to rewrite.
"""

import ast
import re
import sys
from pathlib import Path

SRC = Path("src/cadrumo")
ROOT = SRC.parent
apply = "--apply" in sys.argv
report: list[str] = []


def fix_dot_depth() -> int:
    """Reduce by one the dot count of a relative import that lands nowhere."""
    fixed = 0
    for path in sorted(SRC.rglob("*.py")):
        pkg = path.relative_to(ROOT).with_suffix("").parts[:-1]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        bad = []
        for n in ast.walk(tree):
            if not isinstance(n, ast.ImportFrom) or not n.level or not n.module:
                continue
            keep = len(pkg) - (n.level - 1)
            if keep < 0:
                continue
            t = ROOT / (".".join(pkg[:keep]) + "." + n.module).replace(".", "/")
            if t.with_suffix(".py").exists() or (t / "__init__.py").exists():
                continue
            keep2 = len(pkg) - (n.level - 2)
            if keep2 > len(pkg):
                continue
            t2 = ROOT / (".".join(pkg[:keep2]) + "." + n.module).replace(".", "/")
            if t2.with_suffix(".py").exists() or (t2 / "__init__.py").exists():
                bad.append((n.lineno, n.level, n.module))
        if not bad:
            continue
        report.append(f"  dot-depth: {path} {[b[2] for b in bad]}")
        if apply:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            for lineno, level, module in bad:
                lines[lineno - 1] = re.sub(
                    rf"^(\s*from ){'.' * level}{re.escape(module)}\b",
                    rf"\g<1>{'.' * (level - 1)}{module}",
                    lines[lineno - 1],
                )
            path.write_text("".join(lines), encoding="utf-8")
        fixed += 1
    return fixed


def fix_module_object_imports() -> int:
    """Rename a module imported as an object by its old private name, and its uses."""
    fixed = 0
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "import _" not in text:
            continue
        pkg = path.relative_to(ROOT).with_suffix("").parts[:-1]
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        subs = []
        for n in ast.walk(tree):
            if not isinstance(n, ast.ImportFrom) or not n.level:
                continue
            keep = len(pkg) - (n.level - 1)
            if keep < 0:
                continue
            base = ROOT / ("/".join(pkg[:keep]) + ("/" + n.module.replace(".", "/") if n.module else ""))
            for a in n.names:
                if not a.name.startswith("_") or a.asname:
                    continue
                if (base / f"{a.name}.py").exists():
                    continue
                if (base / f"{a.name[1:]}.py").exists():
                    subs.append((a.name, a.name[1:]))
        if not subs:
            continue
        report.append(f"  module-object: {path} {[s[0] for s in subs]}")
        if apply:
            for old, new in subs:
                text = re.sub(rf"(?<![\w.]){re.escape(old)}\b", new, text)
            path.write_text(text, encoding="utf-8")
        fixed += 1
    return fixed


def _constants(text: str) -> list[ast.Constant]:
    """Every string constant, INCLUDING those inside embedded Python source.

    A test that reproduces a crash in a fresh interpreter passes the child's
    program as one big string. Every pin inside it -- module basenames, function
    names, paths -- is a constant of the CHILD, and ``ast.parse`` of the parent
    sees a single opaque string where the parent's own walk expects many. So the
    outer walk reports zero pins for a file that is nothing but pins.

    That is not hypothetical: the config-reset recovery gate traces for a
    ``delete`` in a file ending ``_lifecycle.py``. The module was renamed to
    ``lifecycle.py`` and the pin then matched only an unrelated module with no
    ``delete`` in it, so the destructive boundary was never injected and the
    gate had stopped testing what it claimed. This sweep ran clean over it.

    Any constant that itself parses as Python is therefore re-walked. Most
    strings are not Python and raise, which is the filter.
    """
    found: list[ast.Constant] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        found.append(node)
        if "\n" in node.value and len(node.value) > 40:
            for inner in _constants(node.value):
                # The child's own line numbers mean nothing in the parent, so
                # anchor an embedded pin to the line the parent string starts on.
                inner.lineno = node.lineno
                found.append(inner)
    return found


def fix_pins() -> int:
    """Repoint source-path and basename literals naming a module that was made public."""
    public = {p.name for p in SRC.rglob("*.py")}
    edits: dict[Path, set[tuple[str, str]]] = {}
    for path in sorted(SRC.rglob("*.py")) + sorted(Path("dev").rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        for n in _constants(text):
            v = n.value.strip()
            if not v.endswith(".py") or "*" in v:
                continue
            line = lines[n.lineno - 1] if n.lineno <= len(lines) else ""
            if "assert not" in line and "exists" in line:
                continue  # an absence assertion means the opposite of a pin
            if "/" in v:
                if "cadrumo" not in v:
                    continue
                cand = Path(v) if v.startswith(("src/", "dev/")) else Path("src") / v
                if cand.exists() or not cand.name.startswith("_"):
                    continue
                if cand.with_name(cand.name[1:]).exists():
                    edits.setdefault(path, set()).add((v, v.replace("/" + cand.name, "/" + cand.name[1:])))
            elif v.startswith("_"):
                if v in public or v[1:] not in public:
                    continue
                edits.setdefault(path, set()).add((v, v[1:]))
    for path, subs in edits.items():
        report.append(f"  pin: {path} {sorted(s[0] for s in subs)}")
        if apply:
            t = path.read_text(encoding="utf-8")
            for old, new in subs:
                t = t.replace(f'"{old}"', f'"{new}"').replace(f"'{old}'", f"'{new}'")
            path.write_text(t, encoding="utf-8")
    return len(edits)


def fix_pyproject() -> int:
    """Repoint ruff per-file ignores naming a module that was made public."""
    p = Path("pyproject.toml")
    text = p.read_text(encoding="utf-8")
    n = 0
    for m in re.finditer(r'^"([^"]+\.py)" = \[', text, re.M):
        v = m.group(1)
        if "*" in v or Path(v).exists():
            continue
        f = Path(v)
        if not f.name.startswith("_"):
            continue
        pub = f.with_name(f.name[1:])
        if not pub.exists():
            continue
        report.append(f"  pyproject: {v} -> {pub.as_posix()}")
        if apply:
            text = text.replace(f'"{v}"', f'"{pub.as_posix()}"')
        n += 1
    if apply and n:
        p.write_text(text, encoding="utf-8")
    return n



def fix_string_module_paths() -> int:
    """Repoint a dotted cadrumo module path written inside a string literal.

    A module path is not always an import. It appears in a logger name, in a
    ``caplog.at_level`` target, and -- most consequentially -- inside the source
    of a subprocess a test spawns. None of those are import nodes, so every
    AST-based sweep above is blind to them.

    The subprocess case fails in the most misleading way available: the child
    exits non-zero, the parent reports only that it never signalled readiness,
    and the failure reads as flakiness. Four custody lock tests were written off
    that way until the string was read.
    """
    module_path = re.compile(r"cadrumo(?:\.[A-Za-z_][A-Za-z_0-9]*)+")

    def public_form(dotted: str) -> str | None:
        target = ROOT / dotted.replace(".", "/")
        if target.with_suffix(".py").exists() or (target / "__init__.py").exists():
            return None
        leaf = target.name
        if len(leaf) < 2 or not leaf.startswith("_"):
            return None
        public = target.with_name(leaf[1:])
        if public.with_suffix(".py").exists() or (public / "__init__.py").exists():
            return dotted.rsplit(".", 1)[0] + "." + leaf[1:]
        return None

    changed = 0
    for path in sorted(SRC.rglob("*.py")) + sorted(Path("dev").rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (SyntaxError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        subs: set[tuple[str, str]] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            # An absence assertion means the OPPOSITE of a reference: the old
            # module is expected to be gone, so repointing it at the live one
            # inverts the test. The same trap as `assert not (pkg / "_x.py")`,
            # in the dotted spelling.
            context = "\n".join(lines[max(0, node.lineno - 4) : node.lineno])
            if "raises" in context and ("ModuleNotFoundError" in context or "ImportError" in context):
                continue
            for dotted in module_path.findall(node.value):
                replacement = public_form(dotted)
                if replacement:
                    subs.add((dotted, replacement))
        if not subs:
            continue
        report.append(f"  string-path: {path} {sorted(old for old, _ in subs)}")
        if apply:
            for old, new in sorted(subs, key=lambda pair: -len(pair[0])):
                text = text.replace(old, new)
            path.write_text(text, encoding="utf-8")
        changed += 1
    return changed

counts = {
    "dot-depth files": fix_dot_depth(),
    "module-object files": fix_module_object_imports(),
    "pin files": fix_pins(),
    "pyproject ignores": fix_pyproject(),
    "string module paths": fix_string_module_paths(),
}
print("\n".join(report) if report else "  (nothing found)")
print("\n" + ("APPLIED" if apply else "DRY RUN") + ":", ", ".join(f"{k}={v}" for k, v in counts.items()))
