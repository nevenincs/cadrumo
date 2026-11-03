"""Exercise the named precedence API beside the exclusive source merge."""

from collections.abc import Sequence

from ....domain.modelos.source_disagreement import SourceDisagreementRole
from ..source_mesh import CalculationSourceResolution
from ..source_resolution_operations import PrecedenceTier, merge_source_resolutions_by_precedence


def merge_two_source_tiers(sources: Sequence[CalculationSourceResolution]) -> CalculationSourceResolution:
    """Give a pair of test sources explicit lower/backend and higher/caller roles."""
    lower, higher = sources
    return merge_source_resolutions_by_precedence(
        (
            PrecedenceTier(SourceDisagreementRole.BACKEND, lower, str(lower.resolver_id)),
            PrecedenceTier(SourceDisagreementRole.CALLER, higher, str(higher.resolver_id)),
        )
    ).resolution
