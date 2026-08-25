"""CLI projection for adding one schema-declared repeatable profile row."""

from __future__ import annotations

import typer

from ....core.external_constants import OutputLanguage
from .._common import activate_subcommand_output_language, emit_envelope
from .._errors import CliRefusedBoundaryError


def _parse_values(tokens: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in tokens:
        field, separator, value = token.partition("=")
        field = field.strip()
        if not separator or not field:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.add_row.invalid_value",
            )
        if field in values:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.add_row.duplicate_field",
                context={"field": field},
            )
        values[field] = value
    return values


def profile_add_row(
    ctx: typer.Context,
    section: str,
    value: list[str],
    output_language: OutputLanguage | None = None,
) -> None:
    """Add one row through the application-owned schema and atomic writer."""
    activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile.section_rows import add_profile_repeatable_section_row
    from .._config_payloads import ConfigProfileAddRowResult
    from ._profile_support import resolve_active_profile_pointer

    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    outcome = add_profile_repeatable_section_row(
        profile_id=pointer.bucket_id,
        section_key=section,
        values=_parse_values(value),
    )
    result = ConfigProfileAddRowResult(
        profile_id=outcome.record.profile_id,
        section=outcome.section_key,
        row_index=outcome.row_index,
        record_revision=outcome.record.record_revision,
        content_digest=outcome.record.content_digest,
    )
    emit_envelope(
        ctx,
        command="config.profile.add.row",
        result=result,
        lines=[
            f"profile_id\t{result.profile_id}",
            f"section\t{result.section}",
            f"row_index\t{result.row_index}",
            f"record_revision\t{result.record_revision}",
        ],
    )


__all__ = ["profile_add_row"]
