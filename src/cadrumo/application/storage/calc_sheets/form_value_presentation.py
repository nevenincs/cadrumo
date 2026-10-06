"""Human date presentation derived from explicit registry wire-value contracts."""

from ....domain.calculations.registry.export_value_policy import ExportValuePolicy
from ....domain.calculations.registry.schema import ModeloRevision


def compact_date_casillas(revision: ModeloRevision) -> frozenset[str]:
    """Find declared YYYYMMDD text values without guessing from labels or digits.

    Validated export records require the year/month/day components to be a
    complete adjacent group addressing the same semantic value.
    """
    return frozenset(
        str(field.casilla_id)
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id is not None and field.value_policy is ExportValuePolicy.YYYYMMDD_TEXT_YEAR
    )


def compact_date_expression(reference: str) -> str:
    """Display a calendar-valid compact date; never normalize an invalid day.

    DATE rolls February 30 into March. Round-trip validation prevents that
    silent correction. The caller handles missing values separately.
    """
    parsed = f"DATE(VALUE(LEFT({reference},4)),VALUE(MID({reference},5,2)),VALUE(RIGHT({reference},2)))"
    valid = f'AND(LEN({reference})=8,TEXT({parsed},"yyyymmdd")={reference}&"")'
    return f'IFERROR(IF({valid},TEXT({parsed},"dd/mm/yyyy"),"Fecha no válida"),"Fecha no válida")'
