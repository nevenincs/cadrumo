"""Domain-profile test fixtures.

Profile keys are compiled lazily from the wizard catalogue on first access
via the :func:`~aeat.domain.profile._keys._build_profile_keys` cycle-breaker.
No application-layer import is needed here.
"""

from __future__ import annotations
