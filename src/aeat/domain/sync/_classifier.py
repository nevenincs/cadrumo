"""Semantic classifier that emits typed divergence payloads.

The classifier compares a ``local`` pydantic snapshot against a
``live`` pydantic snapshot field-by-field and emits
:class:`DivergencePayload` members. Each emitted payload is then
wrapped into a :class:`DivergenceRecord` whose classification is
assigned via the static ``_CLASSIFICATION_TABLE`` in
:mod:`aeat.domain.sync._divergence`.

Structural dict-diffs are intentionally NOT supported: the whole
point of the classifier is to carry semantic meaning into the
healing dispatcher.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from ...core.logging import get_logger
from ._divergence import (
    CasillaAddedWithDefault,
    CasillaRemoved,
    CasillaTypeChanged,
    DivergencePayload,
    DivergenceRecord,
    FilingStatusChanged,
    FormulaChanged,
    LabelEsChanged,
    LabelTranslationAdded,
    PortalUrlChanged,
    UnknownShape,
    VigenciaExtended,
    classify_kind,
)
from ._protocols import ModeloIdentifier
from ._wire import (
    WireFilingHistory,
    WireModeloDefinition,
    WirePortalManifest,
)

_LOGGER = get_logger(__name__)


class DivergenceClassifier:
    """Produce :class:`DivergenceRecord` sequences from paired wire payloads."""

    def diff_modelo(
        self,
        *,
        local: WireModeloDefinition,
        live: WireModeloDefinition,
    ) -> tuple[DivergenceRecord, ...]:
        """Compare two modelo definitions and emit divergence records.

        Args:
            local: The local authoritative snapshot.
            live: The freshly-fetched live snapshot.

        Returns:
            A tuple of :class:`DivergenceRecord` describing every
            semantic delta. Empty tuple when the two shapes are equal.
        """
        payloads: list[DivergencePayload] = []

        if live.vigencia_end > local.vigencia_end and live.vigencia_start == local.vigencia_start:
            payloads.append(
                VigenciaExtended(
                    modelo=live.modelo,
                    previous_end=local.vigencia_end,
                    new_end=live.vigencia_end,
                )
            )

        local_by_id = {c.id: c for c in local.casillas}
        live_by_id = {c.id: c for c in live.casillas}

        for removed_id in sorted(local_by_id.keys() - live_by_id.keys()):
            payloads.append(CasillaRemoved(modelo=live.modelo, casilla_id=removed_id))

        for added_id in sorted(live_by_id.keys() - local_by_id.keys()):
            added = live_by_id[added_id]
            if added.default is not None:
                payloads.append(
                    CasillaAddedWithDefault(
                        modelo=live.modelo,
                        casilla_id=added.id,
                        default=added.default,
                        label=added.label,
                    )
                )
            else:
                payloads.append(
                    UnknownShape(detail=f"casilla {added.id} added with no default"),
                )

        for common_id in sorted(local_by_id.keys() & live_by_id.keys()):
            local_casilla = local_by_id[common_id]
            live_casilla = live_by_id[common_id]
            if local_casilla.type_ != live_casilla.type_:
                payloads.append(
                    CasillaTypeChanged(
                        modelo=live.modelo,
                        casilla_id=common_id,
                        previous_type=local_casilla.type_,
                        new_type=live_casilla.type_,
                    )
                )
            if local_casilla.formula != live_casilla.formula:
                payloads.append(
                    FormulaChanged(
                        modelo=live.modelo,
                        casilla_id=common_id,
                        previous_formula=local_casilla.formula,
                        new_formula=live_casilla.formula,
                    )
                )
            local_es = local_casilla.label.get("es")
            live_es = live_casilla.label.get("es")
            if local_es and live_es and local_es != live_es:
                payloads.append(
                    LabelEsChanged(
                        modelo=live.modelo,
                        casilla_id=common_id,
                        previous_es=local_es,
                        new_es=live_es,
                    )
                )
            local_langs = set(local_casilla.label.keys())
            live_langs = set(live_casilla.label.keys())
            for new_lang in sorted(live_langs - local_langs):
                value = live_casilla.label.get(new_lang)
                if value:
                    payloads.append(
                        LabelTranslationAdded(
                            modelo=live.modelo,
                            casilla_id=common_id,
                            language=new_lang,
                            value=value,
                        )
                    )

        return tuple(self._wrap(payload, modelo=str(live.modelo)) for payload in payloads)

    def diff_portal_manifest(
        self,
        *,
        local: WirePortalManifest,
        live: WirePortalManifest,
    ) -> tuple[DivergenceRecord, ...]:
        """Emit divergence records for changes in the portal manifest."""
        payloads: list[DivergencePayload] = []
        local_by_modelo = {link.modelo: link for link in local.links}
        live_by_modelo = {link.modelo: link for link in live.links}
        for key in sorted(
            local_by_modelo.keys() & live_by_modelo.keys(),
            key=lambda k: str(k) if k is not None else "",
        ):
            if local_by_modelo[key].url != live_by_modelo[key].url:
                payloads.append(
                    PortalUrlChanged(
                        portal=live.portal,
                        previous_url=local_by_modelo[key].url,
                        new_url=live_by_modelo[key].url,
                    )
                )
        return tuple(self._wrap(payload, modelo=None) for payload in payloads)

    def diff_filing_history(
        self,
        *,
        local: WireFilingHistory,
        live: WireFilingHistory,
    ) -> tuple[DivergenceRecord, ...]:
        """Emit divergence records for changes in a filing history."""
        records: list[DivergenceRecord] = []
        local_by_key = {(e.modelo, e.period): e for e in local.entries}
        live_by_key = {(e.modelo, e.period): e for e in live.entries}
        for key in sorted(local_by_key.keys() & live_by_key.keys()):
            if local_by_key[key].status != live_by_key[key].status:
                payload = FilingStatusChanged(
                    modelo=key[0],
                    period=key[1],
                    previous_status=local_by_key[key].status,
                    new_status=live_by_key[key].status,
                )
                records.append(self._wrap(payload, modelo=str(key[0])))
        return tuple(records)

    def _wrap(self, payload: DivergencePayload, *, modelo: str | None) -> DivergenceRecord:
        classification = classify_kind(payload.kind)
        _LOGGER.debug(
            "classified divergence kind=%s classification=%s",
            payload.kind.value,
            classification.value,
        )
        return DivergenceRecord(
            record_id=uuid.uuid4().hex,
            detected_at=datetime.now(tz=UTC),
            modelo=ModeloIdentifier(modelo) if modelo is not None else None,
            classification=classification,
            payload=payload,
        )
