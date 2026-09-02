"""The operator-level face of an in-progress Modelo edit.

A frontend drives an edit through this module and holds nothing else. It calls
in operator terms -- set this casilla from what the operator typed, clear that
one, abandon -- and receives operator-level outcomes back. Every Edit Contract
V1 record the work actually runs on (intents, addresses, parse requests,
submissions, refusals) is built, held and consumed INSIDE this package and
never crosses the boundary.

That is the whole point of the module rather than a stylistic preference. The
contract's own public face, :mod:`.edit_contract`, deliberately publishes only
the four records a package outside ``application.modelo`` legitimately holds,
on the stated ground that publishing the rest would widen the contract to the
shape of its implementation rather than the shape of its use. A frontend that
staged intents itself would falsify that premise and require ~8 more records to
become public. Keeping the session here keeps the boundary where the contract
put it, and leaves the frontend holding one opaque handle.

The session is the in-memory baseline retainer the contract expects.
:class:`ModeloEditParseRequestV1` documents that the contract mints no
server-side baseline store and that the caller resupplies the admission on
every call; this class is that caller, so a frontend never sees a baseline
either.

Nothing here computes tax or decides what a value MEANS. Parsing a lexeme is
delegated to :func:`parse_modelo_edit_value`, validation to the contract's own
services; this module decides only WHEN a value is staged, replaced or
discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .edit_models import (
    ModeloDetailRowEditIntentV1,
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditDetailRowAddressV1,
    ModeloEditDetailRowIntentKind,
    ModeloEditParsedValueV1,
    ModeloEditParseRequestV1,
    ModeloEditPreflightRequestV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from .edit_services import (
    admit_modelo_edit,
    detail_row_identity_components,
    detail_row_natural_key,
    parse_modelo_edit_value,
    preflight_modelo_edit,
    reconfirm_modelo_edit_baseline,
)
from .operation_definitions import (
    ModeloEditApplyDetailRowAddressV1,
    ModeloEditApplyDetailRowIntentV1,
    ModeloEditApplyOperationRequestV1,
    ModeloEditApplySubmissionV1,
    wire_detail_row,
)

if TYPE_CHECKING:
    from ...core.external_constants import OutputLanguage
    from ...domain.calculations.registry.schema_input_kind import InputKind
    from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, ModeloDetailRow
    from ...domain.modelos.work_unit import WorkUnitCatalogue
    from .edit_models import (
        ModeloEditBaselineV1,
        ModeloEditCompatibilityTupleV1,
        ModeloEditMutationFamily,
        ModeloEditPreflightResultV1,
    )
    from .workspace_models import ModeloWorkspaceTargetV1

__all__ = [
    "ModeloEditSession",
    "ModeloEditSessionClosedError",
    "ScalarEditOutcome",
    "SessionOpenOutcome",
    "WritableScalar",
    "open_modelo_edit_session",
]


class ModeloEditSessionClosedError(RuntimeError):
    """Raised when an abandoned session is asked to stage or review.

    Abandoning is final for the session it is called on. A caller that keeps
    using one afterwards is asking for edits the operator already discarded,
    and silently reopening would resurrect them.
    """


@dataclass(frozen=True, slots=True)
class ScalarEditOutcome:
    """What happened to one operator keystroke-level edit, in operator terms.

    Deliberately NOT the contract's own refusal record. A frontend needs to
    know whether the value took and what to say if it did not; it does not
    need the typed refusal, and handing it one would put an Edit Contract V1
    record in the frontend after all.

    ``message_key`` is a localisation key, never rendered prose and never the
    operator's raw lexeme -- the contract refuses to echo a lexeme in any
    result derived from a parse request, and this outcome keeps that promise.
    """

    casilla_id: str
    accepted: bool
    message_key: str | None = None


@dataclass(frozen=True, slots=True)
class WritableScalar:
    """One editable casilla, in the two facts a control needs to exist.

    ``data_type`` is the contract's own declared type rendered as a string,
    so a frontend can choose a control without importing the enum. The
    control's BEHAVIOUR still belongs to the contract: the lexeme goes back
    through :meth:`ModeloEditSession.set_casilla`, which parses it there.
    """

    casilla_id: str
    data_type: str


@dataclass(frozen=True, slots=True)
class SessionOpenOutcome:
    """A session, or the reason one could not be opened.

    ``message_key`` is a localisation key, never rendered prose: the caller
    that renders it owns the wording, and the contract owns the code.
    """

    session: ModeloEditSession | None
    message_key: str | None


@dataclass(slots=True)
class ModeloEditSession:
    """One operator's in-progress edit over a single admitted work unit.

    Constructed through :func:`open_modelo_edit_session`, never directly: the
    admission produces the baseline, and a caller that built the session
    itself would have to hold one.

    ONE baseline is held: the admission a submission is judged against. It is
    never moved while the session is open, which is what stops a refresh
    silently re-targeting staged edits at whatever the tree looks like now.

    An earlier design held a second "read" baseline for what the operator was
    viewing, and answered staleness by comparing the two records. That was
    wrong: an admission carries its own identity and lifetime -- baseline_id,
    issued_at, expires_at -- so two admissions of an UNCHANGED tree are never
    equal, and the comparison reported stale permanently. Staleness is now
    asked of the contract's own compare-and-swap, which judges the coordinate
    axes rather than the record, so the second baseline had nothing left to
    do and was removed rather than kept as a field only ever written.

    The baseline is package-internal: a frontend holds this session, never a
    baseline.

    The mutation family is fixed at open, so intents staged against one
    contract cannot be submitted under another.
    """

    _edit_baseline: ModeloEditBaselineV1
    _mutation_family: ModeloEditMutationFamily
    _scalars: dict[str, ModeloScalarEditIntentV1] = field(default_factory=dict, init=False)
    _rows: dict[tuple[str, str], ModeloDetailRowEditIntentV1] = field(default_factory=dict, init=False)
    #: Each staged row's identity components, kept because they cannot be
    #: recovered later: the intent's address holds only the JOINED natural key,
    #: and splitting it back apart would guess wrong for exactly the rows whose
    #: own identifier contains the separator. Captured from the row at staging
    #: time, which is the only moment they are unambiguous.
    _row_components: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict, init=False)
    _closed: bool = field(default=False, init=False)

    @classmethod
    def opened_from_admission(
        cls,
        admitted: ModeloEditAdmittedV1,
        *,
        mutation_family: ModeloEditMutationFamily,
    ) -> ModeloEditSession:
        """Open a session whose two baselines start identical.

        Keyed on the admission record rather than on a bare baseline, so the
        "admit first" rule is carried by the signature instead of by a naming
        convention: the only way to hold a :class:`ModeloEditAdmittedV1` is to
        have been admitted. A constructor taking a baseline directly would hand
        a frontend the one record this module exists to keep on this side of
        the boundary; this one cannot be called without the admission that
        already published it.
        """
        return cls(_edit_baseline=admitted.baseline, _mutation_family=mutation_family)

    @property
    def is_closed(self) -> bool:
        """Whether this session has been abandoned."""
        return self._closed

    @property
    def is_dirty(self) -> bool:
        """Whether anything is staged.

        Derived from the staged intents rather than tracked as a flag: a flag
        and the intents are two records of one fact, and only one of them can
        be wrong.
        """
        return bool(self._scalars or self._rows)

    def dirty_casilla_ids(self) -> tuple[str, ...]:
        """Return the staged casilla ids, in canonical order.

        Plain ids rather than the contract's address records, so a frontend
        can highlight what changed without holding a contract type. Semantic
        rather than positional: a control that moves on a re-render still
        names the same casilla, and a widget position would not.
        """
        return tuple(sorted(self._scalars))

    def writable_scalars(self) -> tuple[WritableScalar, ...]:
        """Return the casillas this admission permits editing, with their data type.

        A frontend must know what to render a control FOR, and asking it to
        read ``baseline.permitted_surface`` would hand it the contract's
        surface records. This projects the same admitted fact into two plain
        strings per entry: the casilla to address and the data type that
        decides the control.

        Derived from the EDIT baseline, so it describes what a submit would
        actually be judged against rather than what the operator last looked
        at.
        """
        return tuple(
            WritableScalar(casilla_id=entry.casilla_id, data_type=str(entry.data_type))
            for entry in self._edit_baseline.permitted_surface
            if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
        )

    def set_casilla(
        self,
        casilla_id: str,
        raw_lexeme: str,
        *,
        input_kind: InputKind,
        locale: OutputLanguage,
    ) -> ScalarEditOutcome:
        """Stage what the operator typed for one casilla.

        The lexeme is parsed by the contract's own
        :func:`parse_modelo_edit_value`, never here: a second parser beside
        the one the contract owns would disagree the first time a locale
        changed. A refusal is reported as an outcome rather than raised,
        because a mistyped value is an ordinary event on an editing surface.

        Staging replaces any earlier staging for the same casilla. The
        operator's second answer is their answer, and keeping both would
        submit two intents for one address.
        """
        self._require_open()
        address = ModeloEditScalarAddressV1(casilla_id=casilla_id)
        parsed = parse_modelo_edit_value(
            ModeloEditParseRequestV1(
                baseline=self._edit_baseline,
                address=address,
                input_kind=input_kind,
                locale=locale,
                raw_lexeme=raw_lexeme,
            )
        )
        if not isinstance(parsed, ModeloEditParsedValueV1):
            return ScalarEditOutcome(
                casilla_id=casilla_id,
                accepted=False,
                message_key=_refusal_message_key(parsed.refusal),
            )
        self._scalars[casilla_id] = ModeloScalarEditIntentV1(
            address=address,
            kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
            value=parsed.value,
        )
        return ScalarEditOutcome(casilla_id=casilla_id, accepted=True)

    def clear_casilla(self, casilla_id: str) -> ScalarEditOutcome:
        """Stage the removal of a declared value.

        Distinct from staging zero and from staging nothing: clearing says the
        operator removed a declaration, zero says they declared zero, and an
        untouched casilla says they did not answer. Collapsing any two of the
        three loses a distinction the filing depends on.
        """
        self._require_open()
        self._scalars[casilla_id] = ModeloScalarEditIntentV1(
            address=ModeloEditScalarAddressV1(casilla_id=casilla_id),
            kind=ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
            value=None,
        )
        return ScalarEditOutcome(casilla_id=casilla_id, accepted=True)

    def stage_row(self, detail_row_kind: str, row: ModeloDetailRow) -> str:
        """Stage a detail row under its own natural key, adding or updating it.

        One call for both, because the contract addresses a row by the
        business key it already carries: whether that key is already declared
        is a fact about the work unit, not about the operator's gesture, and
        making the caller choose ADD or UPDATE would ask a frontend to know
        something it would have to guess.

        Returns the natural key it derived, so a frontend learns the address
        its row landed under without deriving one itself -- the derivation
        stays single-homed here rather than being repeated across the
        boundary, where a second copy could disagree.

        The natural key is DERIVED from the row rather than supplied beside
        it. A caller passing both could pass a key that describes a different
        row than the one it carries, and the contract addresses by key while
        the row carries its own identity, so the two disagreeing would stage
        an edit against the wrong declaration.

        Keyed rather than appended, so re-staging the same row replaces it.
        Order is not preserved and deliberately so: the intent kind's own
        documentation records that no MOVE exists because every row-producer
        sorts by a content key before assigning occurrence numbers, so two
        calls supplying the same rows in different orders render
        byte-identical ficheros. Preserving supply order here would imply a
        significance the fichero does not have.
        """
        self._require_open()
        natural_key = detail_row_natural_key(row)
        key = (detail_row_kind, natural_key)
        self._rows[key] = ModeloDetailRowEditIntentV1(
            address=ModeloEditDetailRowAddressV1(detail_row_kind=detail_row_kind, natural_key=natural_key),
            kind=ModeloEditDetailRowIntentKind.UPDATE_ROW,
            row=row,
        )
        self._row_components[key] = detail_row_identity_components(row)
        return natural_key

    def remove_row(self, detail_row_kind: str, row: ModeloDetailRow) -> str:
        """Stage the removal of one declared detail row.

        Distinct from :meth:`discard_row`, which reverts the operator's own
        staging. A row has no ambiguous middle state between declared and
        absent, so an absent key is sufficient to express removal.

        Takes the ROW rather than its key, even though the intent carries no
        row: the key alone cannot yield the identity components the operation
        payload addresses by, and they are unrecoverable once joined. A
        surface offering to delete a declared row is displaying that row, so
        it holds one.
        """
        self._require_open()
        natural_key = detail_row_natural_key(row)
        key = (detail_row_kind, natural_key)
        self._rows[key] = ModeloDetailRowEditIntentV1(
            address=ModeloEditDetailRowAddressV1(detail_row_kind=detail_row_kind, natural_key=natural_key),
            kind=ModeloEditDetailRowIntentKind.DELETE_ROW,
            row=None,
        )
        self._row_components[key] = detail_row_identity_components(row)
        return natural_key

    def discard_row(self, detail_row_kind: str, natural_key: str) -> bool:
        """Unstage one row, returning whether anything was staged."""
        self._require_open()
        self._row_components.pop((detail_row_kind, natural_key), None)
        return self._rows.pop((detail_row_kind, natural_key), None) is not None

    def dirty_row_keys(self) -> tuple[tuple[str, str], ...]:
        """Return the staged ``(detail_row_kind, natural_key)`` pairs, in canonical order."""
        return tuple(sorted(self._rows))

    def discard_casilla(self, casilla_id: str) -> bool:
        """Unstage one casilla, returning whether anything was staged.

        Not the same as :meth:`clear_casilla`: this reverts the operator's
        edit, that one submits a removal.
        """
        self._require_open()
        return self._scalars.pop(casilla_id, None) is not None

    def refresh(
        self,
        *,
        work_catalogue: WorkUnitCatalogue,
        calculation_catalogue: CalculationRevisionCatalogue,
    ) -> tuple[str, ...]:
        """Recheck the edit baseline against the current catalogues.

        Asks the contract's own :func:`reconfirm_modelo_edit_baseline`, which
        is the SAME comparison the guarded commit point runs. An earlier
        version of this method re-admitted and compared the two baseline
        RECORDS, which was wrong twice over: it was a second authority beside
        the contract's, and it could never report agreement, because an
        admission carries its own identity and lifetime -- `baseline_id`,
        `issued_at`, `expires_at` -- so two admissions of an unchanged tree
        are never equal. That made the stale signal permanently stuck on
        "stale", which is the failure mode a compare-and-swap exists to avoid.

        Nothing is merged, rebased or patched: the staged edits and the edit
        baseline are both left exactly as they were, so a submit is still
        judged against the coordinate it was admitted on.

        Returns:
            The names of the coordinates that have drifted, empty when the
            baseline is still current.
        """
        self._require_open()
        stale = reconfirm_modelo_edit_baseline(
            self._edit_baseline,
            work_catalogue=work_catalogue,
            calculation_catalogue=calculation_catalogue,
        )
        if stale is None:
            return ()
        return tuple(getattr(stale, "mismatching_coordinates", ()) or ("baseline",))

    def abandon(self) -> None:
        """Discard every staged edit and close the session.

        Explicit by contract. Nothing discards implicitly on refresh or on
        navigation: an edit the operator did not abandon is still theirs, and
        a surface that quietly drops staged work is indistinguishable from one
        that saved it.
        """
        self._scalars.clear()
        self._rows.clear()
        self._closed = True

    def review(
        self,
        *,
        work_catalogue: WorkUnitCatalogue,
        calculation_catalogue: CalculationRevisionCatalogue,
    ) -> ModeloEditPreflightResultV1:
        """Recheck the staged submission against the current catalogues.

        Review material, never authorization: the contract's execution path
        independently repeats every concurrency and capability check at the
        guarded commit point, so a green result here is not a promise the
        apply will succeed.
        """
        self._require_open()
        return preflight_modelo_edit(
            ModeloEditPreflightRequestV1(submission=self._submission()),
            work_catalogue=work_catalogue,
            calculation_catalogue=calculation_catalogue,
        )

    def submit(self) -> ModeloEditApplyOperationRequestV1:
        """Assemble the staged edit into the request the apply operation accepts.

        Assembly only. This neither dispatches the operation nor claims the
        edit succeeded: the guarded commit point independently repeats every
        concurrency and capability check, so a caller runs :meth:`review`
        first and then hands this request to the operation layer.

        The detail rows are mirrored HERE rather than through
        :meth:`ModeloEditApplySubmissionV1.from_submission`, which refuses
        them and is right to. That classmethod receives a bare domain
        submission whose addresses carry only the JOINED natural key, and
        splitting a key back into components guesses wrong for exactly the
        rows whose own identifier contains the separator. This session
        additionally holds the components it captured from each row at
        staging time, which is the only moment they are unambiguous, so it
        builds the wire address from those instead of guessing.
        """
        self._require_open()
        submission = self._submission()
        scalar_side = ModeloEditApplySubmissionV1.from_submission(
            ModeloEditSubmissionV1(
                baseline=submission.baseline,
                mutation_family=submission.mutation_family,
                scalar_intents=submission.scalar_intents,
                binding_intents=submission.binding_intents,
                row_intents=submission.row_intents,
            )
        )
        wire = scalar_side.model_copy(update={"detail_row_intents": self._wire_detail_row_intents()})
        return ModeloEditApplyOperationRequestV1(submission=wire)

    def _wire_detail_row_intents(self) -> tuple[ModeloEditApplyDetailRowIntentV1, ...]:
        """Mirror every staged detail row, addressed by its retained components."""
        return tuple(self._wire_detail_row_intent(key) for key in sorted(self._rows))

    def _wire_detail_row_intent(self, key: tuple[str, str]) -> ModeloEditApplyDetailRowIntentV1:
        """Mirror one staged detail row onto its wire intent.

        The staged intent is bound to a local before the ``None`` test: repeating
        ``self._rows[key].row`` across the test and the call is two separate
        subscripts, so the absence check narrows neither of them.
        """
        intent = self._rows[key]
        row = intent.row
        return ModeloEditApplyDetailRowIntentV1(
            address=ModeloEditApplyDetailRowAddressV1(
                detail_row_kind=intent.address.detail_row_kind,
                identity_components=self._row_components[key],
            ),
            kind=intent.kind,
            row=None if row is None else wire_detail_row(row),
        )

    def _submission(self) -> ModeloEditSubmissionV1:
        """Build the submission against the EDIT baseline, never the read one.

        The submission is judged against what was admitted, so a divergence
        since then is refused rather than absorbed.
        """
        return ModeloEditSubmissionV1(
            baseline=self._edit_baseline,
            mutation_family=self._mutation_family,
            scalar_intents=tuple(self._scalars[key] for key in sorted(self._scalars)),
            detail_row_intents=tuple(self._rows[key] for key in sorted(self._rows)),
        )

    def _require_open(self) -> None:
        if self._closed:
            raise ModeloEditSessionClosedError("this edit session was abandoned; open a new one to stage edits")


def _refusal_message_key(refusal: object) -> str:
    """Derive a localisation key from any arm of the refusal union.

    Reads the ``kind`` DISCRIMINATOR, which every arm carries by
    construction, rather than ``code``, which only the domain refusal has.
    A helper that read ``code`` worked for the arm it was written against and
    raised ``AttributeError`` on a stale compatibility tuple -- turning an
    ordinary refusal into a crash on the exact path a platform upgrade takes.

    The domain arm's ``code`` is appended when present, because it says WHICH
    domain refusal this is and the discriminator alone does not.
    """
    kind = getattr(refusal, "kind", "refused")
    code = getattr(refusal, "code", None)
    if code is not None:
        return f"{kind}.{getattr(code, 'value', code)}"
    axis = getattr(refusal, "requested_axis", None)
    return f"{kind}.{axis}" if axis else str(kind)


def open_modelo_edit_session(
    target: ModeloWorkspaceTargetV1,
    *,
    mutation_family: ModeloEditMutationFamily,
    bucket_id: str,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    compatibility: ModeloEditCompatibilityTupleV1,
) -> SessionOpenOutcome:
    """Admit a target and open a session over it, in one call.

    The single entry point for a frontend, and the reason the baseline never
    leaves this package: admitting produces one, and a caller that had to
    admit separately would hold it in order to pass it in. Every parameter
    here is either an operator coordinate or a record :mod:`.edit_contract`
    already publishes, so a frontend can call this holding nothing private.

    A refused admission is returned rather than raised. Being unable to edit
    a target is an ordinary answer on a read surface -- the work unit may be
    filed, or its compatibility coordinate may have moved -- and a frontend
    that must catch an exception to render a disabled control is being told
    the same thing in a harder way.
    """
    admitted = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=target, mutation_family=mutation_family),
        bucket_id=bucket_id,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        compatibility=compatibility,
    )
    if not isinstance(admitted, ModeloEditAdmittedV1):
        return SessionOpenOutcome(session=None, message_key=_refusal_message_key(admitted.refusal))
    return SessionOpenOutcome(
        session=ModeloEditSession.opened_from_admission(admitted, mutation_family=mutation_family),
        message_key=None,
    )
