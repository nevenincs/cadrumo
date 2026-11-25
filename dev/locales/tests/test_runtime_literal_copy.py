"""Runtime technical references retain their actual module, suffix and command syntax."""

import re

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.i18n.render import extract_placeholders, tr
from cadrumo.core.optional_extras import GOOGLE_EXTRA
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH

from ..signal_command_paths import command_path_pattern, executable_command_paths
from ..signal_spelling_segments import translation_spelling_segments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("locale", ["ca", "en", "es", "hu"])
@pytest.mark.parametrize(
    "key,literals",
    [
        ("adapters.google.calc_sheets.errors.googleapiclient_not_importable", (GOOGLE_EXTRA.import_name,)),
        ("wizard.setup.certificate.path.prompt", (".p12", ".pfx")),
        ("application.modelo.quickfile.stage_incomplete", ("quickfile",)),
        ("application.modelo.quickfile.stage_refused", ("quickfile",)),
    ],
)
def test_runtime_literals_keep_exact_spelling_and_surrounding_prose_checks(
    locale: str, key: str, literals: tuple[str, ...]
) -> None:
    value = tr(key, locale=locale, stage="prepare", status="complete", error_code="example")
    assert tuple(re.findall(r"`([^`]+)`", value)) == literals
    assert not extract_placeholders(value)
    words = {
        word for _, words, _ in translation_spelling_segments(value + " misspellledd", key, locale) for word in words
    }
    assert "misspellledd" in words
    assert not set(literals) & words


def test_certificate_suffixes_match_the_configuration_contract() -> None:
    description = Settings.model_fields["cadrumo_certificate_path"].description
    assert description is not None
    assert {".p12", ".pfx"} <= set(re.findall(r"\.p(?:12|fx)", description))


def test_quickfile_is_the_registered_executable_group() -> None:
    assert ("aeat", "app", "quickfile") in {node.path for node in COMMAND_GRAPH.nodes()}


@pytest.mark.parametrize("locale,name", [("ca", "NOM"), ("en", "NAME"), ("es", "NOMBRE"), ("hu", "NÉV")])
def test_recovery_notice_names_the_complete_executable_command(locale: str, name: str) -> None:
    value = tr("cli.config.profile.recovery.enabled_notice", locale=locale)
    (literal,) = re.findall(r"`([^`]+)`", value)
    assert literal == "cadrumo-runtime config passphrase reset " + name
    assert ("cadrumo-runtime", "config", "passphrase", "reset") in executable_command_paths()
    matched = command_path_pattern().search(literal)
    assert matched is not None
    assert matched.group() == "cadrumo-runtime config passphrase reset"
