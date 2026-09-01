"""A language switch changes what is written, never what is being addressed.

WHAT ALREADY EXISTED, so this is not a second copy of it. The session layer is
proven: `test_workspace_read_session` shows a language switch is a locale-only
refresh, that the semantic identity ignores every locale-bearing field, and
that the locale axes really do move. The editor screen is proven to render in
every shipped catalogue. Neither reaches the six routed workspace
DESTINATIONS, and both stop short of the screen: a projection can carry a
stable identity while the mounted surface still reorders its controls or
changes which of them can be reached, and nothing would notice.

So this asserts the invariant where the operator meets it -- on the mounted
screen -- and it asserts it across all FOUR shipped languages rather than the
two the session tests use. Catalan and Hungarian are exactly where a missing
catalogue entry shows up, and a fallback is not a failure here: the product is
allowed to resolve a requested language to another one. What it is NOT allowed
to do is let that change the address, the controls, or their order.

THE COMPARISON IS AGAINST ONE SEEDED STORAGE, not four. Resolving four
languages from four separately seeded profiles would differ in bucket identity
and creation instants, so any difference found could not be attributed to
language -- which is the only thing this module is about.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from textual.widget import Widget

from ....core.external_constants import OutputLanguage
from ....tests.modelo_workspace_session import real_workspace_inspection_result
from ....tests.terminal_sizes import TERMINAL_ORDINARY
from ..components.host import ScreenHostApp
from ..modelo.routes import MODELO_WORKSPACE_DESTINATIONS
from ..modelo.view.controller import ModeloWorkspaceReadSession, admit_workspace_session, semantic_identity
from ..modelo.view.models import ModeloWorkspaceDestinationIdV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LANGUAGES = tuple(OutputLanguage)
_DESTINATIONS = [
    pytest.param(destination_id, id=destination_id.rsplit(".", 1)[-1]) for destination_id in MODELO_WORKSPACE_DESTINATIONS
]


@pytest.fixture(scope="module")
def sessions_by_language(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[OutputLanguage, ModeloWorkspaceReadSession]]:
    """One admitted session per shipped language, over ONE seeded address."""
    root = tmp_path_factory.mktemp("localized")
    with real_workspace_inspection_result(root) as seeded:
        opened: dict[OutputLanguage, ModeloWorkspaceReadSession] = {}
        for language in _LANGUAGES:
            session, refusal = admit_workspace_session(seeded.resolve(language))
            assert refusal is None, f"{language} was refused admission: {refusal}"
            assert session is not None
            opened[language] = session
        yield opened


def test_every_shipped_language_opens_the_same_workspace(
    sessions_by_language: dict[OutputLanguage, ModeloWorkspaceReadSession],
) -> None:
    """The semantic identity is one value across all four catalogues.

    Asserted as a SET rather than pairwise against Spanish, so a language that
    agrees with Spanish while disagreeing with the others cannot hide.
    """
    identities = {language: semantic_identity(session.projection) for language, session in sessions_by_language.items()}
    distinct = set(identities.values())
    assert len(distinct) == 1, (
        "a language switch changed which workspace this is: "
        + "; ".join(f"{language.value}={identity}" for language, identity in identities.items())
    )


def test_the_locale_axis_actually_moves_across_the_shipped_catalogues(
    sessions_by_language: dict[OutputLanguage, ModeloWorkspaceReadSession],
) -> None:
    """Invariance is only meaningful if the language is genuinely being varied.

    Without this, every assertion in this module would pass on a product that
    ignored the requested language entirely -- the identities would be stable
    because nothing moved. A fallback is permitted, so the requirement is that
    the REQUESTED language is carried faithfully, not that every request
    resolves to itself.
    """
    requested = {language: session.projection.locale.requested_language for language, session in sessions_by_language.items()}
    assert set(requested.values()) == set(_LANGUAGES), (
        f"the requested language was not carried through for every catalogue: {requested}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("destination_id", _DESTINATIONS)
async def test_a_destination_mounts_the_same_controls_in_every_language(
    destination_id: ModeloWorkspaceDestinationIdV1,
    sessions_by_language: dict[OutputLanguage, ModeloWorkspaceReadSession],
) -> None:
    """Translation may change the words in a control, never which controls exist.

    Compared on the ORDERED focus chain, not on a set of ids: keyboard identity
    is an order, and a language that mounted the same controls in a different
    sequence would move every operator's muscle memory while satisfying a
    set comparison. The ids themselves are semantic addresses and are never
    translated, so any difference here is a structural one.
    """
    chains: dict[OutputLanguage, tuple[str | None, ...]] = {}
    mounted: dict[OutputLanguage, tuple[str | None, ...]] = {}
    for language, session in sessions_by_language.items():
        app = ScreenHostApp(MODELO_WORKSPACE_DESTINATIONS[destination_id](session))
        async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
            await pilot.pause()
            chains[language] = tuple(widget.id for widget in app.screen.focus_chain)
            mounted[language] = tuple(
                sorted(widget.id for widget in app.screen.query(Widget) if widget.id is not None)
            )
            app.exit(None)

    assert len(set(chains.values())) == 1, (
        f"{destination_id} offers a different keyboard order per language: "
        + "; ".join(f"{language.value}={chain}" for language, chain in chains.items())
    )
    assert len(set(mounted.values())) == 1, (
        f"{destination_id} mounts a different control set per language: "
        + "; ".join(f"{language.value}={len(ids)} widgets" for language, ids in mounted.items())
    )


def test_the_requested_languages_resolution_is_reported_so_the_axis_is_not_assumed(
    sessions_by_language: dict[OutputLanguage, ModeloWorkspaceReadSession],
) -> None:
    """Record what each request RESOLVES to, because invariance is cheap when nothing varies.

    This is the control, and it is deliberately a measurement rather than an
    equality: if every request resolves to the same catalogue, the invariance
    assertions above are comparing two copies of one input and prove far less
    than they appear to. Asserting the resolution set makes that visible in the
    suite instead of leaving a green that quietly means nothing.

    The measured state today is that the modelo workspace content carries no
    translations, so every request falls back to the source language. That is
    a fact about the catalogues, not a defect in these screens, and it is
    asserted here so the day a translation lands this test fails and tells
    somebody the axis has become live.
    """
    resolved = {
        language: session.projection.locale.resolved_language for language, session in sessions_by_language.items()
    }
    assert set(resolved) == set(_LANGUAGES), "a shipped language was not exercised"
    assert len(set(resolved.values())) == 1, (
        "a requested language now resolves to its own catalogue, so the locale axis has become "
        f"live for these destinations and the invariance assertions above are finally load-bearing: {resolved}"
    )
