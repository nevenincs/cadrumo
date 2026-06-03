"""Schema-driven wizard subpackage.

The wizard descriptor catalogue is the single source of truth for every
operator-facing configuration question. A ``WizardFlow`` declares the
sections, questions, widgets, conditional branches, and answer model;
the runtime walks that descriptor against a ``Prompter`` implementation
to collect canonical-token answers, runs per-widget validation, parses
the typed projection, and persists the result through the standard
profile workflow. The descriptor also projects onto the
``PROFILE_KEYS`` registry via ``compile_profile_keys``, keeping the
catalogue and the validation registry in lockstep.

Importing this package eagerly registers both surfaces (DB-17 / S64): the
``_compiler`` import runs the import-time ``register_profile_keys`` push (and,
through it, the ``_catalogue`` wizard-catalogue registration), so any consumer
that imports ``aeat.application.wizard`` — the CLI composition root, the
test-session conftests — guarantees the domain ``PROFILE_KEYS`` registry is
seeded before first access. The domain therefore never pulls upward into the
application layer to compile its keys.
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
