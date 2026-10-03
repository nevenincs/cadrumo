"""Public rendered control identities used by installed income-tax acceptance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    pass


#: The workbench line where its refusals and settled operations are reported.
WORKBENCH_NOTICE: Final = "#wb-notice"


#: The workbench's casilla list, present whenever the workbench is the top screen.
WORKBENCH_LIST: Final = "#wb-list"


#: The workbench's line naming the next step and the key that performs it.
WORKBENCH_NEXT: Final = "#wb-next"


#: The accept control of the shared confirmation dialog, which the workbench shows
#: before recalculating a declaration last calculated elsewhere that holds values
#: nobody is recorded as having entered.
WORKBENCH_AT_RISK_PROCEED: Final = "#btn-confirm-accept"


_EXPORT_PATH: Final = "#export-path"


_EXPORT_RESULT_CLOSE: Final = "#modelo-export-result-close"


#: The close control of the statement of which boxes a recalculation changed.
_RESULT_STATEMENT_CLOSE: Final = "#result-close"


#: The workbench key that runs the step it offers next.
_NEXT_STEP_KEY: Final = "f8"


#: The workbench key that opens the review of the staged changes.
_REVIEW_KEY: Final = "R"


#: The key the next-step line shows beside each step a journey waits on.  A
#: verified declaration is offered its export file first, and recording the
#: filing with the next-step key after it.
_OFFERED_STEP_KEYS: Final[Mapping[str, str]] = {
    "apply": "R",
    "confirm": "n",
    "export": "e",
    "record": "F8",
    "verify": "F8",
}


#: The catalogue action that names a step on the next-step line, where it differs from the step's name.
_OFFERED_STEP_ACTIONS: Final[Mapping[str, str]] = {"record": "record_after_file"}


#: Stands in for a count while the next-step line is turned into a pattern.
_COUNT_PLACEHOLDER: Final = "\ue000"


#: Stands in for a date while the next-step line is turned into a pattern.
_DATE_PLACEHOLDER: Final = "\ue001"


_BULK_TICK: Final = "#bulk-tick"


_BULK_CONFIRM: Final = "#bulk-confirm"


_REVIEW_APPLY: Final = "#review-apply"


_REVIEW_ACKNOWLEDGE: Final = "#review-acknowledge"


_REVIEW_FINDINGS: Final = "#review-findings"


#: The greeting the first workbench of a session shows on its notice line.
_FIRST_OPEN_GREETING: Final = "tui.modelo.workbench.legend.first_open"
