"""English technical terms remain exact and locale-scoped."""

import pytest

from dev.locales.signal_spelling_enrollment import is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_attested_english_cli_and_application_terms_are_exact_and_scoped() -> None:
    terms = (
        "claude",
        "antigravity",
        "keychain",
        "unencrypted",
        "keypair",
        "auditable",
        "backend",
        "Backend",
        "validator",
        "validators",
        "enum",
        "Enum",
        "datetime",
        "filesystem",
        "subcommand",
        "stdin",
        "json",
        "csv",
        "tsv",
        "xls",
        "xlsm",
        "xlsx",
        "loopback",
    )
    for term in terms:
        assert is_project_spelling("en", term)

    for near_miss in (
        "claudee",
        "antigravty",
        "keychian",
        "unencryped",
        "keypar",
        "auditablee",
        "backened",
        "validater",
        "validaters",
        "enumm",
        "datatime",
        "filesytem",
        "subcomand",
        "stdiin",
        "jsno",
        "cvs",
        "tsvv",
        "xlss",
        "xlsmm",
        "xslx",
        "loopbak",
    ):
        assert not is_project_spelling("en", near_miss)

    assert not is_project_spelling("ca", "keychain")
    assert not is_project_spelling("es", "keychain")
    assert not is_project_spelling("hu", "keychain")
    assert not is_project_spelling("ca", "antigravity")
    assert not is_project_spelling("es", "antigravity")
    assert not is_project_spelling("hu", "antigravity")
