from pathlib import Path

import pytest
import yaml

from aeat.locales.manager import LocaleManager


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


@pytest.mark.unit
@pytest.mark.domain_application
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


@pytest.mark.unit
@pytest.mark.domain_application
def test_codebase_to_locale_parity(locales_state):
    """Test 1: Parity between the codebase truth and the localizations."""
    codebase_keys, locale_keys_map, _ = locales_state
    assert len(codebase_keys) > 0, "No translation keys found in codebase"

    errors = []
    for name, keys in locale_keys_map.items():
        missing = codebase_keys - keys
        extra = keys - codebase_keys

        if missing:
            errors.append(f"{name} is missing {len(missing)} codebase keys.")
        if extra:
            errors.append(f"{name} contains {len(extra)} extra keys not in the codebase.")

    if errors:
        pytest.fail("\n".join(errors))


@pytest.mark.unit
@pytest.mark.domain_application
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
