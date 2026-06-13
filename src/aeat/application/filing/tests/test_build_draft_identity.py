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

from datetime import date
from decimal import Decimal

import pytest

from ....core import Period
from ....core.resources import resources
from .. import _filing_period_date, build_draft, build_runtime_schema_provider
from ..testing import ModeloTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
        period=Period.from_year_and_code(2026, "1T"),
        profile=_profile(),
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            # Binding IDs are extracted from the flat inputs dict via
            # _decimal_inputs_for_ids(inputs, decimal_binding_ids).
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
            # Casilla 15 is previous_filing-bound (modelo-130-resultados-
            # negativos-anteriores). For Q1 the prior-quarter anchor is
            # absent by design (max_year_delta=0, no prior trimestre in
            # the same ejercicio). Supplying it as a casilla input would
            # violate the smuggled-binding guard; the formula
            # engine materialises it as Decimal("0") via the absent-by-
            # design path with provenance marker on the CasillaObservation.
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(),
    )

    assert draft.subject_tax_id is not None
    assert draft.subject_tax_id == "12345678Z"
    assert draft.subject_tax_id == draft.profile_tax_id

    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T", on=date(2026, 4, 1))

    assert draft.snapshot_ref is not None
    assert draft.snapshot_ref.modelo == "130"
    assert draft.snapshot_ref.revision_id == snapshot.revision.id
    assert draft.snapshot_ref.modelo_year == 2026
    assert draft.snapshot_ref.period == "1T"


def test_typed_extended_and_event_periods_resolve_filing_date_context() -> None:
    """Typed non-standard registry periods still supply the calculation date axis."""

    assert _filing_period_date(Period.from_year_and_code(2025, "EXT-1T")) == date(2025, 3, 31)
    assert _filing_period_date(Period.from_year_and_code(2025, "EXT-4T")) == date(2025, 12, 31)
    assert _filing_period_date(Period.from_year_and_code(2025, "AD-HOC")) == date(2025, 12, 31)
