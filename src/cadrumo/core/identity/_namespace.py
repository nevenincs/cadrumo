"""Closed taxonomy of the document-identifier namespaces this app handles.

An identifier is not interchangeable with another identifier merely because
both are strings of similar length. AEAT issues several distinct identifier
concepts against one filing -- a Código Seguro de Verificación, a *número de
justificante*, an expediente id, a clave de liquidación -- and this app mints
several of its own. Before this module existed, every one of them was a bare
``str`` field carrying a locally re-declared bound, so a value from one
namespace could be passed wherever another was expected and no layer objected.

:class:`IdentifierNamespace` names each concept once. Each member's constraint
shape is carried by a matching pydantic alias, so the namespace distinction is
enforced at the model boundary rather than by field-naming discipline.

The enum is split into two groups that must never be merged into one member:

* ``AEAT_*`` -- issued by AEAT. External, never minted here, never
  clock-derived, and shape-bounded by *observed AEAT behaviour* rather than by
  a specification this app controls. Tightening one of these beyond what has
  been observed risks refusing a real AEAT-issued document, which is a worse
  failure than a diagnosed conflation.
* ``APP_*`` -- minted by this application, content-addressed or otherwise
  derived, and clock-free per the standing identity rule.

Keeping the groups distinct is what stops a future author typing an
app-derived identity as AEAT-issued, or the reverse.

Enrollment is staged, so this taxonomy is deliberately incomplete until every
namespace's alias lands: each member below records where its alias lives
today, and a member whose alias is not yet declared says so plainly rather
than implying the surface is closed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

from pydantic import BeforeValidator, StringConstraints

from .._aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH, normalise_aeat_csv

__all__ = [
    "AEAT_EXPEDIENTE_ID_MAX_LENGTH",
    "AEAT_EXPEDIENTE_ID_MIN_LENGTH",
    "AEAT_EXPEDIENTE_ID_PATTERN",
    "AeatClaveLiquidacion",
    "AeatCsv",
    "AeatExpedienteId",
    "AeatPresentationId",
    "IdentifierNamespace",
]


class IdentifierNamespace(StrEnum):
    """Every document-identifier namespace this codebase distinguishes.

    Membership is a claim that the concept is a distinct *identity namespace*:
    two values from different members may share a shape and still name
    unrelated things. Values that merely look identifier-shaped are not
    members -- see the exclusions recorded below the enum.

    Attributes:
        AEAT_CSV: Código Seguro de Verificación. AEAT's per-document verifier
            hash, printed on a justificante and accepted at the public cotejo
            endpoint to re-serve that document. Shape contract lives at
            :mod:`core._aeat_csv`. Alias: :data:`AeatCsv`.
        AEAT_PRESENTATION_ID: *Número de justificante*. AEAT's internal
            presentation identifier, printed on the receipt body. Distinct
            from :attr:`AEAT_EXPEDIENTE_ID`, which never appears on a
            receipt -- conflating the two is the defect this taxonomy exists
            to make unrepresentable. Alias: :data:`AeatPresentationId`.
        AEAT_EXPEDIENTE_ID: The register/procedure-listing identifier, read
            from *Mis Expedientes* and *Consultar declaraciones presentadas*.
            Alias: :data:`AeatExpedienteId`.
        AEAT_CLAVE_LIQUIDACION: AEAT's identifier for a liquidación, carried
            on a debt row. A fourth AEAT namespace, unrelated to the three
            above. Alias: :data:`AeatClaveLiquidacion`.
        APP_SNAPSHOT_ID: Content-addressed snapshot identity. Alias:
            :data:`~core.identity.SnapshotId`.
        APP_TRANSACTION_ID: Content-addressed ledger-transaction identity.
            Alias: :data:`~core.identity.TransactionId`.
        APP_INVOICE_ID: Content-addressed invoice identity. Its alias is
            declared in the invoice domain and has not yet been relocated
            into this package.
        APP_WORK_UNIT_ID: Content-addressed modelo work-unit identity. Its
            alias is declared in the modelo domain and has not yet been
            relocated into this package.
        APP_CALCULATION_REVISION_ID: Content-addressed calculation-revision
            identity. Alias not yet relocated into this package. Distinct
            from the registry's own human-authored revision version tag,
            which is a different namespace with its own home in the registry
            schema package.
        APP_FILING_RECORD_ID: Content-addressed filing-record identity.
            Alias not yet relocated into this package.
        APP_VERIFICATION_REPORT_ID: Content-addressed verification-report
            identity. Alias not yet relocated into this package.
    """

    AEAT_CSV = "aeat_csv"
    AEAT_PRESENTATION_ID = "aeat_presentation_id"
    AEAT_EXPEDIENTE_ID = "aeat_expediente_id"
    AEAT_CLAVE_LIQUIDACION = "aeat_clave_liquidacion"
    APP_SNAPSHOT_ID = "app_snapshot_id"
    APP_TRANSACTION_ID = "app_transaction_id"
    APP_INVOICE_ID = "app_invoice_id"
    APP_WORK_UNIT_ID = "app_work_unit_id"
    APP_CALCULATION_REVISION_ID = "app_calculation_revision_id"
    APP_FILING_RECORD_ID = "app_filing_record_id"
    APP_VERIFICATION_REPORT_ID = "app_verification_report_id"


# Deliberately NOT members of the taxonomy above, recorded here so a later
# sweep does not enroll them by name-shape and call the surface closed:
#
#   * AEAT-printed adjudicated-case prose the app neither controls nor can
#     enumerate -- a declaration's ``estado``, a debt's ``situacion``. These
#     are bounded free text. Typing them as a closed set would assert a
#     vocabulary AEAT has never published.
#   * Counterparty-issued document numbers -- an ``invoice_number`` is minted
#     by a third party, not by AEAT and not by this app.
#   * Identifiers from non-AEAT issuing authorities -- Google file, folder and
#     spreadsheet ids; an X.509 certificate serial; an SPDX id. Each belongs
#     to some other authority's namespace, and none belongs in the ``AEAT_*``
#     group. Whether any warrants typing at all is a separate question this
#     taxonomy does not answer.


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

Eight to thirty-two uppercase alphanumerics, the shape :mod:`core._aeat_csv`
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

The bound is the one place in this taxonomy where the TIGHTER type won, so the
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

AeatPresentationId = Annotated[str, StringConstraints(max_length=64)]
"""AEAT's *número de justificante*, printed on a receipt body.

Held at the receipt boundary's existing bound. This is NOT an expediente id
and the two are not derivable from one another: a presentation id appears only
on the receipt, an expediente id only in the register listing. Every
comparison this app performs between a receipt and a filing target runs on
:attr:`IdentifierNamespace.AEAT_CSV`, never on this namespace, precisely
because a caller holding a register value cannot supply one of these.

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
