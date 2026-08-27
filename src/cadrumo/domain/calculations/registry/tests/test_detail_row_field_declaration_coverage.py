"""Every declarable field on a detail observation must be a drawable row field.

A detail family carries two halves that can drift apart silently. The
observation MODEL holds what the app knows about one row; the family's
``_*RowField`` Literal declares which of those a binding may draw as a column.
A field present in the model and absent from the Literal is a quantity the app
holds and no declaration can ever reach.

That drift is invisible from either side alone. A fact-level sweep does not see
it because facts are aggregates, not columns. A row-level sweep does not see it
because the Literal IS the row-level search space -- asking "is every declared
row field supplied" can never surface a field the Literal never named.

=========================================================
Why most of the difference is benign, and why that is stated here
=========================================================

Four classes of model field are legitimately absent from a Literal, and they
account for every difference except one. There is no ``internal_only``
equivalent for row fields, so the tree cannot say "this field is a join key,
not a declarable column" at the site. Until it can, the classification lives
here, named and reasoned, rather than in a review note nobody re-reads:

* JOIN AND IDENTITY KEYS -- ``source_id``, ``invoice_id``. The row's handle
  back to its source record. Not a column in any sense.
* PERIOD WINDOW KEYS -- ``transaction_date``. Consumed to select rows into the
  filing window. These informativas declare annual per-counterparty aggregates,
  so the date is the filter, not the datum.
* DRAWN THROUGH THE FACT CHANNEL INSTEAD -- ``base_amount`` and
  ``invoice_total_amount`` are drawn as the ``base_sum`` and
  ``invoice_total_sum`` facts. Not undrawn at all; drawn on the other axis.
* SELECTOR FILTER KEYS -- ``iva_regime``, ``intracommunity_clave``,
  ``is_rectification``, ``source_kind``. These choose WHICH rows a binding
  consumes, on the selector, rather than being projected.

Everything else must be declared, or the modelo must have no export layout to
lose it from.
"""

from __future__ import annotations

from typing import Final, cast, get_args

import pytest
from pydantic import BaseModel

from .....core import Modelo
from ..authority import bundled_authority
from ..detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    RelatedPartyOperationObservation,
    _AtributionRowField,
    _ForeignAssetRowField,
    _RefundRowField,
    _RelatedPartyRowField,
)
from ..donativo_bindings import DonativoDonorObservation, _DonativoRowField
from ..errors import NoRevisionForPeriodError, RegistryValidationError
from ..invoice_bindings import InvoiceObservation, _InvoiceRowField
from ..withholding_bindings import WithholdingObservation, _WithholdingRowField

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Model fields that are legitimately not drawable columns. Reasoned in the
#: module docstring; each entry is a class, not a per-field exemption.
_NOT_A_DRAWABLE_COLUMN: Final[frozenset[str]] = frozenset(
    {
        # join / identity
        "source_id",
        "invoice_id",
        # period window
        "transaction_date",
        # drawn as a fact instead of a column
        "base_amount",
        "invoice_total_amount",
        # selector filter keys
        "iva_regime",
        "intracommunity_clave",
        "is_rectification",
        "source_kind",
    },
)

#: family -> (observation model, row-field Literal, modelo it declares into)
_FAMILIES: Final[tuple[tuple[str, type[BaseModel], object, Modelo], ...]] = (
    ("atribucion_member", AtributionMemberObservation, _AtributionRowField, Modelo.M184),
    ("foreign_asset", Modelo720RowObservation, _ForeignAssetRowField, Modelo.M720),
    ("refund_operation", RefundOperationObservation, _RefundRowField, Modelo.M360),
    ("related_party_operation", RelatedPartyOperationObservation, _RelatedPartyRowField, Modelo.M232),
    ("withholding", WithholdingObservation, _WithholdingRowField, Modelo.M190),
    ("donativo_donor", DonativoDonorObservation, _DonativoRowField, Modelo.M182),
    ("invoice", InvoiceObservation, _InvoiceRowField, Modelo.M347),
)


def _undeclared(model: type[BaseModel], literal: object) -> frozenset[str]:
    declared = frozenset(cast(str, field_name) for field_name in get_args(literal))
    model_fields = frozenset(cast(str, field_name) for field_name in model.model_fields)
    return model_fields - declared - _NOT_A_DRAWABLE_COLUMN


def _has_export_layout(modelo: Modelo) -> bool:
    """Whether this modelo writes any artefact a dropped column could vanish from."""
    authority = bundled_authority()
    for year in (2024, 2025):
        try:
            revision = authority.snapshot(modelo.value, filing_year=year, period="0A").revision
        except NoRevisionForPeriodError:
            # A modelo with no revision for the year exports nothing that year.
            # Caught by name rather than broadly: any OTHER failure here means
            # the probe itself is broken, and a broad except would let this gate
            # report "no layout" for a modelo it simply failed to load.
            continue
        except RegistryValidationError:
            # A filing-grade snapshot refuses for two reasons that BOTH mean this
            # modelo writes no artefact today: the revision declares no export
            # layout, or it is still `pending_review` and so cannot reach filing
            # grade at all. Either way a dropped column has nothing to vanish
            # from, which is precisely the state this gate treats as latent.
            #
            # This branch is not cosmetic. The review-status refusal was added to
            # snapshot building after this probe was written, and without it the
            # refusal propagates: measured, the probe RAISED for ten
            # registry-present modelos -- 165, 181, 182, 220, 270, 721 and 840 on
            # review status, 187, 188 and 194 on the missing layout -- so
            # `donativo_donor` failed here reporting that M182 "now HAS an export
            # layout" when M182 has none, authored or derived from its five
            # bindings. The probe could not answer for exactly the modelos most
            # likely to be missing a column.
            continue
        if revision.export_layouts:
            return True
    return False


def test_the_probe_answers_for_a_modelo_whose_snapshot_refuses() -> None:
    """A refusing snapshot must yield "exports nothing", never propagate.

    The probe asks one question -- does this modelo write an artefact a dropped
    column could vanish from -- and a filing-grade snapshot refuses for two
    reasons that both answer it NO: no export layout, or a `pending_review`
    revision that cannot reach filing grade. Letting either escape turns the
    answer into a crash for exactly the modelos most likely to be missing a
    column, and the assertion message then reports the opposite of the truth
    ("now HAS an export layout" for a modelo that has none).

    Anti-vacuity: the modelos below are asserted to be genuinely refusing, so
    this cannot pass because the probe stopped being exercised.
    """
    refusing = [Modelo.M182, Modelo.M187]

    for modelo in refusing:
        with pytest.raises(RegistryValidationError):
            bundled_authority().snapshot(modelo.value, filing_year=2025, period="0A")
        assert _has_export_layout(modelo) is False, (
            f"{modelo.value}: a refusing snapshot must read as 'exports nothing'"
        )


def test_the_families_are_all_reachable_and_carry_both_halves() -> None:
    """Anti-vacuity: with nothing resolved, every assertion below agrees with everything."""
    for name, model, literal, _ in _FAMILIES:
        assert model.model_fields, f"{name}: observation model has no fields"
        assert get_args(literal), f"{name}: row-field Literal declares nothing"


@pytest.mark.parametrize(("name", "model", "literal", "modelo"), _FAMILIES, ids=[f[0] for f in _FAMILIES])
def test_an_exporting_family_declares_every_drawable_field(
    name: str,
    model: type[BaseModel],
    literal: object,
    modelo: Modelo,
) -> None:
    """A field the model holds must be drawable, unless the modelo exports nothing.

    The escape is deliberate and is the whole reason this gate can be written
    today. ``donativo_donor`` holds ``country_code`` and its Literal never names
    it -- the only residue across all seven families, and an inconsistency
    rather than a design: every sibling family whose model carries
    ``country_code`` DOES declare it. It is not a live drop only because M182
    has no export layout, so there is no artefact for the column to be missing
    from.

    That makes "M182 gains an export layout" the trigger condition, and this
    gate is the tripwire on it. Before, the trigger lived in a review note; a
    note does not fire. Now, adding a layout to a modelo with an undeclared
    drawable field reds here instead of shipping a silently narrower record.
    """
    undeclared = _undeclared(model, literal)
    if not undeclared:
        return

    assert not _has_export_layout(modelo), (
        f"{name} holds {sorted(undeclared)} which its row-field Literal never declares, and "
        f"{modelo.value} now HAS an export layout. Either declare the field in the Literal, or "
        f"classify it in _NOT_A_DRAWABLE_COLUMN with a reason -- it can no longer stay latent, "
        f"because there is now an artefact for the column to be missing from."
    )


def test_the_known_latent_residue_is_exactly_donativo_country_code() -> None:
    """Pin the residue so it cannot silently grow, and so the gate above is not vacuous.

    Without this, a second family acquiring an undeclared field would be
    absorbed silently for as long as its modelo exports nothing -- and the
    parametrised gate would keep passing while the latent debt doubled. This
    asserts the exact shape of what is currently tolerated.
    """
    residue = {name: sorted(_undeclared(model, literal)) for name, model, literal, _ in _FAMILIES}
    non_empty = {name: fields for name, fields in residue.items() if fields}

    assert non_empty == {"donativo_donor": ["country_code"]}, (
        f"the tolerated residue changed: {non_empty}. A new entry is either a field to declare, "
        f"or a class to name in _NOT_A_DRAWABLE_COLUMN -- not something to add here"
    )
