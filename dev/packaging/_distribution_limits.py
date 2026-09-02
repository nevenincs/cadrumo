"""Publishing limits every Cadrumo distribution artifact must satisfy.

These are facts about the index we publish to, not about any one build or smoke
lane. The cohort builder, the smoke lanes, and their tests are all *consumers*
of the same number, so it lives here rather than in any one of them: a copy in
a consumer is a copy that can drift from the limit it claims to enforce.

That is not hypothetical. This module replaced FIVE declarations of the cap
feeding SIX assertion sites: ``python_cohort`` (checking wheels and sdists
separately), ``smoke_split_install``, ``_smoke_common``, the companion
distribution gate, and -- worst of the set -- a bare ``100 * 1_000_000``
literal inside the core payload test. A test asserting against its own private
copy of a threshold cannot fail when the real limit moves; it keeps passing and
reports the value it was policing as still correct.

Prose statements of the number elsewhere are deliberately left alone: the
``pyproject`` wheel-split comment, both companion ``hatch_build`` hooks, and
both companion READMEs explain to a human WHY the corpus split exists. They assert nothing and cannot drift a gate, so a
consistency sweep should leave them where they are. Only executable copies
needed one owner, and there is now exactly one.
"""

from __future__ import annotations

from typing import Final

__all__ = ["PYPI_FILE_CAP_BYTES"]

# PyPI's default per-file upload limit. Decimal megabytes, matching how PyPI
# states and enforces it -- 100 MB here is 100,000,000 bytes, not 104,857,600.
# The corpus wheel split exists to keep every companion under this cap without
# requesting a per-project size grant.
PYPI_FILE_CAP_BYTES: Final[int] = 100 * 1_000_000
