"""Whether a citation's quotation was read against the corpus, refused, or unreachable.

A citation carries a document pointer, a locator and — when it can — the verbatim
text that makes the pointer checkable. This enum is the record of which of those
the citation actually has, and it lives in ``core`` because two registry corpora
now depend on the same distinction: the IVA catalogue, where it was first drawn,
and the spending-category profiles.

The distinction is the point. An unverified citation, one examined and found
unsupportable, and one whose source is not bundled at all look identical when all
three simply lack text. Both corpora spent their whole lives in that undifferentiated
state: every quotation was a translation key resolving to the literal word "Quote"
or "Quoted text", so nothing could tell a grounded citation from an ungrounded one.

The states are deliberately not ranked. :attr:`VERIFIED` is the only one that
asserts evidence; the other two are different REASONS for its absence, and
collapsing them would restore exactly the ambiguity this enum exists to remove.
"""

from __future__ import annotations

from enum import StrEnum


class CitationGrounding(StrEnum):
    """What a citation's record actually holds in place of its quotation."""

    VERIFIED = "verified"
    """The quotation was read from the bundled corpus and supports the claim.

    A citation in this state MUST carry its verbatim text, and the text MUST
    occur in the normalised corpus of its own legal reference. This is the only
    state that asserts checkable evidence.
    """

    UNRESOLVED = "unresolved"
    """Examined and refused: the cited provision does not support the claim.

    Not "not yet checked". A citation carrying this has been read against the
    corpus and the reason it failed is recorded beside it.
    """

    SOURCE_NOT_BUNDLED = "source_not_bundled"
    """The cited source is authoritative but is not in the bundled corpus.

    Distinct from :attr:`UNRESOLVED` in the direction of the failure, which is
    why it is a third state rather than a reuse of the second. An unresolved
    citation was checked and found wanting; this one COULD NOT be checked,
    because the document it names — an AEAT *Manual práctico* edition, a portal
    help page — is not among the consolidated BOE texts shipped with the
    application, so no verbatim excerpt can be transcribed from anything the
    repository holds.

    Labelling such a citation ``UNRESOLVED`` would assert that its provision was
    read and rejected, which is a claim about the law nobody made. Labelling it
    ``VERIFIED`` with invented text would be worse: it would manufacture the
    evidence the state exists to say is missing. The honest record is that the
    pointer stands and the excerpt is unreachable from here.
    """


__all__ = ["CitationGrounding"]
