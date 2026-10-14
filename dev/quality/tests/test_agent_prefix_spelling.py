"""Gate: the agent's environment prefix is spelled only where the package and the runtime declare it.

The agent's hosting contract forbids Cadrumo to define any value under the agent's
environment prefix for its own use. The package file, ``native/application-environment.toml``,
declares which of those names each packaged image admits. The runtime's launch composer
fills exactly the gateway's launch slots. The build generates the native contract from the
file. Those are the places that may name the variables. A spelling anywhere else is a second
declaration, and it drifts from the first without any check noticing.

What counts as a spelling
-------------------------
Any occurrence of the prefix, upper case, in a text file of the repository's enumerated
tree. The match is case-sensitive: the variables are upper case by the agent's contract, and
the lower-case form is the agent's Python package name. A different product prefix, the
renamed CMake selector and the lane marker file do not contain the prefix and are not
spellings. A file with a NUL byte near its start is binary and is not read as source, except
a UTF-16 file with a byte-order mark, which is decoded.

What is scanned
---------------
The enumeration is :func:`dev.source_tree.repository_files`: the working tree minus what
the ``.gitignore`` files exclude, so a new file nobody has ignored is read before it is ever
committed. Version control is not consulted. Build output is ignored by that rule, so the
generated contract is outside the scan; it is also allowed by name, for a build that writes it
inside the tree. Two kinds of tree are not scanned, and each says why in ``_UNSCANNED_TREES``:
removable scaffolding and its generated provider copies, and user documentation.

How to satisfy the gate
-----------------------
Read the name from the compiled contract, or do not spell it. A file whose subject is the
agent's declared environment, or the proof that the runtime never emits a retired name, goes
into ``_ALLOWED_FILES`` with a one-line reason. An entry whose file no longer spells the prefix
fails the gate, so the list shrinks when the spellings do.

The prefix is assembled from fragments, so this module carries no spelling of its own and the
scan covers it without a self-exclusion.
"""

from __future__ import annotations

import codecs
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from dev._paths import REPO_ROOT
from dev.source_tree import repository_files

from ..unread_inputs import report_unread

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _join(*fragments: str) -> str:
    """Join fragments into one string, so no spelling appears whole in this source."""
    return "".join(fragments)


_PREFIX: Final = _join("CADRUMO", "_AGENT", "_")
_NEEDLE: Final = _PREFIX.encode("ascii")

#: How much of a file decides text from binary: a NUL byte within it marks the file binary.
_PROBE_BYTES: Final = 8000
_UTF16_BOMS: Final = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)

#: Trees the gate does not read, each with the reason it may name the variables.
_UNSCANNED_TREES: Final[Mapping[str, str]] = {
    ".vault/": "decision records name what they decide, and are removable scaffolding",
    ".vaultspec/": "removable scaffolding: its skills describe the repository, and the repository never cites them",
    ".agents/": "removable scaffolding: agent handovers",
    ".claude/": "provider copy generated from .vaultspec",
    ".codex/": "provider copy generated from .vaultspec",
    ".gemini/": "provider copy generated from .vaultspec",
    "docs/": "user documentation, the generated environment reference included, states which names an image passes",
}
#: Files the gate does not read, each with the reason.
_UNSCANNED_FILES: Final[Mapping[str, str]] = {
    "CHANGELOG.md": "release notes record what changed, retired names included",
}

#: Files that may spell the prefix, each with the reason. Exact repository-relative paths.
_ALLOWED_FILES: Final[Mapping[str, str]] = {
    "native/application-environment.toml": (
        "the package declaration: the one file that names each packaged image's environment, the agent's included"
    ),
    "src/cadrumo/application/agent_host/launch_environment.py": (
        "the runtime's launch composer: names the gateway's launch slots and the names Cadrumo advertises to the agent"
    ),
    "src/cadrumo/application/agent_host/tests/test_launch_environment.py": (
        "retired-name refusal fixture: the composer drops every agent name it receives and never emits a retired path"
    ),
    "src/cadrumo/entrypoints/runtime/tests/test_agent_host_runtime.py": (
        "retired-name refusal fixture: the runtime's start fills exactly the gateway slots and never a retired path"
    ),
    "dev/packaging/native/tests/test_agent_image.py": (
        "package-side test of the agent image: asserts the names its profiles admit, refuse and type"
    ),
    "dev/packaging/native/tests/test_launch_profile_vectors.py": (
        "package-side test of the launch vectors: asserts the generic python image clears the agent prefix"
    ),
    "native/platform/src/launch.rs": (
        "package-side platform test: plants an agent name in the ambient environment for the python image to clear"
    ),
}

#: The contract step's outputs. A build that writes them inside the tree names the file's variables there.
_GENERATED_CONTRACT_NAMES: Final = frozenset({"contract.json", "contract.rs", "contract.h"})
_GENERATED_CONTRACT_DIRECTORY: Final = "generated"


def _out_of_scope(relative: str) -> bool:
    return relative in _UNSCANNED_FILES or relative.startswith(tuple(_UNSCANNED_TREES))


def _is_generated_contract(relative: str) -> bool:
    path = PurePosixPath(relative)
    return path.name in _GENERATED_CONTRACT_NAMES and path.parent.name == _GENERATED_CONTRACT_DIRECTORY


def _permitted(relative: str) -> bool:
    return relative in _ALLOWED_FILES or _is_generated_contract(relative)


def _source_bytes(path: Path) -> bytes | None:
    """Return the file's content as UTF-8 bytes, or ``None`` when it is binary.

    Raises:
        OSError: The file could not be read.
    """
    with path.open("rb") as handle:
        head = handle.read(_PROBE_BYTES)
        if head.startswith(_UTF16_BOMS):
            return (head + handle.read()).decode("utf-16", errors="replace").encode("utf-8")
        if b"\0" in head:
            return None
        return head + handle.read()


@dataclass(frozen=True, slots=True)
class _Scan:
    """What one pass over an enumerated tree found."""

    root: Path
    inventory: tuple[str, ...]
    """Every in-scope file the enumeration returned, read or not."""
    spelled: tuple[str, ...]
    """Every in-scope file that spells the prefix, allowed or not."""
    unread: tuple[str, ...]
    """Files that could not be read, each describing itself."""

    @property
    def offenders(self) -> tuple[str, ...]:
        return tuple(relative for relative in self.spelled if not _permitted(relative))

    @property
    def stale_allowances(self) -> tuple[str, ...]:
        """Allowed files that no longer spell the prefix, so no longer need their entry."""
        return tuple(sorted(set(_ALLOWED_FILES) - set(self.spelled)))

    def locations(self, relative: str) -> str:
        """Return ``path:line`` pairs for the first spellings in one file."""
        content = _source_bytes(self.root / relative) or b""
        lines = content.decode("utf-8", errors="replace").splitlines()
        found = [number for number, line in enumerate(lines, start=1) if _PREFIX in line]
        return f"{relative}: line {', '.join(map(str, found[:5]))}"


def _scan(root: Path, read: Callable[[Path], bytes | None] = _source_bytes) -> _Scan:
    inventory: list[str] = []
    spelled: list[str] = []
    unread: list[str] = []
    for relative in repository_files(root):
        if _out_of_scope(relative):
            continue
        inventory.append(relative)
        try:
            content = read(root / relative)
        except OSError as refusal:
            unread.append(f"{relative} ({refusal})")
            continue
        if content is not None and _NEEDLE in content:
            spelled.append(relative)
    return _Scan(root, tuple(inventory), tuple(spelled), tuple(unread))


def _plant(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _name(suffix: str) -> str:
    return _PREFIX + suffix


@pytest.fixture(scope="module")
def live() -> _Scan:
    """Scan the live tree once for the whole-tree checks."""
    scan = _scan(REPO_ROOT)
    report_unread("agent prefix scan", "a spelling inside one would not appear below", scan.unread)
    return scan


# -- The live tree -----------------------------------------------------------------------------------------------


def test_the_prefix_is_spelled_only_where_the_package_and_the_runtime_declare_it(live: _Scan) -> None:
    required = {
        "justfile",
        "CMakeLists.txt",
        "CMakePresets.json",
        "pyproject.toml",
        "native/cmake/Agent.cmake",
        "native/desktop/frontend/package.json",
        "dev/runtime_lifecycle/agent_live.py",
        "dev/quality/tests/test_agent_prefix_spelling.py",
        ".github/workflows/release.yml",
        *_ALLOWED_FILES,
    }
    assert required <= set(live.inventory), f"the scan is missing owners: {sorted(required - set(live.inventory))}"
    offenders = [live.locations(relative) for relative in live.offenders]
    print(f"Agent prefix audit: {len(live.inventory)} files; {len(live.spelled)} spell it; {len(offenders)} offenders.")
    assert not offenders, (
        "The agent's environment prefix is spelled outside the places that declare it: "
        f"{offenders}. Read the name from the package contract instead of spelling it. A file whose subject is the "
        "agent's declared environment belongs in _ALLOWED_FILES, with a one-line reason."
    )


def test_every_allowed_file_still_spells_the_prefix(live: _Scan) -> None:
    assert not live.stale_allowances, (
        f"These files no longer spell the prefix; remove their _ALLOWED_FILES entries: {list(live.stale_allowances)}"
    )


def test_every_allowance_and_exclusion_states_a_one_line_reason() -> None:
    reasons = [*_ALLOWED_FILES.values(), *_UNSCANNED_TREES.values(), *_UNSCANNED_FILES.values()]
    assert reasons
    assert all(reason.strip() and "\n" not in reason for reason in reasons)
    assert not set(_ALLOWED_FILES) & set(_UNSCANNED_FILES)
    assert all(not path.startswith(tuple(_UNSCANNED_TREES)) for path in _ALLOWED_FILES)


# -- A planted defect in each language the repository's sources are written in ---------------------------------

#: One planted spelling per language, at a path a real source of that language could occupy and no allowance covers.
_PLANTED_DEFECTS: Final[Mapping[str, tuple[str, str]]] = {
    "python": ("src/cadrumo/adapters/example.py", 'import os\nvalue = os.environ.get("<name>")\n'),
    "python-test": (
        "src/cadrumo/adapters/tests/test_example.py",
        'def test_it(monkeypatch):\n    monkeypatch.setenv("<name>", "1")\n',
    ),
    "rust": ("native/manager/src/example.rs", 'const AGENT_VARIABLE: &str = "<name>";\n'),
    "c": ("native/interpreter/example.c", 'static const char *const variable = "<name>";\n'),
    "c-header": ("native/interpreter/example.h", '#define AGENT_VARIABLE "<name>"\n'),
    "cmake": ("native/cmake/Example.cmake", 'set(ENV{<name>} "1")\n'),
    "cmake-lists": ("CMakeLists.txt", 'message(STATUS "$ENV{<name>}")\n'),
    "cmake-presets": ("CMakePresets.json", '{"version": 6, "environment": {"<name>": "1"}}\n'),
    "justfile": ("justfile", 'export <name> := "1"\n\ncheck:\n    echo ok\n'),
    "powershell": ("dev/packaging/example.ps1", '$env:<name> = "1"\n'),
    "shell": ("dev/ci/example.sh", "#!/bin/sh\nexport <name>=1\n"),
    "javascript": ("native/desktop/frontend/scripts/example.mjs", "const value = process.env.<name>;\n"),
    "typescript": ("native/desktop/frontend/src/example.ts", 'export const value = process.env["<name>"];\n'),
    "toml": ("dev/packaging/example.toml", '<name> = "1"\n'),
    "pyproject": ("pyproject.toml", '[tool.pytest.ini_options]\nenv = ["<name>=1"]\n'),
    "workflow": (".github/workflows/example.yml", 'jobs:\n  build:\n    env:\n      <name>: "1"\n'),
}


@pytest.mark.parametrize("language", sorted(_PLANTED_DEFECTS))
def test_a_spelling_planted_in_each_language_is_refused(tmp_path: Path, language: str) -> None:
    relative, template = _PLANTED_DEFECTS[language]
    _plant(tmp_path, relative, template.replace("<name>", _name("HOSTED_ROOT")))
    _plant(tmp_path, "src/cadrumo/clean.py", "VALUE = 1\n")

    scan = _scan(tmp_path)

    assert scan.offenders == (relative,)
    assert scan.locations(relative).startswith(f"{relative}: line ")


@pytest.mark.parametrize("language", sorted(_PLANTED_DEFECTS))
def test_the_same_sources_without_the_prefix_are_accepted(tmp_path: Path, language: str) -> None:
    relative, template = _PLANTED_DEFECTS[language]
    _plant(tmp_path, relative, template.replace("<name>", "CADRUMO_LOCAL_STORAGE_ROOT"))

    scan = _scan(tmp_path)

    assert relative in scan.inventory
    assert not scan.spelled


@pytest.mark.parametrize(
    "near_miss",
    [
        _join("CADRUMO_PACKAGE", "_AGENT_SOURCE_DIR"),
        _join("CADRUMO_LLM", "_ANTHROPIC_API_KEY"),
        _join("CADRUMO", "_AGENT"),
        _join(".cadrumo-agent", "-lane.json"),
        _join("cadrumo", "_agent.worker"),
    ],
)
def test_names_that_do_not_contain_the_prefix_are_not_spellings(tmp_path: Path, near_miss: str) -> None:
    _plant(tmp_path, "native/cmake/Example.cmake", f"set(VALUE {near_miss})\n")

    assert not _scan(tmp_path).spelled


# -- Where the prefix may be spelled -----------------------------------------------------------------------------


def test_every_allowed_file_and_the_generated_contract_may_spell_the_prefix(tmp_path: Path) -> None:
    for relative in _ALLOWED_FILES:
        _plant(tmp_path, relative, f'NAME = "{_name("PORT")}"\n')
    generated = [f"build/windows-x64/generated/{name}" for name in sorted(_GENERATED_CONTRACT_NAMES)]
    for relative in generated:
        _plant(tmp_path, relative, f'"{_name("PORT")}"\n')

    scan = _scan(tmp_path)

    assert set(scan.spelled) == {*_ALLOWED_FILES, *generated}
    assert not scan.offenders
    assert not scan.stale_allowances


@pytest.mark.parametrize(
    "relative",
    [
        "native/other/application-environment.toml",
        "native/application-environment.toml.bak",
        "src/cadrumo/application/agent_host/launch_environment_copy.py",
        "src/cadrumo/application/agent_host/other/launch_environment.py",
        "native/manager/src/contract.rs",
        "native/generated/contract.toml",
        "dev/generated/contract.py",
    ],
)
def test_an_allowance_covers_its_own_path_and_nothing_near_it(tmp_path: Path, relative: str) -> None:
    _plant(tmp_path, relative, f'NAME = "{_name("PORT")}"\n')

    assert _scan(tmp_path).offenders == (relative,)


def test_scaffolding_documentation_and_release_notes_may_name_the_variables(tmp_path: Path) -> None:
    excluded = [f"{tree}notes/example.md" for tree in _UNSCANNED_TREES] + list(_UNSCANNED_FILES)
    for relative in excluded:
        _plant(tmp_path, relative, f"{_name('PORT')} is the gateway's port.\n")

    scan = _scan(tmp_path)

    assert not scan.inventory
    assert not scan.offenders


def test_the_scan_follows_the_inclusion_policy_not_a_version_control_listing(tmp_path: Path) -> None:
    _plant(tmp_path, ".gitignore", "build/\n")
    _plant(tmp_path, "build/windows-x64/example.py", f'NAME = "{_name("PORT")}"\n')
    _plant(tmp_path, "native/new_and_unignored.rs", f'const NAME: &str = "{_name("PORT")}";\n')

    scan = _scan(tmp_path)

    assert "build/windows-x64/example.py" not in scan.inventory
    assert scan.offenders == ("native/new_and_unignored.rs",)


# -- What counts as source text ------------------------------------------------------------------------------------


def test_a_utf16_file_with_a_byte_order_mark_is_decoded_and_refused(tmp_path: Path) -> None:
    path = tmp_path / "dev/packaging/example.ps1"
    path.parent.mkdir(parents=True)
    path.write_bytes(codecs.BOM_UTF16_LE + f'$env:{_name("PORT")} = "1"\n'.encode("utf-16-le"))

    assert _scan(tmp_path).offenders == ("dev/packaging/example.ps1",)


def test_a_binary_file_is_not_read_as_source(tmp_path: Path) -> None:
    path = tmp_path / "src/cadrumo/_data/example.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\0\1\2" + _NEEDLE + b"PORT")

    scan = _scan(tmp_path)

    assert "src/cadrumo/_data/example.bin" in scan.inventory
    assert not scan.spelled


def test_a_spelling_that_straddles_the_binary_probe_boundary_is_found(tmp_path: Path) -> None:
    lead = "export "
    padding = "#" * (_PROBE_BYTES - len(_NEEDLE) // 2 - len(lead) - 1) + "\n"
    _plant(tmp_path, "dev/ci/example.sh", f"{padding}{lead}{_name('PORT')}=1\n")
    content = (tmp_path / "dev/ci/example.sh").read_bytes()
    start = content.index(_NEEDLE)
    assert start < _PROBE_BYTES < start + len(_NEEDLE)

    assert _scan(tmp_path).offenders == ("dev/ci/example.sh",)


def test_a_file_that_cannot_be_read_is_reported_not_taken_for_clean(tmp_path: Path) -> None:
    _plant(tmp_path, "native/cmake/Example.cmake", "set(VALUE 1)\n")
    _plant(tmp_path, "native/cmake/Locked.cmake", "set(VALUE 2)\n")

    def read(path: Path) -> bytes | None:
        if path.name == "Locked.cmake":
            message = "locked by another process"
            raise PermissionError(message)
        return _source_bytes(path)

    scan = _scan(tmp_path, read)

    assert scan.unread == ("native/cmake/Locked.cmake (locked by another process)",)
    assert scan.inventory == ("native/cmake/Example.cmake", "native/cmake/Locked.cmake")
    assert not scan.offenders


# -- A stale allowance ----------------------------------------------------------------------------------------------


def test_an_allowance_whose_file_is_gone_or_no_longer_spells_the_prefix_is_stale(tmp_path: Path) -> None:
    kept, cleaned, *gone = sorted(_ALLOWED_FILES)
    _plant(tmp_path, kept, f'NAME = "{_name("PORT")}"\n')
    _plant(tmp_path, cleaned, 'NAME = "CADRUMO_LOCAL_STORAGE_ROOT"\n')

    scan = _scan(tmp_path)

    assert set(scan.stale_allowances) == {cleaned, *gone}
    assert kept not in scan.stale_allowances
