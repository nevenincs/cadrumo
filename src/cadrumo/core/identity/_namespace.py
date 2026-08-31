"""Canonical AEAT document-identifier aliases and their validated shapes."""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import BeforeValidator, StringConstraints

from ..aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH, normalise_aeat_csv

__all__ = [
    "AEAT_EXPEDIENTE_ID_MAX_LENGTH",
    "AEAT_EXPEDIENTE_ID_MIN_LENGTH",
    "AEAT_EXPEDIENTE_ID_PATTERN",
    "AeatBoxNumber",
    "AeatCertificadoId",
    "AeatClaveLiquidacion",
    "AeatCsv",
    "AeatExpedienteId",
    "AeatPresentationId",
    "RegistrySnapshotId",
]


AeatCsv = Annotated[
    str,
    BeforeValidator(normalise_aeat_csv),
    StringConstraints(
        min_length=AEAT_CSV_MIN_LENGTH,
        max_length=AEAT_CSV_MAX_LENGTH,
        pattern=rf"^[A-Z0-9]{{{AEAT_CSV_MIN_LENGTH},{AEAT_CSV_MAX_LENGTH}}}$",
    ),
]
"""AEAT's Codigo Seguro de Verificacion, at the documented contract's bound.

Eight to thirty-two uppercase alphanumerics, the shape :mod:`core.aeat_csv`
states and every real captured CSV satisfies. A receipt-domain alias once
carried a wider four-to-sixty-four bound with no pattern at all, and the two
coexisted as one concept at two strengths. That alias is retired rather than
kept as a second opinion.

The alias NORMALISES through the shared comparison form BEFORE its own
constraints run, which is the same shape :data:`~core.identity.TaxIdIdentityToken`
already uses in this package. Ordering matters: a trailing uppercase transform
runs AFTER the pattern check, so it would still refuse the lowercase value it
was added to accept. Normalising first means the constraints only ever see the
canonical form.

Uppercasing rather than refusing a lowercase value is a
correction rather than a convenience. Case-insensitive matching of one CSV
against another is a deliberate, named, tested capability of the calendar
evidence surface -- two case-equivalent values are the same identifier and are
expected to conflict as one. A pattern-only alias would have refused the
lowercase side at the model boundary and deleted that capability, which is why
normalising belongs here rather than at each comparison site: the boundary is
the one place every value passes through.

The bound is the one place in this alias set where the TIGHTER type won, so the
reasoning is recorded rather than assumed: every AEAT-issued CSV observed in
this repository sits at sixteen characters, mid-window, with margin on both
sides, while the retired bound admitted values no receipt could carry. The
evidence is three real captures rather than a specification, which is thin --
what makes the tighter bound safe is the margin and the asymmetry of the two
failure directions, not the size of the sample.
"""

AEAT_EXPEDIENTE_ID_MIN_LENGTH: Final[int] = 12
AEAT_EXPEDIENTE_ID_MAX_LENGTH: Final[int] = 32

AEAT_EXPEDIENTE_ID_PATTERN: Final[str] = r"^[0-9]{4,}[A-Z0-9]+$"
"""Shape of an AEAT expediente id: a leading year run, then uppercase alphanumerics.

An expediente id reads ``<year><sequence><checksum-letter>``, e.g.
``"202310013522456T"``. The pattern deliberately allows more than four leading
digits, because the sequence that follows the year is itself numeric and the
boundary between them is not marked.
"""

AeatExpedienteId = Annotated[
    str,
    StringConstraints(
        min_length=AEAT_EXPEDIENTE_ID_MIN_LENGTH,
        max_length=AEAT_EXPEDIENTE_ID_MAX_LENGTH,
        pattern=AEAT_EXPEDIENTE_ID_PATTERN,
    ),
]
"""An AEAT expediente id, at the shape the live sede capture evidences.

The bound is an OBSERVED range, not a published specification: captures fall
between 14 and 20 characters and the declared 12-32 window is deliberately
wider than that on both sides. AEAT controls this shape and has never
documented it, so the permissive margin is the point -- a narrower bound would
refuse a real expediente this app has not yet seen, and the artefact it
refused would be filing evidence.

Do not tighten this alias toward the observed range. Widen it, with a captured
counterexample recorded, if AEAT is seen to issue a shape it refuses.
"""

AeatClaveLiquidacion = Annotated[str, StringConstraints(min_length=1, max_length=64)]
"""AEAT's identifier for the liquidación a debt row settles.

Carried unchanged at the bound the debt boundary already evidences. No shape
pattern is asserted: unlike an expediente id, no clave de liquidación grammar
has been observed across enough captures to constrain beyond a length, and
asserting one on a single sighting would be invention rather than evidence.
"""

RegistrySnapshotId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
"""The colon-joined four-coordinate identity of one validated registry snapshot.

A registry snapshot is addressed by ``modelo:revision_id:filing_year:period``
(see :func:`~domain.calculations.registry.registry_snapshot_id`), because AEAT
binds each ``(modelo, filing_year, period)`` triple to exactly one revision by
published orden -- dropping any coordinate produces an id two genuinely
different snapshots can share.

Explicitly NOT :data:`~core.identity.SnapshotId`: that alias is a SHA-256
content-address of a payload, while this one is DERIVED from four coordinates
and carries no digest. Two snapshots with identical content but different
coordinates get different ids here and would collide under the content-address
scheme, so they require distinct aliases.

No colon-structure pattern is asserted, matching :data:`AeatClaveLiquidacion`'s
reasoning: the ``revision_id`` segment is a human-authored registry slug of
variable shape (see :data:`~domain.calculations.registry.RevisionId`), so a
regex built from today's observed values would be invention, not evidence. The
bound is carried unchanged from the one production field this alias replaces
(``adapters.outbound.aeat.sede.schema``).
"""

AeatCertificadoId = Annotated[str, StringConstraints(min_length=10, max_length=16, pattern=r"^\d{10,16}$")]
"""AEAT's *Nº de certificado*, at the bound the live notifications parser already enforces.

Every real capture observed is 13 digits (``2699101808461`` / ``2596230606502``); the
parser's own gate (``adapters.outbound.aeat.sede.notifications._CERT_RE``) admits
10 to 16 digits, a deliberate margin around the observation rather than the observation
itself, matching :data:`AeatExpedienteId`'s precedent of widening past a thin sample
rather than pinning to it exactly.

Digits-only, unlike the class docstring's looser "13-digit (or longer)" phrasing this
alias replaces: the parser never constructs the field from anything the regex has not
already matched, so digits-only is the ACTUAL bound already enforced, not an invention.
Do not tighten this alias toward the 13-digit observation, and do not widen it past what
the parser gate admits without moving the gate itself in the same change -- the two must
travel together, or the alias tightens ahead of the parser and refuses a value the parser
already accepted.
"""

AeatBoxNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16, pattern=r"^\d+$"),
]
"""The box or form number AEAT prints or displays for one casilla position.

Digits-only, variable width and padding (``"1"``, ``"01"``, ``"0611"``, ``"611"`` all
appear across the tree with no consistent zero-padding convention observed), at the
1-16 bound already established independently at the two sites that already carried a
``Field`` bound before this alias existed
(``domain.calculations.registry._schema_surfaces.CasillaDefinition.form_number`` and
``domain.calculations.registry._renta_web_open_oracle``'s ``display_number``). Every
other value found in the tree -- production code, TOML registry data, and test
fixtures -- fits inside that same window.

Strips surrounding whitespace before the pattern check, preserving a
behaviour ``domain.calculations.registry._renta_web_open_oracle
.RentaWebOpenDisplayOverride`` already asserts with its own
``@field_validator``: that validator runs AFTER this alias's own
constraints, so a value the pattern would otherwise refuse for untrimmed
whitespace must already be clean by the time this alias sees it.

Distinct from :class:`~domain.calculations.registry.CasillaId`: this value is AEAT's
OWN printed or on-screen numbering, carried by the registry as authored metadata about
an official form's layout, never invented by this app the way a `CasillaId` slug is.
Conflating the two loses that provenance distinction -- a box number can repeat across
modelos and revisions where a `CasillaId` slug never does.
"""

AeatPresentationId = Annotated[str, StringConstraints(max_length=64)]
"""AEAT's *número de justificante*, printed on a receipt body.

Held at the receipt boundary's existing bound. This is NOT an expediente id
and the two are not derivable from one another: a presentation id appears only
on the receipt, an expediente id only in the register listing. Every
comparison this app performs between a receipt and a filing target runs on
the CSV value, because a caller holding a register value cannot supply a
presentation id.

No lower bound is asserted, because the receipt sources that omit the label
carry no value at all rather than an empty one -- absence is modelled by the
field being optional, not by a zero-length string.

That leaves the same gap :data:`AeatClaveLiquidacion` has, and it is named
here for the same reason: an empty string PASSES this alias. It is stated
rather than closed because adding a minimum would refuse a value the receipt
boundary accepts at ``HEAD`` today, and this alias exists to carry that
boundary's bound unchanged, not to tighten it in passing. A surface that
needs ``""`` refused declares its own guard, exactly as ``Deuda`` does for
the clave.
"""
