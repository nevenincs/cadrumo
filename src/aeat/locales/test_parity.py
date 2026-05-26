from pathlib import Path

import pytest
import yaml

from aeat.locales.manager import LocaleManager

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


def test_scaffold_can_sync_dynamic_namespace_locale_parity(tmp_path):
    """Scaffolding repairs dynamic namespace drift between abstract catalogues."""

    src_dir = tmp_path / "src"
    locales_dir = src_dir / "locales"
    locales_dir.mkdir(parents=True)
    (src_dir / "producer.py").write_text(
        "\n".join(
            [
                "def render(slug):",
                "    tr('shared.key')",
                "    return tr(f'topic.{slug}')",
            ]
        ),
        encoding="utf-8",
    )
    (locales_dir / "catalogue_a.yml").write_text(
        "\n".join(
            [
                "shared:",
                "  key: shared.key",
                "topic:",
                "  alpha: topic.alpha",
            ]
        ),
        encoding="utf-8",
    )
    (locales_dir / "catalogue_b.yml").write_text(
        "\n".join(
            [
                "shared:",
                "  key: shared.key",
            ]
        ),
        encoding="utf-8",
    )

    manager = LocaleManager(src_dir, locales_dir)
    before = {
        locale_path.name: manager.get_yaml_keys(manager.load_locale(locale_path))
        for locale_path in sorted(locales_dir.glob("*.yml"))
    }
    assert before == {
        "catalogue_a.yml": {"shared.key", "topic.alpha"},
        "catalogue_b.yml": {"shared.key"},
    }

    manager.scaffold(sync_locale_parity=True)

    after = {
        locale_path.name: manager.get_yaml_keys(manager.load_locale(locale_path))
        for locale_path in sorted(locales_dir.glob("*.yml"))
    }
    assert after == {
        "catalogue_a.yml": {"shared.key", "topic.alpha"},
        "catalogue_b.yml": {"shared.key", "topic.alpha"},
    }
    catalogue_b = manager.load_locale(locales_dir / "catalogue_b.yml")
    assert catalogue_b["topic"]["alpha"] == "topic.alpha"
