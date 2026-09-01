"""Import-light tuple composer for all non-work Modelo CommandSpec families."""

from __future__ import annotations

from ._modelo_nonwork_bindings_command_specs import MODELO_NONWORK_BINDINGS_COMMAND_SPECS
from ._modelo_nonwork_calculations_command_specs import MODELO_NONWORK_CALCULATION_COMMAND_SPECS
from ._modelo_nonwork_discovery_command_specs import MODELO_NONWORK_DISCOVERY_COMMAND_SPECS
from ._modelo_nonwork_filing_record_command_specs import MODELO_NONWORK_FILING_RECORD_COMMAND_SPECS
from ._modelo_nonwork_groups_command_specs import MODELO_NONWORK_GROUP_COMMAND_SPECS
from ._modelo_nonwork_iva_wallet_command_specs import MODELO_NONWORK_IVA_WALLET_COMMAND_SPECS
from ._modelo_nonwork_m036_command_specs import MODELO_NONWORK_M036_COMMAND_SPECS
from ._modelo_nonwork_m145_command_specs import MODELO_NONWORK_M145_COMMAND_SPECS
from ._modelo_nonwork_reconcile_command_specs import MODELO_NONWORK_RECONCILE_COMMAND_SPECS
from ._modelo_nonwork_review_package_command_specs import MODELO_NONWORK_REVIEW_PACKAGE_COMMAND_SPECS
from ._modelo_nonwork_verification_report_command_specs import MODELO_NONWORK_VERIFICATION_REPORT_COMMAND_SPECS
from ._modelo_nonwork_work_amend_command_specs import MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS
from ._modelo_nonwork_work_preview_command_specs import MODELO_NONWORK_WORK_PREVIEW_COMMAND_SPECS
from .command_spec import CommandSpec

MODELO_NONWORK_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *MODELO_NONWORK_GROUP_COMMAND_SPECS,
    *MODELO_NONWORK_DISCOVERY_COMMAND_SPECS,
    *MODELO_NONWORK_BINDINGS_COMMAND_SPECS,
    *MODELO_NONWORK_CALCULATION_COMMAND_SPECS,
    *MODELO_NONWORK_FILING_RECORD_COMMAND_SPECS,
    *MODELO_NONWORK_VERIFICATION_REPORT_COMMAND_SPECS,
    *MODELO_NONWORK_RECONCILE_COMMAND_SPECS,
    *MODELO_NONWORK_M036_COMMAND_SPECS,
    *MODELO_NONWORK_M145_COMMAND_SPECS,
    *MODELO_NONWORK_WORK_PREVIEW_COMMAND_SPECS,
    *MODELO_NONWORK_IVA_WALLET_COMMAND_SPECS,
    *MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS,
    *MODELO_NONWORK_REVIEW_PACKAGE_COMMAND_SPECS,
)

__all__ = ["MODELO_NONWORK_COMMAND_SPECS"]
