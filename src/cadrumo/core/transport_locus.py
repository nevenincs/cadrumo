"""The declared axes that say what a CLI parameter carries and which way it moves.

A command graph can be read for what a verb is CALLED and for what its
parameters are TYPED, and neither answers the question an operator-surface gate
has to ask: does this parameter name a file on the operator's own disk, or a
handle to something on a machine elsewhere?

Typing cannot answer it. A Drive folder id and a filesystem directory are both
``str``; a repository root and a single input file are both :class:`pathlib.Path`.
Inferring the answer from the type produces a gate that misfires in both
directions, and inferring it from the option's spelling produces a gate that
tests the very convention it is supposed to enforce — a name list wearing a
property's clothes.

So the axes are DECLARED. A parameter states its locus, and a gate reads the
declaration rather than guessing. The cost is that an author must fill the field
in; the benefit is that the spelling convention becomes checkable at all.

Three axes are needed, not one, and the third is the one that is easy to miss.
Locus says which side of the wire the value lives on. Shape distinguishes a
single file from a directory from a named root, because those take different
spellings. Role distinguishes the ONE input a verb is fundamentally about from
the further inputs it also happens to read: a verb that takes a statement to
import and, separately, a file to verify that statement against has two local
inputs, and a convention that recognises only one of them forces the second into
a name that describes its type instead of its job.

See Also:
    :class:`~cadrumo.core.transport_locus.TransportRole`
        The axis that permits a verb more than one local input without
        collapsing their names.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["TransportLocus", "TransportRole", "TransportShape"]


class TransportLocus(StrEnum):
    """Which side of the wire a parameter's value lives on.

    Closed by construction. A parameter that carries neither a path nor a
    handle declares :attr:`NONE` rather than being left undeclared, so that
    "not applicable" and "nobody filled this in" stay distinguishable.
    """

    NONE = "none"
    """Carries neither a local path nor a remote handle.

    The correct declaration for a closed-enum discriminator, a year, an
    identifier, or a flag. It is what keeps a value axis that happens to be
    spelled like a transport option — a link-source enum named ``source`` —
    outside the spelling convention entirely.
    """

    LOCAL_IN = "local_in"
    """A path the command READS from the operator's own filesystem."""

    LOCAL_OUT = "local_out"
    """A path the command WRITES to the operator's own filesystem."""

    REMOTE_HANDLE = "remote_handle"
    """An address for something held on a machine elsewhere.

    A Drive folder id, a spreadsheet id, a document link reference. Spelling is
    free for these, because the thing being named is a counterparty's
    identifier and no filesystem convention applies to it.
    """


class TransportShape(StrEnum):
    """What kind of filesystem object a local path names.

    Only meaningful when the locus is local: a remote handle has no filesystem
    shape, and declaring one for it would assert a fact that does not exist.
    """

    NOT_APPLICABLE = "not_applicable"
    """The locus is not local, so no filesystem shape applies."""

    FILE = "file"
    """One file."""

    DIRECTORY = "directory"
    """A directory whose contents the command enumerates."""

    ROOT = "root"
    """A named tree the command resolves other paths against.

    Distinct from :attr:`DIRECTORY`, which is scanned for its members. A root is
    a base for resolution, which is why it takes a name of its own rather than
    the bare directory spelling.
    """


class TransportRole(StrEnum):
    """Whether a local parameter is the verb's subject or one of its supports.

    A verb has at most one primary input and at most one primary output. Every
    further local path is auxiliary and is named for the job it does, because
    an auxiliary's name is the only place that job is written down.
    """

    NOT_APPLICABLE = "not_applicable"
    """The locus is not local, so no role applies."""

    PRIMARY = "primary"
    """The one local path the verb is fundamentally about."""

    AUXILIARY = "auxiliary"
    """A further local path the verb also reads or writes.

    Auxiliary is not a lesser status; it is a different question. A verify
    fixture, a receipt to countersign, a prior observation to compare against
    are all auxiliary, and each is better served by a name stating what it is
    than by a numbered variant of the primary's name.
    """
