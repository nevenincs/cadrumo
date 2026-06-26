"""Cross-cutting validator for :mod:`aeat.domain.filing` drafts.

The validator is intentionally pure: it consumes a draft + the
casilla collection it was built against and returns a tuple of
:class:`ModeloValidationFinding` records. It never raises — strict
behaviour is the caller's responsibility via
``fail_on_warning`` on :func:`build_draft`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.errors import BaseSeverity
from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ...core.time import now
from ._protocols import (
    CasillaCollection,
    CasillaSchemaProvider,
    DeadlineChecker,
)
from ._schema import (
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValidationFinding,
    ModeloValueKind,
)

if TYPE_CHECKING:  # pragma: no cover - type-only import
    from ..calculations.registry import CasillaId

_logger = get_logger(__name__)


class ModeloValidator:
    """Apply cross-cutting validation rules to a :class:`ModeloDraft`.

    The validator depends on Protocols, not concrete subpackages,
    so alternative casilla, formula, or deadline implementations can
    be supplied without touching the validator.
    """

    def __init__(
        self,
        *,
        schema_provider: CasillaSchemaProvider,
        deadline_checker: DeadlineChecker | None = None,
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
        """
        self._schema_provider = schema_provider
        self._deadline_checker = deadline_checker

    def validate(self, draft: ModeloDraft) -> tuple[ModeloValidationFinding, ...]:
        """Run every validation rule against ``draft``.

        Args:
            draft: The :class:`ModeloDraft` to validate.

        Returns:
            A tuple of :class:`ModeloValidationFinding` items, possibly empty.
        """
        collection = self._schema_provider.get_collection(draft.modelo)
        findings: list[ModeloValidationFinding] = []
        findings.extend(self._validate_schema_version(draft, collection))
        findings.extend(self._validate_declared_casillas(draft, collection))
        findings.extend(self._validate_required(draft, collection))
        findings.extend(self._validate_ranges(draft, collection))
        findings.extend(self._validate_formula_traces(draft, collection))
        findings.extend(self._validate_deadline(draft))
        result = tuple(findings)
        errors = sum(1 for f in result if f.severity is BaseSeverity.ERROR)
        _logger.debug(
            "validated draft modelo=%s period=%s errors=%d total_findings=%d",
            draft.modelo,
            draft.period,
            errors,
            len(result),
        )
        return result

    # ── individual rules ─────────────────────────────────────────

    def _validate_schema_version(
        self,
        draft: ModeloDraft,
        collection: CasillaCollection,
    ) -> list[ModeloValidationFinding]:
        if draft.schema_version == collection.schema_version:
            return []
        return [
            ModeloValidationFinding(
                casilla_id=None,
                severity=BaseSeverity.WARNING,
                code="filing-schema-version-mismatch",
                message=tr("filing.validation.schema_mismatch"),
                references_rules=(),
            ),
        ]

    def _validate_declared_casillas(
        self,
        draft: ModeloDraft,
        collection: CasillaCollection,
    ) -> list[ModeloValidationFinding]:
        known_ids = {casilla.casilla_id for casilla in collection.all()}
        return [
            ModeloValidationFinding(
                casilla_id=value.casilla_id,
                severity=BaseSeverity.ERROR,
                code="casilla-unknown",
                message=tr("filing.validation.schema_mismatch"),
                references_rules=(),
            )
            for value in draft.values
            if value.casilla_id not in known_ids
        ]

    def _validate_required(self, draft: ModeloDraft, collection: CasillaCollection) -> list[ModeloValidationFinding]:
        by_id = {v.casilla_id: v for v in draft.values}
        out: list[ModeloValidationFinding] = []
        for casilla in collection.all():
            if not casilla.required:
                continue
            value = by_id.get(casilla.casilla_id)
            if value is None or value.kind is ModeloValueKind.EMPTY or value.value is None:
                out.append(
                    ModeloValidationFinding(
                        casilla_id=casilla.casilla_id,
                        severity=BaseSeverity.ERROR,
                        code="casilla-required-missing",
                        message=tr("filing.validation.required_missing"),
                        references_rules=(),
                    ),
                )
        return out

    def _validate_ranges(self, draft: ModeloDraft, collection: CasillaCollection) -> list[ModeloValidationFinding]:
        out: list[ModeloValidationFinding] = []
        for value in draft.values:
            casilla = collection.get(value.casilla_id)
            if casilla is None or value.value is None:
                continue
            if not isinstance(value.value, Decimal | int):
                continue
            numeric = Decimal(value.value) if isinstance(value.value, int) else value.value
            if casilla.min_value is not None and numeric < casilla.min_value:
                out.append(self._range_finding(value.casilla_id, "below"))
            if casilla.max_value is not None and numeric > casilla.max_value:
                out.append(self._range_finding(value.casilla_id, "above"))
        return out

    @staticmethod
    def _range_finding(casilla_id: CasillaId, direction: str) -> ModeloValidationFinding:
        return ModeloValidationFinding(
            casilla_id=casilla_id,
            severity=BaseSeverity.ERROR,
            code="casilla-out-of-range",
            message=tr("filing.validation.out_of_range"),
            references_rules=(),
        )

    def _validate_formula_traces(
        self,
        draft: ModeloDraft,
        collection: CasillaCollection,
    ) -> list[ModeloValidationFinding]:
        out: list[ModeloValidationFinding] = []
        for value in draft.values:
            casilla = collection.get(value.casilla_id)
            if casilla is None:
                _logger.debug(
                    "formula trace check: casilla=%s in draft=%s not found in collection schema_version=%s; "
                    "casilla-unknown finding already emitted",
                    value.casilla_id,
                    draft.draft_id,
                    collection.schema_version,
                )
                continue
            if not casilla.formula_input_casilla_ids:
                if value.formula_trace_casilla_ids:
                    out.append(self._divergence(value.casilla_id))
                continue
            if value.kind is not ModeloValueKind.COMPUTED:
                out.append(self._divergence(value.casilla_id))
                continue
            if value.formula_trace_casilla_ids is None or set(value.formula_trace_casilla_ids) != set(
                casilla.formula_input_casilla_ids,
            ):
                out.append(self._divergence(value.casilla_id))
        return out

    @staticmethod
    def _divergence(casilla_id: CasillaId) -> ModeloValidationFinding:
        return ModeloValidationFinding(
            casilla_id=casilla_id,
            severity=BaseSeverity.ERROR,
            code="formula-divergence",
            message=tr("filing.validation.formula_divergence"),
            references_rules=(),
        )

    def _validate_deadline(self, draft: ModeloDraft) -> list[ModeloValidationFinding]:
        if self._deadline_checker is None:
            _logger.debug("deadline check skipped: no deadline_checker provided for modelo=%s", draft.modelo)
            return []
        status = self._deadline_checker.check(draft.modelo, draft.period)
        if not status.is_overdue:
            return []
        return [
            ModeloValidationFinding(
                casilla_id=None,
                severity=BaseSeverity.ERROR,
                code="filing-deadline-missed",
                message=tr("filing.validation.deadline_missed"),
                references_rules=(),
            ),
        ]


def apply_validation(
    draft: ModeloDraft,
    findings: tuple[ModeloValidationFinding, ...],
) -> ModeloDraft:
    """Return a :class:`ModeloDraft` copy of ``draft`` with ``findings`` and a fresh status.

    Status promotion logic:

    - Any ``ERROR`` → :attr:`ModeloDraftStatus.BORRADOR` (still
      blocking).
    - Any ``WARNING`` only → :attr:`ModeloDraftStatus.VALIDADO`.
    - No findings → :attr:`ModeloDraftStatus.LISTO_PARA_PRESENTAR`.
    """
    new_status = derive_validation_status(findings)
    return draft.model_copy(
        update={
            "findings": findings,
            "status": new_status,
            "updated_at": now(),
        },
    )


def derive_validation_status(
    findings: tuple[ModeloValidationFinding, ...],
) -> ModeloDraftStatus:
    """Return the machine validation status implied by ``findings``.

    Returns:
        The :class:`ModeloDraftStatus` derived from the severity of the findings.
    """
    has_error = any(f.severity is BaseSeverity.ERROR for f in findings)
    has_warning = any(f.severity is BaseSeverity.WARNING for f in findings)
    if has_error:
        return ModeloDraftStatus.BORRADOR
    if has_warning:
        return ModeloDraftStatus.VALIDADO
    return ModeloDraftStatus.LISTO_PARA_PRESENTAR
