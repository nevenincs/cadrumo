"""Typed ``--json`` payload schemas for ``aeat config profile censo``.

The pull reports its reconciliation rather than only its outcome: which
paths it adopted because the profile left them blank, and which paths AEAT
answers differently from the operator's own declared answer. A divergence
row carries both sides, because the operator is the one who adjudicates
between them — the pull never decides.

These strict :class:`OutputSchema` subclasses document only the transport
shape referenced as a deferred public schema target by production-authored CommandSpec and emitted through
:class:`SchemaEnvelope`. The projection and the adopt/defer split live in
:mod:`user_profile`; the commit lives behind the single cotejo apply
authority.
"""

from __future__ import annotations

from pydantic import model_validator

from ....core.json_contract import OutputSchema
from ....domain.user_profile import UserProfileFact


class CensoFactPayload(OutputSchema):
    """One censal fact projected by either file or live-read transport.

    ``source`` keeps each transport's declared provenance token: a G313
    artefact remains non-official while a census read remains AEAT-verified.
    The canonical domain fact contract validates both shapes, so this shared
    wire row refuses malformed paths and undeclared or oversized provenance
    instead of giving each transport a parallel validator.
    """

    path: str
    value: str
    source: str

    @model_validator(mode="after")
    def _validate_canonical_profile_fact(self) -> CensoFactPayload:
        """Keep the presentation row on the domain's profile path/provenance contract."""
        UserProfileFact(path=self.path, value=self.value, source=self.source)
        return self


class CensoFileIngestResult(OutputSchema):
    """Result of ``config profile censo file``: previewed or enrolled facts."""

    applied: bool
    facts: tuple[CensoFactPayload, ...] = ()


class CensoPullDivergencePayload(OutputSchema):
    """One path where AEAT and the operator disagree, reported never resolved.

    ``aeat_value`` is what the consulta answers. ``profile_value`` is the
    operator's position, and it has two shapes because a disagreement
    does: a string is the value they declared, and ``None`` means they
    deliberately CLEARED the path — a deletion is a declaration too, and
    the one form of it that has no value to show. Rendering a cleared
    path as an empty string would make it indistinguishable from a field
    carrying blank text, which is a different claim.

    The pull adopts neither side: an autofill that silently corrected a
    declared answer, or silently undid a deletion, is the failure this
    surface exists to prevent.
    """

    path: str
    profile_value: str | None
    aeat_value: str


class CensoPullResult(OutputSchema):
    """Result of ``config profile censo pull``: previewed or enrolled facts.

    ``applied`` is ``False`` for the default preview posture. The read has
    three outcomes and all three are reported: ``adopted`` are the paths
    the read writes — never set, or last written by a previous censal read
    and since changed at AEAT — ``unchanged`` are the paths already
    carrying exactly what AEAT reports, and ``divergences`` are the
    disagreements reported instead of overwritten. Reporting only the
    first and last would hide which paths the authority confirmed, leaving
    an operator unable to tell a corroborated field from one the read
    never covered.
    """

    applied: bool
    source_url: str
    adopted: tuple[CensoFactPayload, ...] = ()
    unchanged: tuple[CensoFactPayload, ...] = ()
    divergences: tuple[CensoPullDivergencePayload, ...] = ()


__all__ = [
    "CensoFactPayload",
    "CensoFileIngestResult",
    "CensoPullDivergencePayload",
    "CensoPullResult",
]
