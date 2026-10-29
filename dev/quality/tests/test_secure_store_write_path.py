"""Detector teeth for the secure-store write-path gate.

Every case builds an isolated source tree under ``tmp_path``. The gate must
report a store nothing fills, stay silent on the binding shapes the codebase
actually uses to write one, and fail on a declaration that has gone stale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ..secure_store_write_path import (
    OPAQUE_RECORD_VERBS,
    SecureStoreWritePathError,
    collect_store_usage,
    evaluate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPOSITORY = '''
class ExampleRepository(SecureBoundRepository[Payload]):
    """A secure store."""

    def save(self, payload: Payload) -> None:
        self._objects.save(payload)

    def load(self) -> Payload | None:
        return None
'''


def _tree(root: Path, modules: dict[str, str]) -> Path:
    """Write one synthetic source tree and return its root."""
    source = root / "src" / "cadrumo"
    for name, body in modules.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return source


def _declaration(root: Path, body: str) -> Path:
    path = root / "declaration.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_reports_a_store_that_is_read_and_never_written(tmp_path: Path) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
        },
    )
    problems = evaluate((source,), _declaration(tmp_path, ""))
    assert len(problems) == 1
    assert "ExampleRepository" in problems[0]
    assert "reader.py" in problems[0]


@pytest.mark.parametrize(
    "writer",
    [
        pytest.param("def go():\n    ExampleRepository().save(1)\n", id="direct-construction"),
        pytest.param(
            "def go():\n    repo = ExampleRepository()\n    repo.save(1)\n",
            id="assigned-name",
        ),
        pytest.param(
            "def go(repo: ExampleRepository) -> None:\n    repo.save(1)\n",
            id="annotated-parameter",
        ),
        pytest.param(
            "def go(repo: ExampleRepository | None = None) -> None:\n"
            "    resolved = repo if repo is not None else ExampleRepository()\n"
            "    resolved.save(1)\n",
            id="inject-or-default-conditional",
        ),
        pytest.param(
            "def go(repo=None):\n    resolved = repo or ExampleRepository()\n    resolved.save(1)\n",
            id="inject-or-default-boolop",
        ),
        pytest.param(
            "class Holder:\n"
            "    def __init__(self):\n"
            "        self._repo = ExampleRepository()\n"
            "    def go(self):\n"
            "        self._repo.save(1)\n",
            id="instance-attribute",
        ),
        pytest.param(
            "def _store() -> ExampleRepository:\n    return ExampleRepository()\ndef go():\n    _store().save(1)\n",
            id="module-accessor",
        ),
        pytest.param(
            "class Holder:\n"
            "    def _drafts(self) -> ExampleRepository:\n"
            "        return ExampleRepository()\n"
            "    def go(self):\n"
            "        self._drafts().save(1)\n",
            id="lazy-method-accessor",
        ),
        pytest.param(
            "class Holder:\n"
            "    @property\n"
            "    def _drafts(self) -> ExampleRepository:\n"
            "        return ExampleRepository()\n"
            "    def go(self):\n"
            "        self._drafts.save(1)\n",
            id="lazy-property-accessor",
        ),
        pytest.param(
            "class ExampleRepositoryProtocol:\n"
            "    pass\n"
            "def go(repo: ExampleRepositoryProtocol) -> None:\n"
            "    repo.save(1)\n",
            id="named-structural-port",
        ),
        pytest.param(
            "class Ports:\n    store: ExampleRepository\ndef go(ports: Ports) -> None:\n    ports.store.save(1)\n",
            id="port-field",
        ),
    ],
)
def test_stays_silent_when_some_production_path_writes(tmp_path: Path, writer: str) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
            "writer.py": writer,
        },
    )
    assert evaluate((source,), _declaration(tmp_path, "")) == ()


@pytest.mark.parametrize(
    "method",
    ["save_period", "save_observation", "persist_row", "to_secure_object_write"],
)
def test_mutation_is_recognised_by_token_not_by_prefix(tmp_path: Path, method: str) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
            "writer.py": f"def go():\n    ExampleRepository().{method}(1)\n",
        },
    )
    assert evaluate((source,), _declaration(tmp_path, "")) == ()


def test_an_uncalled_method_is_not_a_repository_receiver(tmp_path: Path) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
            "writer.py": (
                "class Holder:\n"
                "    def _drafts(self) -> ExampleRepository:\n"
                "        return ExampleRepository()\n"
                "    def go(self):\n"
                "        self._drafts.save(1)\n"
            ),
        },
    )
    problems = evaluate((source,), _declaration(tmp_path, ""))
    assert len(problems) == 1
    assert "ExampleRepository" in problems[0]


def test_a_sibling_property_write_is_not_credited_to_another_store(tmp_path: Path) -> None:
    other = _REPOSITORY.replace("ExampleRepository", "OtherRepository")
    adapters = (
        "class ExampleAdapter:\n"
        "    @property\n"
        "    def _repository(self) -> ExampleRepository:\n"
        "        return ExampleRepository()\n"
        "    def read(self):\n"
        "        return self._repository.load()\n"
        "class OtherAdapter:\n"
        "    @property\n"
        "    def _repository(self) -> OtherRepository:\n"
        "        return OtherRepository()\n"
        "    def write(self):\n"
        "        self._repository.save(1)\n"
    )
    source = _tree(tmp_path, {"store.py": _REPOSITORY, "other.py": other, "adapters.py": adapters})
    problems = evaluate((source,), _declaration(tmp_path, ""))
    assert len(problems) == 1
    assert "ExampleRepository" in problems[0]


def test_a_sibling_adapter_write_is_not_credited_to_another_store(tmp_path: Path) -> None:
    """Two adapters holding ``_repository`` in one module each bind their own store."""
    other = _REPOSITORY.replace("ExampleRepository", "OtherRepository")
    adapters = (
        "class ExampleAdapter:\n"
        "    def __init__(self, *, repository: ExampleRepository) -> None:\n"
        "        self._repository = repository\n"
        "    def read(self):\n"
        "        return self._repository.load()\n"
        "class OtherAdapter:\n"
        "    def __init__(self, *, repository: OtherRepository) -> None:\n"
        "        self._repository = repository\n"
        "    def write(self):\n"
        "        self._repository.save(1)\n"
    )
    source = _tree(tmp_path, {"store.py": _REPOSITORY, "other.py": other, "adapters.py": adapters})
    problems = evaluate((source,), _declaration(tmp_path, ""))
    assert len(problems) == 1
    assert "ExampleRepository" in problems[0]


def test_a_store_only_its_own_module_reads_is_not_reported(tmp_path: Path) -> None:
    source = _tree(tmp_path, {"store.py": _REPOSITORY + "\n\ndef peek():\n    return ExampleRepository().load()\n"})
    assert evaluate((source,), _declaration(tmp_path, "")) == ()


def test_a_declaration_the_tree_now_writes_fails_as_spent(tmp_path: Path) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
            "writer.py": "def go():\n    ExampleRepository().save(1)\n",
        },
    )
    declaration = _declaration(
        tmp_path,
        '[[read_only]]\nname = "ExampleRepository"\nkind = "awaiting_writer"\nrationale = "stale"\n',
    )
    problems = evaluate((source,), declaration)
    assert len(problems) == 1
    assert problems[0].startswith("- ExampleRepository")


def test_a_declared_store_passes(tmp_path: Path) -> None:
    source = _tree(
        tmp_path,
        {
            "store.py": _REPOSITORY,
            "reader.py": "def show():\n    return ExampleRepository().load()\n",
        },
    )
    declaration = _declaration(
        tmp_path,
        '[[read_only]]\nname = "ExampleRepository"\nkind = "awaiting_writer"\nrationale = "known gap"\n',
    )
    assert evaluate((source,), declaration) == ()


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param('name = "X"\nkind = "invented"\nrationale = "r"', id="unknown-kind"),
        pytest.param('name = "X"\nkind = "awaiting_writer"\nrationale = ""', id="blank-rationale"),
        pytest.param('name = ""\nkind = "awaiting_writer"\nrationale = "r"', id="blank-name"),
    ],
)
def test_an_unusable_declaration_is_refused(tmp_path: Path, entry: str) -> None:
    source = _tree(tmp_path, {"store.py": _REPOSITORY})
    declaration = _declaration(tmp_path, f"[[read_only]]\n{entry}\n")
    with pytest.raises(SecureStoreWritePathError):
        evaluate((source,), declaration)


_SERVICE_STORE = '''
class SecureExampleStore:
    """A service store over the runtime's opaque custody."""

    def read(self, key):
        return self._client.record_read("example", key)

    def write(self, record):
        return self._client.record_write("example", record.key, payload=bytearray())
'''

_SERVICE_PORT = """
class ExampleStore(Protocol):
    def read(self, key): ...

    def write(self, record): ...
"""


def _package(root: Path, package: str, modules: dict[str, str]) -> Path:
    """Write one synthetic package beside the others under ``root / src``."""
    source = root / "src" / package
    for name, body in modules.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return source


def test_a_service_store_read_through_its_port_and_never_written_is_reported(tmp_path: Path) -> None:
    """The opaque-custody family is a store too, reached through its structural port."""
    service = _package(
        tmp_path,
        "service",
        {
            "store.py": _SERVICE_STORE,
            "ports.py": _SERVICE_PORT,
            "reader.py": "def show(store: ExampleStore):\n    return store.read('k')\n",
        },
    )
    problems = evaluate((service,), _declaration(tmp_path, ""))
    assert len(problems) == 1
    assert "SecureExampleStore" in problems[0]
    assert "service/reader.py" in problems[0]


def test_a_service_store_written_through_its_port_passes(tmp_path: Path) -> None:
    service = _package(
        tmp_path,
        "service",
        {
            "store.py": _SERVICE_STORE,
            "ports.py": _SERVICE_PORT,
            "reader.py": "def show(store: ExampleStore):\n    return store.read('k')\n",
            "writer.py": "def go(store: ExampleStore):\n    store.write(1)\n",
        },
    )
    assert evaluate((service,), _declaration(tmp_path, "")) == ()


def test_a_port_the_store_does_not_satisfy_is_not_credited(tmp_path: Path) -> None:
    """A name suffix alone does not make a protocol the store's port."""
    service = _package(
        tmp_path,
        "service",
        {
            "store.py": _SERVICE_STORE,
            "ports.py": "class ExampleStore(Protocol):\n    def purge(self): ...\n",
            "reader.py": "def show():\n    return SecureExampleStore().read('k')\n",
            "writer.py": "def go(store: ExampleStore):\n    store.write(1)\n",
        },
    )
    problems = evaluate((service,), _declaration(tmp_path, ""))
    assert len(problems) == 1
    assert "SecureExampleStore" in problems[0]


def test_a_write_from_another_package_fills_the_store(tmp_path: Path) -> None:
    """Readers and writers need not share the store's package."""
    product = _package(
        tmp_path,
        "cadrumo",
        {"store.py": _REPOSITORY, "reader.py": "def show():\n    return ExampleRepository().load()\n"},
    )
    runtime = _package(tmp_path, "runtime", {"writer.py": "def go():\n    ExampleRepository().save(1)\n"})

    assert len(evaluate((product,), _declaration(tmp_path, ""))) == 1
    assert evaluate((product, runtime), _declaration(tmp_path, "")) == ()


def test_a_store_name_two_packages_define_is_refused(tmp_path: Path) -> None:
    product = _package(tmp_path, "cadrumo", {"store.py": _REPOSITORY})
    runtime = _package(tmp_path, "runtime", {"store.py": _REPOSITORY})
    with pytest.raises(SecureStoreWritePathError, match="ExampleRepository is defined in both"):
        evaluate((product, runtime), _declaration(tmp_path, ""))


def test_an_absent_source_root_is_refused(tmp_path: Path) -> None:
    product = _package(tmp_path, "cadrumo", {"store.py": _REPOSITORY})
    with pytest.raises(SecureStoreWritePathError, match="source root is unavailable"):
        evaluate((product, tmp_path / "src" / "missing"), _declaration(tmp_path, ""))


def test_the_opaque_record_verbs_are_the_service_client_s_own() -> None:
    """The service-store marker follows the client that defines it."""
    assert all(callable(getattr(InstalledServiceClient, verb, None)) for verb in OPAQUE_RECORD_VERBS)


def test_the_shipped_tree_reports_its_stores() -> None:
    """The live scan finds repositories at all, so a silent pass cannot be vacuous."""
    usage = collect_store_usage()
    assert len(usage) >= 20
    assert any(store.written_by for store in usage)
    assert any(store.read_by for store in usage)
    assert any(store.owner.startswith("cadrumo_agent_service/") for store in usage)


def test_the_shipped_tree_agrees_with_its_declaration() -> None:
    """The live gate, run where CI can see it.

    Without this the module is a command nobody invokes: the synthetic cases
    above prove the detector works on trees that do not ship, and a store wired
    for reading with no writer would still reach a release unremarked.
    """
    assert evaluate() == ()
