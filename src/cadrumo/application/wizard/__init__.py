"""Schema-driven setup-wizard application facade.

The concrete setup flow lives in this package.
:class:`_models.WizardFlow` descriptors declare the operator-facing sections,
questions, widgets, visibility gates, and answer model. The command builder
projects those descriptors onto the flow substrate
(:mod:`cadrumo.application.flows`) and drives them through its engine and
frontends, validates raw input with the per-widget canonical-token rules,
rebuilds the typed :class:`core.setup_answers.SetupAnswers` projection, and
persists profile facts through the user-profile orchestration layer.

Importing :mod:`application.wizard` intentionally performs the startup
registrations that downstream layers consume without importing the application
package directly. ``_catalogue`` registers :data:`_catalogue.SETUP_FLOW` and
:data:`WIZARD_FLOWS` in :mod:`core.wizard_catalogue`; ``_persistence`` registers
its concrete :func:`project_answers` implementation in
:mod:`core.setup_answers`; and ``_compiler`` compiles the wizard catalogue into
:class:`domain.contribuyente.ProfileKey` rows before pushing them into the
contribuyente profile-key registry. Domain modules read those core slots and the
domain registry only, preserving the one-way application boundary.

See Also:
    :func:`build_wizard_command`: Build a setup CLI command from a registered
        flow descriptor.
    :func:`validate_widget_answer`: Validate one raw answer into
        canonical-token form.
    :func:`project_answers`: Rebuild typed setup answers from persisted
        canonical profile values.
    :class:`core.setup_answers.SetupAnswers`: Canonical typed model
        for setup answers.
    :func:`core.wizard_catalogue.get_setup_flow`: Return the registered setup
        flow for core and domain consumers.
    :func:`domain.contribuyente.get_profile_key`: Resolve compiled
        profile-key rows registered by the wizard compiler.
"""

from . import _compiler as _compiler
from . import _copy_sources as _copy_sources
from ._catalogue import WIZARD_FLOWS
from ._checkpoint_store import (
    ProfileFactsCheckpointStore,
    checkpoint_answers_from_record,
    checkpoint_facts_from_answers,
)
from ._commands import build_wizard_command
from ._copy_sources import (
    register_profile_copy_sources,
    resolve_profile_schema_copy,
    resolve_profile_terminology_copy,
)
from ._cotejo import (
    COTEJO_LOCALE_KEYS,
    COTEJO_SECTION_ID,
    CotejoAxis,
    attach_cotejo_pages,
    build_cotejo_pages,
    cotejo_axes,
    cotejo_outcome,
)
from ._descendant_door import (
    DESCENDANT_DOOR_LOCALE_KEYS,
    build_descendant_door,
    persist_descendant_door_answers,
)
from ._descendant_group import (
    DESCENDANT_GROUP,
    DESCENDANT_LOCALE_KEYS,
    DESCENDANT_NIF_VALIDATOR_ID,
    DESCENDANTS_COUNT_PAGE_ID,
    DESCENDANTS_GROUP_ID,
    attach_descendant_group,
)
from ._errors import (
    WizardEditUnsupportedConsoleError,
    WizardUnsupportedConsoleError,
    WizardValidationError,
)
from ._flow_validators import (
    TAXPAYER_PROJECTION_VALIDATOR_ID,
    build_taxpayer_projection_validator,
    register_taxpayer_projection_validator,
)
from ._legal_zone import PageLegalZone, build_flow_legal_zones
from ._models import (
    WizardChoice,
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardSection,
    WizardVisibility,
)
from ._persistence import descendant_facts_from_answers, project_answers
from ._setup_legal_validators import (
    SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID,
    attach_setup_legal_validators,
    validate_unidad_familiar_conjunta,
)
from ._status import (
    WizardStatusError,
    WizardStatusReport,
    build_wizard_status,
    load_active_taxpayer_profile,
)
from ._widgets import validate_widget_answer

__all__ = [
    "COTEJO_LOCALE_KEYS",
    "COTEJO_SECTION_ID",
    "DESCENDANTS_COUNT_PAGE_ID",
    "DESCENDANTS_GROUP_ID",
    "DESCENDANT_DOOR_LOCALE_KEYS",
    "DESCENDANT_GROUP",
    "DESCENDANT_LOCALE_KEYS",
    "DESCENDANT_NIF_VALIDATOR_ID",
    "SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID",
    "TAXPAYER_PROJECTION_VALIDATOR_ID",
    "WIZARD_FLOWS",
    "CotejoAxis",
    "PageLegalZone",
    "ProfileFactsCheckpointStore",
    "WizardChoice",
    "WizardCondition",
    "WizardEditUnsupportedConsoleError",
    "WizardFlow",
    "WizardQuestion",
    "WizardSection",
    "WizardStatusError",
    "WizardStatusReport",
    "WizardUnsupportedConsoleError",
    "WizardValidationError",
    "WizardVisibility",
    "attach_cotejo_pages",
    "attach_descendant_group",
    "attach_setup_legal_validators",
    "build_cotejo_pages",
    "build_descendant_door",
    "build_flow_legal_zones",
    "build_taxpayer_projection_validator",
    "build_wizard_command",
    "build_wizard_status",
    "checkpoint_answers_from_record",
    "checkpoint_facts_from_answers",
    "cotejo_axes",
    "cotejo_outcome",
    "descendant_facts_from_answers",
    "load_active_taxpayer_profile",
    "persist_descendant_door_answers",
    "project_answers",
    "register_profile_copy_sources",
    "register_taxpayer_projection_validator",
    "resolve_profile_schema_copy",
    "resolve_profile_terminology_copy",
    "validate_unidad_familiar_conjunta",
    "validate_widget_answer",
]
