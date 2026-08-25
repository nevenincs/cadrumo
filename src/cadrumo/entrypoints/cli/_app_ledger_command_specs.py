"""Import-light tuple composer for the complete application ledger CommandSpec subtree."""

from __future__ import annotations

from ._app_ledger_bienes_inversion_command_specs import LEDGER_BIENES_INVERSION_COMMAND_SPECS
from ._app_ledger_classification_command_specs import LEDGER_CLASSIFICATION_COMMAND_SPECS
from ._app_ledger_counterparty_command_specs import LEDGER_COUNTERPARTY_COMMAND_SPECS
from ._app_ledger_evidence_command_specs import LEDGER_EVIDENCE_COMMAND_SPECS
from ._app_ledger_evidence_followup_command_specs import LEDGER_EVIDENCE_FOLLOWUP_COMMAND_SPECS
from ._app_ledger_foundation_command_specs import LEDGER_FOUNDATION_COMMAND_SPECS
from ._app_ledger_inventory_analysis_command_specs import LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS
from ._app_ledger_inventory_command_specs import LEDGER_INVENTORY_COMMAND_SPECS
from ._app_ledger_invoice_intake_command_specs import LEDGER_INVOICE_INTAKE_COMMAND_SPECS
from ._app_ledger_invoice_lifecycle_command_specs import LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS
from ._app_ledger_lifecycle_command_specs import LEDGER_LIFECYCLE_COMMAND_SPECS
from ._app_ledger_management_command_specs import LEDGER_MANAGEMENT_COMMAND_SPECS
from ._app_ledger_operations_command_specs import LEDGER_OPERATIONS_COMMAND_SPECS
from ._app_ledger_participation_command_specs import LEDGER_PARTICIPATION_COMMAND_SPECS
from ._app_ledger_prorrata_command_specs import LEDGER_PRORRATA_COMMAND_SPECS
from ._app_ledger_ratios_command_specs import LEDGER_RATIOS_COMMAND_SPECS
from ._app_ledger_rule_command_specs import LEDGER_RULE_COMMAND_SPECS
from ._command_spec import CommandSpec

LEDGER_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *LEDGER_FOUNDATION_COMMAND_SPECS,
    *LEDGER_CLASSIFICATION_COMMAND_SPECS,
    *LEDGER_OPERATIONS_COMMAND_SPECS,
    *LEDGER_MANAGEMENT_COMMAND_SPECS,
    *LEDGER_LIFECYCLE_COMMAND_SPECS,
    *LEDGER_BIENES_INVERSION_COMMAND_SPECS,
    *LEDGER_COUNTERPARTY_COMMAND_SPECS,
    *LEDGER_EVIDENCE_COMMAND_SPECS,
    *LEDGER_INVENTORY_COMMAND_SPECS,
    *LEDGER_INVOICE_INTAKE_COMMAND_SPECS,
    *LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS,
    *LEDGER_PARTICIPATION_COMMAND_SPECS,
    *LEDGER_PRORRATA_COMMAND_SPECS,
    *LEDGER_RATIOS_COMMAND_SPECS,
    *LEDGER_RULE_COMMAND_SPECS,
    *LEDGER_EVIDENCE_FOLLOWUP_COMMAND_SPECS,
    *LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS,
)

__all__ = ["LEDGER_COMMAND_SPECS"]
