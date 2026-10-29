"""No environment template or package declaration names a setting that nothing reads.

A name in ``env/.env.example`` or ``native/application-environment.toml`` that
no setting declares and no source reads looks configured and configures
nothing. Retired model options sat in an operator's ``env/.env`` that way, with
every command still passing. This gate reads both files and refuses each
``CADRUMO_`` name that is neither a field of :class:`~cadrumo.core.config.Settings`
nor spelled by a first-party source that reads it. A second
row keeps :data:`~cadrumo.core.unread_settings.SETTINGS_OWNED_NAME_PREFIXES`
honest: every name a source spells under a family the settings own whole must
be a setting. Each row is first shown to catch a representative defect in an
isolated fixture and to pass a clean one, then run against the real tree.

Read as declarations:

- ``env/.env.example``: the name of every assignment, including a commented
  example such as ``# CADRUMO_PYTEST_WORKERS=2``.
- ``native/application-environment.toml``: every ``CADRUMO_`` name in a key or a
  string value, except the launch conformance vectors, whose ambient
  environments are test inputs, and the agent's never-admitted list, which
  names what no profile may pass. A name ending in an underscore is a prefix,
  not a name.

Read as readers:

- The environment names of the settings model, which declare them.
- Every ``.py``, ``.rs``, ``.ts``, ``.tsx``, ``.mjs``, ``.js``, ``.c``,
  ``.h``, ``.cmake`` and ``.ps1`` file under ``src``, ``dev`` and ``native``,
  and the ``justfile``, that the repository's inclusion policy keeps. A name
  such a file spells is read by it. A test module proper -- a ``test_*`` or
  ``conftest`` Python file, a Rust ``tests`` directory, ``tests.rs`` or
  ``*_tests.rs`` file, and a ``.test.`` or ``.spec.`` file -- reads a name only
  through a direct lookup of a literal, ``os.environ.get("NAME")``,
  ``os.environ["NAME"]`` or ``os.getenv("NAME")``, because a test also names a
  retired setting to prove it is refused. Test support in a ``tests``
  directory is read like any other source.

Where it stops:

- A mention is a spelling, not a read. A source that only names the setting in
  a message, a comment or a list of names it must not pass counts as its reader,
  and so does a CMake file that sets the name for a build. The gate refuses a
  name nobody spells; it does not prove that a spelled name is consulted.
- A setting field that no code consults is not seen. The gate reads the
  templates, not the consumers of the model.
- Only ``CADRUMO_`` names are read. The template's other names, such as
  ``NO_COLOR`` and ``CLOUDFLARE_ACCOUNT_ID``, are not checked here; ``python -m
  dev.env setup`` reports any name in ``env/.env`` that the template lacks.
- A name assembled at run time from parts is not seen.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Final, override

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.unread_settings import SETTINGS_OWNED_NAME_PREFIXES
from dev._paths import REPO_ROOT
from dev.first_party_source import PYTEST_CONFTEST, TEST_MODULE_PREFIXES
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

ENV_TEMPLATE: Final = "env/.env.example"
PACKAGE_DECLARATION: Final = "native/application-environment.toml"
_SOURCE_ROOTS: Final = ("src", "dev", "native", "justfile")
_SOURCE_FILES: Final = frozenset({"justfile"})
_SOURCE_SUFFIXES: Final = frozenset({".py", ".rs", ".ts", ".tsx", ".mjs", ".js", ".c", ".h", ".cmake", ".ps1"})

# A name is not preceded by an identifier character, so ``FOO_CADRUMO_BAR`` is not one.
_NAME: Final = re.compile(r"(?<![A-Za-z0-9_])CADRUMO_[A-Z0-9_]+")
# A lookup of a literal name in the environment, which is what makes a test module a reader.
_DIRECT_READ: Final = re.compile(
    r"""(?:environ\.get|getenv)\(\s*["'](CADRUMO_[A-Z0-9_]*[A-Z0-9])["']"""
    r"""|environ\[\s*["'](CADRUMO_[A-Z0-9_]*[A-Z0-9])["']\s*\](?!\s*=[^=])"""
)
_TEMPLATE_ASSIGNMENT: Final = re.compile(r"^\s*#?\s*(?:export\s+)?(CADRUMO_[A-Z0-9_]*[A-Z0-9])=", re.MULTILINE)
_SKIPPED_TOML_TABLES: Final = frozenset({"launch_vectors"})
_SKIPPED_TOML_PATHS: Final = frozenset({("agent", "never_admitted")})


class Row(StrEnum):
    """The ways a declaration can name a setting nothing reads."""

    TEMPLATE = "names a setting nothing reads (env template)"
    DECLARATION = "names a setting nothing reads (package declaration)"
    FAMILY = "spells a name no setting reads in a family the settings own"


@dataclass(frozen=True, order=True, slots=True)
class Finding:
    """One name that nothing reads."""

    label: str
    line: int
    name: str
    row: Row

    @override
    def __str__(self) -> str:
        """Render the finding as ``label:line: name row``; never any value."""
        where = self.label if self.line == 0 else f"{self.label}:{self.line}"
        return f"{where}: {self.name} {self.row.value}"


def _names(text: str) -> list[str]:
    """Return the names in ``text``, in order, without prefixes (names that end in an underscore)."""
    return [token for token in _NAME.findall(text) if not token.endswith("_")]


def template_declarations(text: str) -> list[tuple[str, int]]:
    """Return each ``CADRUMO_`` assignment of an environment template as ``(name, line)``."""
    return [(match.group(1), text.count("\n", 0, match.start()) + 1) for match in _TEMPLATE_ASSIGNMENT.finditer(text)]


def _toml_names(node: object, path: tuple[str, ...] = ()) -> Iterable[str]:
    if path in _SKIPPED_TOML_PATHS:
        return
    if isinstance(node, str):
        yield from _names(node)
    elif isinstance(node, Mapping):
        for key, value in node.items():
            if not path and key in _SKIPPED_TOML_TABLES:
                continue
            yield from _names(str(key))
            yield from _toml_names(value, (*path, str(key)))
    elif isinstance(node, list):
        for item in node:
            yield from _toml_names(item, path)


def package_declarations(text: str) -> list[str]:
    """Return every distinct ``CADRUMO_`` name a package declaration states, in first-seen order."""
    return list(dict.fromkeys(_toml_names(tomllib.loads(text))))


def _is_test_module(relative: str) -> bool:
    """Return whether ``relative`` is a test module proper, as opposed to test support or product source."""
    path = PurePosixPath(relative)
    leaf = path.name
    if path.suffix == ".py":
        return leaf.startswith(TEST_MODULE_PREFIXES) or leaf == PYTEST_CONFTEST
    return (
        "tests" in path.parts[:-1]
        or leaf == "tests.rs"
        or leaf.endswith("_tests.rs")
        or ".test." in leaf
        or ".spec." in leaf
    )


def _read_names(relative: str, text: str) -> list[str]:
    """Return the names ``relative`` reads: every name it spells, or for a test module only the ones it looks up."""
    if _is_test_module(relative):
        return [name for groups in _DIRECT_READ.findall(text) for name in groups if name]
    return _names(text)


def reader_mentions(root: Path) -> dict[str, frozenset[str]]:
    """Return, for each name a source reads, the files that read it."""
    mentions: dict[str, set[str]] = {}
    for relative in repository_files(root, under=_SOURCE_ROOTS):
        path = PurePosixPath(relative)
        if path.suffix not in _SOURCE_SUFFIXES and relative not in _SOURCE_FILES:
            continue
        text = (root / relative).read_text(encoding="utf-8", errors="ignore")
        for name in _read_names(relative, text):
            mentions.setdefault(name, set()).add(relative)
    return {name: frozenset(files) for name, files in mentions.items()}


def unread_declarations(
    root: Path, setting_names: Collection[str], *, prefixes: Collection[str] = SETTINGS_OWNED_NAME_PREFIXES
) -> list[Finding]:
    """Return every declaration under ``root`` that nothing reads, and every unread name in an owned family."""
    mentions = reader_mentions(root)
    findings: list[Finding] = []

    def read(name: str) -> bool:
        return name in setting_names or name in mentions

    template = root / ENV_TEMPLATE
    if template.is_file():
        for name, line in template_declarations(template.read_text(encoding="utf-8")):
            if not read(name):
                findings.append(Finding(ENV_TEMPLATE, line, name, Row.TEMPLATE))
    declaration = root / PACKAGE_DECLARATION
    if declaration.is_file():
        findings.extend(
            Finding(PACKAGE_DECLARATION, 0, name, Row.DECLARATION)
            for name in package_declarations(declaration.read_text(encoding="utf-8"))
            if not read(name)
        )
    owned = tuple(prefixes)
    findings.extend(
        Finding(sorted(files)[0], 0, name, Row.FAMILY)
        for name, files in mentions.items()
        if name.startswith(owned) and name not in setting_names
    )
    return sorted(findings)


# --- isolated fixtures -------------------------------------------------------

_SETTINGS = frozenset({"CADRUMO_LLM_KEPT", "CADRUMO_LLM_ALSO_KEPT"})
_OWNED = ("CADRUMO_LLM_",)


def _tree(root: Path, files: Mapping[str, str]) -> Path:
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="")
    return root


def _lookup(name: str) -> str:
    """Python source that looks ``name`` up, built so this module does not itself spell a lookup of it."""
    return f'import os\nos.environ.get("{name}")\n'


def _assignment(name: str) -> str:
    """Python source that assigns ``name`` in the environment, which reads nothing."""
    return f'import os\nos.environ["{name}"] = "1"\n'


_CLEAN_TEMPLATE: Final = (
    "CADRUMO_LLM_KEPT=1\n"
    "# CADRUMO_DEV_TOOL=2\n"
    "CADRUMO_SUPPORT_READ=\n"
    "CADRUMO_LIVE_OPT_IN=0\n"
    "CADRUMO_JUST_READ=\n"
    "NO_COLOR=\n"
)
_NEXT_TEMPLATE_LINE: Final = _CLEAN_TEMPLATE.count("\n") + 1
_PACKAGE_CONTRACT: Final = tomllib.loads((REPO_ROOT / PACKAGE_DECLARATION).read_text(encoding="utf-8"))
_AGENT_PREFIX: Final = _PACKAGE_CONTRACT["agent"]["prefix"]
_AGENT_NEVER_ADMITTED: Final = _PACKAGE_CONTRACT["agent"]["never_admitted"][0]

_CLEAN: Final = {
    "env/.env.example": _CLEAN_TEMPLATE,
    "native/application-environment.toml": (
        '[names]\nCADRUMO_PACKAGE_FACT = { kind = "text", role = "fixed" }\n'
        f'[agent]\nprefix = "{_AGENT_PREFIX}"\nnever_admitted = ["{_AGENT_NEVER_ADMITTED}"]\n'
        '[[launch_vectors]]\nname = "v"\nambient = { CADRUMO_VECTOR_ONLY = "x" }\n'
    ),
    "dev/tool.py": _lookup("CADRUMO_DEV_TOOL"),
    "dev/tests/support.py": 'NAME = "CADRUMO_SUPPORT_READ"\n',
    "dev/tests/test_live.py": _lookup("CADRUMO_LIVE_OPT_IN"),
    "justfile": 'workers := env_var_or_default("CADRUMO_JUST_READ", "auto")\n',
    "native/host/src/main.rs": 'const FACT: &str = "CADRUMO_PACKAGE_FACT";\n',
}


def _with_template(addition: str) -> dict[str, str]:
    return {**_CLEAN, "env/.env.example": _CLEAN_TEMPLATE + addition}


@pytest.mark.parametrize(
    ("row", "files", "expected"),
    [
        pytest.param(
            Row.TEMPLATE,
            _with_template("CADRUMO_LLM_GONE=5\n"),
            (f"env/.env.example:{_NEXT_TEMPLATE_LINE}", "CADRUMO_LLM_GONE"),
            id="template-name-nothing-reads",
        ),
        pytest.param(
            Row.TEMPLATE,
            _with_template("# CADRUMO_COMMENTED_GONE=5\n"),
            (f"env/.env.example:{_NEXT_TEMPLATE_LINE}", "CADRUMO_COMMENTED_GONE"),
            id="commented-template-example-nothing-reads",
        ),
        pytest.param(
            Row.DECLARATION,
            {
                **_CLEAN,
                "native/application-environment.toml": _CLEAN["native/application-environment.toml"]
                + '[extra]\nlist = ["CADRUMO_DECLARED_ONLY"]\n',
            },
            ("native/application-environment.toml", "CADRUMO_DECLARED_ONLY"),
            id="declaration-name-nothing-reads",
        ),
        pytest.param(
            Row.TEMPLATE,
            {
                **_with_template("CADRUMO_ONLY_SET_IN_A_TEST=1\n"),
                "dev/tests/test_tool.py": 'SET = "CADRUMO_ONLY_SET_IN_A_TEST"\n',
            },
            (f"env/.env.example:{_NEXT_TEMPLATE_LINE}", "CADRUMO_ONLY_SET_IN_A_TEST"),
            id="a-test-module-that-only-names-the-setting-reads-nothing",
        ),
        pytest.param(
            Row.TEMPLATE,
            {
                **_with_template("CADRUMO_ONLY_WRITTEN_IN_A_TEST=1\n"),
                "dev/tests/test_tool.py": _assignment("CADRUMO_ONLY_WRITTEN_IN_A_TEST"),
            },
            (f"env/.env.example:{_NEXT_TEMPLATE_LINE}", "CADRUMO_ONLY_WRITTEN_IN_A_TEST"),
            id="a-test-module-that-assigns-the-setting-reads-nothing",
        ),
        pytest.param(
            Row.FAMILY,
            {**_CLEAN, "dev/rogue.py": _lookup("CADRUMO_LLM_ROGUE")},
            ("dev/rogue.py", "CADRUMO_LLM_ROGUE"),
            id="source-spells-a-name-in-an-owned-family-no-setting-reads",
        ),
    ],
)
def test_each_row_catches_its_defect_in_an_isolated_fixture(
    row: Row, files: Mapping[str, str], expected: tuple[str, str], tmp_path: Path
) -> None:
    findings = unread_declarations(_tree(tmp_path, files), _SETTINGS, prefixes=_OWNED)

    assert [(str(finding).split(": ")[0], finding.name, finding.row) for finding in findings] == [
        (expected[0], expected[1], row)
    ]


def test_a_clean_fixture_passes(tmp_path: Path) -> None:
    """The control: a setting field, a source, test support, a looked-up test, the justfile, a prefix and a vector."""
    assert unread_declarations(_tree(tmp_path, _CLEAN), _SETTINGS, prefixes=_OWNED) == []


def test_a_setting_field_is_read_without_any_source_spelling_it(tmp_path: Path) -> None:
    files = _with_template("CADRUMO_LLM_ALSO_KEPT=2\n")

    assert unread_declarations(_tree(tmp_path, files), _SETTINGS, prefixes=_OWNED) == []


def test_an_ignored_build_tree_is_not_a_reader(tmp_path: Path) -> None:
    """The inclusion policy keeps build output out: a name spelled only in an ignored tree is unread."""
    files = {
        **_with_template("CADRUMO_ONLY_IN_BUILD_OUTPUT=1\n"),
        ".gitignore": "target/\n",
        "native/application/target/debug/generated.rs": 'const X: &str = "CADRUMO_ONLY_IN_BUILD_OUTPUT";\n',
    }

    findings = unread_declarations(_tree(tmp_path, files), _SETTINGS, prefixes=_OWNED)

    assert [finding.name for finding in findings] == ["CADRUMO_ONLY_IN_BUILD_OUTPUT"]


@cache
def _real_findings() -> tuple[Finding, ...]:
    return tuple(unread_declarations(REPO_ROOT, Settings.env_var_names() | Settings.storage_env_var_names()))


def test_no_template_or_declaration_in_the_repository_names_a_setting_nothing_reads() -> None:
    """A finding names the file, the line when the file has them, and the name; never a value."""
    findings = _real_findings()

    assert findings == (), "\n".join(str(finding) for finding in findings)
