"""No product Python downloads, installs, extracts, starts, asks or decides the state of a component.

The native component engine owns the browser and the local AI: it downloads
their pinned archives, installs and checks them, runs the local AI's program
through the runtime manager, writes the receipts and location records, and
decides every item's state. Python locates and uses the browser it installed.
The local AI is reached only through the agent: no product Python calls the
local AI server or looks for its executable.
This gate reads the product's Python sources and refuses each way a Python
module could take that work back. Every row is first shown to catch a
representative defect in an isolated fixture, then run against the real tree.

Scanned: every ``.py`` file under ``src/cadrumo``, ``src/cadrumo_runtime``,
``src/cadrumo_mcp``, ``src/cadrumo_client`` and ``src/cadrumo_agent_service``,
except test directories and the shared test support in ``src/cadrumo/tests``.
Developer tooling under ``dev/`` is not product code and is not scanned: the
pin tools download archives to pin them, and the test lanes' browser setup
runs the vendor installer for the shared test cache.

Where each row stops:

- Download. A module that imports an HTTP client and either names a declared
  component host (the external constants' browser, program and model registry
  hosts) in a string or imports the component pins; or a module that names the
  program's pull or delete endpoint, as a path or as the word an endpoint helper
  is called with. A host handed in by another module that imports no pins is
  not seen.
- Install. A module that starts a process and names a package manager or
  installer word (``winget``, ``brew``, ``apt-get``, ``install-deps`` ...), or
  that imports the Playwright driver's own entry points. An installer reached
  through a variable the module does not spell is not seen.
- Extract. A call to ``extractall`` or ``shutil.unpack_archive`` anywhere, or
  to ``extract`` in a module that imports ``zipfile`` or ``tarfile``. Reading an
  archive member by member is not extraction and passes.
- Spawn the model program. A module that starts a process and names the
  program (``ollama``) or its ``serve`` command in a string. Naming it to
  locate the executable without starting a process passes this row and is
  refused by the locate row below.
- Ask the model program. A module that names one of the program's read or
  inference endpoints (``/api/ps``, ``/api/tags``, ``/api/version``,
  ``/api/show``, ``/api/chat``, ``/api/generate``, ``/api/embed``), as a path
  or as the word an endpoint helper is called with. An address built from
  pieces the module does not spell is not seen.
- Locate the model program. A ``which`` call given the program's name, or a
  string naming its executable file (``ollama.exe``, ``Ollama.app``) or a
  ``bin/ollama`` path. The bare word ``ollama`` as a provider or catalogue
  identifier, and the storage folders named after it, name no executable and
  pass.
- Write a receipt or record. A module that names the components storage
  (``DEPENDENCY_RECEIPTS`` or the ``components/receipts`` and
  ``components/activity`` folders) and also writes, renames or removes a file.
- Decide state. A call that builds a status row with a literal
  ``state=DependencyState.<member>``, or any name of the removed derivation
  (``derive_dependency_row``, ``DependencyProbeReading``, ``DependencyRegistry``,
  ``DependencyItemProvisioner``), defined, imported or used. The one sanctioned
  builder is the components client's answer for a build without the role,
  which the Rust ADR's exposure rule makes every surface read as not in this
  build. A state built from a mapping the module does not spell is not seen.
- Setup operation. A string that is exactly a removed setup operation id
  (``dependencies.setup``, ``dependencies.status``, ``dependencies.verify``).
  The components role's phase codes extend the id with further segments and
  pass.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.external_constants import load_external_constants
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRODUCT_ROOTS: Final = (
    REPO_ROOT / "src" / "cadrumo",
    REPO_ROOT / "src" / "cadrumo_runtime",
    REPO_ROOT / "src" / "cadrumo_mcp",
    REPO_ROOT / "src" / "cadrumo_client",
    REPO_ROOT / "src" / "cadrumo_agent_service",
)
_TEST_SUPPORT: Final = REPO_ROOT / "src" / "cadrumo" / "tests"

#: The host groups of the two setup items: the browser archives, the local AI
#: program archives and the model registry.
_COMPONENT_HOST_GROUPS: Final = ("browser", "model_runtime", "model_registry")

_HTTP_CLIENT_MODULES: Final = frozenset(
    {"httpx", "requests", "aiohttp", "urllib.request", "urllib3", "http.client", "socket", "ssl"}
)
_PULL_ENDPOINTS: Final = ("/api/pull", "api/pull", "/api/delete", "api/delete")
_ENDPOINT_WORDS: Final = frozenset({"pull", "delete"})
_SERVER_ENDPOINT_WORDS: Final = ("ps", "tags", "version", "show", "chat", "generate", "embed")
_SERVER_ENDPOINTS: Final = tuple(f"/api/{word}" for word in _SERVER_ENDPOINT_WORDS)
#: The program's executable file names; the bare program name is a file only where a lookup or a path says so.
_PROGRAM_FILES: Final = frozenset({"ollama.exe", "ollama.app"})
_PROGRAM_NAMES: Final = frozenset({"ollama", *_PROGRAM_FILES})
#: The modules that read the component pins: the bytes only the engine may fetch.
_PIN_MODULES: Final = ("cadrumo.application.browser_archive_pins",)
_PIN_MODULE_NAMES: Final = frozenset(module.rsplit(".", 1)[1] for module in _PIN_MODULES)
_REMOVED_OPERATIONS: Final = frozenset({"dependencies.setup", "dependencies.status", "dependencies.verify"})

#: Process starters, by the module they are reached through.
_QUALIFIED_STARTERS: Final[Mapping[str, frozenset[str]]] = {
    "subprocess": frozenset({"Popen", "run", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}),
    "asyncio": frozenset({"create_subprocess_exec", "create_subprocess_shell"}),
    "os": frozenset(
        {
            "system",
            "popen",
            "startfile",
            "posix_spawn",
            "posix_spawnp",
            *(f"spawn{suffix}" for suffix in ("l", "le", "lp", "lpe", "v", "ve", "vp", "vpe")),
            *(f"exec{suffix}" for suffix in ("l", "le", "lp", "lpe", "v", "ve", "vp", "vpe")),
        }
    ),
}
#: Starters called by their own name, imported or defined by the product's process owners.
_NAMED_STARTERS: Final = frozenset(
    {
        "Popen",
        "create_subprocess_exec",
        "create_subprocess_shell",
        "check_call",
        "check_output",
        "launch_with_standard_pipes",
        "launch_worker",
        "launch_components_role",
    }
)
_INSTALLER_WORDS: Final = frozenset(
    {"winget", "brew", "apt", "apt-get", "dnf", "yum", "msiexec", "choco", "scoop", "install-deps", "pip"}
)
_DRIVER_ENTRY_POINTS: Final = ("playwright.__main__", "playwright._impl._driver", "playwright._impl._installer")
_PROGRAM_WORDS: Final = frozenset({"ollama", "ollama.exe", "serve"})

_RECORD_MARKERS: Final = ("components/receipts", "components/activity", ".activity.json")
_RECORD_CATEGORY: Final = "DEPENDENCY_RECEIPTS"
_WRITE_CALLS: Final = frozenset(
    {
        "write_text",
        "write_bytes",
        "atomic_write_bytes",
        "atomic_write_text",
        "atomic_write_json",
        "replace",
        "rename",
        "unlink",
        "rmtree",
        "remove",
        "mkdir",
        "makedirs",
        "dump",
    }
)

_ROW_TYPES: Final = frozenset({"DependencyStatusRow", "ComponentsRow"})
_REMOVED_DERIVATION: Final = frozenset(
    {"derive_dependency_row", "DependencyProbeReading", "DependencyRegistry", "DependencyItemProvisioner"}
)
#: The one sanctioned row builder: the answer for a build that has no components role.
_NOT_IN_THIS_BUILD_BUILDER: Final = "cadrumo.adapters.outbound.components.client"


@dataclass(frozen=True)
class Source:
    """One parsed module and the facts every row reads from it."""

    module: str
    tree: ast.Module

    @cached_property
    def strings(self) -> tuple[str, ...]:
        """Every string constant that is not a docstring."""
        documented = {id(node) for node in _docstrings(self.tree)}
        return tuple(
            node.value
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in documented
        )

    @cached_property
    def imports(self) -> frozenset[str]:
        """Every absolute module name the module imports, with each of its parents."""
        names: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
                modules = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            else:
                continue
            for module in modules:
                parts = module.split(".")
                names.update(".".join(parts[:index]) for index in range(1, len(parts) + 1))
        return frozenset(names)

    @cached_property
    def imported_module_leaves(self) -> frozenset[str]:
        """The last segment of every module imported, relative imports included."""
        leaves: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                leaves.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    leaves.add(node.module.rsplit(".", 1)[-1])
                leaves.update(alias.name for alias in node.names)
        return frozenset(leaves)

    @cached_property
    def names(self) -> frozenset[str]:
        """Every name the module defines, imports, loads or reaches as an attribute."""
        found: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                found.add(node.id)
            elif isinstance(node, ast.Attribute):
                found.add(node.attr)
            elif isinstance(node, ast.alias):
                found.add((node.asname or node.name).rsplit(".", 1)[-1])
                found.add(node.name.rsplit(".", 1)[-1])
            found.update(_defined_names(node))
        return frozenset(found)

    def calls(self) -> Iterator[tuple[str, ast.Call]]:
        """Every call with the final name it is made through."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Attribute):
                    yield function.attr, node
                elif isinstance(function, ast.Name):
                    yield function.id, node

    def starts_a_process(self) -> bool:
        """Whether the module calls a process starter, through its module or by its own name."""
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if isinstance(function, ast.Name) and function.id in _NAMED_STARTERS:
                return True
            if isinstance(function, ast.Attribute):
                receiver = function.value
                if function.attr in _NAMED_STARTERS:
                    return True
                if isinstance(receiver, ast.Name) and function.attr in _QUALIFIED_STARTERS.get(receiver.id, ()):
                    return True
        return False


def _docstrings(tree: ast.Module) -> Iterator[ast.Constant]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                yield first.value


def parse_source(module: str, text: str) -> Source:
    """Parse ``text`` as the module named ``module``."""
    return Source(module=module, tree=ast.parse(text))


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------


def download_findings(source: Source, hosts: Iterable[str]) -> list[str]:
    """Name a module that reaches a component host or the program's pull and delete endpoints."""
    strings = source.strings
    findings = [
        f"{source.module}: names the model program's endpoint {endpoint!r}"
        for endpoint in _PULL_ENDPOINTS
        if any(endpoint in text for text in strings)
    ][:1]
    findings.extend(
        f"{source.module}:{call.lineno}: asks {name}() for the model program's {argument.value!r} endpoint"
        for name, call in source.calls()
        if name.endswith("endpoint")
        for argument in call.args
        if isinstance(argument, ast.Constant) and argument.value in _ENDPOINT_WORDS
    )
    if source.imports & _HTTP_CLIENT_MODULES:
        findings.extend(
            f"{source.module}: names the component host {host!r} and imports an HTTP client"
            for host in sorted(set(hosts))
            if any(host in text for text in strings)
        )
        findings.extend(
            f"{source.module}: imports the component pins {pins!r} and an HTTP client"
            for pins in sorted(source.imported_module_leaves & _PIN_MODULE_NAMES)
        )
    return findings


def install_findings(source: Source) -> list[str]:
    """Name a module that starts an installer or imports the Playwright driver's entry points."""
    findings = [
        f"{source.module}: imports the Playwright driver entry point {entry!r}"
        for entry in _DRIVER_ENTRY_POINTS
        if entry in source.imports
    ]
    if source.starts_a_process():
        words = {text.strip().lower() for text in source.strings} & _INSTALLER_WORDS
        findings.extend(f"{source.module}: starts a process and names the installer {word!r}" for word in sorted(words))
    return findings


def extract_findings(source: Source) -> list[str]:
    """Name a module that extracts an archive."""
    archives = bool(source.imports & {"zipfile", "tarfile"})
    return [
        f"{source.module}:{call.lineno}: extracts an archive through {name}()"
        for name, call in source.calls()
        if name in {"extractall", "unpack_archive"} or (name == "extract" and archives)
    ]


def spawn_findings(source: Source) -> list[str]:
    """Name a module that starts a process and names the model program or its serve command."""
    if not source.starts_a_process():
        return []
    words = {text.strip().lower() for text in source.strings} & _PROGRAM_WORDS
    return [f"{source.module}: starts a process and names {word!r}" for word in sorted(words)]


def server_call_findings(source: Source) -> list[str]:
    """Name a module that addresses one of the model program's read or inference endpoints."""
    findings = [
        f"{source.module}: names the model program's endpoint {endpoint!r}"
        for endpoint in _SERVER_ENDPOINTS
        if any(_names_endpoint(text, endpoint) for text in source.strings)
    ]
    findings.extend(
        f"{source.module}:{call.lineno}: asks {name}() for the model program's {argument.value!r} endpoint"
        for name, call in source.calls()
        if name.endswith("endpoint")
        for argument in call.args
        if isinstance(argument, ast.Constant) and argument.value in _SERVER_ENDPOINT_WORDS
    )
    return findings


def _names_endpoint(text: str, endpoint: str) -> bool:
    """Whether ``endpoint`` ends a path segment in ``text``, so ``/api/chat`` does not match ``/api/chats``."""
    start = text.find(endpoint)
    while start >= 0:
        end = start + len(endpoint)
        if end == len(text) or text[end] in "/?#\\\"'":
            return True
        start = text.find(endpoint, start + 1)
    return False


def locate_findings(source: Source) -> list[str]:
    """Name a module that looks for the model program's executable."""
    findings = [
        f"{source.module}:{call.lineno}: looks the model program up through {name}({argument.value!r})"
        for name, call in source.calls()
        if name == "which"
        for argument in call.args[:1]
        if isinstance(argument, ast.Constant)
        and isinstance(argument.value, str)
        and argument.value.strip().lower() in _PROGRAM_NAMES
    ]
    findings.extend(
        f"{source.module}: names the model program's executable {text!r}"
        for text in sorted(set(source.strings))
        if _names_program_file(text)
    )
    return findings


def _names_program_file(text: str) -> bool:
    segments = text.strip().lower().replace("\\", "/").rstrip("/").split("/")
    return segments[-1] in _PROGRAM_FILES or segments[-2:] == ["bin", "ollama"]


def record_findings(source: Source) -> list[str]:
    """Name a module that names the components storage and writes, renames or removes a file."""
    names_storage = any(marker in text for text in source.strings for marker in _RECORD_MARKERS) or any(
        isinstance(node, ast.Attribute) and node.attr == _RECORD_CATEGORY for node in ast.walk(source.tree)
    )
    if not names_storage:
        return []
    writes = sorted({name for name, _ in source.calls() if name in _WRITE_CALLS})
    opened = any(name == "open" and _opens_for_writing(call) for name, call in source.calls())
    if opened:
        writes.append("open")
    return [f"{source.module}: names the components storage and calls {name}()" for name in writes]


def _opens_for_writing(call: ast.Call) -> bool:
    modes = [call.args[1]] if len(call.args) > 1 else []
    modes.extend(keyword.value for keyword in call.keywords if keyword.arg == "mode")
    return any(
        isinstance(mode, ast.Constant) and isinstance(mode.value, str) and set(mode.value) & set("wax+")
        for mode in modes
    )


def state_findings(source: Source) -> list[str]:
    """Name a module that builds a status row with a literal state or brings back the removed derivation."""
    findings = [
        f"{source.module}: names the removed state derivation {name}"
        for name in sorted(source.names & _REMOVED_DERIVATION)
    ]
    if source.module == _NOT_IN_THIS_BUILD_BUILDER:
        return findings
    for name, call in source.calls():
        if name not in _ROW_TYPES:
            continue
        for keyword in call.keywords:
            value = keyword.value
            if (
                keyword.arg == "state"
                and isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == "DependencyState"
            ):
                findings.append(f"{source.module}:{call.lineno}: builds a {name} that decides state={value.attr}")
    return findings


def _defined_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return (node.name,)
    if isinstance(node, ast.TypeAlias):
        return (node.name.id,)
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def operation_findings(source: Source) -> list[str]:
    """Name a module that spells a removed setup operation id on its own."""
    return [
        f"{source.module}: names the removed setup operation {identity!r}"
        for identity in sorted({text for text in source.strings if text in _REMOVED_OPERATIONS})
    ]


def provisioning_findings(source: Source, hosts: Iterable[str]) -> list[str]:
    """Every row's findings for one module."""
    return [
        *download_findings(source, hosts),
        *install_findings(source),
        *extract_findings(source),
        *spawn_findings(source),
        *server_call_findings(source),
        *locate_findings(source),
        *record_findings(source),
        *state_findings(source),
        *operation_findings(source),
    ]


# --------------------------------------------------------------------------
# The real tree
# --------------------------------------------------------------------------


def _component_hosts() -> tuple[str, ...]:
    declared = load_external_constants().dependency_hosts
    return tuple(sorted({host for group in _COMPONENT_HOST_GROUPS for host in declared.hosts_for(group)}))


def _product_files() -> Iterator[Path]:
    for root in _PRODUCT_ROOTS:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(REPO_ROOT)
            if "tests" in relative.parts or "__pycache__" in relative.parts or path.is_relative_to(_TEST_SUPPORT):
                continue
            yield path


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(REPO_ROOT / "src").with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _product_sources() -> Mapping[str, Source]:
    return {
        _module_name(path): parse_source(_module_name(path), path.read_text(encoding="utf-8"))
        for path in _product_files()
    }


# --------------------------------------------------------------------------
# Each row catches a representative defect in an isolated fixture
# --------------------------------------------------------------------------

_HOSTS: Final = ("cdn.playwright.dev", "registry.ollama.ai", "github.com")


def test_a_module_that_opens_a_download_from_a_component_host_is_refused() -> None:
    fetching = parse_source(
        "fixture.fetch",
        'import httpx\n\ndef fetch():\n    return httpx.get("https://cdn.playwright.dev/builds/chromium.zip")\n',
    )
    pulling = parse_source("fixture.pull", 'URL = "http://127.0.0.1:11434/api/pull"\n')
    helper = parse_source(
        "fixture.helper", 'def pull(ollama_endpoint, url):\n    return ollama_endpoint(url, "pull")\n'
    )
    pinned = parse_source(
        "fixture.pinned",
        "import httpx\n\nfrom ..application.browser_archive_pins import load_browser_archive_pins\n\n"
        "def fetch():\n    return [httpx.get(pin.urls[0]) for pin in load_browser_archive_pins().archives]\n",
    )
    naming_only = parse_source("fixture.namespace", 'NAMESPACE = "https://github.com/example/ns/1/"\n')
    reading = parse_source("fixture.reader", 'def ps(ollama_endpoint, url):\n    return ollama_endpoint(url, "ps")\n')
    assert download_findings(fetching, _HOSTS) == [
        "fixture.fetch: names the component host 'cdn.playwright.dev' and imports an HTTP client"
    ]
    assert download_findings(pulling, _HOSTS) == ["fixture.pull: names the model program's endpoint '/api/pull'"]
    assert download_findings(helper, _HOSTS) == [
        "fixture.helper:2: asks ollama_endpoint() for the model program's 'pull' endpoint"
    ]
    assert download_findings(pinned, _HOSTS) == [
        "fixture.pinned: imports the component pins 'browser_archive_pins' and an HTTP client"
    ]
    assert download_findings(naming_only, _HOSTS) == [], "a host named without an HTTP client downloads nothing"
    assert download_findings(reading, _HOSTS) == [], "asking what the server holds downloads nothing"


def test_a_module_that_spawns_an_installer_or_imports_the_driver_installer_is_refused() -> None:
    winget = parse_source(
        "fixture.winget",
        'import subprocess\n\ndef install(path):\n    subprocess.run([path, "install", "--id", "Ollama.Ollama"])\n'
        'MANAGER = "winget"\n',
    )
    driver = parse_source("fixture.driver", "from playwright._impl._driver import compute_driver_executable\n")
    locating = parse_source("fixture.locate", 'import shutil\n\nFOUND = shutil.which("winget")\n')
    assert install_findings(winget) == ["fixture.winget: starts a process and names the installer 'winget'"]
    assert install_findings(driver) == [
        "fixture.driver: imports the Playwright driver entry point 'playwright._impl._driver'"
    ]
    assert install_findings(locating) == [], "locating an installer starts nothing"


def test_a_module_that_extracts_a_component_archive_is_refused() -> None:
    extracting = parse_source(
        "fixture.extract", "import zipfile\n\ndef unpack(path, into):\n    zipfile.ZipFile(path).extractall(into)\n"
    )
    member = parse_source(
        "fixture.member", "import zipfile\n\ndef first(path):\n    return zipfile.ZipFile(path).read('a.txt')\n"
    )
    extractor = parse_source("fixture.reader", "def read(extractor, text):\n    return extractor.extract(text)\n")
    assert extract_findings(extracting) == ["fixture.extract:4: extracts an archive through extractall()"]
    assert extract_findings(member) == []
    assert extract_findings(extractor) == [], "a field extractor in a module without archives is not extraction"


def test_a_module_that_spawns_the_model_program_is_refused() -> None:
    spawning = parse_source(
        "fixture.serve",
        'import subprocess\n\ndef start(program):\n    return subprocess.Popen([program, "serve"])\n',
    )
    locating = parse_source(
        "fixture.locate_program", 'import shutil\n\ndef locate():\n    return shutil.which("ollama")\n'
    )
    assert spawn_findings(spawning) == ["fixture.serve: starts a process and names 'serve'"]
    assert spawn_findings(locating) == []


def test_a_module_that_asks_the_model_program_is_refused() -> None:
    chatting = parse_source("fixture.chat", 'URL = "http://127.0.0.1:23743/api/chat"\n')
    resident = parse_source(
        "fixture.resident", 'def ps(ollama_endpoint, url):\n    return ollama_endpoint(url, "ps")\n'
    )
    version = parse_source("fixture.version", 'def read(base):\n    return f"{base}/api/version?x=1"\n')
    agent = parse_source("fixture.agent", 'RUNS = "/v1/runs"\nCHATS = "/api/chats"\nPROVIDER = "ollama"\n')
    assert server_call_findings(chatting) == ["fixture.chat: names the model program's endpoint '/api/chat'"]
    assert server_call_findings(resident) == [
        "fixture.resident:2: asks ollama_endpoint() for the model program's 'ps' endpoint"
    ]
    assert server_call_findings(version) == ["fixture.version: names the model program's endpoint '/api/version'"]
    assert server_call_findings(agent) == [], "the agent's own routes and a longer path ask the program nothing"


def test_a_module_that_locates_the_model_program_is_refused() -> None:
    which = parse_source("fixture.which", 'import shutil\n\ndef locate():\n    return shutil.which("ollama")\n')
    windows = parse_source("fixture.windows", 'def program(root):\n    return root / "ollama.exe"\n')
    path = parse_source("fixture.path", 'PROGRAM = "/usr/local/bin/ollama"\nAPP = "/Applications/Ollama.app"\n')
    provider = parse_source(
        "fixture.provider",
        'import shutil\n\nPROVIDER = "ollama"\nFOUND = shutil.which("git")\nMODELS = "models/ollama"\n',
    )
    assert locate_findings(which) == ["fixture.which:4: looks the model program up through which('ollama')"]
    assert locate_findings(windows) == ["fixture.windows: names the model program's executable 'ollama.exe'"]
    assert locate_findings(path) == [
        "fixture.path: names the model program's executable '/Applications/Ollama.app'",
        "fixture.path: names the model program's executable '/usr/local/bin/ollama'",
    ]
    assert locate_findings(provider) == [], "a provider id, another program's lookup and a folder name no executable"


def test_a_module_that_writes_a_component_receipt_or_record_is_refused() -> None:
    writing = parse_source(
        "fixture.receipt",
        "from pathlib import Path\n\ndef record(root: Path, text: str) -> None:\n"
        '    (root / "components/receipts" / "browser.json").write_text(text)\n',
    )
    category = parse_source(
        "fixture.category",
        "def record(storage_path, StorageCategory, text):\n"
        "    with open(storage_path(StorageCategory.DEPENDENCY_RECEIPTS) / 'x.json', 'w') as handle:\n"
        "        handle.write(text)\n",
    )
    reading = parse_source(
        "fixture.reader",
        "def read(storage_path, StorageCategory):\n"
        "    return (storage_path(StorageCategory.DEPENDENCY_RECEIPTS) / 'browser.json').read_text()\n",
    )
    assert record_findings(writing) == ["fixture.receipt: names the components storage and calls write_text()"]
    assert record_findings(category) == ["fixture.category: names the components storage and calls open()"]
    assert record_findings(reading) == [], "reading the engine's record is what Python may do"


def test_a_module_that_decides_component_state_is_refused() -> None:
    deciding = parse_source(
        "fixture.state",
        "def row(DependencyStatusRow, DependencyState):\n"
        "    return DependencyStatusRow(item_id='browser', state=DependencyState.READY)\n",
    )
    derivation = parse_source("fixture.derive", "def derive_dependency_row(declaration, reading):\n    pass\n")
    probing = parse_source("fixture.probe", "from ..application.dependency_contracts import DependencyProbeReading\n")
    rendering = parse_source(
        "fixture.render", "def ready(row, DependencyState):\n    return row.state is DependencyState.READY\n"
    )
    exempt = parse_source(
        _NOT_IN_THIS_BUILD_BUILDER,
        "def blocked(ComponentsRow, DependencyState):\n    return ComponentsRow(state=DependencyState.BLOCKED)\n",
    )
    assert state_findings(deciding) == ["fixture.state:2: builds a DependencyStatusRow that decides state=READY"]
    assert state_findings(derivation) == ["fixture.derive: names the removed state derivation derive_dependency_row"]
    assert state_findings(probing) == ["fixture.probe: names the removed state derivation DependencyProbeReading"]
    assert state_findings(rendering) == [], "rendering a reported state decides nothing"
    assert state_findings(exempt) == [], "a build without the role reads every item as not in this build"


def test_a_module_that_names_a_removed_setup_operation_is_refused() -> None:
    operation = parse_source("fixture.operation", 'DEFINITION_ID = "dependencies.setup"\n')
    phase = parse_source("fixture.phase", 'def code(item):\n    return f"dependencies.setup.{item}.plan"\n')
    assert operation_findings(operation) == [
        "fixture.operation: names the removed setup operation 'dependencies.setup'"
    ]
    assert operation_findings(phase) == [], "a phase code names a setup step, not the operation"


# --------------------------------------------------------------------------
# The real product sources
# --------------------------------------------------------------------------


def test_no_product_python_downloads_installs_extracts_spawns_asks_locates_writes_or_decides_a_component() -> None:
    sources = _product_sources()
    hosts = _component_hosts()
    assert len(sources) > 2000, f"the census read only {len(sources)} product modules, so it would pass by reading none"
    assert len(hosts) >= 5, f"the component host census read {hosts}"
    assert "cadrumo.application.provisioning_browser" in sources, "the census missed the browser's locate module"
    findings = [finding for source in sources.values() for finding in provisioning_findings(source, hosts)]
    assert not findings, "\n".join(findings)


def test_the_removed_python_provisioning_modules_are_gone() -> None:
    removed = (
        "src/cadrumo/application/dependency_setup_operation.py",
        "src/cadrumo/application/dependency_transfer.py",
        "src/cadrumo/application/dependency_network.py",
        "src/cadrumo/application/dependency_receipts.py",
        "src/cadrumo/application/dependency_activity.py",
        "src/cadrumo/application/dependency_withdrawal.py",
        "src/cadrumo/application/local_reader_setup_items.py",
        "src/cadrumo/application/provisioning_host.py",
        "src/cadrumo/application/provisioning_runtime.py",
        "src/cadrumo/entrypoints/dependency_operation_composition.py",
        "src/cadrumo/adapters/outbound/browser_runtime",
        "src/cadrumo/adapters/outbound/model_runtime",
    )
    present = [path for path in removed if (REPO_ROOT / path).exists()]
    assert not present, f"removed provisioning code came back: {present}"
