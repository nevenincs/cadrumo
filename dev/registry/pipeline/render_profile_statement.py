"""Find a render profile's quoted design statement in the design's own text."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cadrumo.core.text_fold import normalise_corpus_text
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ..compiler.validate_evidence import EvidenceValidator
from .render_profile_model import RenderProfile

__all__ = ["verify_alphanumeric_text_statement"]


def verify_alphanumeric_text_statement(
    profile: RenderProfile,
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> None:
    """Find the profile's alphanumeric text statement in the text of the design it names.

    The design is read through the canonical citation reader: a workbook or PDF
    from its own bytes, a manual PDF from its content-keyed shipped text. Both
    sides are folded the same way (accents, case, whitespace), so a line break
    or a typographic accent in the design does not hide its words, and words
    the design does not contain refuse.
    """
    rule = profile.alphanumeric_text_rule
    if rule is None:
        return
    source_ref = profile.design_identity.source_ref
    source = sources.get(source_ref)
    if source is None:
        raise RegistryValidationError(
            f"alphanumeric text rule cites design {source_ref!r}, which the target revision does not catalogue",
        )
    text = EvidenceValidator(legal_refs={}, source_refs=sources, source_root=source_root).source_text(source)
    if text is None:
        raise RegistryValidationError(f"alphanumeric text rule design {source_ref!r} cannot be read")
    if normalise_corpus_text(rule.official_statement) not in text:
        raise RegistryValidationError(
            f"alphanumeric text rule quotes a statement design {source_ref!r} does not contain: "
            f"{rule.official_statement!r}",
        )
