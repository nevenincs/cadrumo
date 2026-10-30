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
    # Provider identifiers keep their canonical spelling in every locale.
    for locale in ("en", "es", "ca", "hu"):
        assert is_project_spelling(locale, "antigravity")
        assert not is_project_spelling(locale, "antigravty")


@pytest.mark.parametrize(
    ("word", "near_miss"),
    [
        ("Maximize", "Maximze"),
        ("Minimize", "Minimze"),
        ("Organize", "Organze"),
        ("Initialize", "Initialze"),
        ("Summarize", "Summarze"),
        ("summarize", "summarze"),
        ("finalized", "finalzed"),
        ("synchronization", "syncronization"),
        ("Synchronization", "Syncronization"),
        ("synchronizing", "syncronizing"),
        ("synchronize", "syncronize"),
        ("enrollment", "enrolmentt"),
        ("Enrollment", "Enrolmentt"),
        ("enroll", "enrolll"),
        ("Enroll", "Enrolll"),
        ("Unrecognized", "Unrecogized"),
        ("recognized", "recogized"),
        ("authorized", "autorized"),
        ("authorize", "autorize"),
        ("authorization", "autorization"),
        ("serialization", "seralization"),
        ("localized", "localzed"),
        ("localization", "localzation"),
        ("normalization", "normalzation"),
    ],
)
def test_attested_us_english_forms_do_not_admit_typos_or_other_locales(word: str, near_miss: str) -> None:
    assert is_project_spelling("en", word)
    assert not is_project_spelling("en", near_miss)
    assert not is_project_spelling("en", word.upper())
    for locale in ("es", "ca", "hu"):
        assert not is_project_spelling(locale, word)
