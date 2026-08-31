"""One header fact AEAT states in a filed fichero, carried with its provenance.

AEAT's diseño de registro models some filing elections as HEADER fields rather
than as casillas: the tipo de declaración (the result disposition), the
sin-actividad marker, the REDEME marker, the prorrata elections. The boxes a
taxpayer might expect for these are deliberately ABSENT from the record design,
because AEAT encodes the election in the header instead. A header is therefore
not a casilla, and giving one a synthetic casilla id would put this application
and the official structure in disagreement about the concept's kind.

That distinction is why this is its own type rather than a reused casilla
observation, and why it lives in ``core`` rather than beside either of the two
surfaces that need it: the outbound AEAT adapter produces these facts, the
application persistence payload stores them, and ``application`` may not import
``adapters``. ``core`` is the one layer both may reach without widening a
layered-architecture carve-out.

The value carried here is evidence of an ARTEFACT, not a derived quantity, so it
stays the token AEAT actually wrote. Nothing in this module elects on a header;
carrying the evidence and acting on it are separate decisions, and which
identifier a disposition-aware read should key on is still open.

See :class:`ObservedHeaderFact`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import STRICT_FROZEN_CONFIG

__all__ = [
    "ObservedHeaderFact",
]


class ObservedHeaderFact(BaseModel):
    """One header field AEAT stated in a filed fichero, with where it came from.

    Attributes:
        header_key: The registry export layout's own ``header_key`` for the
            field. Deliberately a constrained string and NOT an enum: the key
            space is registry-driven and open, spanning 69 distinct values
            across the bundled modelos at the time of writing, including
            loader-generated slugs such as
            ``datos_adicionales_entidad-que-aplica-el-r-gimen-de-la-ley``. A
            closed enum here would have to be edited every time a diseño gains
            a header, and the registry TOML is the authority for which headers
            exist. Enumerating it would also invite the false conclusion that
            an absent member means AEAT states no such header.
        value: The token the artefact carried, stripped of padding but otherwise
            unconverted. A one-byte election flag is ``"D"`` or ``"X"``, never a
            parsed enum member, because this record is evidence of what was
            filed rather than an interpretation of it. A header AEAT left blank
            is OMITTED from the observation rather than recorded empty: an empty
            string is indistinguishable from AEAT stating a value, whereas
            absence honestly means the fichero did not say.
        source_artefact_kind: Which artefact family the fact was read from.
            Narrower than the sibling axis on the casilla observation, which
            admits five kinds, because only the submitted fichero carries a
            diseño header today -- a declaración PDF is a rendering and a
            justificante is a receipt, and neither exposes the record design's
            header fields. A single-member literal REFUSES a fact attributed to
            a source that cannot produce one, which is the honest state until a
            second source genuinely does. Unifying this axis and the casilla
            one into a shared enum is the right end state and is deliberately
            not done here: the casilla literal is a persisted shape, so
            widening it is a versioned change rather than a rename.
        source_locator: The export parser's own locator for the field, of the
            form ``{layout_id}:{record_id}:{field_id}:{offset}:{length}``. This
            is what makes the fact auditable: it names the record design
            position the token was read from, so a later reader can go back to
            the bytes rather than trusting the projection. It is also what
            distinguishes a fact read through the official layout from one
            produced any other way.

    Value coverage, stated because the shape being right is not the same as the
    values being exercised: every disposition and marker this type carries is
    proven in SHAPE by exporter-produced ficheros, but no bundled AEAT facsimile
    elected devolución and none filed sin actividad, so those two values are
    UNEXERCISED against real AEAT evidence. Now that a disposition can flow
    through to storage, a reader who does not know this will read the plumbing
    working as the values being confirmed. They are not the same claim, and the
    second one is not yet made.
    """

    model_config = STRICT_FROZEN_CONFIG

    header_key: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=512)
    source_artefact_kind: Literal["submitted_file"]
    source_locator: str = Field(min_length=1, max_length=512)
