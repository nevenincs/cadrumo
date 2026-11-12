"""Apply Modelo 100 XML routing declarations to sign and comunidad branches."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from xml.etree.ElementTree import Element

from ...core.casilla_id import CasillaId
from ...core.decimal.coercion import coerce_decimal
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.filing.errors import FilingExportDesignIntegrityError, FilingExportValidationError
from .errors import ModeloApplicationError
from .export_refusal_doors import ExportRefusalReason, export_input_decision

#: Each family minimum the result block claims, and the occurrence that identifies whom it is claimed for.
_FAMILY_MINIMUM_ROWS: Mapping[str, str] = {
    "MDES": "DatosIdentificativos/Hijos/Hijo",
    "MASC": "DatosIdentificativos/Ascendientes/Ascendiente",
}
_MINIMUM_BLOCK_PATH = "DatosEconomicos/Resultados/MinimoPerFamRes"


def refuse_family_minimum_without_its_rows(document: Element) -> None:
    """Refuse a file claiming a descendant or ascendant minimum that identifies nobody.

    The schema makes the identifying block optional, so the file would validate. But the
    filer stated those relatives and the file would drop them while keeping the amount
    they justify, and no profile fact holds the name each occurrence requires.

    Args:
        document: The finished ``Declaracion`` element.

    Raises:
        ModeloApplicationError: A claimed minimum has no identifying occurrence.
    """
    for tag, row_path in _FAMILY_MINIMUM_ROWS.items():
        amount = (document.findtext(f"{_MINIMUM_BLOCK_PATH}/{tag}") or "").strip()
        claimed = coerce_decimal(amount) if amount else None
        if claimed is not None and not claimed.is_zero() and document.find(row_path) is None:
            raise ModeloApplicationError(
                translated_message="application.filing.export.errors.xml_value_required_missing",
                context={"box": f"/{row_path}"},
            )


def registry_modelo_100_xml_declarations() -> Mapping[str, str]:
    """Resolve the selected XML export declarations without a Python copy."""
    authority = governed_facts_in_scope()
    if authority is None:
        raise FilingExportDesignIntegrityError(
            "Modelo 100 XML export declarations require a generation-pinned authority operation",
            translated_message="errors.integrity.filing_export_modelo100_declarations_unpinned",
        )
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-100-xml-export-declarations-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=today_madrid(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise FilingExportDesignIntegrityError(
            "selected Modelo 100 XML declarations must be a mapping fact",
            translated_message="errors.integrity.filing_export_modelo100_declarations_not_mapping",
        )
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def modelo_100_comunidad_block(path: str, *, declarations: Mapping[str, str]) -> str | None:
    """Return the comunidad block ``path`` sits in, or ``None`` when it is elsewhere."""
    block_prefix = declarations.get("xml.comunidad.block_prefix")
    if block_prefix is None:
        raise FilingExportDesignIntegrityError(
            "registry-selected comunidad block prefix is missing",
            translated_message="errors.integrity.filing_export_modelo100_comunidad_prefix_missing",
        )
    if not path.startswith(block_prefix):
        return None
    return path[len(block_prefix) :].split("/", 1)[0]


def _modelo_100_casilla_is_populated(value: object) -> bool:
    """Return whether a CCAA casilla value selects a comunidad block.

    Calculated drafts carry zero-valued placeholders for every CCAA aggregate,
    sometimes as strings. Those placeholders are absent for the XSD ``choice``
    and must not select a block. A nonempty value that cannot be parsed remains
    populated so the later row formatter raises its typed validation error
    instead of silently suppressing the invalid input as if it were absent.
    """
    if value is None or value == "":
        return False
    amount = coerce_decimal(value)
    return amount is None or not amount.is_zero()


def modelo_100_unfiled_comunidad_paths(
    entries: tuple[XmlDictionaryEntry, ...],
    casilla_values: Mapping[CasillaId, object],
    *,
    declarations: Mapping[str, str],
) -> frozenset[str]:
    """Return the autonomic-deduction paths this draft must not write.

    Args:
        entries: Every dictionary row for the layout being rendered.
        casilla_values: Casilla values the draft carries.
        declarations: Generation-pinned XML routing declarations.

    Returns:
        Paths belonging to a comunidad the draft does not file, plus the shared
        total when no comunidad is filed at all.

    Raises:
        FilingExportValidationError: when the draft populates casillas belonging
            to more than one comunidad. The schema admits only one, so there is
            no correct rendering and picking one would launder the conflict.
    """
    own_casillas_by_block = _modelo_100_comunidad_casillas(entries, declarations=declarations)
    filed = _modelo_100_filed_comunidades(own_casillas_by_block, casilla_values)
    resident = _modelo_100_resident_comunidad(filed)
    unfiled = _modelo_100_unfiled_block_paths(entries, resident, declarations=declarations)
    if resident is None:
        unfiled.update(_modelo_100_shared_total_paths(entries, declarations=declarations))
    return frozenset(unfiled)


def _modelo_100_comunidad_casillas(
    entries: tuple[XmlDictionaryEntry, ...],
    *,
    declarations: Mapping[str, str],
) -> dict[str, set[CasillaId]]:
    """Collect each comunidad block's own casillas, excluding the shared total."""
    own_casillas_by_block: dict[str, set[CasillaId]] = {}
    for entry in entries:
        block = modelo_100_comunidad_block(entry.path, declarations=declarations)
        if block is None or entry.casilla_id is None:
            continue
        shared_total = declarations.get("xml.comunidad.shared_total_casilla")
        if shared_total is None:
            raise FilingExportDesignIntegrityError(
                "registry-selected comunidad total casilla is missing",
                translated_message="errors.integrity.filing_export_modelo100_comunidad_total_missing",
            )
        if entry.casilla_id != shared_total:
            own_casillas_by_block.setdefault(block, set()).add(entry.casilla_id)
    return own_casillas_by_block


def _modelo_100_filed_comunidades(
    own_casillas_by_block: Mapping[str, set[CasillaId]],
    casilla_values: Mapping[CasillaId, object],
) -> list[str]:
    """Return comunidad blocks with at least one populated own casilla."""
    return sorted(
        block
        for block, own in own_casillas_by_block.items()
        if any(_modelo_100_casilla_is_populated(casilla_values.get(casilla)) for casilla in own)
    )


def _modelo_100_resident_comunidad(filed: list[str]) -> str | None:
    """Require at most one filed comunidad and return the selected block."""
    if len(filed) > 1:
        raise FilingExportValidationError(
            "draft populates autonomic deductions for more than one comunidad "
            f"({', '.join(filed)}); a declaration may carry only one",
            translated_message="application.filing.export.errors.xml_comunidad_ambiguous",
            context={"comunidades": ", ".join(filed)},
            precondition_verdict=export_input_decision(ExportRefusalReason.COMUNIDAD_AMBIGUOUS),
        )
    return filed[0] if filed else None


def _modelo_100_unfiled_block_paths(
    entries: tuple[XmlDictionaryEntry, ...],
    resident: str | None,
    *,
    declarations: Mapping[str, str],
) -> set[str]:
    """Return all dictionary paths belonging to non-resident comunidad blocks."""
    return {
        entry.path
        for entry in entries
        if (block := modelo_100_comunidad_block(entry.path, declarations=declarations)) is not None
        and block != resident
    }


def _modelo_100_shared_total_paths(
    entries: tuple[XmlDictionaryEntry, ...],
    *,
    declarations: Mapping[str, str],
) -> frozenset[str]:
    """Return shared total paths when no comunidad block is filed."""
    shared_total = declarations.get("xml.comunidad.shared_total_casilla")
    if shared_total is None:
        raise FilingExportDesignIntegrityError(
            "registry-selected comunidad total casilla is missing",
            translated_message="errors.integrity.filing_export_modelo100_comunidad_total_missing",
        )
    return frozenset(entry.path for entry in entries if str(entry.casilla_id) == shared_total)


def modelo_100_sign_branch_value(
    entry: XmlDictionaryEntry,
    raw: object,
    *,
    declarations: Mapping[str, str],
) -> object | None:
    """Return ``raw`` for the sign branch it belongs to and omit the other.

    Args:
        entry: Dictionary row being rendered.
        raw: Value resolved for the row's casilla.
        declarations: Generation-pinned XML sign-branch declarations.

    Returns:
        ``raw`` when the row's branch matches its sign, ``None`` when the row is
        the opposite branch, and ``raw`` unchanged for every other row.

        A value that will not coerce carries no sign to route on, so it is read
        as zero for the purpose of choosing a branch. This selects a branch
        rather than validating a value: deciding what an uncoercible amount
        means is :func:`~cadrumo.application.filing.export_xml_dictionary_values.format_xml_dictionary_value`'s job,
        and it is the job
        it does for every other casilla. Without the default, ``coerce_decimal``
        answers ``None`` and the comparison below raises ``TypeError`` on the
        export path.
    """
    negative_field = declarations.get("xml.sign.negative_field")
    non_negative_field = declarations.get("xml.sign.non_negative_field")
    if negative_field is None or non_negative_field is None:
        raise FilingExportDesignIntegrityError(
            "registry-selected XML sign declarations are incomplete",
            translated_message="errors.integrity.filing_export_modelo100_sign_declarations_incomplete",
        )
    negative_branch = entry.field_id == negative_field
    if not negative_branch and entry.field_id != non_negative_field:
        return raw
    amount = coerce_decimal(raw, default=Decimal("0"))
    return raw if (amount < 0) is negative_branch else None
