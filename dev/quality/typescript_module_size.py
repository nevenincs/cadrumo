"""The most physical lines a TypeScript module in the repository may take.

A module that size carries many responsibilities at once: a reader cannot hold
it, a reviewer cannot see what a change touches, and every edit collides with
another. This module is the bound's only definition. The frontend's generators
receive it from their Python producers and refuse to write a module past it, so
a generated module is split by its generator and never by hand.

A physical line is a line of the file as stored, blank lines and comments
included, and a last line without its newline counts.
"""

from __future__ import annotations

from typing import Final

MAX_PHYSICAL_LINES: Final[int] = 1500
