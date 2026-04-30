"""``aeat llm`` sub-app for prompt execution, translation, cache, and usage."""

from __future__ import annotations

import asyncio
from datetime import date

import typer

from ....adapters.outbound.llm import LLMCache, LLMClient, LLMRequest, PromptRegistry, Translator, UsageRecorder

app = typer.Typer(name="llm", no_args_is_help=True, help="LLM helpers.")
cache_app = typer.Typer(name="cache", no_args_is_help=True, help="LLM cache helpers.")
app.add_typer(cache_app, name="cache")


def _parse_inputs(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            msg = f"Invalid --input value {item!r}; expected key=value."
            raise typer.BadParameter(msg)
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


@app.command(name="complete")
def complete(
    prompt_id: str = typer.Argument(..., help="Prompt id from the registry."),
    language: str | None = typer.Option(None, "--language", help="Optional output language."),
    inputs: list[str] | None = typer.Option(None, "--input", help="Prompt variable assignment as key=value."),
) -> None:
    """Render and execute a registered prompt once.

    Args:
        prompt_id: Prompt id from the registry.
        language: Optional output language code.
        inputs: Prompt variable assignments as `key=value`.
    """

    registry = PromptRegistry.seeded()
    definition = registry.get(prompt_id)
    try:
        prompt = definition.template.format_map(_parse_inputs(inputs or []))
    except KeyError as exc:
        raise typer.BadParameter(f"Missing prompt variable {exc.args[0]!r}.") from exc
    client = LLMClient(prompt_id=definition.id)
    response = asyncio.run(client.complete(LLMRequest(prompt=prompt, language=language)))
    typer.echo(response.text)


@app.command(name="translate")
def translate(
    source_lang: str = typer.Option(..., "--from", help="Source language code."),
    target_lang: str = typer.Option(..., "--to", help="Target language code."),
    text: str = typer.Argument(..., help="Text to translate."),
    context: str | None = typer.Option(None, "--context", help="Optional translation context."),
) -> None:
    """Translate a single text with the configured provider.

    Args:
        source_lang: Source language code.
        target_lang: Target language code.
        text: Text to translate.
        context: Optional translation context.
    """

    translation = asyncio.run(Translator().translate(text, source_lang, target_lang, context=context))
    typer.echo(translation.text)


@cache_app.command(name="stats")
def cache_stats() -> None:
    """Print cache statistics."""

    typer.echo(LLMCache().stats().model_dump_json(indent=2))


@cache_app.command(name="prune")
def cache_prune() -> None:
    """Delete cached responses."""

    typer.echo(f"removed {LLMCache().prune()} cache file(s)")


@app.command(name="usage")
def usage(
    since: str | None = typer.Option(None, "--since", help="Inclusive lower date bound as YYYY-MM-DD."),
    until: str | None = typer.Option(None, "--until", help="Inclusive upper date bound as YYYY-MM-DD."),
) -> None:
    """Summarize usage and estimated cost.

    Args:
        since: Optional inclusive lower date bound as `YYYY-MM-DD`.
        until: Optional inclusive upper date bound as `YYYY-MM-DD`.
    """

    since_date = None if since is None else date.fromisoformat(since)
    until_date = None if until is None else date.fromisoformat(until)
    typer.echo(UsageRecorder().summarize(since=since_date, until=until_date).model_dump_json(indent=2))


__all__ = ["app"]
