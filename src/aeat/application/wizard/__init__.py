"""Schema-driven setup-wizard application facade.

The concrete setup flow lives in this package. ``WizardFlow``
descriptors declare the operator-facing sections, questions, widgets,
visibility gates, and answer model. The command builder walks those
descriptors through a ``Prompter`` implementation, validates raw input
with the per-widget canonical-token rules, rebuilds the typed answer
projection, and persists profile facts through the user-profile
orchestration layer.

Importing :mod:`aeat.application.wizard` intentionally performs the
startup registrations that downstream layers consume without importing
the application package directly. ``_catalogue`` registers ``SETUP_FLOW``
and ``WIZARD_FLOWS`` in :mod:`aeat.core.wizard_catalogue`; ``_persistence``
registers its concrete ``project_answers`` implementation in
:mod:`aeat.core.setup_answers`; and ``_compiler`` compiles the wizard
catalogue into ``ProfileKey`` rows before pushing them into the
contribuyente profile-key registry. Domain modules read those core slots
and the domain registry only, preserving the one-way application boundary.

See Also:
    :func:`aeat.application.wizard.build_wizard_command`: Build a setup
        CLI command from a registered flow descriptor.
    :func:`aeat.application.wizard.validate_widget_answer`: Validate one
        raw answer into canonical-token form.
    :func:`aeat.application.wizard.project_answers`: Rebuild typed setup
        answers from persisted canonical profile values.
    :class:`aeat.core.setup_answers.SetupAnswers`: Canonical typed model
        for setup answers.
    :func:`aeat.core.wizard_catalogue.get_setup_flow`: Return the
        registered setup flow for core and domain consumers.
    :func:`aeat.domain.contribuyente.get_profile_key`: Resolve compiled
        profile-key rows registered by the wizard compiler.
"""

from . import _compiler as _compiler
from ._catalogue import WIZARD_FLOWS
from ._commands import build_wizard_command
from ._errors import WizardValidationError
from ._persistence import project_answers
from ._widgets import validate_widget_answer

__all__ = [
    "WIZARD_FLOWS",
    "WizardValidationError",
    "build_wizard_command",
    "project_answers",
    "validate_widget_answer",
]
