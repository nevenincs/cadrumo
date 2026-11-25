"""Public projection of the words that explain an invoice-reading finding.

A finding stores a closed wording code and the values it quotes; the backend
renders that pair into a sentence in the operator's language. A projection that
serves the sentence also carries the stored pair and the language, all three or
none, so a frontend never shows a sentence it cannot attribute.
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, Field

from ...core.draft_discrepancy import DraftFindingWording
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..ledger.invoice_draft_records import FindingWords

_ParamName = Annotated[str, Field(min_length=1, max_length=128)]
_ParamValue = Annotated[str, Field(max_length=2_048)]


class FindingWordsProjectionV1(BaseModel):
    """Which sentence explains a finding and the values it quotes, as the finding stores them."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    wording: DraftFindingWording
    params: Annotated[tuple[tuple[_ParamName, _ParamValue], ...], Field(max_length=16)] = ()

    @classmethod
    def from_words(cls, value: FindingWords | None) -> Self | None:
        """Copy a finding's words, or nothing for a finding stored without them."""
        return None if value is None else cls(wording=value.wording, params=value.params)


def require_served_words(
    stored: FindingWordsProjectionV1 | None,
    words: str | None,
    language: OutputLanguage | None,
) -> None:
    """Refuse a served sentence that does not name the wording it renders and its language."""
    if len({stored is None, words is None, language is None}) != 1:
        raise ValueError("a served sentence names the wording it renders and the language it is in")
