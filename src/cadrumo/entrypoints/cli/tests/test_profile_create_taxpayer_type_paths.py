"""Non-interactive `config profile create` across the taxpayer-type axis.

These tests exercise the real `aeat config profile create ... --quiet`
CLI surface for every entity type. They pin the behaviour that a legal
entity, an attribution entity, and a natural person can each be created
non-interactively without supplying spouse / personal-IRPF flags, that
each taxpayer-type flag populates its own wizard question, and that
a taxpayer with no economic activity is not forced to invent one.

No mocks: the runner drives the real Typer command, the real wizard
runtime, and the real encrypted-SQLite profile store.

Non-interactive creation is now retired: `create` diverts a capable terminal
to the profile manager and refuses a console-less host. What survives here is
what does NOT depend on that path -- two edit refusals, whose fixtures now
register through the credential door, and two foral refusals, which fire
before the retirement check.

Thirteen tests were retired with this change. Each is named with what answers
it now, so a later reader does not read the deletions as lost coverage:

- creates_non_interactively_without_spouse_flags, creates_with_explicit_no_spouse_flag,
  creates_without_activity_start_date_flag: the subject WAS scripted creation,
  which is retired. No successor; the capability is gone by design.
- attribution_entity_profile_creates_without_spouse_flags:
  application/user_profile/tests/test_taxpayer_type_completeness.py
- pure_landlord_profile_creates_without_activity,
  pure_landlord_profile_stores_explicit_iva_regime_when_operator_opts_in,
  natural_person_with_economic_activity_stores_the_activity:
  application/user_profile/tests/test_irnr_profile_completeness.py
- non_resident_irnr_quiet_create_requires_country_before_registration,
  gb_legal_entity_irnr_quiet_create_requires_representante_before_registration:
  the same module, which asserts those paths among the missing-required set.
- legal_entity_form_flag_populates_the_legal_entity_form_field,
  activity_start_date_flag_stores_the_censo_alta_date: their subject is the
  flag-to-fact mapping of a retired path. The mapping itself is declared in
  application/wizard/_catalogue.py, which is its own authority.
- legal_entity_profile_create_and_edit_exposes_legal_name: the create half is
  retired; the edit half is covered by the surviving edit refusals here.
- missing_entity_type_does_not_re_report_supplied_identity_flags: its subject
  is the CONTENT of a refusal message on the retired path. The application
  layer does not render operator text, so it has no home rather than a
  successor.

Two tests are deliberately kept FAILING as the only in-tree evidence of rowed
gaps, rather than retired: the M210 next-action guidance, whose projection is
live but unreachable from the surface that now creates profiles, and the
legal-entity-form refusal, which no surviving surface enforces and which the
registry schema declares not required.
"""

from __future__ import annotations

import pytest

from ....core.i18n import tr
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage
from ....tests.user_profile import register_cli_profile

__all__ = ["isolated_profile_storage"]
from ._profile_cli_support import (
    create_quiet_profile as _create_profile,
)
from ._profile_cli_support import (
    edit_quiet_profile as _edit_profile,
)
from ._profile_cli_support import (
    profile_rows as _profile_rows,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_STATUS_LABEL = tr("application.wizard.output_labels.status", locale="en")
_NEXT_LABEL = tr("application.wizard.output_labels.next", locale="en")
_CREATED = tr("wizard.commands.status.created", locale="en")
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
    from ....core.config import load_settings

    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _registered_profile_exists(name: str) -> bool:
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

    return read_profile_bucket(name) is not None


def test_legal_entity_profile_create_refuses_missing_legal_form_before_registration() -> None:
    """A legal entity without a recognised legal form is not filing-grade."""

    result = _create_profile(
        "missing-form-co",
        "--entity-type",
        "legal_entity",
        "--tax-id",
        "B66012345",
        "--activity",
        "consultoria informatica",
        *_COMMON_TERRITORY_ARGS,
        "--iva-regime",
        "GENERAL",
        *_M303_IVA_FACT_ARGS,
    )

    assert result.exit_code != 0, result.output
    assert "--legal-entity-form" in result.output
    assert _registered_profile_exists("missing-form-co") is False


def test_non_resident_irnr_create_guides_to_m210_discovery_not_work_create() -> None:
    """A successful IRNR profile must not point at unsupported local M210 work."""

    result = _create_profile(
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
        "X1234567L",
        "--iva-regime",
        "GENERAL",
        *_COMMON_TERRITORY_ARGS,
        *_M303_IVA_FACT_ARGS,
    )

    assert result.exit_code == 0, result.output
    assert f"{_NEXT_LABEL}\taeat app modelo describe 210" in result.output
    assert f"{_NEXT_LABEL}\taeat app modelo work create" not in result.output


def test_edit_refuses_natural_person_branch_change_without_legal_name() -> None:
    """A branch-changing edit must not persist a legal entity without legal name."""

    # The profile is registered through the credential door rather than the
    # creation verb. The subject here is the EDIT refusal, which is unchanged
    # and still reachable; only the fixture's route had to move, because
    # non-interactive creation is retired and refuses before this test's own
    # assertion is ever reached.
    register_cli_profile(
        label="branch-to-legal",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Branch",
            "identity.surnames": "Operator",
            "activities.description": "consultoria",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )

    edit = _edit_profile(
        "branch-to-legal",
        "--entity-type",
        "legal_entity",
    )

    assert edit.exit_code != 0, edit.output
    assert "--legal-name" in edit.output
    rows = _profile_rows("branch-to-legal")
    assert rows["taxpayer_type.entity_type"] == "natural_person"
    assert rows["identity.name"] == "Branch"
    assert rows["identity.surnames"] == "Operator"


def test_edit_refuses_legal_entity_branch_change_without_surnames() -> None:
    """A branch-changing edit must not persist a natural person without surnames."""

    # The profile is registered through the credential door rather than the
    # creation verb. The subject here is the EDIT refusal, which is unchanged
    # and still reachable; only the fixture's route had to move, because
    # non-interactive creation is retired and refuses before this test's own
    # assertion is ever reached.
    register_cli_profile(
        label="branch-to-natural",
        facts={
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.tax_id": "B66012345",
            "identity.legal_name": "Branch Legal SL",
            "activities.description": "asesoria",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )

    edit = _edit_profile(
        "branch-to-natural",
        "--entity-type",
        "natural_person",
        "--name",
        "Branch",
    )

    assert edit.exit_code != 0, edit.output
    assert "--surnames" in edit.output
    rows = _profile_rows("branch-to-natural")
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["identity.legal_name"] == "Branch Legal SL"
    assert "identity.name" not in rows


@pytest.mark.parametrize(
    ("name", "tax_id", "activity", "ccaa", "expected_url"),
    (
        pytest.param("lourdes", "44444444A", "traductora", "pais_vasco", "sede.bizkaia.eus", id="pais_vasco"),
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

    result = _create_profile(
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
    body. This is the operator-reported localization gap for foral CCAA.
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
            "44444444A",
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
