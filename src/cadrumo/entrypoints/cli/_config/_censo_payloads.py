"""Typed ``--json`` payload schemas for ``aeat config profile censo pull``.

The pull reports its reconciliation rather than only its outcome: which
paths it adopted because the profile left them blank, and which paths AEAT
answers differently from the operator's own declared answer. A divergence
row carries both sides, because the operator is the one who adjudicates
between them — the pull never decides.

These strict :class:`OutputSchema` subclasses document only the transport
shape registered with :func:`register_schema` and emitted through
:class:`SchemaEnvelope`. The projection and the adopt/defer split live in
:mod:`user_profile`; the commit lives behind the single cotejo apply
authority.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


class CensoPullFactPayload(OutputSchema):
    """One censal fact adopted from the AEAT consulta read.

    ``source`` carries the AEAT-verified censal-read provenance token —
    unlike the operator-supplied artefact door, this read is the authority
    itself.
    """

    path: str
    value: str
    source: str


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


@register_schema("config.profile.censo.pull")
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
    adopted: tuple[CensoPullFactPayload, ...] = ()
    unchanged: tuple[CensoPullFactPayload, ...] = ()
    divergences: tuple[CensoPullDivergencePayload, ...] = ()


__all__ = [
    "CensoPullDivergencePayload",
    "CensoPullFactPayload",
    "CensoPullResult",
]
