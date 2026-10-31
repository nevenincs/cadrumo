"""Localized help retains executable choice values from their typed authorities."""

import re
from enum import Enum
from importlib import import_module
from typing import Any

import pytest

from cadrumo.application.modelo.selectors import ModeloCalculationRevisionSelector
from cadrumo.core.i18n.render import extract_placeholders, tr
from cadrumo.core.identity_check_verdict import IdentityCheckVerdict
from cadrumo.core.toml import parse_toml
from cadrumo.domain.contribuyente.inventory.records import ValuationMethod
from dev._paths import REPO_ROOT

from ..signal_command_paths import _command_graphs
from ..signal_spelling_segments import translation_spelling_segments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HELP_KEYS = [
    "cli.app.ledger.inventory.movement_kind_help",
    "cli.app.ledger.inventory.valuation_method_help",
    "cli.app.live.borrador.state_help",
    "cli.app.live.verify.expected_help",
    "cli.app.live.verify.expected_values_error",
    "cli.app.modelo.casillas.input_kind_help",
    "cli.app.ledger.account.role_help",
    "cli.config.custody.profile_auth_method_help",
    "cli.config.profile.automation.change.kind_help",
    "cli.config.profile.automation.deny.kind_help",
    "cli.config.profile.capabilities.state_help",
    "cli.ledger.list.sort_order_help",
    "cli.root.format_help",
    "cli.app.modelo.reconcile.file_kind_help",
    "cli.app.modelo.reconcile.source_help",
    "cli.app.modelo.work.verify_selector_help",
    "application.workflow.errors.resume_revision_selector_invalid",
    "cli.app.modelo.work.document_format_help",
    "cli.app.modelo.list.domain_help",
]


@pytest.fixture(scope="module")
def accepted_choice_values() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    fallback_axes = {
        "cli.app.live.verify.expected_help": IdentityCheckVerdict,
        "cli.app.live.verify.expected_values_error": IdentityCheckVerdict,
        "application.workflow.errors.resume_revision_selector_invalid": ModeloCalculationRevisionSelector,
    }
    for key, axis in fallback_axes.items():
        result[key] = {member.value for member in axis}
    # Keep the two names advertised by this help, checked against their actual
    # enum members; this copy repair does not expand the advertised choices.
    result["cli.app.ledger.inventory.valuation_method_help"] = {ValuationMethod.FIFO.value, ValuationMethod.PMP.value}
    result["cli.app.modelo.list.domain_help"] = {
        parse_toml(
            (REPO_ROOT / "src/cadrumo/_data/registry/aeat/modelos" / modelo / "manifest.toml").read_text(
                encoding="utf-8"
            )
        )["modelo"]["tax_domain"]
        for modelo in ("303", "100", "200")
    }
    for graph in _command_graphs():
        for node in graph.nodes():
            for parameter in node.spec.parameters:
                if parameter.help_key is None:
                    continue
                key = parameter.help_key.value
                if key not in _HELP_KEYS or key in result:
                    continue
                contract = parameter.value
                if contract.choices:
                    result[key] = {str(choice) for choice in contract.choices}
                else:
                    axis: Any = getattr(import_module(contract.annotation.module), contract.annotation.qualname)
                    assert isinstance(axis, type) and issubclass(axis, Enum), key
                    result[key] = {str(member.value) for member in axis}
    assert set(result) == set(_HELP_KEYS)
    return result


@pytest.mark.parametrize("locale", ["ca", "en", "es", "hu"])
@pytest.mark.parametrize("key", _HELP_KEYS)
def test_help_code_values_match_the_executable_choice_axis(
    locale: str, key: str, accepted_choice_values: dict[str, set[str]]
) -> None:
    value = tr(key, locale=locale, selector="example")
    literals = set(re.findall(r"`([^`]+)`", value))
    assert literals == accepted_choice_values[key]
    assert not extract_placeholders(value)
    words = {
        word for _, words, _ in translation_spelling_segments(value + " misspellledd", key, locale) for word in words
    }
    assert "misspellledd" in words
    assert not literals & words
    assert all(token + "x" not in accepted_choice_values[key] for token in literals)


@pytest.mark.parametrize(
    "locale,key,required,retired",
    [
        ("en", "cli.app.ledger.account.role_help", "direct debit", "domiciliación"),
        ("en", "cli.app.modelo.reconcile.file_kind_help", "tax return PDF", "declaración"),
        ("hu", "cli.app.modelo.list.domain_help", "Szűrd", "Szűrje"),
    ],
)
def test_explanations_use_native_prose_and_informal_singular(
    locale: str, key: str, required: str, retired: str
) -> None:
    value = tr(key, locale=locale)
    assert required in value
    assert retired not in value
