"""The steps a refused Modelo 100 estimate serves for getting the quarterly declarations it reads.

The estimate reads the year's calculated quarterly declarations. When there is
none, the way on is to create the first quarter's; when the quarters exist and
none is calculated, it is to calculate the earliest; when a calculated quarter
cannot yet give a box the estimate reads, it is to open that quarter, whose own
form says what it still lacks. Each is served as a closed kind with the
declaration it concerns and the words that offer it, in the language the
refusal's own sentence is in, so a frontend does what it already knows for that
kind and states the words as served. A step is chosen where the refusal is
raised and worded when its detail is built.
"""

from __future__ import annotations

from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.period import Period
from ...domain.modelos.work_unit import WorkUnit
from ..operations.next_step import (
    OperationCalculateWorkStepV1,
    OperationCreateWorkStepV1,
    OperationNextStepWording,
    OperationOpenWorkStepV1,
    OperationVerifyWorkStepV1,
)
from .work_form_wording import modelo_number, period_words

_CREATE_WORK_LOCALE_KEY: Final[str] = "application.modelo.projection_words.next_step.create_work"
_CALCULATE_WORK_LOCALE_KEY: Final[str] = "application.modelo.projection_words.next_step.calculate_work"
_OPEN_WORK_LOCALE_KEY: Final[str] = "application.modelo.projection_words.next_step.open_work"
_VERIFY_WORK_LOCALE_KEY: Final[str] = "application.modelo.projection_words.next_step.verify_work"


def create_work_step(*, modelo: str, period: Period) -> OperationNextStepWording:
    """Offer creating the declaration of ``modelo`` for ``period``."""

    def worded(language: OutputLanguage) -> OperationCreateWorkStepV1:
        return OperationCreateWorkStepV1(
            modelo=modelo,
            filing_year=period.filing_year,
            period_code=str(period.code),
            words=tr(
                _CREATE_WORK_LOCALE_KEY,
                modelo=modelo_number(modelo, language),
                period=period_words(period, language),
                locale=language.value,
            ),
        )

    return worded


def calculate_work_step(unit: WorkUnit) -> OperationNextStepWording:
    """Offer calculating the declaration ``unit`` holds."""

    def worded(language: OutputLanguage) -> OperationCalculateWorkStepV1:
        return OperationCalculateWorkStepV1(
            work_unit_id=unit.work_unit_id,
            words=tr(
                _CALCULATE_WORK_LOCALE_KEY,
                modelo=modelo_number(str(unit.modelo), language),
                period=period_words(unit.period, language),
                locale=language.value,
            ),
        )

    return worded


def verify_work_step(unit: WorkUnit) -> OperationNextStepWording:
    """Offer checking the declaration ``unit`` holds, which verifies its calculation."""

    def worded(language: OutputLanguage) -> OperationVerifyWorkStepV1:
        return OperationVerifyWorkStepV1(
            work_unit_id=unit.work_unit_id,
            words=tr(
                _VERIFY_WORK_LOCALE_KEY,
                modelo=modelo_number(str(unit.modelo), language),
                period=period_words(unit.period, language),
                locale=language.value,
            ),
        )

    return worded


def open_work_step(unit: WorkUnit) -> OperationNextStepWording:
    """Offer opening the declaration ``unit`` holds."""

    def worded(language: OutputLanguage) -> OperationOpenWorkStepV1:
        return OperationOpenWorkStepV1(
            work_unit_id=unit.work_unit_id,
            words=tr(
                _OPEN_WORK_LOCALE_KEY,
                modelo=modelo_number(str(unit.modelo), language),
                period=period_words(unit.period, language),
                locale=language.value,
            ),
        )

    return worded


__all__ = ["calculate_work_step", "create_work_step", "open_work_step", "verify_work_step"]
