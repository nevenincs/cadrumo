"""Domain-profile test fixtures.

Imports the application-layer compiler to ensure PROFILE_KEYS are
registered in the domain registry before any profile test runs.
Test files in domain/ that depend on application modules for fixture
setup are permitted per project convention; they are not production code.
"""

from __future__ import annotations

# Import for side-effect: _compiler.py registers PROFILE_KEYS in the domain registry
# when this conftest is loaded, satisfying domain/profile tests that access PROFILE_KEYS.
from aeat.application.wizard import _compiler as _compiler
