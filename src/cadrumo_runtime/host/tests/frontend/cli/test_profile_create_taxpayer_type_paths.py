"""Non-interactive `config profile create` across the taxpayer-type axis.

These tests exercise the real `aeat config profile create ... --quiet`
CLI surface for every entity type. They pin the behaviour that a legal
entity, an attribution entity, and a natural person can each be created
non-interactively without supplying spouse / personal-IRPF flags, that
each taxpayer-type flag populates its own wizard question, and that
a taxpayer with no economic activity is not forced to invent one.

No mocks: the runner drives the real Typer command, the real wizard
runtime, and the real encrypted-SQLite profile store.

Non-interactive creation is retired: `create` diverts a capable terminal to the
profile manager and refuses a console-less host. The cases here do not depend on
that path: two edit refusals, whose fixtures register through the credential
door, and two foral refusals, which fire before the retirement check.

The remaining cases assert the live setup-state boundary: registration and
editing may leave a profile incomplete, while ``complete-setup`` refuses a
filing-grade declaration until every conditional identity fact is supplied.
"""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli

__all__ = ["isolated_profile_storage"]
from .profile_cli_support import (
    create_quiet_profile,
    edit_quiet_profile,
    invoke_protected_profile,
    profile_rows,
)
from .profile_cli_support import native_profile_runtime as native_profile_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_COMMON_TERRITORY_ARGS = (
    "--tax-residence-jurisdiction-scope",
    "common_regime",
)
_M303_IVA_FACT_ARGS = (
    "--iva-m303-regime-composition",
    "general",
    "--no-iva-redeme-enrolled",
    "--no-iva-cash-accounting-regime-enrolled",
    "--no-iva-voluntary-sii-enrolled",
    "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
)


def _dev_secret() -> str:
    """The secret the isolated backend seeds custody envelopes with."""
    from cadrumo.core.config import load_settings

    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _registered_profile_exists(name: str) -> bool:
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

    return read_profile_bucket(name) is not None


def test_legal_entity_profile_create_defers_missing_legal_form_to_complete_setup() -> None:
    """Registration persists an incomplete legal entity; completion enforces its form."""

    result = create_quiet_profile(
        "missing-form-co",
        "--entity-type",
        "legal_entity",
        "--tax-id",
        "B00015032",
        "--activity",
        "consultoria informatica",
        *_COMMON_TERRITORY_ARGS,
        "--iva-regime",
        "GENERAL",
        *_M303_IVA_FACT_ARGS,
    )

    assert result.exit_code == 0, result.output
    assert _registered_profile_exists("missing-form-co")
    assert "complete-setup" in result.output


def test_non_resident_irnr_create_guides_to_setup_before_work_creation() -> None:
    """Registration leaves the operator at the explicit setup declaration."""

    result = create_quiet_profile(
        "irnr-profile",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "capital_inmobiliario",
        "--fiscal-residency",
        "non_resident_irnr",
        "--country-of-fiscal-residence",
        "FR",
        "--tax-id",
        "X0001500M",
        "--iva-regime",
        "GENERAL",
        *_COMMON_TERRITORY_ARGS,
        *_M303_IVA_FACT_ARGS,
    )

    assert result.exit_code == 0, result.output
    assert "complete-setup" in result.output
    assert "modelo work create" not in result.output


@pytest.mark.windows_only
@pytest.mark.usefixtures("native_profile_runtime")
def test_edit_refuses_natural_person_branch_change_without_legal_name() -> None:
    """A branch-changing edit must not persist a legal entity without legal name."""

    # The profile is registered through the credential door. This profile is
    # already complete, so the edit itself must reject a transition that omits
    # the legal name.
    register_cli_profile(
        label="branch-to-legal",
        facts={
            **native_general_iva_facts(),
            "identity.tax_id": "12345678Z",
            "identity.name": "Branch",
            "identity.surnames": "Operator",
            "activities.description": "consultoria",
        },
        log_in=False,
    )

    edit = edit_quiet_profile(
        "branch-to-legal",
        "--entity-type",
        "legal_entity",
    )

    assert edit.exit_code != 0, edit.output
    assert "--legal-name" in edit.output
    rows = profile_rows("branch-to-legal")
    assert rows["taxpayer_type.entity_type"] == "natural_person"
    assert rows["identity.name"] == "Branch"
    assert rows["identity.surnames"] == "Operator"


@pytest.mark.windows_only
@pytest.mark.usefixtures("native_profile_runtime")
def test_edit_allows_a_natural_person_branch_without_surnames() -> None:
    """Surnames remain a modelo-specific filing requirement, not setup state."""

    # The profile is registered through the credential door. Setup remains
    # incomplete to prove that the profile setup gate does not impose a
    # modelo-specific surname requirement.
    register_cli_profile(
        label="branch-to-natural",
        facts={
            **native_general_iva_facts(),
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.tax_id": "B00015032",
            "identity.legal_name": "Branch Legal SL",
            "identity.surnames": "",
            "activities.description": "asesoria",
        },
        complete=False,
        log_in=False,
    )

    edit = edit_quiet_profile(
        "branch-to-natural",
        "--entity-type",
        "natural_person",
        "--name",
        "Branch",
    )

    assert edit.exit_code == 0, edit.output
    rows = profile_rows("branch-to-natural")
    assert rows["taxpayer_type.entity_type"] == "natural_person"
    assert rows["identity.name"] == "Branch"
    assert "identity.surnames" not in rows

    completion = invoke_protected_profile("branch-to-natural", "complete-setup")
    assert completion.exit_code == 0, completion.output


@pytest.mark.parametrize(
    ("name", "tax_id", "activity", "ccaa", "expected_url"),
    (
        pytest.param("lourdes", "00001503P", "traductora", "pais_vasco", "sede.bizkaia.eus", id="pais_vasco"),
        pytest.param("navarrese", "44444445B", "agricultor", "navarra", "hacienda.navarra.es", id="navarra"),
    ),
)
def test_profile_create_refuses_foral_tax_residence_with_concierto_economico_redirect(
    name: str,
    tax_id: str,
    activity: str,
    ccaa: str,
    expected_url: str,
) -> None:
    """Foral tax residences must refuse AEAT profile creation with a legal redirect."""

    result = create_quiet_profile(
        name,
        "--entity-type",
        "natural_person",
        "--tax-id",
        tax_id,
        "--activity",
        activity,
        "--tax-residence-ccaa",
        ccaa,
    )

    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")
    output = result.output or ""
    # Rich box rendering may line-wrap "Ley 12/2002" across two lines; assert
    # each token independently so the legal citation is definitely present.
    assert "12/2002" in output, f"Expected 12/2002 (Ley 12/2002) in foral refusal; got: {output!r}"
    assert expected_url in output, f"Expected foral URL {expected_url!r} in refusal; got: {output!r}"


def test_profile_create_foral_refusal_renders_localized_error_document_in_json_mode() -> None:
    """The foral refusal arrives as the shared-spine error document, not Click chrome.

    Under ``--format json`` the refusal must route through the localized
    CadrumoError boundary — a registered ``REFUSED_PROFILE_FORAL_REGIME``
    error document — rather than a Click ``Usage`` box wrapping a localized
    body.
    """
    import json

    result = invoke_cached_cli(
        (
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "lourdes",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--name",
            "Lourdes",
            "--surnames",
            "Foral",
            "--tax-id",
            "00001503P",
            "--activity",
            "traductora",
            "--tax-residence-ccaa",
            "pais_vasco",
            "--secrets-stdin",
        ),
        # The foral refusal this case asserts lives BEHIND the credential channel:
        # create mints custody, so without the passphrase and its confirmation the
        # verb refuses for the channel instead and never evaluates the regime.
        input=json.dumps(
            {
                "passphrase": _dev_secret(),
                "passphrase_confirmation": _dev_secret(),
            }
        ),
    )

    assert result.exit_code == 2, result.output
    output = result.output or ""
    assert "Usage:" not in output, f"Click usage chrome leaked into JSON refusal: {output!r}"
    assert "Traceback" not in output
    document = next((json.loads(line) for line in output.splitlines() if line.strip().startswith("{")), None)
    assert document is not None, f"no JSON error document in output: {output!r}"
    error = document["error"]
    assert error["code"] == "REFUSED_PROFILE_FORAL_REGIME"
    assert error["category"] == "REFUSED"
    # The rendered message is the localized foral body (legal citation present),
    # proving translated_message resolved rather than a bare English fallback.
    assert "12/2002" in str(error["message"])
