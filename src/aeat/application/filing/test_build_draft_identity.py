"""Contract tests for identity fields populated by the production build_draft path.

:class:`ModeloDraft.subject_tax_id` and :class:`ModeloDraft.snapshot_ref`
both default to ``None`` on the model so already-persisted drafts remain
loadable. The production ``build_draft`` entry point is the only path
that constructs a *new* draft, and it must populate both fields:
``subject_tax_id`` from the validated profile substrate and
``snapshot_ref`` from the resolved registry snapshot. Without a contract
test exercising the real ``build_draft``, a regression that stopped
wiring either field would leave new drafts silently identity-less and
the encrypted-persistence roundtrip suite would not catch it (the
roundtrip fixtures build drafts directly, not via ``build_draft``).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import build_draft, build_runtime_schema_provider
from .testing import ModeloTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> ModeloTestProfile:
    return ModeloTestProfile(
        tax_id="12345678Z",
        display_name="build_draft identity contract",
    )


def test_build_draft_populates_subject_tax_id_and_snapshot_ref() -> None:
    """The production build_draft path populates both identity fields.

    Both ``subject_tax_id`` and ``snapshot_ref`` default to ``None`` on
    :class:`ModeloDraft`; this contract test pins that a freshly built
    draft carries the validated taxpayer identity and the registry
    snapshot reference resolved during the build.
    """

    draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(),
    )

    assert draft.subject_tax_id is not None
    assert draft.subject_tax_id == "12345678Z"
    assert draft.subject_tax_id == draft.profile_tax_id

    assert draft.snapshot_ref is not None
    assert draft.snapshot_ref.modelo == "130"
    assert draft.snapshot_ref.revision_id == "2019-y-siguientes"
    assert draft.snapshot_ref.modelo_year == 2026
    assert draft.snapshot_ref.period == "1T"
