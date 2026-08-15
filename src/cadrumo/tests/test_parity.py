import logging
import re
from pathlib import Path

import pytest
import yaml
from dev.locales import (
    DOCS_SRC_DIR,
    HARNESS_SRC_DIR,
    LocaleError,
    LocaleManager,
    LocaleNode,
    scan_namespace_markers,
    scan_source_tree,
)
from dev.locales.cli import app

from ..application.operator_surface import MOUNTED_COMMAND_FAMILIES, FamilyMountState
from ..core import scan_directory
from ..core.external_constants import OutputLanguage
from .cli_runner import invoke_typer_app

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _leaf(data: dict[str, LocaleNode], *keys: str) -> str:
    """Walk a nested locale tree to a string leaf, asserting each level is a dict.

    ``LocaleNode`` is the recursive ``str | dict`` union, so chained
    ``data[a][b]`` subscripting is not type-safe; this helper narrows each
    intermediate node to a dict and the final node to a str.
    """
    node: LocaleNode = data
    for key in keys:
        assert isinstance(node, dict), f"expected dict at {key!r}, got {type(node).__name__}"
        node = node[key]
    assert isinstance(node, str), f"expected str leaf, got {type(node).__name__}"
    return node


def _mapping(data: dict[str, LocaleNode], *keys: str) -> dict[str, LocaleNode]:
    """Walk a nested locale tree to a mapping node."""
    node: LocaleNode = data
    for key in keys:
        assert isinstance(node, dict), f"expected dict at {key!r}, got {type(node).__name__}"
        node = node[key]
    assert isinstance(node, dict), f"expected dict node, got {type(node).__name__}"
    return node


# ---------------------------------------------------------------------------
# Product and executable naming contract
# ---------------------------------------------------------------------------

# The naming contract distinguishes four tokens that a catalogue string may
# legitimately carry, and pinning the surrounding prose to catch a violation
# means every unrelated copy edit reds this file instead. These patterns extract
# only the tokens the contract governs, so a reword stays green while a rename,
# a case slip, or an authority substitution does not.
_IDENTITY_TOKEN_PATTERNS: dict[str, re.Pattern[str]] = {
    # Identity contexts: headings, banners, the product as a name.
    "CADRUMO": re.compile(r"\bCADRUMO\b"),
    # Sentence prose: the product as a subject or possessive.
    "Cadrumo": re.compile(r"\bCadrumo\b"),
    # Machine names, which stay lower case and are not product prose.
    "cadrumo-mcp": re.compile(r"\bcadrumo-mcp\b"),
    "cadrumo": re.compile(r"\bcadrumo\b(?!-mcp)(?!://)"),
    # The tax authority, which is never renamed to the product.
    "AEAT": re.compile(r"\bAEAT\b"),
    # The sole human executable token.
    "aeat": re.compile(r"\baeat\b"),
}


def _identity_tokens(value: str) -> frozenset[str]:
    """Return the naming-contract tokens a catalogue string carries."""

    return frozenset(name for name, pattern in _IDENTITY_TOKEN_PATTERNS.items() if pattern.search(value))


def _assert_identity_contract(
    data: dict[str, LocaleNode],
    *keys: str,
    expected: frozenset[str],
) -> None:
    """Assert a catalogue string carries exactly the contract's identity tokens."""

    value = _leaf(data, *keys)
    actual = _identity_tokens(value)
    assert actual == expected, (
        f"{'.'.join(keys)} carries identity tokens {sorted(actual)}, expected {sorted(expected)}: {value!r}"
    )


# The root help heading and the landing headline are identity contexts: they name
# the product, and the first of them names the authority it files with. Neither
# may drift to sentence-case prose, a machine name, or an executable token.
_ROOT_HEADING_IDENTITY_TOKENS = frozenset({"CADRUMO", "AEAT"})
_LANDING_HEADLINE_IDENTITY_TOKENS = frozenset({"CADRUMO"})

# A command family's own catalogue strings live under ``cli.<root>.<child>``.
_CUSTODY_PASSPHRASE_NAMESPACE = ("cli", "config", "passphrase")
_CUSTODY_PASSPHRASE_PROMPTS = (
    "current_passphrase_prompt",
    "new_passphrase_prompt",
    "confirm_new_passphrase_prompt",
)
# A prompt is sentence prose addressed to the operator, not a heading.
_CUSTODY_PASSPHRASE_IDENTITY_TOKENS = frozenset({"Cadrumo"})


def _declared_family_mount_state(namespace: tuple[str, ...]) -> FamilyMountState:
    """Resolve a ``cli.<root>.<child>`` catalogue namespace to its family's mount state.

    Whether a family's strings are live, held, or gone is the operator surface's
    ruling, not this test's. ``MOUNTED_COMMAND_FAMILIES`` is that ruling, so the
    namespace is mapped to the family identity and the answer is read from
    :class:`FamilyMountState` rather than judged from the catalogue's contents.

    A namespace resolving to no declared family is a hard failure. Retirement is a
    deletion from the register, and the expectation here must be deleted in the
    same move rather than left asserting against a family that no longer exists.
    """

    matches = [family for family in MOUNTED_COMMAND_FAMILIES if ("cli", family.root.value, family.child) == namespace]
    assert matches, (
        f"{'.'.join(namespace)} resolves to no declared command family. "
        "Either the family was retired without removing this expectation, or the "
        "catalogue namespace no longer matches the family's root and child tokens."
    )
    (family,) = matches
    return family.mount_state


def _assert_command_family_catalogue_strings(
    data: dict[str, LocaleNode],
    namespace: tuple[str, ...],
    *,
    leaves: tuple[str, ...],
    expected: frozenset[str],
) -> None:
    """Assert a command family's catalogue strings against the family register.

    A ``MOUNTED`` family is on the wire, so every string it renders must exist and
    must satisfy the naming contract.

    A ``DECLARED_UNIMPLEMENTED`` family holds its strings: the operator surface
    declares the family and states the capability it is waiting on, but nothing
    reaches those strings, so their absence is not a defect and their presence is
    not stale residue to prune. Presence is therefore not asserted; the naming
    contract still binds whatever is present. The day the capability ships and the
    family flips to ``MOUNTED``, this demands the strings back without an edit here.
    """

    state = _declared_family_mount_state(namespace)
    held = state is FamilyMountState.DECLARED_UNIMPLEMENTED

    node: LocaleNode = data
    for key in namespace:
        if not isinstance(node, dict) or key not in node:
            assert held, (
                f"{'.'.join(namespace)} is absent from the catalogue while its command "
                f"family is {state.value}: a family the tree reaches must carry every string it renders."
            )
            return
        node = node[key]

    assert isinstance(node, dict), f"expected a namespace node at {'.'.join(namespace)}"
    for leaf in leaves:
        if leaf not in node:
            assert held, (
                f"{'.'.join((*namespace, leaf))} is absent from the catalogue while its "
                f"command family is {state.value}."
            )
            continue
        _assert_identity_contract(data, *namespace, leaf, expected=expected)


@pytest.fixture(scope="module")
def manager():
    locales_dir = Path(__file__).resolve().parents[1] / "locales"
    src_dir = locales_dir.parent
    # The documentation generators and the MCP harness both live outside the
    # package but render operator-facing prose from this same catalogue, so
    # the gate must see their keys or it reports every one as an extra key
    # with no codebase site.
    return LocaleManager(src_dir, locales_dir, extra_src_dirs=(DOCS_SRC_DIR, HARNESS_SRC_DIR))


@pytest.fixture(scope="module")
def locales_state(manager):
    codebase_keys = manager.get_codebase_keys()
    files = list(scan_directory(manager.locales_dir, pattern="*.yml"))
    locale_keys_map = {}

    for f in files:
        data = manager.load_locale(f)
        locale_keys_map[f.name] = manager.get_yaml_keys(data)

    return codebase_keys, locale_keys_map, files


def test_locale_integrity(manager):
    """Test 3: No duplicate keys, sections, or unparseable data."""
    files = list(scan_directory(manager.locales_dir, pattern="*.yml"))
    errors = []
    for f in files:
        try:
            # StrictUniqueKeyLoader refuses a duplicate key with LocaleError, which
            # is not a ValueError; any other malformed catalogue surfaces as a
            # yaml.YAMLError. Both are collected so one bad file does not hide the
            # rest, and neither is widened to a bare Exception, which would report
            # an unrelated failure as a catalogue-integrity finding.
            manager.load_locale(f)
        except LocaleError as e:
            errors.append(f"Integrity failure in {f.name}: {e}")
        except yaml.YAMLError as e:
            errors.append(f"YAML Parse error in {f.name}: {e}")

    if errors:
        pytest.fail("\n".join(errors))


def test_english_catalogue_distinguishes_product_prose_cli_and_identity_headings(
    manager: LocaleManager,
) -> None:
    """English copy follows the contextual product and executable naming contract."""
    data = manager.load_locale(manager.locales_dir / "en.yml")

    assert _leaf(data, "adapters", "google", "calc_sheets", "errors", "foreign_spreadsheet_not_owned") == (
        "The Google Sheet is not marked as owned by this Cadrumo profile."
    )
    assert _leaf(data, "adapters", "google", "oauth_flow", "errors", "profile_state_unresolved") == (
        "Google OAuth cannot resolve the selected Cadrumo profile state."
    )
    assert _leaf(data, "adapters", "google", "profile_binding", "errors", "no_active_profile") == (
        "No active Cadrumo profile is bound for Google OAuth."
    )
    assert _leaf(data, "adapters", "outbound", "storage", "google_drive", "errors", "former_vault_folder") == (
        "Google Drive vault folder {vault_folder_name} belongs to the former product and cannot be used; "
        "use the Cadrumo vault instead."
    )
    _assert_command_family_catalogue_strings(
        data,
        _CUSTODY_PASSPHRASE_NAMESPACE,
        leaves=_CUSTODY_PASSPHRASE_PROMPTS,
        expected=_CUSTODY_PASSPHRASE_IDENTITY_TOKENS,
    )
    assert _leaf(data, "cli", "config", "google", "profile_help") == (
        "Cadrumo profile name override (default = active profile on workflow state)"
    )

    assert _leaf(data, "mcp", "elicitation", "refusal", "no_channel") == (
        "'{command}' needs a human confirmation, and this client does not support elicitation. "
        "Run it from a client that can ask you questions, or run the equivalent Cadrumo CLI (`aeat`) command "
        "directly in a terminal."
    )
    # Identity contract only, not the prose. These two strings are live operator
    # copy this test does not own; pinning the sentence made every reword fail
    # here, and re-pinning it to whatever the catalogue now says only resets the
    # clock. What must not drift is the naming: the product in its identity
    # casing, the authority under its own acronym, and nothing else.
    _assert_identity_contract(
        data,
        "cli",
        "operator_surface",
        "help",
        "root",
        "heading",
        expected=_ROOT_HEADING_IDENTITY_TOKENS,
    )
    _assert_identity_contract(
        data,
        "cli",
        "root",
        "landing",
        "headline",
        expected=_LANDING_HEADLINE_IDENTITY_TOKENS,
    )


def test_spanish_catalogue_distinguishes_product_prose_cli_and_identity_headings(
    manager: LocaleManager,
) -> None:
    """Spanish copy follows the contextual product and executable naming contract."""
    data = manager.load_locale(manager.locales_dir / "es.yml")

    assert _leaf(data, "adapters", "outbound", "storage", "google_drive", "errors", "former_vault_folder") == (
        "La carpeta vault de Google Drive {vault_folder_name} pertenece al producto anterior y no se puede usar; "
        "usa la carpeta vault de Cadrumo."
    )
    assert _leaf(data, "cli", "ledger", "add", "system_state_not_assignable") == (
        "La clasificación '%{value}' la asigna Cadrumo automáticamente y no puede establecerse a mano. "
        "Elige una de: BUSINESS, PERSONAL, MIXED, u omite --classification para dejar la fila sin clasificar."
    )
    assert _leaf(data, "cli", "ledger", "classify", "system_state_not_assignable") == (
        "La clasificación '%{value}' la asigna Cadrumo automáticamente y no puede establecerse a mano. "
        "Elige una de: BUSINESS, PERSONAL, MIXED."
    )
    # Asserts the naming contract this test owns, not the prose: pinning the whole
    # sentence made every unrelated copy edit (an accent repair, a reword) fail here,
    # and re-pinning it to whatever the catalogue now says only proves the two strings
    # were copied from each other.
    timeout_copy = _leaf(data, "mcp", "call", "timeout")
    assert "aeat" in timeout_copy
    assert all(token in timeout_copy for token in ("{command}", "{tier}", "{seconds}"))
    assert _leaf(data, "mcp", "elicitation", "refusal", "no_channel") == (
        "'{command}' requiere confirmación humana y este cliente no admite la función de preguntas (elicitation). "
        "Ejecútalo desde un cliente que pueda hacerte preguntas, o ejecuta el comando equivalente de Cadrumo CLI "
        "(`aeat`) "
        "directamente en un terminal."
    )
    # Identity contract only — see the English counterpart for why the prose is not pinned.
    _assert_identity_contract(
        data,
        "cli",
        "operator_surface",
        "help",
        "root",
        "heading",
        expected=_ROOT_HEADING_IDENTITY_TOKENS,
    )
    _assert_identity_contract(
        data,
        "cli",
        "root",
        "landing",
        "headline",
        expected=_LANDING_HEADLINE_IDENTITY_TOKENS,
    )


def test_catalan_catalogue_distinguishes_product_prose_cli_and_identity_headings(
    manager: LocaleManager,
) -> None:
    """Catalan copy follows the contextual product and executable naming contract."""
    data = manager.load_locale(manager.locales_dir / "ca.yml")

    assert _leaf(data, "adapters", "google", "calc_sheets", "errors", "foreign_spreadsheet_not_owned") == (
        "El full de Google no està marcat com a propietat d'aquest perfil Cadrumo."
    )
    assert _leaf(data, "adapters", "google", "oauth_flow", "errors", "profile_state_unresolved") == (
        "Google OAuth no pot resoldre l'estat del perfil Cadrumo seleccionat."
    )
    assert _leaf(data, "adapters", "google", "profile_binding", "errors", "no_active_profile") == (
        "No hi ha cap perfil Cadrumo actiu enllaçat per a Google OAuth."
    )
    assert _leaf(data, "adapters", "outbound", "storage", "google_drive", "errors", "former_vault_folder") == (
        "La carpeta vault de Google Drive {vault_folder_name} pertany al producte anterior i no es pot utilitzar; "
        "usa la carpeta vault de Cadrumo."
    )
    _assert_command_family_catalogue_strings(
        data,
        _CUSTODY_PASSPHRASE_NAMESPACE,
        leaves=_CUSTODY_PASSPHRASE_PROMPTS,
        expected=_CUSTODY_PASSPHRASE_IDENTITY_TOKENS,
    )
    assert _leaf(data, "cli", "config", "google", "profile_help") == (
        "Perfil Cadrumo a usar (per defecte = perfil actiu de l'estat de flux)"
    )
    assert _leaf(data, "cli", "ledger", "add", "system_state_not_assignable") == (
        "La classificació '%{value}' l'assigna Cadrumo automàticament i no es pot establir a mà. "
        "Tria'n una: BUSINESS, PERSONAL, MIXED, o omet --classification per deixar la fila sense classificar."
    )
    assert _leaf(data, "cli", "ledger", "classify", "system_state_not_assignable") == (
        "La classificació '%{value}' l'assigna Cadrumo automàticament i no es pot establir a mà. "
        "Tria'n una: BUSINESS, PERSONAL, MIXED."
    )
    # Naming contract only — see the Spanish counterpart for why the prose is not pinned.
    timeout_copy = _leaf(data, "mcp", "call", "timeout")
    assert "aeat" in timeout_copy
    assert all(token in timeout_copy for token in ("{command}", "{tier}", "{seconds}"))
    assert _leaf(data, "mcp", "elicitation", "refusal", "no_channel") == (
        "'{command}' requereix confirmació humana i aquest client no admet la funció de preguntes (elicitation). "
        "Executa'l des d'un client que pugui fer-te preguntes, o executa l'ordre equivalent de Cadrumo CLI "
        "(`aeat`) directament en un terminal."
    )
    # Identity contract only — see the English counterpart for why the prose is not pinned.
    _assert_identity_contract(
        data,
        "cli",
        "operator_surface",
        "help",
        "root",
        "heading",
        expected=_ROOT_HEADING_IDENTITY_TOKENS,
    )
    _assert_identity_contract(
        data,
        "cli",
        "root",
        "landing",
        "headline",
        expected=_LANDING_HEADLINE_IDENTITY_TOKENS,
    )


def test_hungarian_catalogue_distinguishes_product_prose_cli_and_identity_headings(
    manager: LocaleManager,
) -> None:
    """Hungarian copy follows the contextual product and executable naming contract."""
    data = manager.load_locale(manager.locales_dir / "hu.yml")

    assert _leaf(data, "adapters", "outbound", "storage", "google_drive", "errors", "former_vault_folder") == (
        "A Google Drive vault mappa {vault_folder_name} az előző termékhez tartozik és nem használható; "
        "használja a Cadrumo vault mappát."
    )
    assert _leaf(data, "cli", "ledger", "add", "system_state_not_assignable") == (
        "A(z) '%{value}' besorolást a Cadrumo automatikusan állítja be, kézzel nem adható meg. "
        "Válassz egyet: BUSINESS, PERSONAL, MIXED, vagy hagyd ki a --classification kapcsolót, "
        "hogy a sor besorolatlan maradjon."
    )
    assert _leaf(data, "cli", "ledger", "classify", "system_state_not_assignable") == (
        "A(z) '%{value}' besorolást a Cadrumo automatikusan állítja be, kézzel nem adható meg. "
        "Válassz egyet: BUSINESS, PERSONAL, MIXED."
    )
    assert _leaf(data, "mcp", "elicitation", "refusal", "no_channel") == (
        "A(z) '{command}' emberi megerősítést igényel, és ez a kliens nem támogatja a kérdezés "
        "(elicitation) funkciót. Futtasd olyan kliensből, amely tud kérdezni, vagy futtasd a megfelelő "
        "Cadrumo CLI (`aeat`) parancsot közvetlenül a terminálban."
    )
    # Identity contract only — see the English counterpart for why the prose is not pinned.
    _assert_identity_contract(
        data,
        "cli",
        "operator_surface",
        "help",
        "root",
        "heading",
        expected=_ROOT_HEADING_IDENTITY_TOKENS,
    )
    _assert_identity_contract(
        data,
        "cli",
        "root",
        "landing",
        "headline",
        expected=_LANDING_HEADLINE_IDENTITY_TOKENS,
    )


def test_identity_token_extractor_discriminates_product_spellings() -> None:
    """The naming-contract extractor separates the four spellings it governs.

    Anti-vacuity for the re-founded heading assertions: an extractor that matched
    every spelling as one token, or matched none, would let those assertions pass
    on exactly the rename they exist to refuse.
    """

    assert _identity_tokens("CADRUMO - workflow with the Spanish Tax Agency (AEAT)") == {"CADRUMO", "AEAT"}
    assert _identity_tokens("Cadrumo prepares the draft.") == {"Cadrumo"}
    assert _identity_tokens("Install cadrumo; launch cadrumo-mcp.") == {"cadrumo", "cadrumo-mcp"}
    assert _identity_tokens("launch cadrumo-mcp only") == {"cadrumo-mcp"}
    assert _identity_tokens("read cadrumo://status") == set()
    assert _identity_tokens("Run `aeat config profile status`.") == {"aeat"}
    assert _identity_tokens("nothing to see here") == set()


def test_root_heading_identity_contract_refuses_a_product_rename() -> None:
    """The heading contract reds on a rename and stays green on a reword.

    The rot this replaced was a pinned sentence, so the replacement is only worth
    having if it still bites the thing the pin was there for.
    """

    reworded: dict[str, LocaleNode] = {
        "cli": {"operator_surface": {"help": {"root": {"heading": "CADRUMO - anything at all (AEAT)"}}}}
    }
    _assert_identity_contract(
        reworded,
        "cli",
        "operator_surface",
        "help",
        "root",
        "heading",
        expected=_ROOT_HEADING_IDENTITY_TOKENS,
    )

    for corrupted in (
        "Cadrumo - local-first workflow with AEAT",
        "cadrumo - local-first workflow with AEAT",
        "CADRUMO - local-first workflow with CADRUMO",
        "CADRUMO - local-first workflow with the AEAT, run aeat config check",
    ):
        corrupted_catalogue: dict[str, LocaleNode] = {
            "cli": {"operator_surface": {"help": {"root": {"heading": corrupted}}}}
        }
        with pytest.raises(AssertionError):
            _assert_identity_contract(
                corrupted_catalogue,
                "cli",
                "operator_surface",
                "help",
                "root",
                "heading",
                expected=_ROOT_HEADING_IDENTITY_TOKENS,
            )


def test_custody_passphrase_strings_are_held_by_the_family_register() -> None:
    """The passphrase namespace's disposition is read, not judged.

    The catalogue strings for ``config passphrase`` are neither live nor prunable:
    the operator surface declares the family and records that credential rotation
    exists at no layer. That disposition lives in ``MOUNTED_COMMAND_FAMILIES``, so
    this pins that the register is what answers, and that the answer is currently
    ``DECLARED_UNIMPLEMENTED`` rather than silently absent.
    """

    assert _declared_family_mount_state(_CUSTODY_PASSPHRASE_NAMESPACE) is FamilyMountState.DECLARED_UNIMPLEMENTED

    with pytest.raises(AssertionError, match="resolves to no declared command family"):
        _declared_family_mount_state(("cli", "config", "recover"))


def test_a_mounted_family_may_not_hold_its_catalogue_strings() -> None:
    """Absence is tolerated for a held family and refused for a mounted one.

    Anti-vacuity for the held branch: without this, a catalogue that lost every
    command family's strings would pass the four locale tests unchanged.
    """

    mounted = next(family for family in MOUNTED_COMMAND_FAMILIES if family.mount_state is FamilyMountState.MOUNTED)
    mounted_namespace = ("cli", mounted.root.value, mounted.child)

    _assert_command_family_catalogue_strings(
        {},
        _CUSTODY_PASSPHRASE_NAMESPACE,
        leaves=_CUSTODY_PASSPHRASE_PROMPTS,
        expected=_CUSTODY_PASSPHRASE_IDENTITY_TOKENS,
    )

    with pytest.raises(AssertionError, match="absent from the catalogue"):
        _assert_command_family_catalogue_strings(
            {},
            mounted_namespace,
            leaves=("some_prompt",),
            expected=frozenset({"Cadrumo"}),
        )

    populated: dict[str, LocaleNode] = {"cli": {mounted.root.value: {mounted.child: {"other": "Cadrumo"}}}}
    with pytest.raises(AssertionError, match="absent from the catalogue"):
        _assert_command_family_catalogue_strings(
            populated,
            mounted_namespace,
            leaves=("some_prompt",),
            expected=frozenset({"Cadrumo"}),
        )


def test_a_held_family_string_still_carries_the_naming_contract() -> None:
    """Held is not unchecked: a present string still answers to the contract."""

    catalogue: dict[str, LocaleNode] = {
        "cli": {
            "config": {
                "passphrase": {
                    "current_passphrase_prompt": "Current cadrumo secret-store passphrase: ",
                    "new_passphrase_prompt": "New Cadrumo secret-store passphrase: ",
                    "confirm_new_passphrase_prompt": "Confirm new Cadrumo secret-store passphrase: ",
                }
            }
        }
    }

    with pytest.raises(AssertionError, match="carries identity tokens"):
        _assert_command_family_catalogue_strings(
            catalogue,
            _CUSTODY_PASSPHRASE_NAMESPACE,
            leaves=_CUSTODY_PASSPHRASE_PROMPTS,
            expected=_CUSTODY_PASSPHRASE_IDENTITY_TOKENS,
        )


def test_set_locale_value_updates_one_leaf(tmp_path: Path):
    """The locale CLI write path updates a concrete leaf in a real YAML file."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "es.yml"
    locale_path.write_text(
        "cli:\n"
        "  app:\n"
        "    modelo:\n"
        "      aggregate:\n"
        "        json_validation_error: cli.app.modelo.aggregate.json_validation_error\n"
        "        json_parse_error: '{flag} debe ser un objeto JSON.'\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)
    written_path = temp_manager.set_locale_value(
        "es",
        "cli.app.modelo.aggregate.json_validation_error",
        "%{flag} no es válido: %{details}.",
    )

    assert written_path == locale_path
    data = temp_manager.load_locale(locale_path)
    assert _leaf(data, "cli", "app", "modelo", "aggregate", "json_validation_error") == (
        "%{flag} no es válido: %{details}."
    )
    assert _leaf(data, "cli", "app", "modelo", "aggregate", "json_parse_error") == "{flag} debe ser un objeto JSON."


def test_set_locale_value_preserves_multiline_value_roundtrip(tmp_path: Path):
    """A multi-line value survives set + reload byte-identically.

    Single-quoted YAML folds raw line breaks into spaces, so a naive
    quoted write of a multi-line value silently corrupts it on the next
    parse. The setter must emit a representation whose reload equals the
    exact string that was set.
    """

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "es.yml"
    locale_path.write_text(
        "wizard:\n  errors:\n    unsupported_console: marcador\n    other: intacto\n",
        encoding="utf-8",
    )

    value = (
        "El asistente necesita una terminal interactiva.\n"
        "Todavía no se ha guardado nada.\n"
        "\n"
        "1. Vuelve a ejecutar el comando:\n"
        "     aeat config profile create NAME\n"
        "\n"
        "2. O usa flags: --quiet --tax-id NIF/CIF/DNI/NIE"
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)
    temp_manager.set_locale_value("es", "wizard.errors.unsupported_console", value)

    data = temp_manager.load_locale(locale_path)
    assert _leaf(data, "wizard", "errors", "unsupported_console") == value
    assert _leaf(data, "wizard", "errors", "other") == "intacto"


def test_set_locale_value_falls_back_for_multiline_scalar_that_looks_like_a_key(tmp_path: Path):
    """A scalar continuation such as ``basis:`` cannot block a real locale edit."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "en.yml"
    locale_path.write_text(
        "cli:\n"
        "  app:\n"
        "    modelo:\n"
        "      work:\n"
        "        legal_note: 'Legal\n"
        "          basis: regulation.'\n"
        "        next_action: Run aeat app modelo work calculate.\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)
    temp_manager.set_locale_value(
        "en",
        "cli.app.modelo.work.next_action",
        "Run aeat app modelo work calculate.",
    )

    data = temp_manager.load_locale(locale_path)
    assert _leaf(data, "cli", "app", "modelo", "work", "legal_note") == "Legal basis: regulation."
    assert _leaf(data, "cli", "app", "modelo", "work", "next_action") == "Run aeat app modelo work calculate."


def test_set_locale_value_canonicalizes_human_cli_without_rewriting_product_prose(tmp_path: Path):
    """Locale maintenance preserves product prose while canonicalizing the human CLI."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "en.yml"
    locale_path.write_text("cli:\n  root:\n    next_action: placeholder\n", encoding="utf-8")

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)
    temp_manager.set_locale_value(
        "en",
        "cli.root.next_action",
        "Cadrumo prepares the draft; run cadrumo app modelo work calculate.",
    )

    data = temp_manager.load_locale(locale_path)
    assert _leaf(data, "cli", "root", "next_action") == (
        "Cadrumo prepares the draft; run aeat app modelo work calculate."
    )


def test_canonicalize_product_identity_references_handles_folded_help_copy(tmp_path: Path):
    """Bulk maintenance normalizes folded help without changing machine or authority names."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    for locale in ("ca", "en"):
        (locales_dir / f"{locale}.yml").write_text(
            "cli:\n"
            "  root:\n"
            "    next_action: >-\n"
            "      Cadrumo prepares tax forms for AEAT. Run cadrumo\n"
            "      app modelo work calculate or cadrumo manual fetch.\n"
            "product:\n"
            "  machine_names: Install cadrumo; launch cadrumo-mcp; read cadrumo://status.\n",
            encoding="utf-8",
        )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)
    updated = temp_manager.canonicalize_product_identity_references()

    assert {path.name for path in updated} == {"ca.yml", "en.yml"}
    for locale in ("ca", "en"):
        data = temp_manager.load_locale(locales_dir / f"{locale}.yml")
        assert _leaf(data, "cli", "root", "next_action") == (
            "Cadrumo prepares tax forms for AEAT. Run aeat app modelo work calculate or aeat manual fetch."
        )
        assert _leaf(data, "product", "machine_names") == (
            "Install cadrumo; launch cadrumo-mcp; read cadrumo://status."
        )


def test_canonicalize_product_identity_cli_selects_only_one_supported_locale(tmp_path: Path) -> None:
    """The real command updates English without writing any sibling catalogue."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    for locale in OutputLanguage:
        (locales_dir / f"{locale.value}.yml").write_text(
            "product:\n  guidance: Cadrumo works with AEAT; run cadrumo app overview status.\n",
            encoding="utf-8",
        )
    manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)
    sibling_bytes = {
        locale.value: (locales_dir / f"{locale.value}.yml").read_bytes()
        for locale in OutputLanguage
        if locale is not OutputLanguage.EN
    }

    result = invoke_typer_app(
        app,
        ["canonicalize-product-identity", "--locale", "en"],
        obj=manager,
    )

    assert result.exit_code == 0, result.output
    assert "1 locale catalogue(s)" in result.output
    en_data = manager.load_locale(locales_dir / "en.yml")
    assert _leaf(en_data, "product", "guidance") == ("Cadrumo works with AEAT; run aeat app overview status.")
    assert {locale: (locales_dir / f"{locale}.yml").read_bytes() for locale in sibling_bytes} == sibling_bytes


def test_canonicalize_product_identity_cli_rejects_invalid_locale_without_writing(tmp_path: Path) -> None:
    """The production locale enum rejects traversal before the manager can write."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    for locale in OutputLanguage:
        (locales_dir / f"{locale.value}.yml").write_text(
            "product:\n  guidance: Cadrumo works with AEAT.\n",
            encoding="utf-8",
        )
    manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)
    before = {path.name: path.read_bytes() for path in scan_directory(locales_dir, pattern="*.yml")}

    result = invoke_typer_app(
        app,
        ["canonicalize-product-identity", "--locale", "../en"],
        obj=manager,
    )

    assert result.exit_code != 0
    assert "Invalid value" in result.output
    after = {path.name: path.read_bytes() for path in scan_directory(locales_dir, pattern="*.yml")}
    assert after == before


def test_canonicalize_product_identity_cli_omission_updates_every_catalogue(tmp_path: Path) -> None:
    """Omitting the selector preserves the original all-catalogue behavior."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    for locale in OutputLanguage:
        (locales_dir / f"{locale.value}.yml").write_text(
            "product:\n  guidance: Cadrumo works with AEAT; run cadrumo config profile status.\n",
            encoding="utf-8",
        )
    manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    result = invoke_typer_app(app, ["canonicalize-product-identity"], obj=manager)

    assert result.exit_code == 0, result.output
    assert "4 locale catalogue(s)" in result.output
    for locale in OutputLanguage:
        data = manager.load_locale(locales_dir / f"{locale.value}.yml")
        assert _leaf(data, "product", "guidance") == ("Cadrumo works with AEAT; run aeat config profile status.")


def test_set_locale_value_appends_missing_leaf_under_existing_parent(tmp_path: Path):
    """The locale setter can repair a missing leaf without rebuilding the file."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "es.yml"
    locale_path.write_text(
        "cli:\n  locales:\n    app_help: Auditar y generar catálogos de traducción\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.set_locale_value("es", "cli.locales.set_locale_help", "Código de locale.")

    data = temp_manager.load_locale(locale_path)
    assert _leaf(data, "cli", "locales", "set_locale_help") == "Código de locale."


def test_set_locale_value_appends_missing_leaf_after_unterminated_final_line(tmp_path: Path):
    """Appending below a parent whose last child ends the file with no trailing
    newline must not run the new leaf onto that line.

    A hand-recovered file or an editor that strips the final newline leaves the
    catalogue in exactly this shape, and the append is the mandated authoring
    path for a missing key.
    """

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "es.yml"
    locale_path.write_bytes(b"cli:\n  locales:\n    app_help: Auditar y generar catalogos")

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.set_locale_value("es", "cli.locales.set_locale_help", "Codigo de locale.")

    written = locale_path.read_bytes()
    assert b"catalogos\n    set_locale_help:" in written, (
        f"the appended leaf ran onto the parent's unterminated final line: {written!r}"
    )
    data = temp_manager.load_locale(locale_path)
    assert _leaf(data, "cli", "locales", "app_help") == "Auditar y generar catalogos"
    assert _leaf(data, "cli", "locales", "set_locale_help") == "Codigo de locale."


def test_remove_locale_value_deletes_existing_leaf(tmp_path: Path):
    """The locale remover deletes a stale leaf and leaves siblings intact."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "es.yml"
    locale_path.write_text(
        "cli:\n  locales:\n    stale: Obsoleto\n    app_help: Auditar y generar catálogos de traducción\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.remove_locale_value("es", "cli.locales.stale")

    data = temp_manager.load_locale(locale_path)
    assert "stale" not in _mapping(data, "cli", "locales")
    assert _leaf(data, "cli", "locales", "app_help") == "Auditar y generar catálogos de traducción"


def test_remove_locale_value_prunes_empty_namespace(tmp_path: Path):
    """Removing the last leaf below a namespace removes the stale parent row too."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "en.yml"
    locale_path.write_text(
        "wizard:\n"
        "  setup:\n"
        "    flags:\n"
        "      old-option:\n"
        "        help: Old option\n"
        "      current-option:\n"
        "        help: Current option\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.remove_locale_value("en", "wizard.setup.flags.old-option.help")

    data = temp_manager.load_locale(locale_path)
    assert "old-option" not in _mapping(data, "wizard", "setup", "flags")
    assert _leaf(data, "wizard", "setup", "flags", "current-option", "help") == "Current option"


def test_remove_locale_value_deletes_yaml_null_leaf(tmp_path: Path):
    """A stale empty YAML key can be removed through the locale manager."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "en.yml"
    locale_path.write_text(
        "wizard:\n  setup:\n    flags:\n      old-option:\n      current-option:\n        help: Current option\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.remove_locale_value("en", "wizard.setup.flags.old-option")

    data = temp_manager.load_locale(locale_path)
    assert "old-option" not in _mapping(data, "wizard", "setup", "flags")
    assert _leaf(data, "wizard", "setup", "flags", "current-option", "help") == "Current option"


def test_set_locale_value_rejects_locale_path_traversal(tmp_path: Path):
    """The locale setter only writes locale files under its configured root."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "es.yml").write_text("cli:\n  label: correcto\n", encoding="utf-8")
    outside = tmp_path / "outside.yml"
    outside.write_text("cli:\n  label: fuera\n", encoding="utf-8")

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    with pytest.raises(LocaleError):
        temp_manager.set_locale_value("../outside", "cli.label", "no escribir")

    outside_data = temp_manager.load_locale(outside)
    assert _leaf(outside_data, "cli", "label") == "fuera"


def test_locale_set_cli_rejects_path_like_locale_without_writing() -> None:
    """The canonical locale CLI rejects traversal-shaped locale arguments."""

    result = invoke_typer_app(app, ["set", "../outside", "cli.locales.app_help", "unsafe"])

    assert result.exit_code != 0
    assert "Invalid locale code" in result.output


def test_ast_scanner_logs_syntax_failures_and_keeps_scanning(tmp_path: Path, caplog) -> None:
    """A broken module is debug-logged and does not hide valid locale keys nearby."""

    (tmp_path / "valid_surface.py").write_text(
        "from cadrumo.core.i18n import tr\n"
        "\n"
        "def render(reason):\n"
        "    return tr('cli.locales.app_help') + tr(f'wizard.errors.{reason}')\n",
        encoding="utf-8",
    )
    (tmp_path / "broken_surface.py").write_text("def broken(:\n", encoding="utf-8")

    caplog.set_level(logging.DEBUG, logger="dev.locales._ast_scanner")

    assert "cli.locales.app_help" in scan_source_tree(tmp_path)
    assert "wizard.errors.*" in scan_namespace_markers(tmp_path)
    assert any(
        "locale ast scan: parse failure" in record.getMessage() and "broken_surface.py" in record.getMessage()
        for record in caplog.records
    )


def test_ast_scanner_ignores_dynamic_domain_fact_keys(tmp_path: Path) -> None:
    """Dynamic profile fact paths are not locale namespaces."""

    (tmp_path / "profile_facts.py").write_text(
        "def birth_date(fact_index, idx):\n    return fact_index.get(f'renta_family.descendiente.{idx}.birth_date')\n",
        encoding="utf-8",
    )

    assert "renta_family.descendiente.*" not in scan_namespace_markers(tmp_path)


def test_ast_scanner_collects_translation_key_kwargs(tmp_path: Path) -> None:
    """Helper APIs that name `translation_key` still declare live locale keys."""

    (tmp_path / "helper_surface.py").write_text(
        "def helper(*, translation_key: str):\n"
        "    return translation_key\n"
        "\n"
        "def render():\n"
        "    return helper(translation_key='cli.app.modelo.work.sal_reserva_not_decimal')\n",
        encoding="utf-8",
    )

    assert "cli.app.modelo.work.sal_reserva_not_decimal" in scan_source_tree(tmp_path)


def test_ast_scanner_resolves_aliased_translator_import(tmp_path: Path) -> None:
    """An aliased ``tr`` import (``from ... import tr as _tr``) declares live keys.

    The underscore-aliased module-level import convention
    (``from cadrumo.core.i18n import tr as _tr``) is used across the CLI surface.
    The scanner must resolve the alias and treat ``_tr("dotted.key")`` as a live
    translation call; otherwise the key is invisible and its genuinely-live
    catalogue entry is wrongly reported as an orphan.
    """

    (tmp_path / "aliased_surface.py").write_text(
        "from cadrumo.core.i18n import tr as _tr\n\ndef render() -> str:\n    return _tr('cli.root.verbose_help')\n",
        encoding="utf-8",
    )

    assert "cli.root.verbose_help" in scan_source_tree(tmp_path)


def test_ast_scanner_ignores_unaliased_unrelated_call(tmp_path: Path) -> None:
    """A call to a same-named function that is NOT the translator alias is ignored.

    Anti-vacuity for the alias resolver: a bare ``_tr`` name that was never
    imported as an alias of ``tr`` must not have its argument harvested as a
    locale key.
    """

    (tmp_path / "unrelated_surface.py").write_text(
        "def _tr(value: str) -> str:\n"
        "    return value\n"
        "\n"
        "def render() -> str:\n"
        "    return _tr('cli.root.not_a_real_locale_key')\n",
        encoding="utf-8",
    )

    assert "cli.root.not_a_real_locale_key" not in scan_source_tree(tmp_path)


def test_ast_scanner_collects_locale_key_constant_registries(tmp_path: Path) -> None:
    """Policy registries that select locale keys for later callers must be visible."""

    (tmp_path / "policy_surface.py").write_text(
        "REFUSAL_LOCALE_KEYS = {\n"
        "    '151': 'cli.app.modelo.work.create_stub_modelo_151_refused',\n"
        "    '721': 'cli.app.modelo.work.create_stub_modelo_refused',\n"
        "}\n"
        "PLAIN_VALUES = {'not-a-locale-key': 'cli.app.modelo.work.dead_extra'}\n",
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)
    assert "cli.app.modelo.work.create_stub_modelo_151_refused" in keys
    assert "cli.app.modelo.work.create_stub_modelo_refused" in keys
    assert "cli.app.modelo.work.dead_extra" not in keys


def _namespace_covers(key: str, prefix: str) -> bool:
    """Return True when ``key`` carries ``prefix`` as a dot-bounded sub-path.

    Matches both top-level (``residence.ccaa.x``) and wrapped
    (``wizard.setup.residence.ccaa.x``) placements so dynamic-key
    construction that flows through a wrapper helper still counts
    against the declared namespace.
    """

    return f".{prefix}." in f".{key}."


def test_codebase_to_locale_parity(locales_state, manager):
    """Test 1: Parity between the codebase truth and the localizations.

    Concrete codebase keys must be present in every locale. Locale
    keys absent from the concrete codebase set are tolerated when they
    sit under a declared dynamic-namespace prefix (the runtime builds
    the tail via f-string or concatenation, so the static scanner sees
    only the prefix).
    """
    codebase_keys, locale_keys_map, _ = locales_state
    assert len(codebase_keys) > 0, "No translation keys found in codebase"

    namespace_prefixes = tuple(
        marker.rstrip("*").rstrip(".") for marker in manager.get_codebase_namespaces() if marker.rstrip("*").rstrip(".")
    )

    def _covered_by_namespace(key: str) -> bool:
        return any(_namespace_covers(key, prefix) for prefix in namespace_prefixes)

    errors = []
    for name, keys in locale_keys_map.items():
        missing = codebase_keys - keys
        extra = {key for key in keys - codebase_keys if not _covered_by_namespace(key)}

        if missing:
            errors.append(f"{name} is missing {len(missing)} codebase keys.")
        if extra:
            errors.append(f"{name} contains {len(extra)} extra keys not in the codebase.")

    if errors:
        pytest.fail("\n".join(errors))


def test_codebase_namespaces_are_satisfied_by_locale_entries(locales_state, manager):
    """Every dynamic-namespace marker has at least one concrete locale entry."""
    _, locale_keys_map, _ = locales_state
    namespaces = manager.get_codebase_namespaces()
    assert namespaces, (
        "manager.get_codebase_namespaces() returned an empty collection. "
        "The namespace scanner may be broken or misconfigured. "
        "Fix the scanner rather than silently skipping the namespace coverage check."
    )

    errors = []
    for marker in sorted(namespaces):
        prefix = marker.rstrip("*").rstrip(".")
        if not prefix:
            continue
        for name, keys in locale_keys_map.items():
            if not any(_namespace_covers(key, prefix) for key in keys):
                errors.append(f"{name} carries no key matching namespace marker {marker!r}")

    if errors:
        pytest.fail("\n".join(errors))


def test_inter_locale_parity(locales_state):
    """Test 2: Parity between localization files themselves."""
    _, locale_keys_map, files = locales_state
    assert len(files) > 1, "Not enough localization files to compare."

    reference_file = files[0].name
    reference_keys = locale_keys_map[reference_file]

    errors = []
    for name, keys in locale_keys_map.items():
        if name == reference_file:
            continue
        missing = reference_keys - keys
        extra = keys - reference_keys

        if missing or extra:
            msg = f"{name} does not match {reference_file}."
            if missing:
                msg += f" Missing {len(missing)} keys."
            if extra:
                msg += f" Has {len(extra)} extra keys."
            errors.append(msg)

    if errors:
        pytest.fail("\n".join(errors))


# ---------------------------------------------------------------------------
# F-string registry: concrete key expansion and coverage
# ---------------------------------------------------------------------------


def test_fstring_registry_expands_sal_and_sll_keys() -> None:
    """The f-string registry must produce concrete keys for SAL and SLL legal-entity-form entries.

    These two enum values caused the #553 structural-repair-exception incident because
    scaffold could not generate their locale keys from the namespace marker alone.
    """
    from dev.locales import get_registered_keys

    keys = get_registered_keys()
    assert "wizard.setup.taxpayer-type.legal-entity-form.choices.sal.label" in keys, (
        "sal key missing from f-string registry — LegalEntityForm.SAL is not covered"
    )
    assert "wizard.setup.taxpayer-type.legal-entity-form.choices.sll.label" in keys, (
        "sll key missing from f-string registry — LegalEntityForm.SLL is not covered"
    )


def test_fstring_registry_all_keys_present_in_all_locales(manager: LocaleManager) -> None:
    """Every key produced by the f-string registry must exist in every locale file.

    This test is the concrete-key companion to
    test_codebase_namespaces_are_satisfied_by_locale_entries. The namespace check
    validates that at least one entry exists under each prefix; this test validates
    that every specific key the runtime can build from a bounded enumeration is
    scaffolded. A failure here means a new enum value was added without running
    scaffold (or scaffold does not cover it yet).
    """
    from dev.locales import get_registered_keys

    registered_keys = get_registered_keys()
    errors = []
    for locale_file in scan_directory(manager.locales_dir, pattern="*.yml"):
        data = manager.load_locale(locale_file)
        yaml_keys = manager.get_yaml_keys(data)
        missing = registered_keys - yaml_keys
        if missing:
            errors.append(
                f"{locale_file.name} is missing {len(missing)} f-string-registered key(s): "
                + ", ".join(sorted(missing)[:5])
                + (" ..." if len(missing) > 5 else ""),
            )
    if errors:
        pytest.fail(
            "\n".join(errors) + "\nRun `python -m dev.locales scaffold` to insert missing placeholder entries.",
        )


def test_scaffold_surfaces_fstring_registry_keys_as_missing(tmp_path: Path) -> None:
    """Scaffold never silently drops an f-string-registered key.

    Simulates the SAL/SLL incident: an empty locale file receives scaffold,
    and every registered key with no authored value must come back from
    ``audit()`` as a reported ``codebase_missing`` entry. Scaffold no longer
    writes a self-referencing key-echo placeholder for a key with no
    authored value (the honesty ratchet in
    ``test_locale_translation_honesty.py`` forbids exactly that), so the
    guarantee this test pins is visibility through the missing-key report,
    not placeholder presence in the YAML.
    """
    from dev.locales import get_registered_keys

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "es.yml").write_text("{}\n", encoding="utf-8")

    src_dir = Path(__file__).resolve().parents[1]
    temp_manager = LocaleManager(src_dir=src_dir, locales_dir=locales_dir)
    temp_manager.scaffold()

    result = temp_manager.audit()
    (file_result,) = result.files
    codebase_missing = set(file_result.codebase_missing)

    registered_keys = get_registered_keys()
    unreported = registered_keys - codebase_missing
    assert not unreported, (
        f"scaffold silently dropped {len(unreported)} f-string-registered key(s) "
        "with neither a value nor a missing-key report: " + ", ".join(sorted(unreported)[:10])
    )
