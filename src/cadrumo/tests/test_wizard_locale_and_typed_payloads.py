"""Wizard locale routing and typed-payload boundary contracts.

- The wizard catalogue materializes bounded dynamic choice translation
  keys in its runtime descriptors.
- ``OAuthClientPayload`` TypedDict and ``_OAuthClientWrapper`` pydantic
  model validate the Cloud Console Desktop envelope.
- Orphan namespace ``__init__`` modules carry intent documentation.

See Also:
    :mod:`~application.wizard`
        Wizard descriptor package whose bounded dynamic locale keys are
        materialized at runtime.
    :class:`~entrypoints.cli.OAuthClientPayload`
        CLI Google OAuth payload boundary validated from Cloud Console JSON.

These locale and typed-boundary contracts group the wizard's dynamic-key
materialization with the OAuth payload boundary it shares.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import subprocess
import sys

import pytest
import yaml

from ..core.directory_scan import DirectoryEntryKind, scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = pathlib.Path(__file__).parent.parent


def _wizard_descriptor_translation_keys() -> set[str]:
    from ..application.wizard.catalogue import WIZARD_FLOWS

    keys: set[str] = set()
    for flow in WIZARD_FLOWS:
        keys.add(str(flow.title))
        keys.add(str(flow.description))
        for section in flow.sections:
            keys.add(str(section.title))
            for question in section.questions:
                keys.add(str(question.prompt))
                if question.help is not None:
                    keys.add(str(question.help))
                for choice in question.choices:
                    keys.add(str(choice.label))
                    if choice.description is not None:
                        keys.add(str(choice.description))
    return keys


#: Floor for the locale census: the supported locale set is four today, and
#: flooring below it keeps a new locale from failing the gate on arrival.
_MINIMUM_LOCALES = 4


def test_wizard_status_locale_key_exists_in_all_locales() -> None:
    """The key application.wizard.output_labels.status must exist in all locale files."""
    locales_dir = _SRC_ROOT / "locales"
    # One catalogue per LOCALE, not every file. `locales/` holds a directory per
    # locale, so the previous non-recursive `*.yml` scan matched 0 of 328 files
    # and this gate -- named for checking all locales -- checked none of them.
    # Sweeping recursively instead is the opposite error: catalogues are split
    # by domain and only `application.yml` carries the wizard block, so every
    # other file would fail for correctly not owning it.
    catalogues = sorted(
        directory / "application.yml"
        for directory in scan_directory(locales_dir, select=DirectoryEntryKind.DIRECTORIES, require_root=True)
    )
    assert len(catalogues) >= _MINIMUM_LOCALES, (
        f"the locale sweep reached only {len(catalogues)} locale(s) under {locales_dir}; "
        "a scan matching nothing asserts the key exists in every locale by checking none"
    )
    for locale_file in catalogues:
        assert locale_file.is_file(), f"{locale_file.parent.name}: application.yml is missing"
        content = yaml.safe_load(locale_file.read_text(encoding="utf-8")) or {}
        application = content.get("application", {})
        wizard = application.get("wizard", {}) if isinstance(application, dict) else {}
        output_labels = wizard.get("output_labels", {}) if isinstance(wizard, dict) else {}
        assert isinstance(output_labels, dict), f"{locale_file.name}: application.wizard.output_labels block missing"
        assert "status" in output_labels, f"{locale_file.name}: application.wizard.output_labels.status key missing"


# ---------------------------------------------------------------------------
# Wizard bounded dynamic keys materialize in descriptors
# ---------------------------------------------------------------------------


def test_wizard_catalogue_materializes_bounded_dynamic_choice_keys() -> None:
    """Enum- and language-derived choice labels must be concrete descriptor keys."""
    from ..core.i18n.render import SUPPORTED_OUTPUT_LANGUAGES
    from ..domain.contribuyente.entity_type import EntityType
    from ..domain.deadlines.models import FiscalResidency, IrpfIncomeCategory

    keys = _wizard_descriptor_translation_keys()

    expected = {
        *{
            f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label"
            for member in EntityType
        },
        *{
            f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.label"
            for member in IrpfIncomeCategory
        },
        *{
            f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label"
            for member in FiscalResidency
        },
        *{f"wizard.setup.profile.output-language.choices.{language}.label" for language in SUPPORTED_OUTPUT_LANGUAGES},
    }

    assert expected <= keys


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Orphan __init__ modules remain namespace containers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "cadrumo.application.storage",
        "cadrumo.domain.calculations",
    ],
)
def test_namespace_init_modules_document_intent_without_reexports(module_name: str) -> None:
    """Namespace package roots must document intent and expose no public aggregation API."""
    module = importlib.import_module(module_name)

    assert "namespace" in (module.__doc__ or "").lower(), f"{module_name} must document its namespace-container intent"
    probe = subprocess.run(  # noqa: S603 - static module list under this test's control.
        [
            sys.executable,
            "-c",
            (
                "import importlib, json; "
                f"module = importlib.import_module({module_name!r}); "
                "print(json.dumps(sorted(name for name in vars(module) if not name.startswith('_'))))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    public_exports = json.loads(probe.stdout)
    assert public_exports == [], f"{module_name} unexpectedly re-exports public names: {public_exports}"
