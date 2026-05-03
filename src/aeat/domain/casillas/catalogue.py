"""Catalogue loading, saving, and verification helpers.

Persistence layer for :class:`~aeat.domain.casillas.models.CasillaCatalogue`:
resolves the corpus root from configuration, validates the on-disk
JSON against the strict pydantic schema, and runs structural
verification (authoritative Spanish text on label/help, review
metadata when canonical, intra-catalogue cross-reference resolution).

The verification pass is the trust boundary between operator-edited
JSON and the rest of the system; failures are reported as
:exc:`~aeat.domain.casillas.errors.VerifyError` instances so callers
can surface every problem in a single batch.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from ...core.config import PROJECT_ROOT, load_settings
from ...core.i18n import TranslationError, require_authoritative
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
"""Default on-disk root for committed casilla catalogue JSON files."""
_log = get_logger(__name__)


def _catalogue_root(root: Path | None) -> Path:
    """Resolve the effective corpus root, falling back to settings."""
    if root is not None:
        return root
    settings = load_settings()
    return settings.aeat_casillas_root


def catalogue_path(modelo: str, period: str, root: Path | None = None) -> Path:
    """Return the canonical on-disk path for a modelo / period catalogue.

    Args:
        modelo: Modelo identifier (e.g. ``"MODELO_303"``); folded to
            lowercase for the directory component.
        period: Period label (e.g. ``"2025Q4"`` or ``"2025"``).
        root: Optional corpus-root override; defaults to
            :attr:`Settings.aeat_casillas_root` from
            :func:`aeat.core.config.load_settings`.

    Returns:
        The expected ``<root>/<modelo>/<period>.json`` path.
    """
    return _catalogue_root(root) / modelo.lower() / f"{period}.json"


def iter_casillas(catalogue: CasillaCatalogue) -> Iterator[CasillaRecord]:
    """Iterate over the records in a catalogue.

    Args:
        catalogue: Catalogue to iterate.

    Returns:
        Iterator over the catalogue's records in declared order.
    """
    return iter(catalogue.records)


def verify_casillas(catalogue: CasillaCatalogue) -> tuple[VerifyError, ...]:
    """Return structured verification failures for a catalogue.

    Runs every structural invariant the corpus must satisfy:
    authoritative Spanish text on ``label`` and ``help``, review
    metadata when the project is configured to require it, and that
    every ``references_casillas`` entry points at another record in
    the same catalogue.

    Args:
        catalogue: Catalogue to verify.

    Returns:
        Tuple of :exc:`VerifyError` instances describing every
        violation. Empty when the catalogue is well-formed.
    """
    errors: list[VerifyError] = []
    review_required = load_settings().aeat_casillas_review_required
    valid_ids = {record.casilla_id for record in catalogue.records}
    _log.debug(
        "verifying casilla catalogue %s/%s (%d records)",
        catalogue.modelo,
        catalogue.period,
        len(catalogue.records),
    )

    def _record_error(err: VerifyError) -> None:
        _log.debug(
            "casilla verify error %s/%s casilla=%s: %s",
            err.modelo,
            err.period,
            err.casilla_id,
            err.message,
        )
        errors.append(err)

    for record in catalogue.records:
        try:
            require_authoritative(record.label, domain="aeat")
        except TranslationError as exc:
            _record_error(
                MissingFieldError(
                    modelo=record.modelo,
                    period=record.period,
                    casilla_id=record.casilla_id,
                    message=f"label is missing authoritative Spanish text: {exc}",
                )
            )
        try:
            require_authoritative(record.help, domain="aeat")
        except TranslationError as exc:
            _record_error(
                MissingFieldError(
                    modelo=record.modelo,
                    period=record.period,
                    casilla_id=record.casilla_id,
                    message=f"help is missing authoritative Spanish text: {exc}",
                )
            )

        if review_required:
            if not record.definition_reviewed_by.strip():
                _record_error(
                    UnreviewedRecordError(
                        modelo=record.modelo,
                        period=record.period,
                        casilla_id=record.casilla_id,
                        message="definition_reviewed_by is required for canonical records",
                    )
                )
            if record.definition_reviewed_at is None:
                _record_error(
                    UnreviewedRecordError(
                        modelo=record.modelo,
                        period=record.period,
                        casilla_id=record.casilla_id,
                        message="definition_reviewed_at is required for canonical records",
                    )
                )

        for reference in record.references_casillas:
            if reference not in valid_ids:
                _record_error(
                    CrossReferenceError(
                        modelo=record.modelo,
                        period=record.period,
                        casilla_id=record.casilla_id,
                        message=f"references unknown casilla {reference}",
                    )
                )

    if errors:
        _log.warning(
            "casilla catalogue %s/%s failed verification: %d error(s)",
            catalogue.modelo,
            catalogue.period,
            len(errors),
        )
    return tuple(errors)


def load_casillas(modelo: str, period: str, root: Path | None = None) -> CasillaCatalogue:
    """Load and validate a canonical casilla catalogue from disk.

    Reads the JSON file resolved by :func:`catalogue_path`, parses it
    against :class:`CasillaCatalogue`, and runs
    :func:`verify_casillas`. Any validation, parse, or structural
    failure raises :exc:`CasillaParseError` so the caller cannot
    accidentally consume partial data.

    Args:
        modelo: Modelo identifier (e.g. ``"MODELO_303"``).
        period: Period label.
        root: Optional corpus-root override.

    Returns:
        The validated :class:`CasillaCatalogue`.

    Raises:
        CasillaParseError: If the file is missing, the JSON is
            malformed, the schema rejects it, or any structural
            invariant fails.
    """
    path = catalogue_path(modelo, period, root=root)
    if not path.exists():
        raise CasillaParseError(path, "catalogue file does not exist")

    _log.debug("loading casilla catalogue %s/%s from %s", modelo, period, path)
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
    _log.debug("loaded casilla catalogue %s/%s (%d records)", modelo, period, len(catalogue.records))
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
    _log.debug("saved casilla catalogue to %s", path)


def write_extract_draft(catalogue: CasillaCatalogue) -> Path:
    """Write a draft extraction payload to a temporary JSON file.

    Args:
        catalogue: Draft catalogue produced by an extraction pipeline.

    Returns:
        Path to the temporary JSON file.
    """
    return _write_temp_catalogue(catalogue, suffix="extract")


def write_translate_draft(catalogue: CasillaCatalogue) -> Path:
    """Write a draft translation payload to a temporary JSON file.

    Args:
        catalogue: Draft catalogue produced by a translation pipeline.

    Returns:
        Path to the temporary JSON file.
    """
    return _write_temp_catalogue(catalogue, suffix="translate")


def _write_temp_catalogue(catalogue: CasillaCatalogue, *, suffix: str) -> Path:
    """Persist a catalogue to a named temporary JSON file.

    Internal helper shared by the ``extract`` and ``translate`` draft
    writers. Cleans up the partial file when serialisation fails so
    the temp directory does not accumulate half-written drafts.
    """
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
    except (OSError, ValueError, TypeError):
        if draft_path is not None:
            _log.warning(
                "draft serialisation failed for %s/%s suffix=%s; removing partial file %s",
                catalogue.modelo,
                catalogue.period,
                suffix,
                draft_path,
                exc_info=True,
            )
            draft_path.unlink(missing_ok=True)
        raise
    assert draft_path is not None
    _log.debug("wrote casilla draft file to %s", draft_path)
    return draft_path


def attach_draft_provenance(
    catalogue: CasillaCatalogue,
    *,
    provenance: LLMDraftProvenance,
) -> CasillaCatalogue:
    """Return a new catalogue with provenance set on every record.

    Args:
        catalogue: Source catalogue.
        provenance: :class:`LLMDraftProvenance` to attach to every
            record's ``llm_draft_provenance`` field.

    Returns:
        A copy of ``catalogue`` with the provenance applied. The
        input is not mutated.
    """
    records = tuple(record.model_copy(update={"llm_draft_provenance": provenance}) for record in catalogue.records)
    return catalogue.model_copy(update={"records": records})
