"""Stable parsing and layout names shared by form-layout generation stages."""

from __future__ import annotations

import re
from typing import Final

_NUMBERED_PAGE: Final[str] = "numbered-boxes"
_INPUTS_PAGE: Final[str] = "other-inputs"
_GENERAL_SECTION: Final[str] = "general"
_RECORD_MATCH_FLOOR: Final[float] = 0.6
_LABEL_MATCH_FLOOR: Final[float] = 0.5
_LABEL_MATCH_MARGIN: Final[float] = 0.2
_DICTIONARY_LINE: Final = re.compile(
    r"^(?P<field>[^=]+)=\[(?P<path>[^\]]*)\]\[[^\]]*\]\[(?P<box>[^\]]*)\]\[(?P<text>.*)\]\s*$"
)
_DIGITS: Final = re.compile(r"^\d{1,16}$")
_BOX: Final = re.compile(r"\[\s*\d{1,5}\s*\]")
