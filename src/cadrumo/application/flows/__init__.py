"""The paged interactive-flow substrate: one engine, many frontends.

This package is the single flow authority for paged operator-facing
flows. A domain flow supplies a declarative :class:`FlowDefinition`
(pages with copy *references*, registered validators, branching
predicates, repeating groups) and consumes the pure engine transitions
over an immutable :class:`FlowState`; the review projection and submit
gate come with the substrate. Frontends contain no flow logic.

The substrate is domain-blind: it carries no profile, censo, or AEAT
vocabulary and resolves all page copy at render time from the bundled
locale catalogues, schema definitions, and terminology concepts.
Consumers import from this facade only.
"""

from __future__ import annotations

from ._capability import detect_frontend_capability
from ._checkpoint import (
    CheckpointStore,
    checkpoint_available,
    discard_checkpoint,
    save_checkpoint,
)
from ._copy import (
    ChoiceCopy,
    CopySourceResolver,
    LegalRefCopy,
    PageCopy,
    assemble_page_copy,
    assemble_section_titles,
    register_copy_source,
    resolve_copy,
    resolve_optional_copy,
)
from ._definition import (
    CopyRef,
    FlowChoice,
    FlowCondition,
    FlowDefinition,
    FlowItem,
    FlowLegalRef,
    FlowPage,
    FlowRepeatingGroup,
    FlowSection,
    FlowVisibility,
    iter_flow_conditions,
)
from ._engine import (
    SECTION_VERDICT_PREFIX,
    FlowState,
    VisiblePage,
    answer,
    back_page,
    jump_to,
    next_page,
    page_status,
    reset_page,
    restart_flow,
    set_instance_count,
    start_flow,
    visible_sequence,
)
from .errors import (
    FlowAnswerError,
    FlowCheckpointError,
    FlowCopyResolutionError,
    FlowError,
    FlowNavigationError,
    FlowRunAbandonedError,
    FlowSubmitError,
    FlowUnsupportedConsoleError,
    FlowValidatorRegistryError,
)
from ._resume import resume_flow
from ._review import ReviewProjection, ReviewRow, assert_submit_eligible, review
from ._scripted import run_scripted_flow
from ._validators import (
    AnswerValidator,
    CrossFieldValidator,
    ValidationVerdict,
    register_answer_validator,
    register_cross_field_validator,
    resolve_answer_validator,
    resolve_cross_field_validator,
    run_answer_validation,
    validate_widget_shape,
)
from ._wizard_projection import flow_definition_from_wizard_flow

__all__ = [
    "SECTION_VERDICT_PREFIX",
    "AnswerValidator",
    "CheckpointStore",
    "ChoiceCopy",
    "CopyRef",
    "CopySourceResolver",
    "CrossFieldValidator",
    "FlowAnswerError",
    "FlowCheckpointError",
    "FlowChoice",
    "FlowCondition",
    "FlowCopyResolutionError",
    "FlowDefinition",
    "FlowError",
    "FlowItem",
    "FlowLegalRef",
    "FlowNavigationError",
    "FlowPage",
    "FlowRepeatingGroup",
    "FlowRunAbandonedError",
    "FlowSection",
    "FlowState",
    "FlowSubmitError",
    "FlowUnsupportedConsoleError",
    "FlowValidatorRegistryError",
    "FlowVisibility",
    "LegalRefCopy",
    "PageCopy",
    "ReviewProjection",
    "ReviewRow",
    "ValidationVerdict",
    "VisiblePage",
    "answer",
    "assemble_page_copy",
    "assemble_section_titles",
    "assert_submit_eligible",
    "back_page",
    "checkpoint_available",
    "detect_frontend_capability",
    "discard_checkpoint",
    "flow_definition_from_wizard_flow",
    "iter_flow_conditions",
    "jump_to",
    "next_page",
    "page_status",
    "register_answer_validator",
    "register_copy_source",
    "register_cross_field_validator",
    "reset_page",
    "resolve_answer_validator",
    "resolve_copy",
    "resolve_cross_field_validator",
    "resolve_optional_copy",
    "restart_flow",
    "resume_flow",
    "review",
    "run_answer_validation",
    "run_scripted_flow",
    "save_checkpoint",
    "set_instance_count",
    "start_flow",
    "validate_widget_shape",
    "visible_sequence",
]
