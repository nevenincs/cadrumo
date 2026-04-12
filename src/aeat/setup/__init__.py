"""First-run interactive setup wizard (#61).

This subpackage ships ``aeat setup``, the on-ramp a fresh Spanish
autónomo runs after ``just bootstrap`` to produce a valid
``env/.env`` and an :class:`aeat.deadlines.AutonomoProfile` JSON
file, without ever writing a certificate password to disk.

Callers outside the subpackage import only from this module, honouring
the project's public-API-discipline rule.
"""

from __future__ import annotations

from aeat.setup._env_writer import owned_env_keys, write_env_file, write_profile_file
from aeat.setup._errors import (
    SetupAbortedError,
    SetupAnswersError,
    SetupError,
    SetupVerifyError,
)
from aeat.setup._models import (
    SetupAnswers,
    SetupOutcome,
    SetupResult,
    SetupStep,
    VerifyFinding,
    VerifySeverity,
)
from aeat.setup._prompter import QueuedPrompter, TyperPrompter
from aeat.setup._protocols import FirstRunRunner, Prompter
from aeat.setup._verifier import Verifier, load_answers_from_file
from aeat.setup._wizard import SetupWizard

__all__ = [
    "FirstRunRunner",
    "Prompter",
    "QueuedPrompter",
    "SetupAbortedError",
    "SetupAnswers",
    "SetupAnswersError",
    "SetupError",
    "SetupOutcome",
    "SetupResult",
    "SetupStep",
    "SetupVerifyError",
    "SetupWizard",
    "TyperPrompter",
    "Verifier",
    "VerifyFinding",
    "VerifySeverity",
    "load_answers_from_file",
    "owned_env_keys",
    "write_env_file",
    "write_profile_file",
]
