"""Catalogue loading, saving, and verification helpers."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from ...core.config import PROJECT_ROOT, load_settings
from ...core.i18n import require_authoritative
from ...core.logging import get_logger
from .errors import (
    CasillaParseError,
    CrossReferenceError,
    MissingFieldError,
    UnreviewedRecordError,
    VerifyError,
)
from .models import CasillaCatalogue, CasillaRecord, LLMDraftProvenance

DEFAULT_CASILLAS_ROOT = PROJECT_ROOT / "corpus" / "casillas"
_log = get_logger(__name__)


def _catalogue_root(root: Path | None) -> Path:
    """Resolve the effective corpus root."""
    if root is not None:
        return root
    settings = load_settings()
    return settings.aeat_casillas_root


def catalogue_path(modelo: str, period: str, root: Path | None = None) -> Path:
    """Return the canonical on-disk path for a modelo/period catalogue."""
    return _catalogue_root(root) / modelo.lower() / f"{period}.json"


def iter_casillas(catalogue: CasillaCatalogue) -> Iterator[CasillaRecord]:
    """Iterate over the records in a catalogue."""
    return iter(catalogue.records)


def verify_casillas(catalogue: CasillaCatalogue) -> tuple[VerifyError, ...]:
    """Return structured verification failures for a catalogue."""
    errors: list[VerifyError] = []
    review_required = load_settings().aeat_casillas_review_required
    valid_ids = {record.casilla_id for record in catalogue.records}

    for record in catalogue.records:
        try:
            require_authoritative(record.label, domain="aeat")
        except Exception as exc:
            errors.append(
                MissingFieldError(
                    modelo=record.modelo,
                    period=record.period,
                    casilla_id=record.casilla_id,
                    message=f"label is missing authoritative Spanish text: {exc}",
                )
            )
        try:
            require_authoritative(record.help, domain="aeat")
        except Exception as exc:
            errors.append(
                MissingFieldError(
                    modelo=record.modelo,
                    period=record.period,
                    casilla_id=record.casilla_id,
                    message=f"help is missing authoritative Spanish text: {exc}",
                )
            )

        if review_required:
            if not record.definition_reviewed_by.strip():
                errors.append(
                    UnreviewedRecordError(
                        modelo=record.modelo,
                        period=record.period,
                        casilla_id=record.casilla_id,
                        message="definition_reviewed_by is required for canonical records",
                    )
                )
            if record.definition_reviewed_at is None:
                errors.append(
                    UnreviewedRecordError(
                        modelo=record.modelo,
                        period=record.period,
                        casilla_id=record.casilla_id,
                        message="definition_reviewed_at is required for canonical records",
                    )
                )

        for reference in record.references_casillas:
            if reference not in valid_ids:
                errors.append(
                    CrossReferenceError(
                        modelo=record.modelo,
                        period=record.period,
                        casilla_id=record.casilla_id,
                        message=f"references unknown casilla {reference}",
                    )
                )

    return tuple(errors)


def load_casillas(modelo: str, period: str, root: Path | None = None) -> CasillaCatalogue:
    """Load and validate a canonical casilla catalogue."""
    path = catalogue_path(modelo, period, root=root)
    if not path.exists():
        raise CasillaParseError(path, "catalogue file does not exist")

    try:
        catalogue = CasillaCatalogue.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise CasillaParseError(path, str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise CasillaParseError(path, f"invalid JSON: {exc}") from exc

    errors = verify_casillas(catalogue)
    if errors:
        summary = "; ".join(str(error) for error in errors)
        raise CasillaParseError(path, summary)
    return catalogue


def save_casillas(catalogue: CasillaCatalogue, root: Path | None = None) -> None:
    """Persist a catalogue to its canonical JSON path.

    Args:
        catalogue: Catalogue to persist.
        root: Optional corpus root override.

    Raises:
        CasillaParseError: If the catalogue fails verification.
    """
    errors = verify_casillas(catalogue)
    if errors:
        path = catalogue_path(catalogue.modelo, catalogue.period, root=root)
        summary = "; ".join(str(error) for error in errors)
        raise CasillaParseError(path, summary)

    path = catalogue_path(catalogue.modelo, catalogue.period, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = catalogue.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    _log.info("saved casilla catalogue to %s", path)


def write_extract_draft(catalogue: CasillaCatalogue) -> Path:
    """Write a draft extraction payload to a temporary JSON file."""
    return _write_temp_catalogue(catalogue, suffix="extract")


def write_translate_draft(catalogue: CasillaCatalogue) -> Path:
    """Write a draft translation payload to a temporary JSON file."""
    return _write_temp_catalogue(catalogue, suffix="translate")


def _write_temp_catalogue(catalogue: CasillaCatalogue, *, suffix: str) -> Path:
    """Persist a catalogue to a named temporary file."""
    prefix = f"aeat-casillas-{catalogue.modelo.lower()}-{catalogue.period}-{suffix}-"
    draft_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=prefix,
            delete=False,
        ) as handle:
            draft_path = Path(handle.name)
            json.dump(catalogue.model_dump(mode="json"), handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
    except Exception:
        if draft_path is not None:
            draft_path.unlink(missing_ok=True)
        raise
    assert draft_path is not None
    _log.info("wrote casilla draft file to %s", draft_path)
    return draft_path


def attach_draft_provenance(
    catalogue: CasillaCatalogue,
    *,
    provenance: LLMDraftProvenance,
) -> CasillaCatalogue:
    """Return a new catalogue with provenance set on every record."""
    records = tuple(record.model_copy(update={"llm_draft_provenance": provenance}) for record in catalogue.records)
    return catalogue.model_copy(update={"records": records})
