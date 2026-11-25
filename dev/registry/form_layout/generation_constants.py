"""Stable parsing and layout names shared by form-layout generation stages."""

from __future__ import annotations

import re
from typing import Final

NUMBERED_PAGE: Final[str] = "numbered-boxes"
INPUTS_PAGE: Final[str] = "other-inputs"
GENERAL_SECTION: Final[str] = "general"
RECORD_MATCH_FLOOR: Final[float] = 0.6
LABEL_MATCH_FLOOR: Final[float] = 0.5
LABEL_MATCH_MARGIN: Final[float] = 0.2
DICTIONARY_LINE: Final = re.compile(
    r"^(?P<field>[^=]+)=\[(?P<path>[^\]]*)\]\[[^\]]*\]\[(?P<box>[^\]]*)\]\[(?P<text>.*)\]\s*$"
)
DIGITS: Final = re.compile(r"^\d{1,16}$")
BOX: Final = re.compile(r"\[\s*\d{1,5}\s*\]")
