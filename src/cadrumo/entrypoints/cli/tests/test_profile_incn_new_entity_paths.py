"""Non-interactive `config profile edit` for the INCN and new-entity facts.

These tests exercise the real CLI surface for the two optional profile
facts added by the corporate-tax-runtime plan:

* `--incn-prior-12-months` — the importe neto de la cifra de negocios
  of the prior 12 months, a typed Decimal that gates the Modelo 202
  modality split at the 6.000.000 EUR threshold (LIS Art. 40.3).
* `--new-entity-first-two-profit-periods` — the LIS Art. 29
  first-two-profit-making-periods state that opts a newly-created
  legal entity into the 15 percent rate override.

Both facts are optional: an unset profile must not carry the fact at
all, so the downstream engine stays at INCOMPLETE (for the modality
gate) or on the otherwise-applicable rate (for the new-entity
override) instead of guessing.

Each profile is seeded through the credential registration door and the
fact under test is then written with the real ``edit --quiet`` patch verb.
That is a move, not a narrowing: the subject was always the flag-to-fact
mapping and the three-state absence semantics, and ``edit`` carries the same
two flags. The wizard ``create`` arm refuses unconditionally, so it can no
longer carry the seed OR the write.

No mocks: the runner drives the real Typer command, the real wizard
runtime, and the real encrypted-SQLite profile store.
"""

from __future__ import annotations

import pytest

from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage

__all__ = ["isolated_profile_storage"]
from ._profile_cli_support import (
    edit_quiet_profile as _edit_profile,
)
from ._profile_cli_support import (
    profile_rows as _profile_rows,
)
from ._profile_cli_support import (
    seed_profile as _seed_profile,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LEGAL_ENTITY_FACTS = {
    "taxpayer_type.entity_type": "legal_entity",
    "taxpayer_type.legal_entity_form": "sl",
    "identity.tax_id": "B66012345",
    "identity.legal_name": "Test SL",
    # Blank drops the natural-person placeholders the shared seeding door
    # applies, which a legal entity has no business carrying.
    "identity.name": "",
    "identity.surnames": "",
    "taxpayer_type.irpf_income_categories": "",
    "irpf.estimation_regime": "",
}


def _seed_legal_entity(name: str, *, activity: str) -> str:
    return _seed_profile(name, **_LEGAL_ENTITY_FACTS, **{"activities.description": activity})


def test_incn_prior_12_months_flag_stores_the_decimal_fact() -> None:
    """The optional INCN figure of the prior 12 months lands in its own
    profile fact. Stored verbatim as a canonical decimal token so the
    Modelo 202 modality gate (6.000.000 EUR threshold, LIS Art. 40.3)
    can decide without re-parsing."""

    _seed_legal_entity("incn-co", activity="asesoria")
    result = _edit_profile("incn-co", "--incn-prior-12-months", "7500000.00")

    assert result.exit_code == 0, result.output
    rows = _profile_rows("incn-co")
    assert rows["taxpayer_type.incn_prior_12_months"] == "7500000.00"


def test_profile_creates_without_incn_flag_leaves_fact_unset() -> None:
    """The INCN is optional: a profile created with no
    `--incn-prior-12-months` flag must not carry the fact at all, so
    the downstream Modelo 202 modality gate stays at INCOMPLETE rather
    than guessing a modality."""

    _seed_legal_entity("no-incn-co", activity="comercio")

    rows = _profile_rows("no-incn-co")
    assert "taxpayer_type.incn_prior_12_months" not in rows


def _load_active_taxpayer_profile():
    """Return the reloaded ``TaxpayerProfile`` for the active profile.

    Used by the three-state assertions below — the projection layer
    is the surface the LIS Art. 29 gate reads, so the contract under
    test must be asserted there, not only at the canonical-dict layer.

    The CLI ``config profile create`` provisioned the bucket but its
    storage session is scoped to the command invocation.  Read the
    active bucket pointer minted by create, then re-open a storage
    session so ``workflow_state_repository()`` can decrypt through
    the storage runtime.
    """

    from ....application.user_profile.projections import record_to_path_values
    from ....application.workflow.persistence import workflow_state_repository
    from ....core.bucket_pointer import read_pointer
    from ....core.config import load_settings
    from ....domain.deadlines.profiles import taxpayer_profile_from_mapping

    pointer = read_pointer(load_settings().cadrumo_local_storage_root)
    assert pointer.bucket_id is not None, "config profile create did not mint an active bucket pointer"
    with open_test_profile_session(pointer.bucket_id):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        canonical = dict(record_to_path_values(record))
    # The LIS Art. 29 gate consumes the canonical-token mapping projected
    # via ``taxpayer_profile_from_mapping`` in ``domain.deadlines.profiles``.
    # That projection carries ``new_entity_first_two_profit_periods`` and
    # ``incn_prior_12_months`` through to the corporate-tax record, unlike
    # the narrower wizard-status ``TaxpayerProfile`` projection.
    return taxpayer_profile_from_mapping(canonical, tax_id_default=canonical.get("identity.tax_id", ""))


def test_new_entity_first_two_profit_periods_flag_stores_the_bool() -> None:
    """The optional LIS Art. 29 first-two-profit-periods state lands in
    its own profile fact. A positively-declared True opts the entity
    into the 15 percent new-entity rate override."""

    _seed_legal_entity("new-co", activity="consultoria")
    result = _edit_profile("new-co", "--new-entity-first-two-profit-periods")

    assert result.exit_code == 0, result.output
    rows = _profile_rows("new-co")
    assert rows["taxpayer_type.new_entity_first_two_profit_periods"] == "true"
    profile = _load_active_taxpayer_profile()
    assert profile.new_entity_first_two_profit_periods is True


def test_profile_creates_without_new_entity_flag_leaves_fact_undeclared() -> None:
    """The new-entity state is opt-in and three-state: a profile created
    with neither ``--new-entity-first-two-profit-periods`` nor
    ``--no-new-entity-first-two-profit-periods`` must not carry the
    fact at all, so the LIS Art. 29 gate reads it as INCOMPLETE rather
    than collapsing onto a positively-declared no-override.

    This is the BLOCKER-1 contract: the canonical row is absent (not
    a stored ``"false"``), and the reloaded ``TaxpayerProfile``
    projection reads ``None``."""

    _seed_legal_entity("no-new-co", activity="asesoria")

    rows = _profile_rows("no-new-co")
    assert "taxpayer_type.new_entity_first_two_profit_periods" not in rows
    profile = _load_active_taxpayer_profile()
    assert profile.new_entity_first_two_profit_periods is None


def test_no_new_entity_first_two_profit_periods_flag_records_declared_false() -> None:
    """``--no-new-entity-first-two-profit-periods`` positively declares
    the absence of the override. The stored canonical row is the
    explicit ``"false"`` token, and the reloaded
    ``TaxpayerProfile`` projects it to ``False`` — distinct from the
    undeclared three-state ``None``."""

    _seed_legal_entity("decline-new-co", activity="asesoria")
    result = _edit_profile("decline-new-co", "--no-new-entity-first-two-profit-periods")

    assert result.exit_code == 0, result.output
    rows = _profile_rows("decline-new-co")
    assert rows["taxpayer_type.new_entity_first_two_profit_periods"] == "false"
    profile = _load_active_taxpayer_profile()
    assert profile.new_entity_first_two_profit_periods is False


def test_edit_patches_incn_and_new_entity_flags_onto_existing_profile() -> None:
    """`config profile edit --quiet` must patch the INCN and the
    new-entity state onto an existing profile without disturbing the
    other facts. Patch semantics, not a full rewrite."""

    _seed_legal_entity("edit-co", activity="asesoria")

    edit = _edit_profile(
        "edit-co",
        "--incn-prior-12-months",
        "1234567.89",
        "--new-entity-first-two-profit-periods",
    )
    assert edit.exit_code == 0, edit.output

    rows = _profile_rows("edit-co")
    assert rows["taxpayer_type.incn_prior_12_months"] == "1234567.89"
    assert rows["taxpayer_type.new_entity_first_two_profit_periods"] == "true"
    # Other facts left untouched by the patch edit.
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"


def test_charge_iban_flag_is_rejected_after_the_profile_export_path_cutover() -> None:
    """The real CLI cannot reintroduce the retired persisted debit path."""
    _seed_legal_entity("charge-account-co", activity="asesoria")

    edit = _edit_profile(
        "charge-account-co",
        "--charge-iban",
        "ES7921000813610123456789",
    )
    assert edit.exit_code != 0
    assert "--charge-iban" in edit.output

    rows = _profile_rows("charge-account-co")
    assert not any(path.startswith("filing_export.") for path in rows)
