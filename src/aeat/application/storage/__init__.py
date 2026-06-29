"""Application storage namespace for calc-sheet export planning.

This package is a namespace container. Callers must import from the subpackages
directly (e.g. ``aeat.application.storage.calc_sheets``); nothing is re-exported
at this level by design. Exporting here would couple callers to the internal
subpackage layout and undermine the layered-import discipline.

The calc-sheet subpackage builds renderer-neutral workbook plans and offline
XLSX/JSON payloads. Runtime encrypted persistence remains owned by the storage
adapter and domain repository layers; operator-directed workbook bytes are an
explicit export surface, not canonical application state.

See Also:
    :mod:`aeat.application.storage.calc_sheets`
        Registry-backed workbook plan engine and offline export surface.
    :class:`aeat.application.storage.calc_sheets.SheetExportPlan`
        Renderer-neutral workbook contract shared by offline and Google Sheets
        materializers.
    :func:`aeat.application.storage.calc_sheets.build_export_plan`
        Pure plan builder that consumes a
        :class:`aeat.domain.calculations.registry.RegistrySnapshot`.
    :func:`aeat.application.storage.calc_sheets.serialize_offline_export`
        Operator-directed XLSX and evidence-sidecar serializer.
    :func:`aeat.adapters.outbound.google._calc_sheets_apply.apply_export_plan`
        Remote Google Sheets materializer for the same export plan.
    :class:`aeat.adapters.persistence.storage.sql.SecureObjectRepository`
        Encrypted canonical persistence boundary that this namespace does not
        replace.
"""
