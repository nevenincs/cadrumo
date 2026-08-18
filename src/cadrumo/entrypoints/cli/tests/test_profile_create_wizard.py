"""Terminal-boundary coverage for ``aeat config profile create``.

``config profile create`` is the operator's first contact with Cadrumo.
The scripted arm (``create NAME --quiet``) is the live creation door; its
real-behaviour coverage lives in the sibling
``_config/tests/test_scripted_profile_creation`` module, including the
refusal when no passphrase channel is available and the JSON-envelope
shape of a successful run. This module keeps the runtime-dispatch
boundary of a naked ``create`` -- it reaches its own refusal without a
missing-argument error and without being pre-empted by the storage
runtime's no-active-session refusal -- plus the verb-path preference and
the pinned question inventory the flags are derived from.

Two interactive-run tests were retired with the wizard: their premise --
that a console-less ``create`` is refused -- died when the scripted arm
landed, and their refusal and JSON-parseability shapes are asserted by
the scripted-creation module.
"""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage.master_key import close_active_bucket_session
from ....application.wizard import WIZARD_FLOWS
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from ....tests.user_profile import register_cli_profile
from .. import _prefer_complete_verb_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

def test_create_without_a_name_reaches_runtime_dispatch() -> None:
    """The registration TUI owns name collection for a naked create."""
    result = invoke_cached_cli(["config", "profile", "create"])

    assert result.exit_code != 0
    assert "Missing argument" not in result.output
    assert "Traceback" not in result.output


def test_bare_create_is_not_pre_empted_by_a_locked_existing_profile() -> None:
    """The create refusal must be reachable before any old bucket is unlocked.

    The important boundary is that the command reaches its own refusal rather
    than failing earlier with the storage runtime's no-active-session refusal,
    which would tell a first-timer to log in to a profile they do not have.
    """
    register_cli_profile(
        label="existing",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Existing",
            "identity.surnames": "Profile",
            "activities.description": "design",
        },
    )
    close_active_bucket_session()

    result = invoke_cached_cli(["config", "profile", "create"])

    assert result.exit_code != 0
    assert "No active bucket session" not in result.output
    assert "Traceback" not in result.output


def test_partial_click_path_cannot_mask_the_profile_create_leaf() -> None:
    """A group prefix must not remove the create bootstrap exemption.

    The root callback may see only ``config profile`` from Click while the
    real console argv still names ``config profile create``. Retaining the
    shorter path reproduces the live login refusal before the TUI opens.
    """
    assert (
        _prefer_complete_verb_path(
            context_path="config profile",
            argv_path="config profile create",
        )
        == "config profile create"
    )


# The pinned profile-create prompted-question inventory (see the question-count
# decision note in the cli-authority-quality-backlog plan): the full declared question set
# of the setup flow, which is exactly the ``supplied_question_ids`` frozenset the
# ``create`` path writes to the payload. This is the single place the inventory is
# pinned; a legitimate add or drop updates this set here, and any silent change
# fails the gate below.
_EXPECTED_SETUP_QUESTION_IDS = frozenset(
    {
        "activity",
        "activity-start-date",
        "address-postcode",
        "art109-activity-income-withholding-ge-70pct",
        "bienes-extranjero-above-threshold",
        # NOT "cloud-evidence-upload". It was a setup question and was deliberately
        # retired with the off-host read path (04561ef0f6, which names "the setup-wizard
        # question that asked the operator to opt in" among what it deleted). That commit
        # did not update this pin, so the entry outlived the question it named and this
        # gate has been red ever since -- reported as a moved COUNT rather than a named
        # id until the tally was removed.
        #
        # The capability's later return (069e0f5a96, 1ba2eb3633) did not reverse that.
        # Both are scoped to the ELIGIBILITY BAR and say so: the enum member and its
        # profile-schema field, restored because the enum/schema parity gate was red, and
        # a per-locale label because the translation-honesty ratchet refuses a
        # placeholder. Neither touches the wizard catalogue or this file. The operator
        # sets it through --cloud-evidence-upload/--no-cloud-evidence-upload, which is a
        # deliberate posture for a capability governing off-host transmission: settable,
        # but not offered in the interactive walk-through.
        "country-of-fiscal-residence",
        "does-intracomunitario",
        "enrollment-large-company",
        "enrollment-public-administration-budget-gt-6000000",
        "entity-type",
        "family-descendants-eu-eea-deduction",
        "family-minor-children-in-unit",
        "fiscal-residency",
        "google-export",
        "has-employees",
        "incn-prior-12-months",
        "irpf-estimation-regime",
        "irpf-income-categories",
        "irpf-special-regime",
        "irpf-special-regime-start-date",
        "iva-cash-accounting-regime-enrolled",
        "iva-group-dominant-entity-enrolled",
        "iva-group-member-enrolled",
        "iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        "iva-intracommunity-operations-exceed-50000-eur",
        "iva-m303-regime-composition",
        "iva-oss-enrolled",
        "iva-redeme-enrolled",
        "iva-regime",
        "iva-roi-enrolled",
        "iva-sii-enrolled",
        "iva-voluntary-sii-enrolled",
        "legal-entity-form",
        "legal-name",
        "ley-49-2002-option-date",
        "ley-49-2002-option-declared",
        "ley-49-2002-renunciation-date",
        "ley-49-2002-renunciation-declared",
        "llm-vision",
        "modelo-111-no-retenciones-periods",
        "monedas-virtuales-extranjero-above-threshold",
        "name",
        "new-entity-first-two-profit-periods",
        "notes",
        "objective-estimation-modulos-iae-epigraph",
        "objective-estimation-modulos-module-1-units",
        "objective-estimation-modulos-module-2-units",
        "objective-estimation-modulos-module-3-units",
        "objective-estimation-modulos-module-4-units",
        "objective-estimation-modulos-module-5-units",
        "objective-estimation-modulos-module-6-units",
        "objective-estimation-modulos-module-7-units",
        "output-language",
        "pays-capital-income-with-retencion",
        "pays-professionals-with-retencion",
        "pays-rent-with-retencion",
        "representante-fiscal-nif",
        "representante-fiscal-nombre",
        "situacion-familiar",
        "spouse-birth-date",
        "spouse-disability-grade",
        "spouse-eu-eea-country",
        "spouse-eu-eea-resident",
        "spouse-name",
        "spouse-non-resident-irpf",
        "spouse-sex",
        "spouse-surnames",
        "spouse-tax-id",
        "surnames",
        "tax-id",
        "tax-residence-ccaa",
        "tax-residence-jurisdiction-scope",
        "taxation-type",
        "taxpayer-birth-date",
        "taxpayer-death-date",
        "taxpayer-disability-grade",
        "taxpayer-marital-status",
        "taxpayer-marriage-date",
        "taxpayer-sex",
        "third-party-transactions-above-347-threshold",
    }
)


def test_profile_create_prompted_question_inventory_is_pinned() -> None:
    """A silent add, drop, or rename of a setup-flow question fails loudly.

    The wizard surfaces one flow; ``create`` writes every declared question id to
    the payload. The pinned SET is the contract, and it already catches an added
    question, a dropped one and a same-size rename swap; conditional per-answer
    visibility stays covered by the interactive persisted-fact tests above.

    There is deliberately no pinned COUNT. A tally encodes a moment rather than a
    property: it trains everyone to bump the constant, and once bumped it detects
    nothing the set does not already catch. It is also strictly worse at
    reporting — a count answers "something moved", the set answers WHICH question
    moved, which is the fact a reader needs. This gate previously failed with
    ``assert 75 == 76`` while the id naming the real defect sat one assertion
    below, unreached.

    Duplicates are still refused, as a property of the declaration rather than a
    size: the list being longer than the set means an id appears twice, and that
    holds at any inventory size.
    """
    assert len(WIZARD_FLOWS) == 1, WIZARD_FLOWS
    flow = WIZARD_FLOWS[0]
    assert flow.id == "setup", flow.id

    declared_ids = [question.id for section in flow.sections for question in section.questions]
    surfaced_ids = frozenset(declared_ids)

    duplicated = sorted({question_id for question_id in declared_ids if declared_ids.count(question_id) > 1})
    assert not duplicated, f"setup declares these question ids more than once: {duplicated}"

    pinned_but_absent = sorted(_EXPECTED_SETUP_QUESTION_IDS - surfaced_ids)
    declared_but_unpinned = sorted(surfaced_ids - _EXPECTED_SETUP_QUESTION_IDS)
    assert not (pinned_but_absent or declared_but_unpinned), (
        "setup question inventory drifted from the pinned set. "
        f"Pinned but not declared by the flow: {pinned_but_absent}. "
        f"Declared by the flow but not pinned: {declared_but_unpinned}."
    )
