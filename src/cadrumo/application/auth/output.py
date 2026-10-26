"""Application-owned authentication output contracts.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

from pydantic import Field

from ...core.json_contract import OutputSchema
from .catalogue import AuthProviderId


class AuthProviderRow(OutputSchema):
    """One provider row as the operator reads it.

    The catalogue's :class:`~application.auth.catalogue.AuthProviderListing`
    carries ``label`` and ``description`` as
    :class:`~core.i18n.translatable.Translatable` keys, which are identities
    rather than text. Emitting that record straight into the envelope put the
    raw dotted paths in front of the operator (``auth.catalogue.certificate_label``)
    while the text lines beside it were rendered. This row is the rendered
    projection, so JSON and text carry the same words.
    """

    id: AuthProviderId
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AuthProvidersResult(OutputSchema):
    """The typed result of listing the configured authentication providers."""

    providers: list[AuthProviderRow]


__all__ = ["AuthProviderRow", "AuthProvidersResult"]
