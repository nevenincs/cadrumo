"""The Spanish postcode shape, declared once.

A postcode is five digits whose first two are a province code from 01 to 52.
It is a STRING throughout and must never be int-coerced: leading zeros are
significant, and ``01001`` is Vitoria-Gasteiz while ``1001`` is nothing.

The rule was enforced in exactly one place -- the setup wizard, and only for
questions whose id said "postcode". The profile field the wizard writes into
carried no constraint at all, so any other route to it (a bulk import, a direct
profile mutation, a future API) could persist a malformed value with no
refusal. A rule that lives at one entrance is not a rule about the data.

It was also, at the same time, enforced DIFFERENTLY elsewhere: the registry
scalar boundary took any five digits. Both halves of that sentence were true at
once, which is the reason this module states the province alternation as its own
named fragment rather than inlining it -- a caller that needs a province code, a
postcode or an INE municipality code now reads the same characters.

Two framings over one pattern, because the field genuinely has two states: a
postcode that has been declared, and a profile where the operator has not
supplied one yet.
"""

from __future__ import annotations

import re
from typing import Annotated, Final

from pydantic import StringConstraints

SPANISH_PROVINCE_CODE_PATTERN: Final[str] = r"(0[1-9]|[1-4][0-9]|5[0-2])"
"""A province code in 01..52, unanchored.

Its own name because it is not only the head of a postcode. A province code
stands alone on a censo declaration, and it prefixes an INE municipality code
as well, so three shapes read this one alternation. They were each carrying
their own copy of it, and the copies had already come apart: the postcode
validator at the registry boundary accepted any five digits, so ``99999``
passed as a Spanish postcode with a province that does not exist.
"""

SPANISH_POSTCODE_PATTERN: Final[str] = SPANISH_PROVINCE_CODE_PATTERN + r"[0-9]{3}"
"""Five digits whose leading pair is a province code in 01..52, unanchored."""

OptionalSpanishPostcode = Annotated[str, StringConstraints(pattern=rf"^$|^{SPANISH_POSTCODE_PATTERN}$")]
"""A postcode field an operator may legitimately have left undeclared."""

_COMPILED: Final[re.Pattern[str]] = re.compile(rf"^{SPANISH_POSTCODE_PATTERN}$")


def is_spanish_postcode(value: str) -> bool:
    """Whether ``value`` is a well-formed Spanish postcode.

    For a caller that needs a boolean rather than a refusal -- an input widget
    deciding whether to re-prompt, say -- so the shape is asked of the same
    pattern the models validate against.
    """
    return _COMPILED.match(value) is not None


__all__ = [
    "SPANISH_POSTCODE_PATTERN",
    "SPANISH_PROVINCE_CODE_PATTERN",
    "OptionalSpanishPostcode",
    "is_spanish_postcode",
]
