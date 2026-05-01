"""``aeat rental`` sub-app: per-finca + per-contract register CLI (#454).

Five command groups (finca / contract / income / amortization / anexo-c)
back the rental hardening feature. Every command is wrapped by the
project-wide error boundary via ``decorate_typer_app(app)`` at the
root, so callbacks may raise :class:`AeatError` subclasses freely.

Trilingual surface: command help strings ship in Spanish (the
authoritative AEAT-domain language) with English fallbacks via the
shared :class:`Translatable` primitive in error messages.
"""

from __future__ import annotations

import typer

from .anexo_c import app as anexo_c_app
from .contract import app as contract_app
from .expense import app as expense_app
from .finca import app as finca_app
from .income import app as income_app

app = typer.Typer(
    name="rental",
    no_args_is_help=True,
    help=(
        "Registro de fincas y contratos de arrendamiento; deriva "
        "automáticamente las casillas de Anexo C del Modelo 100 a partir de "
        "los datos por finca / contrato (#454)."
    ),
)

app.add_typer(finca_app, name="finca", help="Gestión de fincas (alta, listado, detalle, baja).")
app.add_typer(contract_app, name="contract", help="Gestión de contratos de arrendamiento.")
app.add_typer(income_app, name="income", help="Registro de ingresos íntegros por contrato/ejercicio.")
app.add_typer(expense_app, name="expense", help="Registro de gastos deducibles por finca/ejercicio.")
app.add_typer(anexo_c_app, name="anexo-c", help="Cálculo y verificación de Anexo C M100 desde el registro.")


__all__ = ["app"]
