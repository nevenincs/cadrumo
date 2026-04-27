"""First-run interactive setup wizard (#61).

This subpackage ships ``aeat setup``, the on-ramp a fresh Spanish
autónomo runs after ``just bootstrap`` to produce a valid
``env/.env`` and an :class:`aeat.deadlines.AutonomoProfile` JSON
file, without ever writing a certificate password to disk.

Callers outside the subpackage import only from this module, honouring
the project's public-API-discipline rule.
"""

from __future__ import annotations

from ._env_writer import load_profile_envelope, owned_env_keys, write_env_file, write_profile_file
from ._errors import (
    SetupAbortedError,
    SetupAnswersError,
    SetupError,
    SetupVerifyError,
)
from ._models import (
    SetupAnswers,
    SetupOutcome,
    SetupResult,
    SetupStep,
    VerifyFinding,
    VerifySeverity,
)
from ._prompter import QueuedPrompter, TyperPrompter
from ._protocols import FirstRunRunner, Prompter
from ._verifier import Verifier, load_answers_from_file
from ._wizard import SetupWizard

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
    "load_profile_envelope",
    "owned_env_keys",
    "write_env_file",
    "write_profile_file",
]
