"""Select fictional template inputs through the validated development authority."""

from datetime import date

from cadrumo.application.storage.calc_sheets.records import SheetAdministrativeFrame
from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.core.period import Period, is_administrative_period_token
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.snapshot import collect_snapshot_ref_ids
from cadrumo.domain.calculations.registry.temporal import select_revision

from .compiler.authority import compiled_bundled_authority


def load_workbook_template_source(
    modelo_id: str,
    *,
    revision_id: str,
    source_ref: str,
    preview_year: int,
    preview_period: str,
    on: date | None = None,
) -> WorkbookTemplateSource:
    """Resolve an exact authored design without changing filing-year admission.

    The canonical selector checks revision, inception, period and optional date.
    The filing support envelope is deliberately not supplied for this fictional
    development artifact; production snapshot construction is unchanged.
    """
    authority = compiled_bundled_authority()
    modelo = authority.modelo(modelo_id)
    revision = select_revision(
        modelo,
        filing_year=preview_year,
        period=preview_period,
        revision_id=revision_id,
        on=on,
    )
    legal_ids, source_ids = collect_snapshot_ref_ids(modelo, revision)
    design_sources = set(revision.source_refs)
    for layout in revision.form_layouts:
        design_sources.update(pin.source_ref for pin in layout.design_sources)
    if source_ref not in design_sources:
        raise RegistryValidationError("fictional template source does not belong to the selected revision")
    frame = (
        SheetAdministrativeFrame(filing_year=preview_year, code=preview_period)
        if is_administrative_period_token(preview_period)
        else Period.from_year_and_code(preview_year, preview_period)
    )
    return WorkbookTemplateSource(
        modelo_id=modelo.id,
        revision=revision,
        preview_frame=frame,
        source_ref=source_ref,
        legal={key: authority.catalogues.legal[key] for key in sorted(legal_ids)},
        sources={key: authority.catalogues.sources[key] for key in sorted(set(source_ids) | design_sources)},
    )
