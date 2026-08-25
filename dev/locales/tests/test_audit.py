"""Production locale audit contracts over real YAML catalogues."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core import normalise_product_identity_references
from cadrumo.core.i18n import extract_placeholders
from cadrumo.core.product_identity import AEAT_AUTHORITY_SHORT_NAME, PRODUCT_IDENTITY
from cadrumo.tests.cli_runner import invoke_typer_app

from .._paths import DOCS_SRC_DIR, HARNESS_SRC_DIR, LOCALES_DIR, SRC_DIR
from ..cli import app
from ..manager import LocaleError, LocaleManager, _flatten_leaf_values, locale_catalogue_source


def _catalogue_source(locale: str) -> Path:
    """Resolve one committed catalogue's source path, shard directory or flat file.

    Constructing ``LOCALES_DIR / f"{locale}.yml"`` here is what silently
    retired both assertions below when the catalogues were resharded: the
    gates stopped checking and started raising.
    """
    source = locale_catalogue_source(LOCALES_DIR, locale)
    if source is None:
        raise AssertionError(f"no committed catalogue found for locale {locale!r}")
    return source


pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALES = ("ca", "en", "es", "hu")
_PROSE_NAME_RE = re.compile(r"\bCadrumo\b")
_DISPLAY_NAME_RE = re.compile(r"\bCADRUMO\b")
_IDENTITY_HEADING_KEYS = {
    "cli.operator_surface.help.root.heading",
    "cli.root.landing.headline",
}
# Keys whose value names the product in sentence prose. A hand-maintained
# inventory is the point: a NEW key mentioning the product must be a deliberate
# addition here, not a silent one. Its cost is that a deleted key leaves a dead
# entry, which the staleness assertion below reports as itself rather than as an
# unreadable set difference.
#
# The ``cli.config.passphrase.*`` prompts were entries here until the
# ``config rekey`` -> ``config passphrase change`` rename relocated them: the
# current-passphrase prompt now lives under ``cli.config.custody`` and the
# create-time pair under ``cli.config.profile``. The verb itself ships and its
# family is MOUNTED, so the prompts are relocated rather than owed; what remains
# under ``cli.config.passphrase`` is its help pair and one refusal.
_PROSE_KEYS = {
    "ca": {
        "errors.auth.auth_former_product_session_state",
        "errors.internal.cli_outbound_payload_boundary",
        "cli.operator_surface.help.root.paragraph_local_first",
        "adapters.google.calc_sheets.errors.foreign_spreadsheet_not_owned",
        "adapters.google.oauth_flow.errors.profile_state_unresolved",
        "adapters.google.profile_binding.errors.no_active_profile",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "application.iva_wallet.decision_reason.first_period_zero_activity_start_uncontrasted",
        "cli.config.google.profile_help",
        "cli.ledger.add.system_state_not_assignable",
        "cli.ledger.classify.system_state_not_assignable",
        "provisioning.model.licence.non_commercial_advisory",
        "docs.legal.index.intro",
        "docs.legal.page.intro",
    },
    "en": {
        "errors.auth.auth_former_product_session_state",
        "errors.internal.cli_outbound_payload_boundary",
        "cli.operator_surface.help.root.paragraph_local_first",
        "adapters.google.calc_sheets.errors.foreign_spreadsheet_not_owned",
        "adapters.google.oauth_flow.errors.profile_state_unresolved",
        "adapters.google.profile_binding.errors.no_active_profile",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "application.iva_wallet.decision_reason.first_period_zero_activity_start_uncontrasted",
        "cli.config.google.profile_help",
        "provisioning.model.licence.non_commercial_advisory",
        "docs.legal.index.intro",
        "docs.legal.page.intro",
    },
    "es": {
        "errors.auth.auth_former_product_session_state",
        "errors.internal.cli_outbound_payload_boundary",
        "cli.operator_surface.help.root.paragraph_local_first",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "application.iva_wallet.decision_reason.first_period_zero_activity_start_uncontrasted",
        "cli.ledger.add.system_state_not_assignable",
        "cli.ledger.classify.system_state_not_assignable",
        "provisioning.model.licence.non_commercial_advisory",
        "docs.legal.index.intro",
        "docs.legal.page.intro",
    },
    "hu": {
        "errors.auth.auth_former_product_session_state",
        "errors.internal.cli_outbound_payload_boundary",
        "cli.operator_surface.help.root.paragraph_local_first",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "application.iva_wallet.decision_reason.first_period_zero_activity_start_uncontrasted",
        "cli.ledger.add.system_state_not_assignable",
        "cli.ledger.classify.system_state_not_assignable",
        "provisioning.model.licence.non_commercial_advisory",
        "docs.legal.index.intro",
        "docs.legal.page.intro",
    },
}


def _manager_for(tmp_path: Path, values: Mapping[str, str]) -> LocaleManager:
    """Write one real YAML catalogue per language and return its manager."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    translation_key = "audit.message"
    (source_dir / "surface.py").write_text(
        f"from cadrumo.core.i18n import tr\n\ndef render() -> str:\n    return tr({translation_key!r})\n",
        encoding="utf-8",
    )
    for locale in _LOCALES:
        (locales_dir / f"{locale}.yml").write_text(values[locale], encoding="utf-8")
    return LocaleManager(src_dir=source_dir, locales_dir=locales_dir)


def test_extract_placeholders_matches_renderer_grammar() -> None:
    """Conversions are retained while escaped and prose braces remain literal."""
    value = (
        "pct=%{amount}; converted={subject!r}; formatted={ratio:.2f}; "
        'escaped={{ignored}}; positional={}; prose={not a placeholder}; json={"kind": 1}'
    )

    assert extract_placeholders(value) == frozenset({"amount", "subject", "ratio"})
    assert extract_placeholders("%{kept} {discarded} broken {") == frozenset({"kept", "discarded"})


def test_codebase_keys_exclude_test_module_literals(tmp_path: Path) -> None:
    """A ``tr()`` literal inside a test module never becomes a required key.

    Required keys are what production code can request; a fixture payload
    or assertion literal in a test file must not inject a phantom demand
    into every catalogue.
    """
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    source_dir = tmp_path / "source"
    tests_dir = source_dir / "tests"
    tests_dir.mkdir(parents=True)
    (source_dir / "surface.py").write_text(
        'from cadrumo.core.i18n import tr\n\ndef render() -> str:\n    return tr("prod.message")\n',
        encoding="utf-8",
    )
    (tests_dir / "test_surface.py").write_text(
        'from cadrumo.core.i18n import tr\n\ndef test_render() -> None:\n    assert tr("phantom.nested")\n',
        encoding="utf-8",
    )
    (source_dir / "test_toplevel.py").write_text(
        "PAYLOAD = 'return tr(\"phantom.toplevel\")'\n",
        encoding="utf-8",
    )

    keys = LocaleManager(src_dir=source_dir, locales_dir=locales_dir).get_codebase_keys()

    assert "prod.message" in keys
    assert "phantom.nested" not in keys
    assert "phantom.toplevel" not in keys


def test_set_refuses_a_blank_locale_value(tmp_path: Path) -> None:
    """The CLI write path never lets an empty or whitespace-only leaf in."""
    manager = _manager_for(
        tmp_path,
        {locale: "audit:\n  message: 'texto'\n" for locale in _LOCALES},
    )

    for blank in ("", "   "):
        with pytest.raises(LocaleError, match="must not be blank"):
            manager.set_locale_value("en", "audit.message", blank)


def test_audit_rejects_boolean_and_null_leaves(tmp_path: Path) -> None:
    """YAML booleans and nulls cannot pass as locale strings."""
    manager = _manager_for(
        tmp_path,
        {
            "ca": "message: null\n",
            "en": "message: true\n",
            "es": "message: text\n",
            "hu": "message: szöveg\n",
        },
    )

    result = manager.audit()

    violations = {
        (violation.locale_file, violation.key, violation.value_type)
        for file_result in result.files
        for violation in file_result.scalar_violations
    }
    assert violations == {("ca.yml", "message", "NoneType"), ("en.yml", "message", "bool")}
    assert not result.ok


def test_audit_reports_symmetric_key_drift_without_reference_locale(tmp_path: Path) -> None:
    """Every catalogue reports union keys it lacks; no file is canonical."""
    manager = _manager_for(
        tmp_path,
        {
            "ca": "common: ca\n",
            "en": "common: en\nen_only: value\n",
            "es": "common: es\nes_only: valor\n",
            "hu": "common: hu\n",
        },
    )

    result = manager.audit()
    missing = {file.locale_file: set(file.inter_locale_missing) for file in result.files}

    assert missing == {
        "ca.yml": {"en_only", "es_only"},
        "en.yml": {"es_only"},
        "es.yml": {"en_only"},
        "hu.yml": {"en_only", "es_only"},
    }


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            {
                "ca": "message: '%{amount} %{extra}'\n",
                "en": "message: '%{amount}'\n",
                "es": "message: '%{renamed}'\n",
                "hu": "message: nincs helyőrző\n",
            },
            {
                "ca.yml": frozenset({"amount", "extra"}),
                "en.yml": frozenset({"amount"}),
                "es.yml": frozenset({"renamed"}),
                "hu.yml": frozenset(),
            },
        ),
        (
            {
                "ca": "message: '{amount!r} {extra:.2f}'\n",
                "en": "message: '{amount}'\n",
                "es": "message: '{renamed!s}'\n",
                "hu": "message: nincs helyőrző\n",
            },
            {
                "ca.yml": frozenset({"amount", "extra"}),
                "en.yml": frozenset({"amount"}),
                "es.yml": frozenset({"renamed"}),
                "hu.yml": frozenset(),
            },
        ),
    ],
)
def test_audit_reports_missing_renamed_and_extra_placeholders(
    tmp_path: Path,
    values: dict[str, str],
    expected: dict[str, frozenset[str]],
) -> None:
    """Both supported syntaxes expose every per-locale placeholder variant."""
    result = _manager_for(tmp_path, values).audit()

    assert len(result.placeholder_mismatches) == 1
    mismatch = result.placeholder_mismatches[0]
    assert mismatch.key == "message"
    assert {variant.locale_file: variant.placeholders for variant in mismatch.variants} == expected


def test_audit_reports_root_and_nested_format_field_drift(tmp_path: Path) -> None:
    """Audit parity includes runtime roots and nested specification kwargs."""
    result = _manager_for(
        tmp_path,
        {
            "ca": "message: '{user.name} {amount:{width}.{precision}f}'\n",
            "en": "message: '{user.name} {amount:{width}.{precision}f}'\n",
            "es": "message: '{account.name} {amount:{width}f}'\n",
            "hu": "message: '{user.name} {amount:{width}.{precision}f}'\n",
        },
    ).audit()

    assert len(result.placeholder_mismatches) == 1
    mismatch = result.placeholder_mismatches[0]
    assert mismatch.key == "message"
    assert {variant.locale_file: variant.placeholders for variant in mismatch.variants} == {
        "ca.yml": frozenset({"user", "amount", "width", "precision"}),
        "en.yml": frozenset({"user", "amount", "width", "precision"}),
        "es.yml": frozenset({"account", "amount", "width"}),
        "hu.yml": frozenset({"user", "amount", "width", "precision"}),
    }


def test_audit_accepts_matching_conversions_escaped_and_literal_braces(tmp_path: Path) -> None:
    """Equivalent names pass despite conversion and harmless brace differences.

    Asserted on ``placeholder_mismatches`` rather than on ``result.ok``, and the
    change is a ruling rather than a weakening. ``ok`` also requires catalogue
    COMPLETENESS, and a fixture holding one authored key cannot be complete now
    that the scaffold no longer fabricates a value for every codebase key it
    finds. It used to audit clean only because the scaffold wrote each missing
    key's own dotted path as its value -- a placeholder the honesty ratchet and
    three coverage gates all refuse, so this case passed on the strength of the
    very thing those gates exist to catch.

    The property under test never involved completeness: it is that two
    spellings of one placeholder set are recognised as equivalent. That is what
    is asserted, and it fails for its own reason now rather than for a reason
    the fixture happened to satisfy.
    """
    values = {
        locale: f"{locale} %{{amount}} {{subject!r}} {{{{escaped}}}} {{not a placeholder}}" for locale in _LOCALES
    }
    manager = _manager_for(tmp_path, {locale: "{}\n" for locale in _LOCALES})
    manager.scaffold()
    for locale, value in values.items():
        manager.set_locale_value(locale, "audit.message", value)

    result = manager.audit()

    assert result.placeholder_mismatches == (), result.placeholder_mismatches


def test_committed_catalogues_pass_production_audit() -> None:
    """The shipped four-language catalogue is accepted by the real validator."""
    manager = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR, extra_src_dirs=(DOCS_SRC_DIR, HARNESS_SRC_DIR))

    result = manager.audit()

    assert result.ok, result


def test_committed_catalogues_follow_contextual_product_identity_contract() -> None:
    """Shipped locale values preserve prose, identity, CLI, machine, and authority referents."""
    manager = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR, extra_src_dirs=(DOCS_SRC_DIR, HARNESS_SRC_DIR))

    assert PRODUCT_IDENTITY.prose_name == "Cadrumo"
    assert PRODUCT_IDENTITY.display_name == "CADRUMO"
    assert PRODUCT_IDENTITY.cli_executable == "aeat"
    assert PRODUCT_IDENTITY.python_package == PRODUCT_IDENTITY.distribution == "cadrumo"
    assert PRODUCT_IDENTITY.environment_prefix == "CADRUMO_"
    assert AEAT_AUTHORITY_SHORT_NAME == "AEAT"

    for locale in _LOCALES:
        # ``_flatten_leaf_values`` returns ``str | None``: a null leaf is a key that
        # exists but carries no text -- an untranslated modelo-schema label, or an
        # optional ``.help`` the source itself leaves empty. Those carry no prose, so
        # every referent contract below holds trivially for them, and the regex and
        # membership checks would raise ``TypeError`` on ``None`` rather than assert.
        # Filter them out, then prove the remainder is not a hollowed-out set: a
        # filter that swallowed everything would make the equality assertions pass
        # vacuously.
        leaves = {
            key: value
            for key, value in _flatten_leaf_values(manager.load_locale(_catalogue_source(locale))).items()
            if value is not None
        }
        assert len(leaves) > 10_000, (
            f"{locale}: only {len(leaves)} non-null leaves survived filtering, so the product-identity "
            f"contract below would be asserted against a near-empty catalogue"
        )
        # Report a dead inventory entry as what it is. Without this, a key deleted
        # from the catalogue surfaces only as an opaque set difference alongside any
        # genuine contract breach, and the two read identically.
        stale_prose_keys = _PROSE_KEYS[locale] - leaves.keys()
        assert not stale_prose_keys, (
            f"{locale}: _PROSE_KEYS names {sorted(stale_prose_keys)}, absent from the catalogue. "
            "Remove the dead entries, or restore the keys alongside the code that renders them."
        )
        assert {key for key, value in leaves.items() if _PROSE_NAME_RE.search(value)} == _PROSE_KEYS[locale]
        assert {key for key, value in leaves.items() if _DISPLAY_NAME_RE.search(value)} == _IDENTITY_HEADING_KEYS
        assert not {key for key, value in leaves.items() if normalise_product_identity_references(value) != value}
        assert any(PRODUCT_IDENTITY.environment_prefix in value for value in leaves.values())
        assert any("cadrumo-vault/" in value for value in leaves.values())
        assert any(AEAT_AUTHORITY_SHORT_NAME in value for value in leaves.values())

    audit = manager.audit()
    assert audit.ok, audit


_EM_DASH = chr(0x2014)
# No key is exempted today. An exemption is added here, keyed by its exact
# ``(locale, dotted_key)`` pair with a stated reason, only for an em dash inside a
# verbatim official AEAT designation or legal citation -- never a blanket pattern
# or a line-number exemption.
_EM_DASH_EXEMPT_KEYS: frozenset[tuple[str, str]] = frozenset()


def test_committed_catalogues_carry_no_em_dash() -> None:
    """No shipped locale value may contain U+2014; a spaced hyphen reads naturally.

    A rendered page must never show an em dash (operator directive). Every prior
    occurrence in the four catalogues was the same label/qualifier or
    parenthetical-aside pattern, none a verbatim official AEAT designation or
    legal citation, so ``_EM_DASH_EXEMPT_KEYS`` starts empty -- a future
    genuinely-official exemption is added there by exact key, not by loosening
    this assertion.
    """
    manager = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR)
    violations: list[str] = []
    for locale in _LOCALES:
        leaves = manager.load_locale(_catalogue_source(locale))
        for key, value in _flatten_leaf_values(leaves).items():
            if value is None or _EM_DASH not in value:
                continue
            if (locale, key) in _EM_DASH_EXEMPT_KEYS:
                continue
            violations.append(f"{locale}.yml:{key}")
    assert violations == [], "em dash (U+2014) found in locale value(s): " + ", ".join(violations)


def test_real_audit_cli_rejects_placeholder_drift(tmp_path: Path) -> None:
    """The Typer command renders manager findings and exits unsuccessfully."""
    manager = _manager_for(
        tmp_path,
        {
            "ca": "message: '%{amount}'\n",
            "en": "message: '%{amount}'\n",
            "es": "message: '%{total}'\n",
            "hu": "message: '%{amount}'\n",
        },
    )

    result = invoke_typer_app(app, ["audit"], obj=manager)

    assert result.exit_code == 1
    assert "placeholder mismatch key=message" in result.output
    assert "es.yml=['total']" in result.output
