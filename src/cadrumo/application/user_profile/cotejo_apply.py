"""Cotejo censal apply: adopt artefact values, record deferred divergences.

The setup flow's phase-8 compare-select reconciliation of a Certificado de
Situación Censal (procedure G313) against the profile answers commits
through the one sanctioned write path here. Adopted certificate values
persist as ordinary effective-dated
:class:`~cadrumo.domain.user_profile.values.UserProfileFact` rows stamped with the
non-official artefact provenance token; deferred axes persist as
``censo.divergencia.{n}.*`` divergence rows recording the unadopted
certificate evidence. Exactly one ``CENSO_APPLIED`` bucket event marks the
apply-commit (never one per fact). Re-running the cotejo replaces the whole
divergence namespace: stale rows the fresh set does not re-declare are
cleared (``value=None``) in the same atomic commit, mirroring the
descendant count-shrink clearing pattern.

A later profile read surfaces one warning :class:`Notice` while any
divergence row is open, so a deferred divergence is never silently
resolved; the notice rides the envelope notices channel like every other
diagnostic.

The whole cotejo family is unreachable live until a real G313 specimen
pins the inbound parser's layout extraction (the adapter refuses every
document today). This module is therefore driven synthetically until then
— the provenance token, the divergence shape, the single apply event, and
the namespace-replace semantics are all enforced by tests constructing the
certificate directly, never a parsed PDF.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, TypeAdapter

from ...core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.buckets.event import BucketEventType
from ...domain.user_profile.values import ProfileSetupState, UserProfileFact
from .capsule_record import ProfileRecordConflictError
from .profile_record_repository import ProfileRecordRepository
from .validation import reject_invalid_profile_facts

if TYPE_CHECKING:
    from ...domain.censo.certificado import CertificadoSituacionCensal
    from ...domain.user_profile.values import UserProfileRecord
    from .censal_operation import CensalReviewedOperand

#: Schema field family the deferred divergence rows persist under, indexed
#: as ``censo.divergencia.{n}.{axis,artefact_value,source}``. This is the
#: object-field-with-indexed-subpaths shape the
#: ``renta_family.descendiente`` family established: every indexed subpath
#: validates against the single ``censo.divergencia`` schema field.
CENSO_DIVERGENCE_PREFIX = "censo.divergencia"
_DIVERGENCE_AXIS = "axis"
_DIVERGENCE_ARTEFACT_VALUE = "artefact_value"
_DIVERGENCE_SOURCE = "source"

#: Axis namespace for a certified field the cotejo does not adopt and that
#: has no profile counterpart. A divergence row addressed here records
#: certificate evidence, NOT a writable profile schema path: a consumer that
#: resolves a divergence axis against the profile schema must tolerate it.
CENSO_CERTIFICATE_AXIS_PREFIX = "censo.certificado"

#: The certified fields projected as unadopted evidence rather than adopted
#: as facts. Both are obligation-bearing free-form prose whose vocabulary is
#: unpinned until a real G313 specimen exists, so their lines are preserved
#: verbatim and never parsed into typed facts.
CENSO_UNADOPTED_EVIDENCE_FIELDS: tuple[str, ...] = (
    "situacion_tributaria",
    "obligaciones_periodicas",
)

_UNADOPTED_EVIDENCE_FIELD_ADAPTER: TypeAdapter[tuple[str, ...]] = TypeAdapter(tuple[str, ...])

#: Notice code for the open-divergence advisory a profile read surfaces.
CENSO_DIVERGENCE_NOTICE_CODE = "profile.censo.divergences_open"

#: Message key for the open-divergence advisory. Declared as a module
#: constant whose name ends in ``_LOCALE_KEY`` so the static locale scanner
#: enumerates it as live; the four-locale copy is authored through the locales CLI.
_CENSO_DIVERGENCE_NOTICE_LOCALE_KEY = "application.user_profile.notices.censo_divergences_open"


class CensoDivergence(BaseModel):
    """One deferred cotejo axis: a certificate value the operator did not adopt.

    ``axis`` is the axis of the diverging EVIDENCE. Where the certificate
    axis has a profile counterpart it is that profile schema path, and the
    operator keeps their own answer there. Where it has none — a certified
    field the cotejo cannot adopt because its vocabulary is unpinned — it is
    a :data:`CENSO_CERTIFICATE_AXIS_PREFIX` path naming the certificate
    field, which is NOT writable profile state.

    ``artefact_value`` is the stringified certificate value left unadopted;
    ``source`` is the non-official artefact provenance token. A divergence
    row carries no AEAT-verified stamp — it records unadopted evidence,
    never an official fact.
    """

    model_config = STRICT_FROZEN_CONFIG

    axis: str = Field(min_length=1)
    artefact_value: str = Field(min_length=1)
    source: str = PROVENANCE_SOURCE_CENSO_ARTEFACT


def censo_unadopted_evidence(
    certificado: CertificadoSituacionCensal,
) -> tuple[CensoDivergence, ...]:
    """Project the certificate's unadopted obligation fields into divergence rows.

    The certificate's ``situacion_tributaria`` and ``obligaciones_periodicas``
    are certified statements about the taxpayer's obligation surface, and the
    cotejo does NOT adopt them as profile facts: both are free-form prose
    whose vocabulary stays unpinned until a real G313 specimen exists, so any
    mapping onto a typed profile axis — the Ley 49/2002 régimen among them —
    would be invented tax semantics rather than grounded ones.

    Discarding them is equally wrong: AEAT's certified statement would reach
    the operator nowhere at all. So each certified line is preserved as one
    unadopted-evidence :class:`CensoDivergence` at
    ``censo.certificado.<field>.<line index>``, carrying that line verbatim.
    One row per line, never a joined string, so no separator has to be
    invented and a line containing punctuation cannot be silently re-split.

    Nothing here parses, classifies or interprets the prose. The rows ride
    :func:`apply_cotejo` like any operator-deferred axis, inheriting the
    namespace-replace on re-cotejo and the standing warning
    :class:`~cadrumo.core.json_contract.Notice` that surfaces on every
    profile read until the operator resolves them.

    Args:
        certificado: The parsed :class:`CertificadoSituacionCensal` whose
            obligation-bearing certified fields are projected.
    """
    rows: list[CensoDivergence] = []
    for field in CENSO_UNADOPTED_EVIDENCE_FIELDS:
        lines = _UNADOPTED_EVIDENCE_FIELD_ADAPTER.validate_python(getattr(certificado, field))
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            rows.append(
                CensoDivergence(
                    axis=f"{CENSO_CERTIFICATE_AXIS_PREFIX}.{field}.{index}",
                    artefact_value=line,
                ),
            )
    return tuple(rows)


def _divergence_path(index: int, field: str) -> str:
    return f"{CENSO_DIVERGENCE_PREFIX}.{index}.{field}"


def divergence_facts(divergences: Sequence[CensoDivergence]) -> tuple[UserProfileFact, ...]:
    """Project deferred divergences into the indexed ``censo.divergencia.{n}.*`` facts."""
    facts: list[UserProfileFact] = []
    for index, divergence in enumerate(divergences):
        facts.append(UserProfileFact(path=_divergence_path(index, _DIVERGENCE_AXIS), value=divergence.axis))
        facts.append(
            UserProfileFact(
                path=_divergence_path(index, _DIVERGENCE_ARTEFACT_VALUE),
                value=divergence.artefact_value,
            ),
        )
        facts.append(UserProfileFact(path=_divergence_path(index, _DIVERGENCE_SOURCE), value=divergence.source))
    return tuple(facts)


def _existing_divergence_paths(record: UserProfileRecord | None) -> tuple[str, ...]:
    """Return every live ``censo.divergencia.*`` path on the record.

    Uses the last-value-wins projection so an already-cleared row is not
    re-cleared, and every currently-set divergence subpath is named for the
    namespace-replace clear.
    """
    from .projections import record_to_path_values

    prefix = f"{CENSO_DIVERGENCE_PREFIX}."
    return tuple(sorted(path for path in record_to_path_values(record) if path.startswith(prefix)))


def open_censo_divergences(record: UserProfileRecord | None) -> tuple[CensoDivergence, ...]:
    """Reconstruct the open divergence rows from a record's facts.

    Reads the last-value-wins projection so a cleared (``value=None``) row
    never resurfaces, groups the indexed ``censo.divergencia.{n}.*``
    subpaths back into typed rows in index order, and skips any incomplete
    index (a missing axis or artefact value).

    Args:
        record: The :class:`UserProfileRecord` whose facts are projected for
            open ``censo.divergencia.*`` rows, or ``None``.
    """
    from .projections import record_to_path_values

    values = record_to_path_values(record)
    prefix = f"{CENSO_DIVERGENCE_PREFIX}."
    indices: set[int] = set()
    for path in values:
        if not path.startswith(prefix):
            continue
        instance, _, field = path[len(prefix) :].partition(".")
        if instance.isdigit() and field:
            indices.add(int(instance))
    rows: list[tuple[int, CensoDivergence]] = []
    for index in sorted(indices):
        axis = values.get(_divergence_path(index, _DIVERGENCE_AXIS))
        artefact_value = values.get(_divergence_path(index, _DIVERGENCE_ARTEFACT_VALUE))
        source = values.get(_divergence_path(index, _DIVERGENCE_SOURCE), PROVENANCE_SOURCE_CENSO_ARTEFACT)
        if not axis or not artefact_value:
            continue
        rows.append((index, CensoDivergence(axis=axis, artefact_value=artefact_value, source=source)))
    return tuple(row for _index, row in rows)


def censo_divergence_notice(record: UserProfileRecord | None) -> Notice | None:
    """Return the warning :class:`Notice` for open cotejo divergences, or ``None``.

    A non-blocking advisory surfaced on profile reads: it never silently
    resolves an open divergence. Returns ``None`` when no divergence row is
    open so a clean profile carries no notice.

    Args:
        record: The :class:`UserProfileRecord` whose open divergence rows are
            summarised into the notice, or ``None``.
    """
    divergences = open_censo_divergences(record)
    if not divergences:
        return None
    axes = tuple(divergence.axis for divergence in divergences)
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=CENSO_DIVERGENCE_NOTICE_CODE,
        message=tr(
            _CENSO_DIVERGENCE_NOTICE_LOCALE_KEY,
            default=(
                "{count} profile or certificate field(s) still diverge from the Certificado "
                "de Situación Censal and remain unresolved: {axes}."
            ),
            count=len(divergences),
            axes=", ".join(axes),
        ),
        context={"count": str(len(divergences)), "axes": ", ".join(axes)},
    )


def apply_cotejo[StateT](
    state: StateT,
    *,
    adopted: Sequence[UserProfileFact] | None = None,
    divergences: Sequence[CensoDivergence] | None = None,
    reviewed_proposal: CensalReviewedOperand | None = None,
) -> StateT:
    """Commit a cotejo reconciliation: adopt certificate values, record divergences.

    Publishes, in one revision-bound record command:

    * clearing facts (``value=None``) for every ``censo.divergencia.*`` path
      currently on record that the fresh set does not re-declare — the
      namespace-replace so a re-cotejo cannot leave a stale divergence
      standing;
    * the adopted certificate facts (each already carrying the artefact
      provenance token, so the registered-values suffix renders them as
      non-official evidence);
    * the fresh ``censo.divergencia.{n}.*`` rows for the deferred axes.

    Then emits exactly one ``CENSO_APPLIED`` bucket event marking the
    apply-commit — never one per fact. Returns the updated
    :class:`~cadrumo.application.workflow.WorkflowState`; the caller persists
    it through the workflow repository like every other fact mutation.

    The resulting sequence is judged by the same schema authority the
    registration and wizard doors use, because a certificate is authoritative
    about the TAXPAYER, not about this application's fact vocabulary. AEAT
    certifies what the censal situation is; it does not certify that a value
    belongs at a path this schema declares, or that it arrives in the shape
    the schema types. Those are the profile's own contract, and an official
    origin is not evidence about them — which is why the axis adopting
    certificate values must satisfy them exactly as an operator edit does.
    Provenance is carried separately and is not weakened by this: each adopted
    fact keeps its ``censo_artefact_g313`` source token, a value the schema
    itself declares, so a reader can still tell a certified value from a typed
    one. Adopting unjudged is how a fact at an undeclared ``censo`` path was
    once written with no complaint.

    ``require_complete`` follows the record's own setup state rather than
    being asserted here. The cotejo runs DURING setup, so a profile that is
    still incomplete is legitimately missing the fields filing depends on, and
    demanding them would refuse the very reconciliation that helps supply
    them; a profile already past setup is held to the complete contract.
    """
    from ...core.bucket_pointer import require_active_bucket_id

    profile_id = require_active_bucket_id()
    repository = ProfileRecordRepository.for_current_session(profile_id)
    record = repository.load(profile_id)
    if reviewed_proposal is not None:
        if adopted is not None or divergences is not None:
            raise ValueError("a reviewed censal proposal cannot be combined with direct cotejo effects")
        adopted, divergences = _reviewed_censal_effects(reviewed_proposal, record)
    elif adopted is None or divergences is None:
        raise ValueError("direct cotejo apply requires both adopted facts and divergences")
    fresh = divergence_facts(divergences)
    fresh_paths = {fact.path for fact in fresh}
    clearing = tuple(
        UserProfileFact(path=path, value=None) for path in _existing_divergence_paths(record) if path not in fresh_paths
    )
    next_facts = (*record.facts, *clearing, *tuple(adopted), *fresh)
    reject_invalid_profile_facts(
        profile_id,
        next_facts,
        require_complete=record.setup_state is not ProfileSetupState.INCOMPLETE,
    )
    replacement = repository.apply_fact_changes(
        profile_id,
        facts=next_facts,
        expected_revision=record.record_revision,
        expected_content_digest=record.content_digest,
        event_type=BucketEventType.CENSO_APPLIED,
        event_payload={
            "adopted_count": str(len(tuple(adopted))),
            "divergence_count": str(len(divergences)),
        },
    )
    if replacement.record_revision != record.record_revision + 1:
        # A bare assert here was stripped under optimised interpretation and,
        # when it did run, reached the operator as an AssertionError carrying
        # nothing to act on. The invariant is worth keeping -- a commit that
        # did not advance the revision by exactly one means the record this
        # cotejo published is not the one it read -- so it is enforced as a
        # typed refusal on a filing-adjacent write path instead.
        raise ProfileRecordConflictError(
            "cotejo apply did not advance the profile record by exactly one revision",
        )
    return state


def _reviewed_censal_effects(
    proposal: CensalReviewedOperand,
    record: UserProfileRecord,
) -> tuple[tuple[UserProfileFact, ...], tuple[CensoDivergence, ...]]:
    """Verify one approved operand and derive only its explicitly reviewed effects."""
    from .censal_operation import CensalFieldIntent, CensalReviewedOperand
    from .censo_sync import CENSO_SOURCE_TAG, censal_facts_from_read

    verified = CensalReviewedOperand.model_validate_json(proposal.model_dump_json(), strict=True)
    baseline = verified.baseline
    if (
        baseline.profile_id != record.profile_id
        or baseline.record_revision != record.record_revision
        or baseline.content_digest != record.content_digest
    ):
        raise ProfileRecordConflictError("reviewed censal proposal baseline is stale")

    observed = {fact.path: fact for fact in censal_facts_from_read(verified.observation)}
    adopted: list[UserProfileFact] = []
    divergences: list[CensoDivergence] = []
    for field_intent in verified.field_intents:
        fact = observed.get(field_intent.path)
        if fact is None:
            continue
        if field_intent.intent is CensalFieldIntent.ADOPT:
            adopted.append(fact)
        else:
            divergences.append(
                CensoDivergence(
                    axis=field_intent.path,
                    artefact_value=str(fact.value),
                    source=CENSO_SOURCE_TAG,
                )
            )
    return tuple(adopted), tuple(divergences)


__all__ = [
    "CENSO_CERTIFICATE_AXIS_PREFIX",
    "CENSO_DIVERGENCE_NOTICE_CODE",
    "CENSO_DIVERGENCE_PREFIX",
    "CENSO_UNADOPTED_EVIDENCE_FIELDS",
    "CensoDivergence",
    "apply_cotejo",
    "censo_divergence_notice",
    "censo_unadopted_evidence",
    "divergence_facts",
    "open_censo_divergences",
]
