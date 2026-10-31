"""Name the Modelo boxes of a filing handoff in the filer's words, from the pinned registry layout."""

from __future__ import annotations

from collections.abc import Callable

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.renta.actividad_asset.lifecycle import AssetKind
from ..modelo.work_form_localization import localized_text, unnamed_casilla_label
from .activity_asset_read_models import activity_asset_label_key
from .fact_wording import token_family

BoxNameReader = Callable[[str, int, str, CasillaId, OutputLanguage], str]
"""Read a box's name from ``(modelo, filing year, period token, casilla, language)``."""


def pinned_box_name(operation: PinnedAuthorityOperation) -> BoxNameReader:
    """Read the name a pinned revision's layout gives a casilla, in the language asked and Spanish otherwise."""

    def read(modelo: str, filing_year: int, period: str, casilla_id: CasillaId, language: OutputLanguage) -> str:
        revision = operation.revision_for_context(modelo, filing_year=filing_year, period=period)
        casilla = next((item for item in revision.casillas if item.id == casilla_id), None)
        named = None if casilla is None else localized_text(casilla.localization_keys, language)
        return (named or unnamed_casilla_label(language)).text

    return read


def box_name_for_kind(box_name: str, asset_kind: AssetKind, language: OutputLanguage) -> str:
    """Tell apart the rows of one box that each state one asset kind, by that kind's catalogue word."""
    kind = tr(activity_asset_label_key(token_family(AssetKind), asset_kind), locale=language.value)
    return f"{box_name} - {kind}"
