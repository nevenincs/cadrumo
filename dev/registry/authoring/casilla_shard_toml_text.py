"""Shared syntax markers for generated casilla shard TOML."""

from __future__ import annotations

import re

#: A line break inside a design cell, with whatever indentation wrapped
#: around it. Folded to one space; runs of real spaces are left alone.
_NL = chr(10)


_KEY_LINE = re.compile(r"^([a-z_][a-z0-9_]*) = ")
