"""One reader for the justfile recipes that run pytest over this directory.

Two gates ask the same question of the justfile -- the preflight selection gate
and the performance-marker gate -- and each carried its own copy of the answer.
The copies were semantically identical, which is exactly what made the pair
expensive: a defect in the reading had to be found twice and fixed twice, and
the second copy is the one nobody remembers to look at.

The defect that surfaced the duplication is worth stating, because it is the
reason this module reads lines the way it does. A recipe body line is
recognised by its INDENTATION, so the indentation test has to run against the
raw line. A commented-out body line is indented exactly like a live one and
names the same directory, and ``shlex.split`` keeps a leading ``#`` as an
ordinary token -- so ``"pytest" in tokens`` answers yes for a recipe that was
switched off. The fix is to test indentation on the raw line and then hand that
line to :func:`~dev.ci.workflow_run_text.executed_lines`, which owns the
comment rule for this repository. Structure first, execution second; neither
question is answered with a private copy of the other's rule.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Final, NamedTuple

from ..._paths import REPO_ROOT, UTF_8
from ...ci.workflow_run_text import executed_lines

__all__ = ["Recipe", "packaging_pytest_recipes"]

#: The directory whose recipes both consuming gates measure.
TARGET_DIRECTORY: Final[str] = "dev/packaging/tests"

_JUSTFILE: Final[Path] = REPO_ROOT / "justfile"

#: A recipe header: a name at column zero, then just's parameter grammar --
#: each parameter optionally variadic (`*ARGS`, `+ARGS`), exported (`$VAR`),
#: or defaulted (`workers="auto"`) -- and then a bare `:`, never `:=`, which
#: is a variable assignment rather than a recipe.
#:
#: The parameter region is modelled rather than skipped with a wildcard,
#: because the name here is harvested out of free text and a wildcard would
#: also accept a column-zero line that is no header at all. Omitting the
#: region entirely -- which this pattern did -- is worse still: a
#: parameterised header does not fail LOUDLY, it simply does not match, and
#: every body line beneath it is then attributed to the PRECEDING recipe.
#: Sixteen of this justfile's 111 recipes carry parameters, so a pytest
#: invocation moving under any one of them would have been measured under
#: another lane's name while both consuming gates stayed green.
_RECIPE_HEADER: Final[re.Pattern[str]] = re.compile(
    r"""^(?P<name>[a-z][\w-]*)(?:\s+[*+$]?[A-Za-z_]\w*(?:\s*=\s*(?:"[^"]*"|'[^']*'))?)*\s*:(?![=])""",
)


class Recipe(NamedTuple):
    """One pytest invocation over the target directory, read off the justfile.

    Attributes:
        name: The recipe name as written in the justfile.
        arguments: The pytest arguments, excluding the ``pytest`` token itself.
    """

    name: str
    arguments: tuple[str, ...]


def packaging_pytest_recipes(*, justfile: Path | None = None) -> tuple[Recipe, ...]:
    """Discover every justfile recipe invoking pytest over the target directory.

    A commented-out body line is not an invocation and is not returned. See the
    module docstring for why that needs the raw line and the shared reader
    together rather than either one alone.

    Args:
        justfile: The justfile to read. Defaults to the repository's own. The
            parameter exists so the gate proving this reader rejects a
            commented-out recipe can hand it a fixture instead of patching a
            module constant out from under the real callers.

    Returns:
        One entry per matching recipe body line, in justfile order.
    """
    recipes: list[Recipe] = []
    current = ""
    for raw_line in (justfile or _JUSTFILE).read_text(encoding=UTF_8).splitlines():
        header = _RECIPE_HEADER.match(raw_line)
        if header is not None:
            current = header.group("name")
            continue
        if not raw_line[:1].isspace() or TARGET_DIRECTORY not in raw_line:
            continue
        line = next(iter(executed_lines(raw_line)), "")
        if not line:
            continue
        tokens = shlex.split(line.lstrip("@"))
        if "pytest" not in tokens:
            continue
        assert current, (
            f"a pytest invocation over {TARGET_DIRECTORY} was read before any recipe header "
            f"matched: {raw_line.strip()!r}. Filing it under an empty name would put a real "
            "lane where no gate looks for it, which reads exactly like a lane that is not there."
        )
        recipes.append(Recipe(name=current, arguments=tuple(tokens[tokens.index("pytest") + 1 :])))
    return tuple(recipes)
