"""Resource ceilings the supervised profile KDF worker runs under.

Standard-library only: the worker attests these values back to its supervisor,
and every wrap and unwrap starts that worker afresh.
"""

from __future__ import annotations

from typing import Final

PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES: Final = 1024 * 1024 * 1024
PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS: Final = 15
PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES: Final = 2

__all__ = [
    "PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS",
    "PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES",
    "PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES",
]
