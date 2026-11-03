"""Profile facts that elect the cash imputation criterion for activity income and expense.

RIRPF art. 7.2 opens the cobros y pagos election only to a taxpayer in an
estimacion directa regime who does not keep Codigo de Comercio accounting, so
the criterion, the regime and the accounting travel together, each dated to the
whole ejercicio it governs.
"""

from __future__ import annotations

from datetime import date

from ..values import UserProfileFact


def cash_criterion_facts(*years: int, estimation_regime: str = "directa_simplificada") -> tuple[UserProfileFact, ...]:
    """Declare the cobros y pagos criterion, with the regime and accounting it requires, for each ejercicio.

    Either estimacion directa modality admits the election; ``estimation_regime`` names the one
    the caller's figures assume, since the simplified modality adds the art. 30.2.4.a provision
    to Modelo 130 box 02.
    """
    facts: list[UserProfileFact] = []
    for year in years:
        window = {"valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
        for path, value in (
            ("irpf.activity_income_imputation_criterion", "cobros_y_pagos"),
            ("irpf.estimation_regime", estimation_regime),
            ("irpf.codigo_comercio_accounting", False),
        ):
            facts.append(UserProfileFact.model_validate({"path": path, "value": value, **window}))
    return tuple(facts)
