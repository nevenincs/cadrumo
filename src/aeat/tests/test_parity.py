import logging
from pathlib import Path

import pytest
import yaml

from ..locales._ast_scanner import scan_namespace_markers, scan_source_tree
from ..locales.cli import app
from ..locales.manager import LocaleError, LocaleManager, LocaleNode
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


@pytest.fixture(scope="module")
def manager():
    locales_dir = Path(__file__).resolve().parents[1] / "locales"
    src_dir = locales_dir.parent
    return LocaleManager(src_dir, locales_dir)


@pytest.fixture(scope="module")
def locales_state(manager):
    codebase_keys = manager.get_codebase_keys()
    files = list(manager.locales_dir.glob("*.yml"))
    locale_keys_map = {}

    for f in files:
        data = manager.load_locale(f)
        locale_keys_map[f.name] = manager.get_yaml_keys(data)

    return codebase_keys, locale_keys_map, files


def test_locale_integrity(manager):
    """Test 3: No duplicate keys, sections, or unparseable data."""
    files = list(manager.locales_dir.glob("*.yml"))
    errors = []
    for f in files:
        try:
            # load_locale uses StrictUniqueKeyLoader, which throws ValueError on duplicates
            manager.load_locale(f)
        except ValueError as e:
            errors.append(f"Integrity failure in {f.name}: {e}")
        except yaml.YAMLError as e:
            errors.append(f"YAML Parse error in {f.name}: {e}")

    if errors:
        pytest.fail("\n".join(errors))


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

    assert "    set_locale_help: 'Código de locale.'\n" in locale_path.read_text(encoding="utf-8")
    data = temp_manager.load_locale(locale_path)
    assert _leaf(data, "cli", "locales", "set_locale_help") == "Código de locale."


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

    text = locale_path.read_text(encoding="utf-8")
    assert "stale" not in text
    assert "    app_help: Auditar y generar catálogos de traducción\n" in text


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

    text = locale_path.read_text(encoding="utf-8")
    assert "old-option" not in text
    assert "      current-option:\n" in text
    assert "        help: Current option\n" in text


def test_remove_locale_value_deletes_yaml_null_leaf(tmp_path: Path):
    """A stale empty YAML key can be removed through the locale manager."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "en.yml"
    locale_path.write_text(
        "wizard:\n"
        "  setup:\n"
        "    flags:\n"
        "      old-option:\n"
        "      current-option:\n"
        "        help: Current option\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.remove_locale_value("en", "wizard.setup.flags.old-option")

    text = locale_path.read_text(encoding="utf-8")
    assert "old-option" not in text
    assert "      current-option:\n" in text


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

    assert outside.read_text(encoding="utf-8") == "cli:\n  label: fuera\n"


def test_locale_set_cli_rejects_path_like_locale_without_writing() -> None:
    """The canonical locale CLI rejects traversal-shaped locale arguments."""

    result = invoke_typer_app(app, ["set", "../outside", "cli.locales.app_help", "unsafe"])

    assert result.exit_code != 0
    assert "Invalid locale code" in result.output


def test_ast_scanner_logs_syntax_failures_and_keeps_scanning(tmp_path: Path, caplog) -> None:
    """A broken module is debug-logged and does not hide valid locale keys nearby."""

    (tmp_path / "valid_surface.py").write_text(
        "from aeat.core.i18n import tr\n"
        "\n"
        "def render(reason):\n"
        "    return tr('cli.locales.app_help') + tr(f'wizard.errors.{reason}')\n",
        encoding="utf-8",
    )
    (tmp_path / "broken_surface.py").write_text("def broken(:\n", encoding="utf-8")

    caplog.set_level(logging.DEBUG, logger="aeat.locales._ast_scanner")

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
    from ..locales._fstring_registry import get_registered_keys

    keys = get_registered_keys()
    assert "wizard.setup.taxpayer-type.legal-entity-form.choices.sal.label" in keys, (
        "sal key missing from f-string registry — LegalEntityForm.SAL is not covered"
    )
    assert "wizard.setup.taxpayer-type.legal-entity-form.choices.sll.label" in keys, (
        "sll key missing from f-string registry — LegalEntityForm.SLL is not covered"
    )


def test_fstring_registry_covers_all_legal_entity_form_members() -> None:
    """Every LegalEntityForm member must have a registered locale key."""
    from ..domain.deadlines._models import LegalEntityForm
    from ..locales._fstring_registry import get_registered_keys

    keys = get_registered_keys()
    missing = []
    for member in LegalEntityForm:
        expected = f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label"
        if expected not in keys:
            missing.append(expected)
    assert not missing, (
        f"LegalEntityForm members not covered by the f-string registry: {missing}\n"
        "Add the missing values to _fstring_registry._build_registrations()."
    )


def test_fstring_registry_covers_all_fiscal_residency_members() -> None:
    """Every FiscalResidency member must have a registered locale key."""
    from ..domain.deadlines._models import FiscalResidency
    from ..locales._fstring_registry import get_registered_keys

    keys = get_registered_keys()
    missing = []
    for member in FiscalResidency:
        expected = f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label"
        if expected not in keys:
            missing.append(expected)
    assert not missing, (
        f"FiscalResidency members not covered by the f-string registry: {missing}\n"
        "Add the missing values to _fstring_registry._build_registrations()."
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
    from ..locales._fstring_registry import get_registered_keys

    registered_keys = get_registered_keys()
    errors = []
    for locale_file in sorted(manager.locales_dir.glob("*.yml")):
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
            "\n".join(errors) + "\nRun `python -m aeat.locales scaffold` to insert missing placeholder entries.",
        )


def test_scaffold_inserts_fstring_registry_keys(tmp_path: Path) -> None:
    """Scaffold inserts placeholder entries for every f-string-registered key.

    Simulates the SAL/SLL incident: an empty locale file receives scaffold and
    must contain every registered key as a placeholder afterwards.
    """
    from ..locales._fstring_registry import get_registered_keys

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "es.yml").write_text("{}\n", encoding="utf-8")

    src_dir = Path(__file__).resolve().parents[1]
    temp_manager = LocaleManager(src_dir=src_dir, locales_dir=locales_dir)
    temp_manager.scaffold()

    data = temp_manager.load_locale(locales_dir / "es.yml")
    yaml_keys = temp_manager.get_yaml_keys(data)

    registered_keys = get_registered_keys()
    missing = registered_keys - yaml_keys
    assert not missing, f"scaffold failed to insert {len(missing)} f-string-registered key(s): " + ", ".join(
        sorted(missing)[:10],
    )
