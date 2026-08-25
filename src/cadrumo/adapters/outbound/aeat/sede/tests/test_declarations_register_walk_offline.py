"""The register walk, browser shell included, driven offline end to end.

The truncation refusal was proven at the parse boundary by feeding
``_register_rows_from_snapshot`` a fixture directly, which deliberately excluded
everything wrapping it: the navigation, the post-navigation landing assertion,
the two combobox drives, the Buscar click and the read of the resulting
document. That exclusion mattered because the residual risk it left is not that
the refusal misfires -- it is that ``walk`` stops reaching the parse at all, in
which case the parse-level gate stays green while the register read returns
nothing through every real caller.

This module closes it. Both tests drive the real ``DeclaracionesRegisterSession``
``walk`` coroutine, so the whole shell runs: a real headless Chromium page
navigates the real listing URL, the landing-prefix assertion sees a genuine AEAT
url because route interception FULFILS that url rather than redirecting away
from it, the form-render check finds its exact ``Modelo (*)`` label, both
comboboxes are opened and an option clicked in each, Buscar is clicked, and the
result is read back off the same document.

Nothing in the fixture behaves like the ZK application; every element only has to
be present, visible and clickable. The Buscar click needs no response precisely
because the one served document is both the form and its own result grid.

No AEAT contact occurs and none is requested: every route is intercepted and
fulfilled from a synthetic fixture, and no live-read opt-in is set.
"""

from __future__ import annotations

import asyncio

import pytest

from ......tests.offline_aeat_register import (
    aeat_sede_fixture,
    declared_register_total,
    open_routed_declarations_register,
    rendered_register_rows,
)
from .._declarations import Declaracion
from ..errors import SedeParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TRUNCATED = "declaraciones-register-form-paginated-synthetic"
_COMPLETE = "declaraciones-register-form-complete-synthetic"


async def _walk_against(html: str, *, modelo: str, ejercicio: int) -> tuple[Declaracion, ...]:
    """Drive the real walk over one intercepted synthetic document."""

    async with open_routed_declarations_register((html,)) as (register, _routed):
        return await register.walk(modelo=modelo, ejercicio=ejercicio)


def test_the_walk_itself_refuses_a_page_declaring_more_than_it_rendered() -> None:
    """Driving the whole shell, the refusal comes out of ``walk``, not just the parse.

    The pass condition is the PROPERTY: a page rendering strictly fewer rows than
    its own pager declares is refused. Both numbers come from the fixture's raw
    markup, so a regenerated fixture of a different size still exercises the same
    property and nothing here has to be rewritten.
    """
    html = aeat_sede_fixture(_TRUNCATED)
    declared_total = declared_register_total(html)
    rendered_rows = rendered_register_rows(html)
    assert declared_total is not None, "fixture's pager label shape changed; it must declare a total"
    assert rendered_rows < declared_total, (
        "fixture no longer renders fewer rows than its pager declares, so it cannot exercise a truncated read"
    )

    with pytest.raises(SedeParseError) as exc_info:
        asyncio.run(_walk_against(html, modelo="100", ejercicio=2025))

    context = exc_info.value.context
    assert context is not None, "the refusal reached the operator without its rendered-versus-declared cause"
    assert context["rendered_count"] == rendered_rows
    assert context["declared_total"] == declared_total
    assert context["modelo"] == "100"
    assert context["ejercicio"] == 2025


def test_the_walk_returns_the_rows_of_a_page_carrying_no_pager() -> None:
    """The companion case: no pager means nothing to fall short of, so rows come back.

    This is the half that makes the refusal above worth having. A detector that
    also fired on an ordinary complete capture would break every real read, and a
    shell that never reached the parse would return an empty tuple here rather
    than raising -- which is why the rows are asserted non-empty and matched
    against the fixture's own rendered count.
    """
    html = aeat_sede_fixture(_COMPLETE)
    assert declared_register_total(html) is None, "fixture grew a pager label; it can no longer pin the no-pager case"

    rows = asyncio.run(_walk_against(html, modelo="100", ejercicio=2024))

    assert rows, "the walk returned nothing, so it did not reach the parse through the browser shell"
    assert len(rows) == rendered_register_rows(html)
    for row in rows:
        assert row.modelo == "100"
        assert row.ejercicio == 2024
        assert row.expediente_id
        assert row.presented_at.tzinfo is not None
