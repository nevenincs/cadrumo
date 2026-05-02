"""Manual-backed loader for category profiles.

Bridges the curated in-code registry
:data:`~aeat.domain.categories.CATEGORY_PROFILES_2025` and the
structured manual corpus exposed by :mod:`aeat.domain.manuals`. The
public entry point :func:`load_category_profiles_from_manual`
returns a manual-backed mapping when the structured manual is
available, and otherwise falls back to the curated registry so
downstream code sees a stable surface.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.logging import get_logger
from ..manuals import ManualId, ManualPart, load_manual
from ..manuals.errors import ManualNotFoundError, ManualParseError
from ._profile import CategoryProfile
from ._registry import CATEGORY_PROFILES_2025
from ._spending_category import SpendingCategory

_log = get_logger(__name__)


def load_category_profiles_from_manual(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    """Load category profiles from the structured manual corpus when available.

    Args:
        year: AEAT handbook year.

    Returns:
        The manual-backed profile mapping when available, otherwise the curated
        hardcoded registry.

    Raises:
        ValueError: If ``year`` is not supported by this branch.
    """

    if year != 2025:
        raise ValueError(f"unsupported category profile corpus year: {year}")

    try:
        load_manual(ManualId.RENTA, 2025, ManualPart.PARTE_1)
    except (ManualNotFoundError, ManualParseError) as exc:
        _log.info("falling back to hardcoded category registry: %s", exc)
        return CATEGORY_PROFILES_2025

    _log.info("structured manual available, returning curated 2025 registry until extractor lands")
    return CATEGORY_PROFILES_2025
