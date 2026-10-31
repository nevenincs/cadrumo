"""Localized interface references resolve to real commands and public methods."""

import ast
import re

import pytest

from cadrumo.application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from cadrumo.core.i18n.render import tr
from cadrumo.core.output_rendering import OutputFormat

from ..._paths import REPO_ROOT
from ..signal_command_paths import command_path_pattern, executable_command_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize(
    "key,paths",
    [
        (
            "cli.app.modelo.reconcile.app_help",
            {
                "aeat app modelo reconcile pull",
                "aeat app modelo reconcile import",
                "aeat app modelo reconcile list",
            },
        ),
        (
            "cli.config.profile.automation.approve.digest_help",
            {"cadrumo-runtime config profile automation inspect"},
        ),
        (
            "cli.config.profile.automation.decline.digest_help",
            {"cadrumo-runtime config profile automation inspect"},
        ),
        ("cli.config.profile.row.row_help", {"aeat config profile view"}),
        ("cli.ledger.classify.reason_help", {"aeat app ledger view"}),
        ("cli.app.modelo.bindings.unscoped_revision_warning", {"aeat app modelo work calculate"}),
        ("cli.config.auth.apoderado.check_help", {"cadrumo-runtime config auth apoderado status"}),
        ("cli.config.profile.create_guidance_unavailable", {"aeat config profile status"}),
        ("cli.ledger.check.period_help", {"aeat app ledger status"}),
    ],
)
def test_referenced_commands_are_complete_executable_paths(locale: str, key: str, paths: set[str]) -> None:
    value = tr(key, locale=locale, missing_filters="example")
    referenced = {match.group() for match in command_path_pattern().finditer(value)}

    assert paths <= referenced
    assert all(tuple(path.split()) in executable_command_paths() for path in paths)


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_format_topic_advertises_only_the_global_output_format_values(locale: str) -> None:
    value = tr("topic.formats.body", locale=locale)
    literals = set(re.findall(r"`([^`]+)`", value))
    assert literals == {member.value for member in OutputFormat} | {"--format"}


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_invoice_evidence_help_names_the_public_request_and_its_scheme_field(locale: str) -> None:
    value = tr("cli.app.modelo.aggregate.received_invoice_retencion_help", locale=locale)
    assert set(re.findall(r"`([^`]+)`", value)) == {InvoiceWithholdingEvidenceRequest.__name__, "scheme"}
    field = InvoiceWithholdingEvidenceRequest.model_fields["scheme"]
    assert field.alias in (None, "scheme")
    assert field.validation_alias in (None, "scheme")


@pytest.fixture(scope="module")
def public_auth_methods() -> dict[str, set[str]]:
    result = {}
    for name, filename in {
        "AeatAuthenticator": "authenticator.py",
        "ClaveMovilAuthProvider": "clave_movil.py",
    }.items():
        source = REPO_ROOT / "src/cadrumo/adapters/outbound/aeat/auth" / filename
        definition = next(
            node
            for node in ast.parse(source.read_text(encoding="utf-8")).body
            if isinstance(node, ast.ClassDef) and node.name == name
        )
        result[name] = {
            node.name
            for node in definition.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
        }
    return result


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize(
    "key,owner,methods",
    [
        ("adapters.auth.authenticator.errors.already_active", "AeatAuthenticator", {"close"}),
        ("adapters.auth.authenticator.errors.no_active_context", "AeatAuthenticator", {"authenticate"}),
        ("adapters.auth.clave_movil.errors.already_active", "ClaveMovilAuthProvider", {"close"}),
        (
            "adapters.auth.clave_movil.errors.verify_requires_active_context",
            "ClaveMovilAuthProvider",
            {"verify", "authenticate"},
        ),
    ],
)
def test_auth_recovery_names_real_methods_instead_of_a_retired_alternative(
    locale: str, key: str, owner: str, methods: set[str], public_auth_methods: dict[str, set[str]]
) -> None:
    value = tr(key, locale=locale)
    references = re.findall(r"(?<![\w.])(?:[A-Za-z_]\w*\.)?[A-Za-z_]\w*\(\)", value)

    assert set(references) == {f"{owner}.{method}()" for method in methods}
    assert methods <= public_auth_methods[owner]
    assert "reauthenticate()" not in value
