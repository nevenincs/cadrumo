"""Bounded operator commentary carried through the review-package exchange.

The review package travels: an author builds it with notes, a counter-signer
returns a receipt with a note, and a reviewer sends feedback with a note. Every
one of those bounds was written out twice -- once on the model that persists the
value and once on the CLI payload that projects it -- which is the shape that
drifts in silence. The payload can tighten below the model and refuse text the
model would have kept, or loosen above it and accept text that fails on the way
to disk, and neither side learns anything from the other.

Two aliases rather than three. The author's notes and the counter-signer's note
carry the SAME bound because they are the same kind of writing at the same point
in the exchange: a short remark travelling beside a signature. Declaring them
separately would put the number in two places again under different names, which
is the original problem wearing a disguise.

:obj:`ReviewFeedbackNote` is genuinely larger and stays its own alias. Feedback
is the one leg of the exchange where the writer is reviewing the return rather
than annotating their own work, so it is prose an operator actually composes.
Deliberately separate from
:obj:`~cadrumo.application.evidence.bundle_text.EvidenceBundleNotes`, which
happens to share the 2000 bound but annotates an evidence bundle and has no
reason to move when the review exchange changes.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

ReviewPackageNote = Annotated[str, StringConstraints(max_length=2000)]
"""A remark travelling beside a review package or its counter-signature.

Empty is a legitimate value: a package with nothing to say about itself is
normal, and refusing it would force operators to type filler.
"""

ReviewFeedbackNote = Annotated[str, StringConstraints(max_length=4000)]
"""A reviewer's written feedback on a calculation revision.

Longer than :obj:`ReviewPackageNote` because this is the leg of the exchange
where the writer is reviewing someone else's return rather than annotating
their own, so the note carries reasoning rather than a label.
"""

__all__ = ["ReviewFeedbackNote", "ReviewPackageNote"]
