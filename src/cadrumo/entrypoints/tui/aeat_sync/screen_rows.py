"""Safe row protocols shared by the AEAT Sync presentation owners."""

from typing import Protocol

from ....application.operations.models import OperationDefinitionId
from ....application.operator_actions.models import ActionReference
from ....core.filing_year import FilingYear
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode


class OperationRow(Protocol):
    """Safe operation axes which S397 already admitted into a row."""

    supported_actions: tuple[ActionReference, ...]
    supported_operations: tuple[OperationDefinitionId, ...]


class DeclarationRow(Protocol):
    """Public declaration coordinate needed for a safe display label."""

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
