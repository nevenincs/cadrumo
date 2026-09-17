"""Contract tests for registry-projected IRNR wire tokens.

Core owns the distinct string types, not their value sets. Membership is
therefore exercised through the validated registry projections that publish
each token family, while direct construction remains closed to consumers.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.irnr import ConvenioOverrideKind, M210PayerMode, TipoRentaIrnr
from ....transactions.m210_income_classification import resolve_m210_payer_mode
from ..authority import PinnedAuthorityOperation
from ..authority_artifact import SnapshotGlobalsComponentQuery
from ..convenio import resolve_convenio_override
from ..irnr_tipo_renta import resolve_tipo_renta_irnr_catalogue
from ..schema import SnapshotGlobalCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_EFFECTIVE_DATE = date(2025, 1, 1)


def test_tipo_renta_tokens_are_published_by_the_validated_catalogue() -> None:
    catalogue = resolve_tipo_renta_irnr_catalogue(effective_date=_EFFECTIVE_DATE)

    assert catalogue.definitions
    assert catalogue.all_tokens == frozenset(definition.token for definition in catalogue.definitions)
    assert all(isinstance(token, TipoRentaIrnr) for token in catalogue.all_tokens)
    assert all(catalogue.require(token) is token for token in catalogue.all_tokens)


def test_payer_mode_is_projected_by_the_selected_detail_catalogue() -> None:
    payer_mode = resolve_m210_payer_mode(effective_date=_EFFECTIVE_DATE)

    assert isinstance(payer_mode, M210PayerMode)
    assert payer_mode.value == str(payer_mode)


def test_convenio_kind_is_projected_by_the_validated_fact_authority(*, operation: PinnedAuthorityOperation) -> None:
    snapshot_globals = operation.load(SnapshotGlobalsComponentQuery(), pin=operation.generation)
    assert isinstance(snapshot_globals, SnapshotGlobalCatalogues)
    convenio = snapshot_globals.convenio
    # A treaty row may predate the supported filing years; resolve one that applies inside them.
    floor = date(operation.supported_filing_years().floor, 1, 1)
    treaty, row = next(
        (candidate, override_row)
        for candidate in convenio.treaties.values()
        for override_row in candidate.overrides
        if override_row.valid_to is None or override_row.valid_to >= floor
    )
    override = resolve_convenio_override(
        country_code=treaty.country_code,
        tipo_renta=row.tipo_renta,
        devengo_date=max(row.valid_from, floor),
        operation=operation,
    )

    assert override is not None
    assert isinstance(override.kind, ConvenioOverrideKind)
    assert override.kind.value == str(override.kind)


@pytest.mark.parametrize("token_type", (TipoRentaIrnr, M210PayerMode, ConvenioOverrideKind))
def test_registry_owned_token_types_reject_direct_construction(token_type: type[str]) -> None:
    with pytest.raises(TypeError, match="projected from"):
        token_type("consumer-authored-token")
