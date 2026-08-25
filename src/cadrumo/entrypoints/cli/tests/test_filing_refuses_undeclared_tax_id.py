"""A filing command refuses an undeclared tax identity instead of filing under a placeholder.

``projection_for_taxpayer`` substitutes a synthetic NIF when the operator has
declared none, and that placeholder passes the Spanish control-letter check, so
downstream it is indistinguishable from a declared identity. On the export path
the value is written into the fichero as the declarant: an operator who never
entered their NIF would receive a structurally valid declaration identifying
somebody else. ``_filing_taxpayer_or_refuse`` is the boundary that stops it.

**On the fixture.** The absent-identity profile is built by CONSTRUCTION, never
by removal: the persisted facts tuple is rebuilt without ``identity.tax_id``, so
the fact is never written and no empty string is ever stored. That distinction is
load-bearing. A fixture that wrote ``value=""`` would be testing "declared as
empty", not "not declared", and would pass while proving nothing about the case
that matters. :func:`test_the_fixture_really_declares_no_tax_id` asserts the
property directly rather than trusting the construction.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile
from .._common import _declared_tax_id, cli_policy_refusal_projection
from ..errors import CliRefusedBoundaryError, error_boundary_under_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TAX_ID = "12345678Z"

#: Everything a filing command needs to get PAST the other preflight gates, so a
#: refusal here can only be about the identity. Mirrors the fact set used by the
#: quickfile suite.
_SUPPORTING_FACTS = (
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2026, 1, 1)),
)


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": _TAX_ID,
            "identity.name": "Operator",
            "identity.surnames": "Identity",
            "activities.description": "design",
        },
    )


def _persist_facts(*, include_tax_id: bool) -> None:
    """Persist the active profile's facts, with ``identity.tax_id`` present or absent.

    The absent case rebuilds the tuple from scratch rather than deleting an
    entry: the path is simply never among the facts written, which is what makes
    absence unambiguous.
    """
    from ....core.bucket_pointer import resolve_active_bucket_id
    from ....tests.profile_capsule import load_test_profile_record, replace_test_profile_record

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "profile create must install an active-profile pointer"
    with open_test_profile_session(bucket_id):
        record = load_test_profile_record(bucket_id)
        kept = {fact.path: fact for fact in record.facts if fact.path != "identity.tax_id"}
        kept.update({fact.path: fact for fact in _SUPPORTING_FACTS})
        if include_tax_id:
            kept["identity.tax_id"] = UserProfileFact(path="identity.tax_id", value=_TAX_ID)
        replace_test_profile_record(
            record.model_copy(
                update={
                    "facts": tuple(kept[path] for path in sorted(kept)),
                    "updated_at": record.created_at,
                },
            ),
        )


def _active_record():
    from ....core.bucket_pointer import resolve_active_bucket_id
    from ....tests.profile_capsule import load_test_profile_record

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with open_test_profile_session(bucket_id):
        return load_test_profile_record(bucket_id)


def _export_result():
    return _invoke(
        [
            "--format", "json",
            "app", "modelo", "export",
            "--modelo", "303", "--year", "2026", "--period", "1T",
            "--output", "declaration.boe",
        ],
    )  # fmt: skip


def test_the_fixture_really_declares_no_tax_id() -> None:
    """Anti-tautology: prove absence directly, rather than trusting the construction.

    If this ever passed while the fact was stored as an empty string, the refusal
    test below would be exercising "declared as empty" and would tell us nothing
    about an undeclared identity. Asserting the property here keeps the fixture
    honest independently of how it was built.
    """
    _create_profile()
    _persist_facts(include_tax_id=False)

    assert _declared_tax_id(_active_record()) == "", (
        "the fixture profile must declare no tax id at all; a stored empty string would make the refusal test vacuous"
    )


def test_export_refuses_when_the_operator_declared_no_tax_id() -> None:
    """The defect: without this the export writes a placeholder NIF as the declarant."""
    _create_profile()
    _persist_facts(include_tax_id=False)

    result = _export_result()

    assert result.exit_code != 0, f"export must refuse an undeclared identity, got:\n{result.output}"
    # Match the identity refusal specifically. A substring like "tax" would also
    # match an unrelated failure -- a missing draft, an unresolved period -- and
    # this test would then pass while never exercising the guard at all.
    assert "does not declare a tax identity" in result.output, (
        f"export failed, but not with the identity refusal -- this test would be passing "
        f"for the wrong reason:\n{result.output}"
    )
    assert "identity.tax_id" in result.output or "tax id" in result.output.lower(), (
        f"the refusal must name WHICH fact is missing, not merely that one is:\n{result.output}"
    )


def test_export_identity_refusal_carries_the_profile_edit_action() -> None:
    _create_profile()
    _persist_facts(include_tax_id=False)

    with error_boundary_under_test(), pytest.raises(CliRefusedBoundaryError) as raised:
        cadrumo_click_command().main(
            args=[
                "--format",
                "json",
                "app",
                "modelo",
                "export",
                "--modelo",
                "303",
                "--year",
                "2026",
                "--period",
                "1T",
                "--output",
                "declaration.boe",
            ],
            prog_name="aeat",
            standalone_mode=False,
        )

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "modelo.export"
    assert projection.precondition_action.failed_condition_id == "taxpayer.identity.tax_id.declared"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.edit"


def test_a_declared_tax_id_is_not_refused_by_the_identity_guard() -> None:
    """Positive control: the guard must not fire for an operator who declared a NIF.

    The command may still fail further along - this fixture has no verified draft
    to export - so this asserts the *identity* refusal specifically is absent
    rather than asserting success. Without this control, a guard that refused
    every export unconditionally would satisfy the refusal test above.
    """
    _create_profile()
    _persist_facts(include_tax_id=True)

    result = _export_result()
    output = result.output.lower()

    assert "filing_requires_declared_tax_id" not in output, (
        f"the identity guard fired for a profile that declares a tax id:\n{result.output}"
    )
    assert "does not declare a tax identity" not in output, (
        f"the identity refusal text appeared for a declared identity:\n{result.output}"
    )
