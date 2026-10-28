"""Conformance gate for the setup-item registry and every surface that renders it.

The registry is what makes "the same everywhere" checkable: each setup item
declares its plain name and its recovery action, the wording for every closed
value lives once in the canonical catalogues in every supported language, no
rendered sentence carries an internal term, and every front end renders the
registry's rows instead of keeping its own list of items.

Each checker below is a pure function over plain inputs, and each is first
shown to catch a representative defect in an isolated fixture before it runs
against the real registry, catalogues and surface sources. The surface checks
read source files rather than importing them, because the application layer
may not import the CLI, the TUI, the MCP harness or the desktop frontend.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Final

import pytest
import yaml

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n.render import lookup_translation
from ..dependency_contracts import (
    DependencyBlockedReason,
    DependencyItemDeclaration,
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
)
from ..dependency_registry import BROWSER_DECLARATION, dependency_item_declarations
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT: Final = Path(__file__).resolve().parents[2]
_SOURCE_ROOT: Final = _PACKAGE_ROOT.parent
_REPOSITORY_ROOT: Final = _SOURCE_ROOT.parent
_LOCALES_ROOT: Final = _PACKAGE_ROOT / "locales"
_FRONTEND_SOURCE: Final = _REPOSITORY_ROOT / "native" / "desktop" / "frontend" / "src"

#: The Python setup operations the native components role replaced, the
#: browser operation before them, and the local reader's direct load and
#: verify; none may be registered or named again.
_REMOVED_OPERATIONS: Final = (
    "browser-runtime.provision",
    "dependencies.setup",
    "dependencies.status",
    "dependencies.verify",
    "local-reader.provision",
)

#: The ``config provision`` verbs that run the native components role through its registered operations.
_COMPONENT_LEAVES: Final = frozenset({"browser", "probe", "remove", "setup", "status", "verify"})
#: The registered operations through which the components role runs in the signed-in profile.
_COMPONENT_OPERATIONS: Final = frozenset(
    {"config.provision.remove", "config.provision.setup", "config.provision.status", "config.provision.verify"}
)
#: The ``config provision`` verb that answers a running setup's review and submits nothing of its own.
_REVIEW_LEAF: Final = "review"
#: The operations the local reader's remaining verbs submit in the signed-in profile.
_LOCAL_READER_OPERATIONS: Final = frozenset({"local-reader.status", "local-reader.report"})

#: Catalogue subtrees that hold setup wording: the plain sentences and actions
#: every surface shows, the desktop's own setup strings, and the words of the
#: profile's Google account, which shares their failure sentences.
_WORDING_SUBTREES: Final = (
    ("application.yml", ("application", "provisioning")),
    ("common.yml", ("desktop", "setup")),
    ("common.yml", ("desktop", "google")),
)

#: The closed value families each of which needs wording in every language.
_WORDED_FAMILIES: Final[tuple[type[StrEnum], ...]] = (
    DependencyState,
    DependencyBlockedReason,
    DependencyStaleReason,
    DependencyFailureCategory,
    DependencyRecoveryAction,
)


# --------------------------------------------------------------------------
# Checkers
# --------------------------------------------------------------------------


def recovery_action_findings(
    declarations: Iterable[DependencyItemDeclaration],
    catalogued_action_ids: Iterable[str],
) -> list[str]:
    """Name every item whose recovery action is not an operator action the catalogue declares."""
    catalogued = set(catalogued_action_ids)
    return [
        f"{declaration.item_id}: recovery action {declaration.recovery_action_id!r} is not in the operator catalogue"
        for declaration in declarations
        if declaration.recovery_action_id not in catalogued
    ]


def display_name_findings(
    declarations: Iterable[DependencyItemDeclaration],
    locales: Sequence[str],
    lookup: Callable[[str, str], str | None],
) -> list[str]:
    """Name every item whose plain name does not resolve to authored text in every language."""
    findings: list[str] = []
    for declaration in declarations:
        key = catalogue_key(declaration.display_key)
        findings.extend(
            f"{declaration.item_id}: {key} has no authored text in {locale!r}"
            for locale in locales
            if not (lookup(key, locale) or "").strip()
        )
    return findings


def catalogue_key(display_key: str) -> str:
    """Return the catalogue key of a registry wording identity, which lives in ``application.yml``."""
    return f"application.{display_key}"


def flatten_leaves(tree: object, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    """Return every leaf of a parsed catalogue subtree, keyed by its path."""
    if isinstance(tree, Mapping):
        leaves: dict[tuple[str, ...], object] = {}
        for key, child in tree.items():
            leaves.update(flatten_leaves(child, (*prefix, str(key))))
        return leaves
    return {prefix: tree}


def locale_parity_findings(subtrees: Mapping[str, Mapping[tuple[str, ...], object]], *, label: str) -> list[str]:
    """Name every language whose subtree is missing, empty, unequal in keys, or holds a blank sentence."""
    findings: list[str] = []
    every_path = set().union(*(set(leaves) for leaves in subtrees.values())) if subtrees else set()
    for locale, leaves in subtrees.items():
        if not leaves:
            findings.append(f"{locale}: {label} is missing or empty")
            continue
        findings.extend(f"{locale}: {label}.{'.'.join(path)} is missing" for path in sorted(every_path - set(leaves)))
        findings.extend(
            f"{locale}: {label}.{'.'.join(path)} is not authored text"
            for path, value in sorted(leaves.items())
            if not isinstance(value, str) or not value.strip()
        )
    return findings


def closed_value_coverage_findings(
    paths: Iterable[tuple[str, ...]],
    families: Iterable[type[StrEnum]],
    *,
    label: str,
) -> list[str]:
    """Name every closed value that no wording path names as one of its segments."""
    segments = {segment for path in paths for segment in path}
    return [
        f"{label}: no wording for {family.__name__}.{member.name} ({member.value!r})"
        for family in families
        for member in family
        if member.value not in segments
    ]


_PLACEHOLDER: Final = re.compile(r"%?\{[^{}]*\}")
_EXCEPTION_NAME: Final = re.compile(r"\b[A-Za-z]+(?:Error|Exception)\b")
_SNAKE_TOKEN: Final = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_OPERATION_ID: Final = re.compile(r"\b(?:dependencies|local-reader|browser-runtime|operator\.provision)[.\w-]*")

#: Internal vocabulary a person never reads in setup wording: implementation
#: words, upstream product names and API path fragments.
INTERNAL_WORDS: Final = ("runtime", "provision", "playwright", "headless", "digest", "ollama", "/api/")


def internal_term_findings(texts: Mapping[str, str]) -> list[str]:
    """Name every sentence that shows a category, an operation id, an exception name or an internal word.

    Placeholders such as ``{size}`` are removed first: they are filled with data
    at render time and their names are never shown.
    """
    findings: list[str] = []
    for origin, text in texts.items():
        visible = _PLACEHOLDER.sub(" ", text)
        lowered = visible.casefold()
        findings.extend(f"{origin}: shows internal word {word!r}" for word in INTERNAL_WORDS if word in lowered)
        findings.extend(
            f"{origin}: shows {kind} {match.group(0)!r}"
            for kind, pattern in (
                ("an identifier", _SNAKE_TOKEN),
                ("an operation id", _OPERATION_ID),
                ("an exception name", _EXCEPTION_NAME),
            )
            for match in pattern.finditer(visible)
        )
    return findings


def item_identities(declarations: Iterable[DependencyItemDeclaration]) -> frozenset[str]:
    """Return every string a private item list would hold: item identities and item kinds."""
    return frozenset(
        {declaration.item_id for declaration in declarations} | {kind.value for kind in DependencyItemKind}
    )


def python_private_list_findings(source: str, identities: frozenset[str], *, origin: str) -> list[str]:
    """Name every tuple, list or set literal in Python source that holds two or more setup items."""
    findings: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Tuple | ast.List | ast.Set):
            continue
        named = {
            element.value
            for element in node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str) and element.value in identities
        }
        if len(named) >= 2:
            findings.append(f"{origin}:{node.lineno}: keeps its own list of setup items {sorted(named)}")
    return findings


_SCRIPT_COMMENT: Final = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_SCRIPT_ARRAY: Final = re.compile(r"\[[^\[\]]*\]", re.DOTALL)
_SCRIPT_STRING: Final = re.compile(r"""(["'`])([^"'`\n]*)\1""")


def script_private_list_findings(source: str, identities: frozenset[str], *, origin: str) -> list[str]:
    """Name every array literal in TypeScript source that holds two or more setup items."""
    stripped = _SCRIPT_COMMENT.sub(lambda match: "\n" * match.group(0).count("\n"), source)
    findings: list[str] = []
    for array in _SCRIPT_ARRAY.finditer(stripped):
        named = {match.group(2) for match in _SCRIPT_STRING.finditer(array.group(0))} & identities
        if len(named) >= 2:
            line = stripped.count("\n", 0, array.start()) + 1
            findings.append(f"{origin}:{line}: keeps its own list of setup items {sorted(named)}")
    return findings


def provision_leaf_findings(rows: Iterable[tuple[tuple[str, ...], str | None]]) -> list[str]:
    """Name every verb whose submission is not its role's: components, review answer or local reader."""
    findings: list[str] = []
    seen = False
    for path, operation in rows:
        if path[:2] != ("config", "provision") or len(path) < 3:
            continue
        seen = True
        if path[2] in _COMPONENT_LEAVES:
            if operation not in _COMPONENT_OPERATIONS:
                findings.append(f"{' '.join(path)}: submits {operation!r}, which is not a components role operation")
        elif path[2] == _REVIEW_LEAF:
            if operation is not None:
                findings.append(f"{' '.join(path)}: submits {operation!r} instead of answering a running review")
        elif operation not in _LOCAL_READER_OPERATIONS:
            findings.append(f"{' '.join(path)}: submits {operation!r}, which is not a local reader operation")
    if not seen:
        findings.append("the command table has no config provision leaf")
    return findings


def removed_operation_findings(definition_ids: Iterable[str]) -> list[str]:
    """Name every removed operation the registered set still holds."""
    registered = set(definition_ids)
    return [f"{operation} is still registered" for operation in _REMOVED_OPERATIONS if operation in registered]


def removed_identity_findings(sources: Mapping[str, str], identity: str) -> list[str]:
    """Name every source that still spells a removed operation id, which would be an alias or a stale caller.

    The id must stand alone: the components role's phase codes, such as
    ``dependencies.setup.browser.plan``, extend the id with further segments
    and name a setup step, not the operation.
    """
    spelled = re.compile(re.escape(identity) + r"(?![\w.-])")
    return [f"{origin}: still names {identity!r}" for origin, text in sources.items() if spelled.search(text)]


# --------------------------------------------------------------------------
# Real inputs
# --------------------------------------------------------------------------


def _wording_subtree(locale: str, catalogue: str, path: tuple[str, ...]) -> dict[tuple[str, ...], object]:
    catalogue_file = _LOCALES_ROOT / locale / catalogue
    if not catalogue_file.is_file():
        return {}
    node: object = yaml.safe_load(catalogue_file.read_text(encoding="utf-8")) or {}
    for segment in path:
        node = node.get(segment) if isinstance(node, Mapping) else None
    return flatten_leaves(node) if isinstance(node, Mapping) else {}


def _command_operation_rows() -> list[tuple[tuple[str, ...], str | None]]:
    table = _PACKAGE_ROOT / "entrypoints" / "cli" / "command_operation_table.py"
    for node in ast.parse(table.read_text(encoding="utf-8")).body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "COMMAND_OPERATION_ROWS"
            and node.value is not None
        ):
            return [_command_row(row) for row in ast.literal_eval(node.value)]
    raise AssertionError(f"{table} no longer declares COMMAND_OPERATION_ROWS")


def _command_row(row: object) -> tuple[tuple[str, ...], str | None]:
    assert isinstance(row, tuple) and len(row) == 2, row
    path, operation = row
    assert isinstance(path, tuple) and all(isinstance(segment, str) for segment in path), row
    assert operation is None or isinstance(operation, str), row
    return tuple(str(segment) for segment in path), operation


def _manifest_definition_ids() -> list[str]:
    manifest = _PACKAGE_ROOT / "_data" / "operations" / "contract_manifest.json"
    parsed = json.loads(manifest.read_text(encoding="utf-8"))
    return [str(operation["contract"]["definition_id"]) for operation in parsed["operations"]]


def _read_sources(roots: Iterable[Path], suffixes: frozenset[str]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*")) if root.is_dir() else []
        for candidate in candidates:
            if candidate.suffix not in suffixes or not candidate.is_file():
                continue
            relative = candidate.relative_to(_REPOSITORY_ROOT).as_posix()
            if "/tests/" in f"/{relative}" or ".stories." in candidate.name or ".test." in candidate.name:
                continue
            sources[relative] = candidate.read_text(encoding="utf-8")
    return sources


#: Python front ends that render setup rows.
_PYTHON_SURFACES: Final = {
    "CLI": _PACKAGE_ROOT / "entrypoints" / "cli" / "config" / "provision_cli.py",
    "TUI": _PACKAGE_ROOT / "entrypoints" / "tui" / "setup",
    "MCP": _SOURCE_ROOT / "cadrumo_mcp" / "mcp",
}
_REGISTRY_REFERENCE: Final = re.compile(
    r"import[^\n]*\bdependency_(?:contracts|registry|wording)\b|\bdependency_(?:contracts|registry|wording) import\b"
)
#: The readers that build ``config check``'s setup rows from the registry: the
#: preflight row builder, and the command that reads the rows through the
#: runtime, since the worker that runs the rest of the report has no runtime
#: connection. ``config repair`` runs without a session and points at
#: ``config provision status`` instead of rendering rows.
_REGISTRY_READERS: Final = (
    _PACKAGE_ROOT / "application" / "preflight.py",
    _PACKAGE_ROOT / "entrypoints" / "cli" / "config" / "check_cli.py",
)
_DESKTOP_SETUP: Final = _FRONTEND_SOURCE / "components" / "setup"
_DESKTOP_SURFACES: Final = (
    _DESKTOP_SETUP,
    _FRONTEND_SOURCE / "components" / "Settings.tsx",
    _FRONTEND_SOURCE / "components" / "Rail.tsx",
    _FRONTEND_SOURCE / "App.tsx",
)
_PYTHON: Final = frozenset({".py"})
_SCRIPT: Final = frozenset({".ts", ".tsx"})


# --------------------------------------------------------------------------
# The checkers catch representative defects
# --------------------------------------------------------------------------


def test_recovery_checker_names_an_item_whose_action_is_not_catalogued() -> None:
    """An item offering an operator action the catalogue lacks is a refusal with no way out."""
    assert recovery_action_findings([BROWSER_DECLARATION], {"operator.provision.browser"}) == []
    findings = recovery_action_findings([BROWSER_DECLARATION], {"operator.provision.model"})
    assert findings == ["browser: recovery action 'operator.provision.browser' is not in the operator catalogue"]


def test_display_name_checker_names_a_language_without_authored_text() -> None:
    """A plain name present in three languages but blank in the fourth is caught for that language only."""
    authored = {"en": "Browser", "es": "Navegador", "ca": "Navegador", "hu": "   "}

    def lookup(key: str, locale: str) -> str | None:
        assert key == "application.provisioning.dependency.browser.name"
        return authored.get(locale)

    findings = display_name_findings([BROWSER_DECLARATION], ("en", "es", "ca", "hu"), lookup)
    assert findings == ["browser: application.provisioning.dependency.browser.name has no authored text in 'hu'"]


def test_parity_checker_names_a_missing_key_a_blank_sentence_and_an_absent_subtree() -> None:
    """Languages must carry the same keys, each with authored text, and none may lack the subtree."""
    english: dict[tuple[str, ...], object] = {
        ("failure", "disk_full"): "There is not enough free space.",
        ("action", "resume"): "Resume",
    }
    spanish: dict[tuple[str, ...], object] = {
        ("failure", "disk_full"): "No hay espacio libre suficiente.",
        ("action", "resume"): " ",
    }
    catalan: dict[tuple[str, ...], object] = {("failure", "disk_full"): "No hi ha prou espai lliure."}
    assert locale_parity_findings({"en": english, "es": dict(english)}, label="provisioning") == []
    findings = locale_parity_findings({"en": english, "es": spanish, "ca": catalan, "hu": {}}, label="provisioning")
    assert findings == [
        "es: provisioning.action.resume is not authored text",
        "ca: provisioning.action.resume is missing",
        "hu: provisioning is missing or empty",
    ]


def test_coverage_checker_names_a_closed_value_without_wording() -> None:
    """Every failure category needs a sentence; dropping one is caught by its name."""
    paths = [("failure", category.value, "sentence") for category in DependencyFailureCategory]
    assert closed_value_coverage_findings(paths, [DependencyFailureCategory], label="en") == []
    without_disk = [path for path in paths if path[1] != DependencyFailureCategory.DISK_FULL.value]
    findings = closed_value_coverage_findings(without_disk, [DependencyFailureCategory], label="en")
    assert findings == ["en: no wording for DependencyFailureCategory.DISK_FULL ('disk_full')"]


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("Setup failed: disk_full", "shows an identifier 'disk_full'"),
        ("The Playwright download stopped.", "shows internal word 'playwright'"),
        ("Could not start the headless browser.", "shows internal word 'headless'"),
        ("El runtime local no responde.", "shows internal word 'runtime'"),
        ("A letöltött fájl digest értéke eltér.", "shows internal word 'digest'"),
        ("Ollama is not running.", "shows internal word 'ollama'"),
        ("Aprovisionamiento interrumpido.", "shows internal word 'provision'"),
        ("dependencies.setup was refused.", "shows an operation id 'dependencies.setup'"),
        ("ConnectionResetError while downloading.", "shows an exception name 'ConnectionResetError'"),
    ],
)
def test_internal_term_checker_names_each_kind_of_internal_vocabulary(sentence: str, expected: str) -> None:
    """Each kind of internal vocabulary the setup wording must never show is caught on its own."""
    findings = internal_term_findings({"fixture": sentence})
    assert f"fixture: {expected}" in findings


def test_internal_term_checker_passes_plain_sentences_with_placeholders() -> None:
    """Plain sentences pass, and a placeholder's own name is never read as shown text."""
    plain = {
        "en": "Cadrumo needs {required_size} free and this computer has {free_size}.",
        "es": "El navegador para la web de la Agencia Tributaria está listo.",
        "hu": "A helyi MI-program nem fut. Indítsd el, majd próbáld újra: %{program_name}.",
    }
    assert internal_term_findings(plain) == []


def test_python_list_checker_names_a_private_item_list_and_passes_a_single_item() -> None:
    """A tuple naming two setup items is a private list; one item compared against a row is not."""
    identities = item_identities(dependency_item_declarations())
    private = 'ITEMS = ("browser", "local_ai")\nif row.item_id == "local_ai":\n    pass\n'
    assert python_private_list_findings(private, identities, origin="fixture.py") == [
        "fixture.py:1: keeps its own list of setup items ['browser', 'local_ai']"
    ]
    single = 'if row.item_id in ("local_ai",):\n    pass\nKINDS = ["text", "table"]\n'
    assert python_private_list_findings(single, identities, origin="fixture.py") == []


def test_script_list_checker_names_a_private_item_array_and_ignores_comments() -> None:
    """An array naming two setup items is a private list, even across lines; a comment is not code."""
    identities = item_identities(dependency_item_declarations())
    private = 'const rows = rowsFrom(snapshot);\nconst order = [\n  "browser",\n  "local_ai",\n];\n'
    assert script_private_list_findings(private, identities, origin="fixture.tsx") == [
        "fixture.tsx:2: keeps its own list of setup items ['browser', 'local_ai']"
    ]
    commented = '// e.g. ["browser", "local_ai"]\nconst rows = snapshot.items.map((item) => item.itemId);\n'
    assert script_private_list_findings(commented, identities, origin="fixture.tsx") == []


def test_provision_leaf_checker_names_a_verb_that_submits_outside_its_role() -> None:
    """A component verb off the components role, a review that submits, or a foreign reader operation is caught."""
    rows = [
        (("config", "provision", "status"), "config.provision.status"),
        (("config", "provision", "status"), "dependencies.status"),
        (("config", "provision", "browser"), None),
        (("config", "provision", "review"), None),
        (("config", "provision", "review"), "config.provision.setup"),
        (("config", "provision", "report"), "local-reader.report"),
        (("config", "provision", "remove"), "local-reader.report"),
        (("config", "provision", "report"), "browser-runtime.provision"),
        (("config", "provision", "report"), None),
        (("config", "check"), None),
    ]
    assert provision_leaf_findings(rows) == [
        "config provision status: submits 'dependencies.status', which is not a components role operation",
        "config provision browser: submits None, which is not a components role operation",
        "config provision review: submits 'config.provision.setup' instead of answering a running review",
        "config provision remove: submits 'local-reader.report', which is not a components role operation",
        "config provision report: submits 'browser-runtime.provision', which is not a local reader operation",
        "config provision report: submits None, which is not a local reader operation",
    ]
    assert provision_leaf_findings([(("config", "check"), None)]) == ["the command table has no config provision leaf"]


def test_removed_operation_checker_names_each_removed_operation_still_registered() -> None:
    """A registered set holding a removed setup operation is caught by that operation's name."""
    assert removed_operation_findings(["local-reader.report", "local-reader.status"]) == []
    findings = removed_operation_findings(
        ["dependencies.setup", "browser-runtime.provision", "local-reader.provision", "ledger.list"]
    )
    assert findings == [
        "browser-runtime.provision is still registered",
        "dependencies.setup is still registered",
        "local-reader.provision is still registered",
    ]


def test_removed_identity_checker_names_a_lingering_alias_and_passes_a_phase_code() -> None:
    """A source spelling a removed operation id is a forwarding alias or a stale caller; a phase code is not."""
    sources = {
        "a.py": 'ALIAS = "browser-runtime.provision"',
        "b.py": 'OPERATION = "dependencies.setup"',
        "c.py": 'PHASE = f"dependencies.setup.{item}.plan"',
    }
    assert removed_identity_findings(sources, "browser-runtime.provision") == [
        "a.py: still names 'browser-runtime.provision'"
    ]
    assert removed_identity_findings(sources, "dependencies.setup") == ["b.py: still names 'dependencies.setup'"]


# --------------------------------------------------------------------------
# The real registry, catalogues and surfaces conform
# --------------------------------------------------------------------------


def test_every_item_offers_a_catalogued_recovery_action() -> None:
    """Every refusal for a setup item names an operator action the catalogue can resolve."""
    catalogued = [entry.action_id for entry in OPERATOR_ACTION_CATALOGUE.entries]
    findings = recovery_action_findings(dependency_item_declarations(), catalogued)
    assert not findings, "\n".join(findings)


def test_the_registry_holds_software_only_one_item_per_kind() -> None:
    """The browser and the local AI are the items; the profile's Google sign-in is not one."""
    declarations = dependency_item_declarations()
    assert [declaration.kind for declaration in declarations] == list(DependencyItemKind)
    assert "google" not in {declaration.item_id for declaration in declarations}


def test_every_item_has_its_plain_name_in_every_language() -> None:
    """Each item's plain name resolves to authored text in every supported language."""
    assert len(SUPPORTED_OUTPUT_LANGUAGES) >= 4, "the language census reached fewer languages than are supported"
    findings = display_name_findings(
        dependency_item_declarations(),
        SUPPORTED_OUTPUT_LANGUAGES,
        lambda key, locale: lookup_translation(key, locale=locale),
    )
    assert not findings, "\n".join(findings)


@pytest.mark.parametrize(
    ("catalogue", "path"), _WORDING_SUBTREES, ids=lambda value: ".".join(value) if isinstance(value, tuple) else value
)
def test_setup_wording_has_the_same_authored_keys_in_every_language(catalogue: str, path: tuple[str, ...]) -> None:
    """Each setup wording subtree exists in every language with the same keys, all authored."""
    subtrees = {locale: _wording_subtree(locale, catalogue, path) for locale in SUPPORTED_OUTPUT_LANGUAGES}
    findings = locale_parity_findings(subtrees, label=".".join(path))
    assert not findings, "\n".join(findings)


def test_setup_wording_covers_every_state_reason_category_and_action() -> None:
    """Every closed value a status row can carry has wording in every language."""
    findings: list[str] = []
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        leaves = _wording_subtree(locale, "application.yml", ("application", "provisioning"))
        findings.extend(closed_value_coverage_findings(leaves, _WORDED_FAMILIES, label=locale))
    assert not findings, "\n".join(findings)


def test_setup_wording_shows_no_internal_term() -> None:
    """No setup sentence, in any language, shows a category, an operation id or an internal word."""
    texts: dict[str, str] = {}
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        for catalogue, path in _WORDING_SUBTREES:
            for leaf, value in _wording_subtree(locale, catalogue, path).items():
                if isinstance(value, str):
                    texts[f"{locale}:{'.'.join((*path, *leaf))}"] = value
    assert texts, "the setup wording census found no sentence, so it would pass by checking none"
    findings = internal_term_findings(texts)
    assert not findings, "\n".join(findings)


@pytest.mark.parametrize("surface", sorted(_PYTHON_SURFACES))
def test_python_surface_reads_the_registry_rows_and_keeps_no_item_list(surface: str) -> None:
    """The CLI, the TUI and MCP read the setup contracts and keep no list of items of their own."""
    root = _PYTHON_SURFACES[surface]
    sources = _read_sources([root], _PYTHON)
    assert sources, f"{surface}: no setup source at {root.relative_to(_REPOSITORY_ROOT).as_posix()}"
    assert any(_REGISTRY_REFERENCE.search(text) for text in sources.values()), (
        f"{surface}: never reads the setup contracts"
    )
    identities = item_identities(dependency_item_declarations())
    findings = [
        finding
        for origin, text in sources.items()
        for finding in python_private_list_findings(text, identities, origin=origin)
    ]
    assert not findings, "\n".join(findings)


def test_config_check_reads_the_registry() -> None:
    """``aeat config check`` builds its setup rows from the registry, read through the runtime."""
    sources = _read_sources(_REGISTRY_READERS, _PYTHON)
    assert len(sources) == len(_REGISTRY_READERS)
    missing = [
        origin
        for origin, text in sources.items()
        if not re.search(r"from \.+(?:application\.)?dependency_(?:registry|contracts) import", text)
    ]
    assert not missing, f"these readers do not read the setup registry: {missing}"
    identities = item_identities(dependency_item_declarations())
    findings = [
        finding
        for origin, text in sources.items()
        for finding in python_private_list_findings(text, identities, origin=origin)
    ]
    assert not findings, "\n".join(findings)


def test_desktop_setup_renders_host_snapshots_and_keeps_no_item_list() -> None:
    """The desktop's setup surfaces render the host's setup snapshot and keep no item list of their own."""
    setup_sources = _read_sources([_DESKTOP_SETUP], _SCRIPT)
    assert setup_sources, "the desktop has no setup components"
    assert any(re.search(r"(?:ipc/contract|shell/host)[\"']", text) for text in setup_sources.values()), (
        "the desktop setup components never read the host's setup contract"
    )
    identities = item_identities(dependency_item_declarations())
    findings = [
        finding
        for origin, text in _read_sources(_DESKTOP_SURFACES, _SCRIPT).items()
        for finding in script_private_list_findings(text, identities, origin=origin)
    ]
    assert not findings, "\n".join(findings)


def test_component_verbs_submit_the_role_operations_and_the_local_reader_verbs_its_own() -> None:
    """The component verbs submit the components role's operations; the local reader's verbs submit its own."""
    findings = provision_leaf_findings(_command_operation_rows())
    assert not findings, "\n".join(findings)


def test_no_removed_setup_operation_is_registered() -> None:
    """The shipped contract manifest holds none of the setup operations the components role replaced."""
    definition_ids = _manifest_definition_ids()
    assert "local-reader.status" in definition_ids, "the manifest census found no operation it should hold"
    findings = removed_operation_findings(definition_ids)
    assert not findings, "\n".join(findings)


@pytest.mark.parametrize("identity", _REMOVED_OPERATIONS)
def test_a_removed_setup_operation_has_no_alias_or_caller_anywhere(identity: str) -> None:
    """A removed setup operation id appears in no product, client, runtime, harness or desktop source."""
    roots = [
        _PACKAGE_ROOT,
        _SOURCE_ROOT / "cadrumo_client",
        _SOURCE_ROOT / "cadrumo_runtime",
        _SOURCE_ROOT / "cadrumo_mcp",
        _FRONTEND_SOURCE,
    ]
    sources = _read_sources(roots, _PYTHON | _SCRIPT | frozenset({".json", ".yml", ".toml"}))
    findings = removed_identity_findings(sources, identity)
    assert not findings, "\n".join(findings)
