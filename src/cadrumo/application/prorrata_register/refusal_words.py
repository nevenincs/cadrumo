"""The sentence the prorrata register operations serve for each of their refusals.

A frontend shows these sentences as served, so they sit under keys of their own
rather than reusing the command line's messages, which name command options. A
sentence is worded from its key alone: it carries no percentage, reference or
sector name.
"""

from __future__ import annotations

from typing import Final, cast, get_args

from ...core.external_constants import OutputLanguage
from ..operations.error_detail import operation_catalogue_refusal_words
from .projection_contracts import ProrrataRefusalCode, ProrrataRefusalReason

_SERVED_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    reason: f"application.prorrata_register.served.{reason}"
    for reason in cast(tuple[str, ...], get_args(ProrrataRefusalReason.__value__))
}


def served_refusal_words(
    reason: ProrrataRefusalReason, *, error_code: ProrrataRefusalCode
) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    return operation_catalogue_refusal_words(error_code, _SERVED_REFUSAL_LOCALE_KEYS[reason])


__all__ = ["served_refusal_words"]
