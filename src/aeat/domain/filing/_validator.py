"""Cross-cutting validator for :mod:`aeat.domain.filing` drafts.

The validator is intentionally pure: it consumes a draft + the
casilla collection it was built against and returns a tuple of
:class:`FilingValidationFinding` records. It never raises — strict
behaviour is the caller's responsibility via
``fail_on_warning`` on :func:`build_draft`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ...core.logging import get_logger
from ._protocols import (
    CasillaCollection,
    CasillaSchemaProvider,
    DeadlineChecker,
)
from ._schema import (
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
    FilingValue,
    FilingValueKind,
)

_logger = get_logger(__name__)


class FilingValidator:
    """Apply cross-cutting validation rules to a :class:`FilingDraft`.

    The validator depends on Protocols, not concrete subpackages,
    so the in-flight #9 / #23 / #38 work can be plugged in via a
    rebase later.
    """

    def __init__(
        self,
        *,
        schema_provider: CasillaSchemaProvider,
        deadline_checker: DeadlineChecker | None = None,
        quarterly_303_drafts: tuple[FilingDraft, ...] | None = None,
    ) -> None:
        """Construct the validator.

        Args:
            schema_provider: Resolves the casilla collection used
                during validation. The collection is the source of
                truth for required-ness, ranges, and formula
                inputs.
            deadline_checker: Optional deadline check Protocol
                implementation. When ``None`` the validator skips the
                deadline rule.
            quarterly_303_drafts: Optional tuple of four Modelo
                303 quarterly drafts. When populated and the
                draft under validation is a Modelo 390, the
                validator runs the
                :meth:`_validate_quarterly_reconciliation` rule
                which cross-checks every annual quarterly-sum
                casilla against the stored 303 drafts and
                surfaces ERROR findings on mismatch. The 130 and
                303 paths ignore this argument.
        """
        self._schema_provider = schema_provider
        self._deadline_checker = deadline_checker
        self._quarterly_303_drafts = quarterly_303_drafts

    def validate(self, draft: FilingDraft) -> tuple[FilingValidationFinding, ...]:
        """Run every validation rule against ``draft``.

        Args:
            draft: The draft to validate.

        Returns:
            A tuple of findings, possibly empty.
        """
        collection = self._schema_provider.get_collection(draft.modelo)
        findings: list[FilingValidationFinding] = []
        findings.extend(self._validate_schema_version(draft, collection))
        findings.extend(self._validate_required(draft, collection))
        findings.extend(self._validate_ranges(draft, collection))
        findings.extend(self._validate_formula_traces(draft, collection))
        findings.extend(self._validate_deadline(draft))
        findings.extend(self._validate_quarterly_reconciliation(draft))
        return tuple(findings)

    # ── individual rules ─────────────────────────────────────────

    def _validate_schema_version(
        self, draft: FilingDraft, collection: CasillaCollection
    ) -> list[FilingValidationFinding]:
        if draft.schema_version == collection.schema_version:
            return []
        return [
            FilingValidationFinding(
                casilla_id=None,
                severity=FilingFindingSeverity.WARNING,
                code="filing-schema-version-mismatch",
                message={
                    "es": (
                        f"Versión de esquema del borrador {draft.schema_version!r} "
                        f"no coincide con la actual {collection.schema_version!r}"
                    ),
                    "en": (
                        f"Draft schema version {draft.schema_version!r} differs from "
                        f"current {collection.schema_version!r}"
                    ),
                    "hu": (
                        f"A piszkozat sémaverziója {draft.schema_version!r} "
                        f"eltér a jelenlegitől {collection.schema_version!r}"
                    ),
                },
                references_rules=(),
            )
        ]

    def _validate_required(self, draft: FilingDraft, collection: CasillaCollection) -> list[FilingValidationFinding]:
        by_id = {v.casilla_id: v for v in draft.values}
        out: list[FilingValidationFinding] = []
        for casilla in collection.all():
            if not casilla.required:
                continue
            value = by_id.get(casilla.id)
            if value is None or value.kind is FilingValueKind.EMPTY or value.value is None:
                out.append(
                    FilingValidationFinding(
                        casilla_id=casilla.id,
                        severity=FilingFindingSeverity.ERROR,
                        code="casilla-required-missing",
                        message={
                            "es": f"Casilla obligatoria {casilla.id} sin valor",
                            "en": f"Required casilla {casilla.id} has no value",
                            "hu": f"A kötelező rovat {casilla.id} hiányzik",
                        },
                        references_rules=(),
                    )
                )
        return out

    def _validate_ranges(self, draft: FilingDraft, collection: CasillaCollection) -> list[FilingValidationFinding]:
        out: list[FilingValidationFinding] = []
        for value in draft.values:
            casilla = collection.get(value.casilla_id)
            if casilla is None or value.value is None:
                continue
            if not isinstance(value.value, Decimal | int):
                continue
            numeric = Decimal(value.value) if isinstance(value.value, int) else value.value
            if casilla.min_value is not None and numeric < Decimal(str(casilla.min_value)):
                out.append(self._range_finding(value.casilla_id, "below"))
            if casilla.max_value is not None and numeric > Decimal(str(casilla.max_value)):
                out.append(self._range_finding(value.casilla_id, "above"))
        return out

    @staticmethod
    def _range_finding(casilla_id: str, direction: str) -> FilingValidationFinding:
        return FilingValidationFinding(
            casilla_id=casilla_id,
            severity=FilingFindingSeverity.ERROR,
            code="casilla-out-of-range",
            message={
                "es": f"Casilla {casilla_id} fuera de rango ({direction})",
                "en": f"Casilla {casilla_id} out of range ({direction})",
                "hu": f"A {casilla_id} rovat tartományon kívül ({direction})",
            },
            references_rules=(),
        )

    def _validate_formula_traces(
        self, draft: FilingDraft, collection: CasillaCollection
    ) -> list[FilingValidationFinding]:
        out: list[FilingValidationFinding] = []
        for value in draft.values:
            casilla = collection.get(value.casilla_id)
            if casilla is None:
                continue
            if not casilla.formula_inputs:
                if value.formula_trace:
                    out.append(self._divergence(value.casilla_id))
                continue
            if value.kind is not FilingValueKind.COMPUTED:
                out.append(self._divergence(value.casilla_id))
                continue
            if value.formula_trace is None or set(value.formula_trace) != set(casilla.formula_inputs):
                out.append(self._divergence(value.casilla_id))
        return out

    @staticmethod
    def _divergence(casilla_id: str) -> FilingValidationFinding:
        return FilingValidationFinding(
            casilla_id=casilla_id,
            severity=FilingFindingSeverity.ERROR,
            code="formula-divergence",
            message={
                "es": f"Divergencia de fórmula en casilla {casilla_id}",
                "en": f"Formula divergence on casilla {casilla_id}",
                "hu": f"Képlet eltérés a {casilla_id} rovaton",
            },
            references_rules=(),
        )

    def _validate_quarterly_reconciliation(self, draft: FilingDraft) -> list[FilingValidationFinding]:
        """Reconcile a Modelo 390 draft against its four quarterly 303 drafts.

        The rule only runs when ``draft.modelo == "390"`` and the
        validator was constructed with ``quarterly_303_drafts``. It
        performs two independent cross-checks:

        - **390 → Σ 303.** For each
          :data:`_MODELO_390_QUARTERLY_MAP` entry the annual
          casilla is compared against the sum of the matching 303
          casilla across the four quarterly drafts. Divergences
          beyond :data:`_RECONCILIATION_TOLERANCE` emit
          ``filing-390-303-mismatch`` ERROR findings.
        - **303 self-consistency.** Each quarterly draft's rate
          triples (``03=01x0.04``, ``06=04x0.10``, ``09=07x0.21``)
          are re-evaluated. Divergences emit
          ``filing-303-internal-mismatch`` ERROR findings against
          the 390 draft, with the offending 303 ``draft_id`` in
          the trilingual message payload.

        Args:
            draft: The draft under validation.

        Returns:
            A list of findings (possibly empty).
        """
        quarterly = self._quarterly_303_drafts
        if quarterly is None or draft.modelo != "390":
            return []
        out: list[FilingValidationFinding] = []
        by_id = {v.casilla_id: v for v in draft.values}
        quarter_values = [{v.casilla_id: v for v in q.values} for q in quarterly]

        for annual_casilla, source_casilla in _MODELO_390_QUARTERLY_MAP.items():
            annual_value = by_id.get(annual_casilla)
            if annual_value is None:
                continue
            annual_decimal = _value_as_decimal(annual_value)
            if annual_decimal is None:
                continue
            recomputed = Decimal("0")
            for casillas in quarter_values:
                source = casillas.get(source_casilla)
                if source is None:
                    continue
                numeric = _value_as_decimal(source)
                if numeric is not None:
                    recomputed += numeric
            if abs(annual_decimal - recomputed) > _RECONCILIATION_TOLERANCE:
                out.append(
                    FilingValidationFinding(
                        casilla_id=annual_casilla,
                        severity=FilingFindingSeverity.ERROR,
                        code="filing-390-303-mismatch",
                        message={
                            "es": (
                                f"Casilla anual {annual_casilla} = {annual_decimal} "
                                f"no coincide con la suma de casilla 303 {source_casilla} "
                                f"({recomputed}) en los cuatro trimestres"
                            ),
                            "en": (
                                f"Annual casilla {annual_casilla} = {annual_decimal} "
                                f"does not match sum of 303 casilla {source_casilla} "
                                f"({recomputed}) across the four quarters"
                            ),
                            "hu": (
                                f"Az éves {annual_casilla} rovat = {annual_decimal} "
                                f"nem egyezik a négy negyedév 303 {source_casilla} "
                                f"rovatának összegével ({recomputed})"
                            ),
                        },
                        references_rules=(),
                    )
                )

        for q in quarterly:
            q_values = {v.casilla_id: v for v in q.values}
            for cuota_id, base_id, rate in _MODELO_303_RATE_TRIPLES:
                base_value = q_values.get(base_id)
                cuota_value = q_values.get(cuota_id)
                if base_value is None or cuota_value is None:
                    continue
                base_decimal = _value_as_decimal(base_value)
                cuota_decimal = _value_as_decimal(cuota_value)
                if base_decimal is None or cuota_decimal is None:
                    continue
                expected = base_decimal * rate
                if abs(cuota_decimal - expected) > _RECONCILIATION_TOLERANCE:
                    out.append(
                        FilingValidationFinding(
                            casilla_id=cuota_id,
                            severity=FilingFindingSeverity.ERROR,
                            code="filing-303-internal-mismatch",
                            message={
                                "es": (
                                    f"303 {q.period} ({q.draft_id}): casilla {cuota_id} "
                                    f"= {cuota_decimal} no coincide con {base_id} x {rate} "
                                    f"= {expected}"
                                ),
                                "en": (
                                    f"303 {q.period} ({q.draft_id}): casilla {cuota_id} "
                                    f"= {cuota_decimal} does not match {base_id} x {rate} "
                                    f"= {expected}"
                                ),
                                "hu": (
                                    f"303 {q.period} ({q.draft_id}): a {cuota_id} rovat "
                                    f"= {cuota_decimal} nem egyezik {base_id} x {rate} "
                                    f"= {expected} értékkel"
                                ),
                            },
                            references_rules=(),
                        )
                    )
        return out

    def _validate_deadline(self, draft: FilingDraft) -> list[FilingValidationFinding]:
        if self._deadline_checker is None:
            return []
        status = self._deadline_checker.check(draft.modelo, draft.period)
        if not status.is_overdue:
            return []
        return [
            FilingValidationFinding(
                casilla_id=None,
                severity=FilingFindingSeverity.ERROR,
                code="filing-deadline-missed",
                message={
                    "es": (f"Plazo de presentación del modelo {draft.modelo} vencido ({status.due_date.isoformat()})"),
                    "en": (f"Filing deadline for modelo {draft.modelo} has passed ({status.due_date.isoformat()})"),
                    "hu": (f"A {draft.modelo} modell beadási határideje lejárt ({status.due_date.isoformat()})"),
                },
                references_rules=(),
            )
        ]


#: Mapping of 390 quarterly-sum casilla → 303 source casilla.
#: Duplicated from :mod:`aeat.domain.filing._builders.modelo_390` so the
#: validator has no import dependency on the private builder.
_MODELO_390_QUARTERLY_MAP: dict[str, str] = {
    "100": "01",
    "101": "03",
    "104": "04",
    "105": "06",
    "108": "07",
    "109": "09",
    "190": "28",
    "191": "29",
    "192": "30",
    "193": "31",
}

#: 303 self-consistency triples (cuota casilla, base casilla, tipo as decimal).
_MODELO_303_RATE_TRIPLES: tuple[tuple[str, str, Decimal], ...] = (
    ("03", "01", Decimal("0.04")),
    ("06", "04", Decimal("0.10")),
    ("09", "07", Decimal("0.21")),
)

#: Tolerance for floating-cent drift during reconciliation.
_RECONCILIATION_TOLERANCE = Decimal("0.005")


def _value_as_decimal(value: FilingValue) -> Decimal | None:
    """Return the numeric value of ``value`` or ``None`` if not numeric."""
    raw = value.value
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return Decimal(raw)
    return None


def apply_validation(
    draft: FilingDraft,
    findings: tuple[FilingValidationFinding, ...],
) -> FilingDraft:
    """Return a copy of ``draft`` with ``findings`` and a fresh status.

    Status promotion logic:

    - Any ``ERROR`` → :attr:`FilingDraftStatus.DRAFT` (still
      blocking).
    - Any ``WARNING`` only → :attr:`FilingDraftStatus.VALIDATED`.
    - No findings → :attr:`FilingDraftStatus.READY_TO_SUBMIT`.
    """
    new_status = derive_validation_status(findings)
    return draft.model_copy(
        update={
            "findings": findings,
            "status": new_status,
            "updated_at": datetime.now(tz=UTC),
        }
    )


def derive_validation_status(
    findings: tuple[FilingValidationFinding, ...],
) -> FilingDraftStatus:
    """Return the machine validation status implied by ``findings``."""

    has_error = any(f.severity is FilingFindingSeverity.ERROR for f in findings)
    has_warning = any(f.severity is FilingFindingSeverity.WARNING for f in findings)
    if has_error:
        return FilingDraftStatus.DRAFT
    if has_warning:
        return FilingDraftStatus.VALIDATED
    return FilingDraftStatus.READY_TO_SUBMIT
