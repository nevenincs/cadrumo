"""Error hierarchy for the AEAT notificación document parsers.

An inbound parse-error boundary. The parser refuses rather than degrades: a
document whose labels it cannot bind raises :class:`SancionParseError` naming
every field it could not resolve, so an incomplete read can never present as a
complete one. Callers inspect the structured attributes rather than the
rendered message.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.errors.hierarchy import CadrumoError


class NotificacionParseError(CadrumoError):
    """Root for every failure raised while parsing an AEAT notification document."""


class SancionParseError(NotificacionParseError):
    """Raised when a sanción / liquidación document cannot be fully parsed.

    The parser has exactly two outcomes: a complete typed record, or this
    error. There is no partial record and no zero-filled record, because a
    figure read off one of these documents is a figure a taxpayer pays or
    appeals against, and a silently-blank field is indistinguishable from a
    genuine zero once it leaves the parser.

    Attributes:
        missing: Field names whose label could not be located in the document
            text at all.
        malformed: Field names whose label was located but whose printed value
            did not match the AEAT money / percentage shape.
        ambiguous: Field names whose label matched more than one distinct
            printed value, so no single reading is defensible.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        missing: tuple[str, ...] = (),
        malformed: tuple[str, ...] = (),
        ambiguous: tuple[str, ...] = (),
    ) -> None:
        """Initialise with the per-field failure inventory.

        Args:
            message: Human-readable description of the failure.
            context: Optional structured context forwarded to the
                :class:`core.errors.CadrumoError` boundary.
            translated_message: Optional locale key rendered at the CLI.
            missing: Field names with no label hit.
            malformed: Field names whose value failed shape validation.
            ambiguous: Field names whose label matched conflicting values.
        """
        super().__init__(message, context=context, translated_message=translated_message)
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous


class SancionArithmeticError(SancionParseError):
    """Raised when the printed lines of a parsed sanción do not reconcile.

    This is a check on the PARSE, not on AEAT's arithmetic. Every figure here
    is printed on the same document, so ``sanción resultante`` minus the
    printed reducciones must equal the printed ``diferencia`` to the cent. A
    divergence means a label was bound to the wrong number — the failure mode
    that would otherwise hand an operator a confidently wrong figure — so it
    refuses instead of returning the record.
    """


__all__ = [
    "NotificacionParseError",
    "SancionArithmeticError",
    "SancionParseError",
]
