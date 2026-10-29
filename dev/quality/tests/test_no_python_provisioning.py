"""No product Python downloads, installs, extracts, starts, asks or decides the state of a component.

The desktop application owns the browser and the local AI: it downloads their
pinned archives, installs and checks them, runs the local AI's program, writes
the receipts and location records, and decides every item's state. Python
locates and uses the browser the desktop installed. The local AI is reached
only through the agent: no product Python calls the local AI server or looks
for its executable.
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

- Download. A module that imports an HTTP client and names a component host
  (the browser archive, program archive and model registry hosts) in a string;
  or a module that names the program's pull or delete endpoint, as a path or as
  the word an endpoint helper is called with. A host handed in by another
  module is not seen.
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
- Write a receipt or record. A module that names the components storage (the
  ``components/receipts`` and ``components/activity`` folders) and also writes,
  renames or removes a file.
- Model argument. A string that is exactly ``--model`` or begins with
  ``--model=``, in any module. The person's selection is the agent's and only
  the desktop hands it to the engine, so no product Python passes a model on a
  command line. A longer option name, such as ``--model-file``, is another
  option and passes this row.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Final

import pytest

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

#: The hosts the browser archives, the local AI program archives and the model registry are served from.
_COMPONENT_HOSTS: Final = (
    "cdn.playwright.dev",
    "playwright.download.prss.microsoft.com",
    "storage.googleapis.com",
    "github.com",
    "release-assets.githubusercontent.com",
    "registry.ollama.ai",
)

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

_MODEL_FLAG: Final = "--model"

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
    }
)
_INSTALLER_WORDS: Final = frozenset(
    {"winget", "brew", "apt", "apt-get", "dnf", "yum", "msiexec", "choco", "scoop", "install-deps", "pip"}
)
_DRIVER_ENTRY_POINTS: Final = ("playwright.__main__", "playwright._impl._driver", "playwright._impl._installer")
_PROGRAM_WORDS: Final = frozenset({"ollama", "ollama.exe", "serve"})

_RECORD_MARKERS: Final = ("components/receipts", "components/activity", ".activity.json")
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
    names_storage = any(marker in text for text in source.strings for marker in _RECORD_MARKERS)
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


def model_argument_findings(source: Source) -> list[str]:
    """Name a module that spells a ``--model`` argument."""
    return [
        f"{source.module}: passes the argument {text!r}"
        for text in sorted(set(source.strings))
        if text == _MODEL_FLAG or text.startswith(_MODEL_FLAG + "=")
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
        *model_argument_findings(source),
    ]


# --------------------------------------------------------------------------
# The real tree
# --------------------------------------------------------------------------


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
    naming_only = parse_source("fixture.namespace", 'NAMESPACE = "https://github.com/example/ns/1/"\n')
    reading = parse_source("fixture.reader", 'def ps(ollama_endpoint, url):\n    return ollama_endpoint(url, "ps")\n')
    assert download_findings(fetching, _HOSTS) == [
        "fixture.fetch: names the component host 'cdn.playwright.dev' and imports an HTTP client"
    ]
    assert download_findings(pulling, _HOSTS) == ["fixture.pull: names the model program's endpoint '/api/pull'"]
    assert download_findings(helper, _HOSTS) == [
        "fixture.helper:2: asks ollama_endpoint() for the model program's 'pull' endpoint"
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
    opening = parse_source(
        "fixture.opening",
        "def record(root, text):\n"
        "    with open(root / 'components/activity' / 'x.json', 'w') as handle:\n"
        "        handle.write(text)\n",
    )
    reading = parse_source(
        "fixture.reader",
        "def read(root):\n    return (root / 'components/receipts' / 'browser.json').read_text()\n",
    )
    assert record_findings(writing) == ["fixture.receipt: names the components storage and calls write_text()"]
    assert record_findings(opening) == ["fixture.opening: names the components storage and calls open()"]
    assert record_findings(reading) == [], "reading the engine's record is what Python may do"


def test_a_module_that_passes_a_model_argument_is_refused() -> None:
    flag = parse_source("fixture.flag", "ARGUMENTS = ['setup', '--model', 'vision_transcription', 'synthetic', '1']\n")
    joined = parse_source("fixture.joined", "FLAG = '--model=synthetic'\n")
    other = parse_source("fixture.other", "FLAGS = ('--model-file', '--models-dir', '--item', 'model')\n")
    assert model_argument_findings(flag) == ["fixture.flag: passes the argument '--model'"]
    assert model_argument_findings(joined) == ["fixture.joined: passes the argument '--model=synthetic'"]
    assert model_argument_findings(other) == [], "a longer option name is another option"


# --------------------------------------------------------------------------
# The real product sources
# --------------------------------------------------------------------------


def test_no_product_python_downloads_installs_extracts_spawns_asks_locates_writes_or_decides_a_component() -> None:
    sources = _product_sources()
    hosts = _COMPONENT_HOSTS
    assert len(sources) > 2000, f"the census read only {len(sources)} product modules, so it would pass by reading none"
    assert "cadrumo.application.browser_location" in sources, "the census missed the browser's locate module"
    findings = [finding for source in sources.values() for finding in provisioning_findings(source, hosts)]
    assert not findings, "\n".join(findings)
