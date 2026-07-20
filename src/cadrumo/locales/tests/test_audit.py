"""Production locale audit contracts over real YAML catalogues."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from ...core.i18n import extract_placeholders
from ...core.product_identity import AEAT_AUTHORITY_SHORT_NAME, PRODUCT_IDENTITY
from ...tests.cli_runner import invoke_typer_app
from ..cli import app
from ..manager import _STALE_CLI_EXECUTABLE_RE, LocaleManager, _flatten_leaf_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALES = ("ca", "en", "es", "hu")
_PROSE_NAME_RE = re.compile(r"\bCadrumo\b")
_DISPLAY_NAME_RE = re.compile(r"\bCADRUMO\b")
_IDENTITY_HEADING_KEYS = {
    "cli.operator_surface.help.root.heading",
    "cli.root.landing.headline",
}
_PROSE_KEYS = {
    "ca": {
        "errors.auth.auth_former_product_session_state",
        "adapters.google.calc_sheets.errors.foreign_spreadsheet_not_owned",
        "adapters.google.oauth_flow.errors.profile_state_unresolved",
        "adapters.google.profile_binding.errors.no_active_profile",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "cli.config.passphrase.confirm_new_passphrase_prompt",
        "cli.config.passphrase.current_passphrase_prompt",
        "cli.config.passphrase.new_passphrase_prompt",
        "cli.config.google.profile_help",
        "cli.ledger.add.system_state_not_assignable",
        "cli.ledger.classify.system_state_not_assignable",
        "mcp.elicitation.refusal.no_channel",
    },
    "en": {
        "errors.auth.auth_former_product_session_state",
        "adapters.google.calc_sheets.errors.foreign_spreadsheet_not_owned",
        "adapters.google.oauth_flow.errors.profile_state_unresolved",
        "adapters.google.profile_binding.errors.no_active_profile",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "cli.config.passphrase.confirm_new_passphrase_prompt",
        "cli.config.passphrase.current_passphrase_prompt",
        "cli.config.passphrase.new_passphrase_prompt",
        "cli.config.google.profile_help",
        "mcp.elicitation.refusal.no_channel",
    },
    "es": {
        "errors.auth.auth_former_product_session_state",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "cli.config.passphrase.confirm_new_passphrase_prompt",
        "cli.config.passphrase.current_passphrase_prompt",
        "cli.config.passphrase.new_passphrase_prompt",
        "cli.ledger.add.system_state_not_assignable",
        "cli.ledger.classify.system_state_not_assignable",
        "mcp.elicitation.refusal.no_channel",
    },
    "hu": {
        "errors.auth.auth_former_product_session_state",
        "adapters.outbound.storage.google_drive.errors.former_vault_folder",
        "cli.config.passphrase.confirm_new_passphrase_prompt",
        "cli.config.passphrase.current_passphrase_prompt",
        "cli.config.passphrase.new_passphrase_prompt",
        "cli.ledger.add.system_state_not_assignable",
        "cli.ledger.classify.system_state_not_assignable",
        "mcp.elicitation.refusal.no_channel",
    },
}
_CLI_KEYS = {
    "ca": {"mcp.call.timeout", "mcp.elicitation.refusal.no_channel"},
    "en": {"mcp.elicitation.refusal.no_channel"},
    "es": {"mcp.call.timeout", "mcp.elicitation.refusal.no_channel"},
    "hu": {"mcp.elicitation.refusal.no_channel"},
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
    """Equivalent names pass despite conversion and harmless brace differences."""
    values = {
        locale: f"{locale} %{{amount}} {{subject!r}} {{{{escaped}}}} {{not a placeholder}}" for locale in _LOCALES
    }
    manager = _manager_for(tmp_path, {locale: "{}\n" for locale in _LOCALES})
    manager.scaffold()
    for locale, value in values.items():
        manager.set_locale_value(locale, "audit.message", value)

    result = manager.audit()

    assert result.ok, result


def test_committed_catalogues_pass_production_audit() -> None:
    """The shipped four-language catalogue is accepted by the real validator."""
    locales_dir = Path(__file__).resolve().parents[1]
    manager = LocaleManager(src_dir=locales_dir.parent, locales_dir=locales_dir)

    result = manager.audit()

    assert result.ok, result


def test_committed_catalogues_follow_contextual_product_identity_contract() -> None:
    """Shipped locale values preserve prose, identity, CLI, machine, and authority referents."""
    locales_dir = Path(__file__).resolve().parents[1]
    manager = LocaleManager(src_dir=locales_dir.parent, locales_dir=locales_dir)

    assert PRODUCT_IDENTITY.prose_name == "Cadrumo"
    assert PRODUCT_IDENTITY.display_name == "CADRUMO"
    assert PRODUCT_IDENTITY.cli_executable == "aeat"
    assert PRODUCT_IDENTITY.python_package == PRODUCT_IDENTITY.distribution == "cadrumo"
    assert PRODUCT_IDENTITY.mcp_server == PRODUCT_IDENTITY.mcp_resource_scheme == "cadrumo"
    assert PRODUCT_IDENTITY.mcp_executable == "cadrumo-mcp"
    assert PRODUCT_IDENTITY.environment_prefix == "CADRUMO_"
    assert AEAT_AUTHORITY_SHORT_NAME == "AEAT"

    for locale in _LOCALES:
        leaves = _flatten_leaf_values(manager.load_locale(locales_dir / f"{locale}.yml"))
        assert {key for key, value in leaves.items() if _PROSE_NAME_RE.search(value)} == _PROSE_KEYS[locale]
        assert {key for key, value in leaves.items() if _DISPLAY_NAME_RE.search(value)} == _IDENTITY_HEADING_KEYS
        assert all(PRODUCT_IDENTITY.cli_executable in leaves[key] for key in _CLI_KEYS[locale])
        assert all(PRODUCT_IDENTITY.display_name not in leaves[key] for key in _CLI_KEYS[locale])
        assert not {key for key, value in leaves.items() if _STALE_CLI_EXECUTABLE_RE.search(value)}
        assert any(PRODUCT_IDENTITY.environment_prefix in value for value in leaves.values())
        assert any("cadrumo-vault/" in value for value in leaves.values())
        assert any(AEAT_AUTHORITY_SHORT_NAME in value for value in leaves.values())

    audit = manager.audit()
    assert audit.ok, audit


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
