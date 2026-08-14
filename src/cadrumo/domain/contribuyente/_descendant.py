"""Canonical descendant model assembled from factual legal responsibilities."""

from ._descendant_guarderia import DescendantGuarderiaMixin
from ._descendant_madrid import DescendantMadridMixin


class DescendantInfo(
    DescendantGuarderiaMixin,
    DescendantMadridMixin,
):
    """Structured per-descendant facts with statutory behavior surfaces."""
