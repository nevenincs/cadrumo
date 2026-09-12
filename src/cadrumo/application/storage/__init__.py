"""Application storage namespace for calc-sheet export planning.

The initializer is inert; import contracts from their defining modules.

The calc-sheet subpackage builds renderer-neutral workbook plans for the live
Google Sheets transport. Runtime encrypted persistence remains owned by the storage
adapter and domain repository layers; operator-directed workbook bytes are an
explicit export surface, not canonical application state.

See Also:
    :mod:`application.storage.calc_sheets`
        Registry-backed workbook plan engine and live Sheets export surface.
    :class:`application.storage.calc_sheets.SheetExportPlan`
        Renderer-neutral workbook contract consumed by Google Sheets.
    :func:`application.storage.calc_sheets.build_export_plan`
        Pure plan builder that consumes a
        :class:`domain.calculations.registry.RegistrySnapshot`.
    :func:`adapters.outbound.google.apply_export_plan`
        Remote Google Sheets materializer for the same export plan.
    :class:`adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
        Encrypted canonical persistence boundary that this namespace does not
        replace.
"""
