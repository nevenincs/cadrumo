"""No shipped Cadrumo source defines an AI model.

The agent's provider catalogue is the only source of providers and models.
Cadrumo carries the person's selection and the local program's pins, but no
model name, no model digest and no table of models. This gate reads the
shipped sources and refuses each way a module could define a model again.
Every row is first shown to catch a representative defect in an isolated
fixture and to pass a representative clean module, then run against the real
tree.

Scanned: every ``.py`` file under ``src/cadrumo``, ``src/cadrumo_runtime``,
``src/cadrumo_mcp``, ``src/cadrumo_client`` and ``src/cadrumo_agent_service``,
except test directories and the shared test support in ``src/cadrumo/tests``,
and every ``.toml`` file under ``src/cadrumo/_data/dependencies``. Developer
tooling under ``dev/``, the Rust engine, the desktop and the bundled corpora
are not scanned.

Where each row stops:

- Model name. A string constant, not a docstring, that contains a model
  family followed by a version or size (``claude-sonnet``, ``gpt-4``,
  ``gemini-2``, ``qwen3``, ``gemma3``, ``llama3`` ...), the family names
  ``moondream`` and ``llava``, or that is exactly an Ollama tag
  (``name:1.7b``); in a TOML file, the same test on every string value and
  key. A model named only in a docstring or comment passes, and so does a name
  built at run time from parts. The bare provider names ``claude``, ``gemini``
  and ``ollama`` are not model names and pass.
- Model digest. A string constant containing ``sha256:`` and 64 hexadecimal
  digits, the form of an Ollama manifest digest; in a TOML file, a 64-digit
  hexadecimal value under a key whose name contains ``digest``. A bare
  64-digit hexadecimal Python string is not a model digest on its own: the
  registry and filing code spell many content hashes, so it passes.
- Model table. A collection literal (tuple, list, set or dict) with at least
  two entries that are calls or dicts carrying a string-literal keyword or
  key named ``model_id``, ``model_name``, ``runtime_id`` or
  ``manifest_digest``; in a TOML file, an array of tables named ``models``
  with at least two entries. A single entry, or a table whose model names
  are read from elsewhere, is not seen.

``_BURN_DOWN`` lists the files that offend today. It only shrinks: a listed
file that no longer offends fails the gate until it is removed from the list,
and a file that offends and is not listed fails it too.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterator, Mapping
from functools import cache
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
_DATA_ROOT: Final = REPO_ROOT / "src" / "cadrumo" / "_data" / "dependencies"

_FAMILY_VERSIONED: Final = re.compile(
    r"(?<![a-z0-9])(?:claude-(?:haiku|sonnet|opus|\d)|gpt-?\d|gemini-(?:\d|pro|flash)|qwen-?\d|gemma-?\d|llama-?\d"
    r"|mistral-|mixtral|phi-?\d|deepseek-|smollm|granite-?\d|minicpm|moondream|llava)",
    re.IGNORECASE,
)
_OLLAMA_TAG: Final = re.compile(r"[a-z][a-z0-9._-]*:\d+(?:\.\d+)?[bm]", re.IGNORECASE)
_MANIFEST_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}", re.IGNORECASE)
_BARE_DIGEST: Final = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)
_TABLE_KEYS: Final = frozenset({"model_id", "model_name", "runtime_id", "manifest_digest"})

#: Files that define a model today. Later Steps remove entries; none may be added.
_BURN_DOWN: Final = frozenset(
    {
        "src/cadrumo/_data/dependencies/local_ai_models.toml",
        "src/cadrumo/core/config_runtime_fields.py",
        "src/cadrumo/core/model_catalogue.py",
    }
)


def _is_model_name(text: str) -> bool:
    return bool(_FAMILY_VERSIONED.search(text)) or _OLLAMA_TAG.fullmatch(text.strip()) is not None


def _docstring_ids(tree: ast.Module) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                found.add(id(first.value))
    return found


def _entry_names_a_model(entry: ast.expr) -> bool:
    if isinstance(entry, ast.Call):
        return any(
            keyword.arg in _TABLE_KEYS
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
            for keyword in entry.keywords
        )
    if isinstance(entry, ast.Dict):
        return any(
            isinstance(key, ast.Constant)
            and key.value in _TABLE_KEYS
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            for key, value in zip(entry.keys, entry.values, strict=True)
        )
    return False


def python_findings(label: str, text: str) -> list[str]:
    """Name each model name, model digest and model table in one Python module."""
    tree = ast.parse(text)
    documented = _docstring_ids(tree)
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in documented:
            if _is_model_name(node.value):
                findings.append(f"{label}:{node.lineno}: names a model in the literal {node.value[:60]!r}")
            if _MANIFEST_DIGEST.search(node.value):
                findings.append(f"{label}:{node.lineno}: spells a model manifest digest")
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            entries = list(node.elts)
        elif isinstance(node, ast.Dict):
            entries = list(node.values)
        else:
            continue
        if sum(_entry_names_a_model(entry) for entry in entries) >= 2:
            findings.append(f"{label}:{node.lineno}: defines a table of models")
    return findings


def _toml_strings(value: object, key: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield key, value
    elif isinstance(value, Mapping):
        for child_key, child in value.items():
            yield from _toml_strings(str(child_key), "")
            yield from _toml_strings(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from _toml_strings(child, key)


def toml_findings(label: str, text: str) -> list[str]:
    """Name each model name, model digest and model table in one TOML file."""
    document = tomllib.loads(text)
    findings: list[str] = []
    for key, value in _toml_strings(document):
        if _is_model_name(value):
            findings.append(f"{label}: names a model in the value {value[:60]!r}")
        if "digest" in key.lower() and _BARE_DIGEST.fullmatch(value):
            findings.append(f"{label}: spells a model digest under {key!r}")
    models = document.get("models")
    if isinstance(models, list) and len(models) >= 2:
        findings.append(f"{label}: defines a table of models")
    return findings


# --------------------------------------------------------------------------
# The real tree
# --------------------------------------------------------------------------


def _product_python_files() -> Iterator[Path]:
    for root in _PRODUCT_ROOTS:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(REPO_ROOT)
            if "tests" in relative.parts or "__pycache__" in relative.parts or path.is_relative_to(_TEST_SUPPORT):
                continue
            yield path


@cache
def _offenders() -> tuple[int, dict[str, list[str]]]:
    scanned = 0
    offenders: dict[str, list[str]] = {}
    for path in _product_python_files():
        scanned += 1
        relative = path.relative_to(REPO_ROOT).as_posix()
        found = python_findings(relative, path.read_text(encoding="utf-8"))
        if found:
            offenders[relative] = found
    for path in sorted(_DATA_ROOT.glob("*.toml")):
        scanned += 1
        relative = path.relative_to(REPO_ROOT).as_posix()
        found = toml_findings(relative, path.read_text(encoding="utf-8"))
        if found:
            offenders[relative] = found
    return scanned, offenders


# --------------------------------------------------------------------------
# Each row catches a representative defect and passes a clean module
# --------------------------------------------------------------------------


def test_a_model_name_literal_is_refused() -> None:
    cloud = python_findings("fixture.cloud", 'DEFAULT = "claude-sonnet-9"\n')
    local = python_findings("fixture.local", 'def pick():\n    return "qwen3-vl:2b"\n')
    tag = python_findings("fixture.tag", 'MODEL = "widget:7b"\n')
    toml = toml_findings("fixture.toml", '[roles]\nvision = "gemma3:4b"\n')
    assert len(cloud) == 1 and "claude-sonnet-9" in cloud[0]
    assert len(local) == 1 and "qwen3-vl:2b" in local[0]
    assert len(tag) == 1 and "widget:7b" in tag[0]
    assert len(toml) == 1 and "gemma3:4b" in toml[0]


def test_a_module_that_names_no_model_passes_the_name_row() -> None:
    clean = python_findings(
        "fixture.clean",
        '"""Reads claude-sonnet-9 and qwen3-vl:2b from the catalogue."""\n\n'
        'PROVIDER = "claude"\nRUNTIME = "ollama"\nSPEED = "10:30"\nSELECTED = lookup(role)\n',
    )
    clean_toml = toml_findings("fixture.toml", '[program]\nname = "ollama"\nversion = "0.40.10"\n')
    assert clean == [], "a docstring, a bare provider name and a clock time name no model"
    assert clean_toml == []


def test_a_model_digest_literal_is_refused() -> None:
    digest = "ab" * 32
    python = python_findings("fixture.digest", f'PIN = "sha256:{digest}"\n')
    toml = toml_findings("fixture.toml", f'[pin]\nmanifest_digest = "{digest}"\n')
    assert python == ["fixture.digest:1: spells a model manifest digest"]
    assert toml == ["fixture.toml: spells a model digest under 'manifest_digest'"]


def test_a_content_hash_passes_the_digest_row() -> None:
    digest = "cd" * 32
    python = python_findings("fixture.hash", f'CONTENT_HASH = "{digest}"\n')
    toml = toml_findings("fixture.toml", f'[source]\nchecksum = "{digest}"\n')
    assert python == [], "a bare 64-digit hash is a content hash, not a model digest"
    assert toml == []


def test_a_model_table_is_refused() -> None:
    call_table = python_findings(
        "fixture.calls",
        'TABLE = (\n    Entry(model_id="alpha", tier=1),\n    Entry(model_id="beta", tier=2),\n)\n',
    )
    dict_table = python_findings(
        "fixture.dicts",
        'ROWS = [{"runtime_id": "alpha", "size": 1}, {"runtime_id": "beta", "size": 2}]\n',
    )
    toml = toml_findings("fixture.toml", "[[models]]\nsize = 1\n\n[[models]]\nsize = 2\n")
    assert call_table == ["fixture.calls:1: defines a table of models"]
    assert dict_table == ["fixture.dicts:1: defines a table of models"]
    assert toml == ["fixture.toml: defines a table of models"]


def test_a_single_entry_or_a_table_read_from_elsewhere_passes_the_table_row() -> None:
    single = python_findings("fixture.single", 'ONE = (Entry(model_id="alpha"),)\n')
    computed = python_findings(
        "fixture.computed",
        "TABLE = tuple(Entry(model_id=name) for name in names)\nOTHER = (Entry(model_id=a), Entry(model_id=b))\n",
    )
    toml = toml_findings("fixture.toml", "[[models]]\nsize = 1\n")
    assert [item for item in single if "table" in item] == []
    assert computed == [], "entries whose id is not a string literal are not a literal model table"
    assert toml == []


# --------------------------------------------------------------------------
# The real product sources
# --------------------------------------------------------------------------


def test_the_census_reads_the_product_and_the_dependency_data() -> None:
    scanned, _ = _offenders()
    assert scanned > 2000, f"the census read only {scanned} files, so it would pass by reading none"
    assert (_DATA_ROOT / "local_ai_program.toml").is_file(), "the census missed the program pin data"


def test_only_the_burn_down_files_define_a_model() -> None:
    _, offenders = _offenders()
    unlisted = sorted(set(offenders) - _BURN_DOWN)
    assert not unlisted, "files define a model and are not on the burn-down list:\n" + "\n".join(
        finding for path in unlisted for finding in offenders[path]
    )


def test_every_burn_down_file_still_defines_a_model() -> None:
    _, offenders = _offenders()
    stale = sorted(_BURN_DOWN - set(offenders))
    assert not stale, f"these files no longer define a model; remove them from the burn-down list: {stale}"
