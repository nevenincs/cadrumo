"""The year a declaration is filed for, bounded once.

A filing year addresses a registry revision: AEAT binds every ``(modelo,
filing_year, period)`` triple to exactly one published revision, so the value
selects which year's norms a calculation runs under. The bound here is a
sanity window on that axis, not a regulatory value -- it refuses a
transposed digit or an uninitialised zero before either can reach revision
resolution and select nothing.

The window is declared here and imported by every carrier: the sede
declaration schemas that read ``ejercicio`` off the portal, the aggregation
and cross-period records that persist it, and the CLI payloads that project
it. Restating ``ge=2000, le=2099`` at each site let the same axis carry
different bounds in the model that writes a year and the model that reads it
back, with nothing to detect the divergence.

Spanish-named fields on AEAT-facing schemas (``ejercicio``, ``año``) keep
their names and take this type; the alias bounds the value, it does not
rename the field.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import Field

#: First filing year this application accepts. Earlier years predate the
#: registry's authored revisions, so no snapshot could resolve for them.
FILING_YEAR_MIN: Final[int] = 2000

#: Last filing year this application accepts.
FILING_YEAR_MAX: Final[int] = 2099

FilingYear = Annotated[int, Field(ge=FILING_YEAR_MIN, le=FILING_YEAR_MAX)]
"""The four-digit year a declaration is filed for."""

__all__ = ["FILING_YEAR_MAX", "FILING_YEAR_MIN", "FilingYear"]
