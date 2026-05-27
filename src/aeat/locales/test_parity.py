import logging
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from aeat.locales._ast_scanner import scan_namespace_markers, scan_source_tree
from aeat.locales.cli import app
from aeat.locales.manager import LocaleError, LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(scope="module")
def manager():
    locales_dir = Path(__file__).parent
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
    aggregate = data["cli"]["app"]["modelo"]["aggregate"]
    assert aggregate["json_validation_error"] == "%{flag} no es válido: %{details}."
    assert aggregate["json_parse_error"] == "{flag} debe ser un objeto JSON."


def test_set_locale_value_appends_missing_leaf_under_existing_parent(tmp_path: Path):
    """The locale setter can repair a missing leaf without rebuilding the file."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "es.yml"
    locale_path.write_text(
        "cli:\n"
        "  locales:\n"
        "    app_help: Auditar y generar catálogos de traducción\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.set_locale_value("es", "cli.locales.set_locale_help", "Código de locale.")

    assert "    set_locale_help: 'Código de locale.'\n" in locale_path.read_text(encoding="utf-8")
    data = temp_manager.load_locale(locale_path)
    assert data["cli"]["locales"]["set_locale_help"] == "Código de locale."


def test_remove_locale_value_deletes_existing_leaf(tmp_path: Path):
    """The locale remover deletes a stale leaf and leaves siblings intact."""

    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "es.yml"
    locale_path.write_text(
        "cli:\n"
        "  locales:\n"
        "    stale: Obsoleto\n"
        "    app_help: Auditar y generar catálogos de traducción\n",
        encoding="utf-8",
    )

    temp_manager = LocaleManager(src_dir=tmp_path, locales_dir=locales_dir)

    temp_manager.remove_locale_value("es", "cli.locales.stale")

    text = locale_path.read_text(encoding="utf-8")
    assert "stale" not in text
    assert "    app_help: Auditar y generar catálogos de traducción\n" in text


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

    result = CliRunner().invoke(app, ["set", "../outside", "cli.locales.app_help", "unsafe"])

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
        "locale ast scan: parse failure" in record.getMessage()
        and "broken_surface.py" in record.getMessage()
        for record in caplog.records
    )


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
