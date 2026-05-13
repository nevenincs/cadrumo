"""``aeat app topic`` conceptual help surface.

Renders topics from
:func:`aeat.application.topics.load_topic_catalogue`; the catalogue
itself reads ``registry/aeat/topics/<slug>.toml`` and the i18n
catalogue under ``topic.<slug>.title`` / ``topic.<slug>.body``.
"""

from __future__ import annotations

import typer

from ...application.topics import (
    TopicCatalogue,
    TopicNotFoundError,
    load_topic_catalogue,
)
from ._common import _bad, _emit
from ._i18n import tr

app = typer.Typer(
    name="topic",
    help=tr("cli.topic.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
)


def _render_topic(ctx: typer.Context, catalogue: TopicCatalogue, slug: str) -> None:
    """Render one topic body and surrounding metadata."""

    try:
        topic = catalogue.topic(slug)
    except TopicNotFoundError:
        raise _bad(tr("cli.topic.errors.not_found", slug=slug)) from None
    payload = {
        "slug": topic.slug,
        "title": tr(topic.title_key),
        "body": tr(topic.body_key),
        "see_also": list(topic.see_also),
        "legal_refs": list(topic.legal_refs),
    }
    lines: list[str] = [
        f"topic\t{topic.slug}",
        f"title\t{tr(topic.title_key)}",
        f"body\t{tr(topic.body_key)}",
    ]
    for related in topic.see_also:
        lines.append(f"see_also\t{related}")
    for legal_ref in topic.legal_refs:
        lines.append(f"legal_ref\t{legal_ref}")
    _emit(ctx, payload, lines)


@app.callback()
def topic_root(
    ctx: typer.Context,
    slug: str | None = typer.Argument(None, help=tr("cli.topic.opts.slug")),
) -> None:
    """List every topic when no slug is given; render the named topic otherwise."""

    if ctx.invoked_subcommand is not None:
        return
    catalogue = load_topic_catalogue()
    if slug is None:
        payload = {"topics": [topic.slug for topic in catalogue.topics]}
        lines = [f"slug\t{topic.slug}\t{tr(topic.title_key)}" for topic in catalogue.topics]
        _emit(ctx, payload, lines)
        return
    _render_topic(ctx, catalogue, slug)


__all__ = ["app"]
