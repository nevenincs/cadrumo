"""``aeat config profile complete-setup`` — declare the active profile ready to file from.

A profile is born ``INCOMPLETE`` on purpose: creation applies supplied facts after
the record exists, so a rejected fact leaves a correctable profile rather than
nothing. The wizard's checkpoint store depends on the same thing, treating
``INCOMPLETE`` as the state a resumed session resumes from.

Nothing then completed it. ``ProfileRecordRepository.complete_setup`` existed and
was exercised only by tests, so no profile could reach ``COMPLETE`` in production
and every modelo verb gated on that state -- ``work create`` and therefore
calculate, verify and export -- refused outright. This verb is that missing door.

It is a DECLARATION, not an inference, which is why it is a verb rather than a
side effect of ``create`` or ``edit``. As the repository puts it, ``COMPLETE`` is
not a label for a record that has stopped being edited, it is the CLAIM that
nothing required is missing. Only the operator can make that claim, so the CLI
asks for it explicitly and the promotion still refuses if the claim is untrue:
``complete_setup`` re-judges the record at the strictest setting the profile
authority offers before writing anything.
"""

from __future__ import annotations

import typer

from ....core import resolve_active_bucket_id
from ....core.i18n import tr
from .._common import bad, emit_envelope

# Eager import so the @register_schema decorator runs when this module is imported
# on the CLI build path, keeping the leaf in the JSON-contract registry.
from ._complete_setup_payloads import ProfileCompleteSetupResult


def _still_missing(record: object) -> tuple[str, ...]:
    """Return the profile paths that keep this record out of ``COMPLETE``.

    Both authorities are consulted and their answers unioned in order: the
    schema-required set, and the conditional set that depends on facts already
    answered (an IRNR representative, a socio's country). Reporting only one of
    them would send the operator to fix a field and meet the same refusal again.
    """
    from ....application.user_profile import (
        conditional_profile_missing_required,
        missing_required_field_paths,
        record_to_path_values,
    )
    from ....domain.user_profile import load_user_profile_schema

    values = record_to_path_values(record)
    schema_missing = missing_required_field_paths(load_user_profile_schema(), values)
    conditional_missing = conditional_profile_missing_required(values)
    # dict.fromkeys de-duplicates while preserving order: a path both authorities
    # name is one thing to fix, not two.
    return tuple(dict.fromkeys((*schema_missing, *conditional_missing)))


def register(profile_app: typer.Typer) -> None:
    """Mount ``complete-setup`` on the ``config profile`` command group."""

    def profile_complete_setup(ctx: typer.Context) -> None:
        """Promote the active profile's setup state to complete."""
        from ....application.user_profile import ProfileRecordRepository
        from ....domain.user_profile import ProfileSchemaValidationError, ProfileSetupState

        from .._common import _no_active_profile_refusal

        profile_id = resolve_active_bucket_id()
        if profile_id is None:
            raise _no_active_profile_refusal()

        profiles = ProfileRecordRepository.for_current_session(profile_id)
        current = profiles.load(profile_id)

        # Idempotent no-op ahead of everything else, matching the repository's own
        # ordering: a retry that changes no state must not be held to a contract
        # the stored record may predate, and an autonomous operator retries.
        if current.setup_state is ProfileSetupState.COMPLETE:
            already = ProfileCompleteSetupResult.model_validate(
                {
                    "profile_id": profile_id,
                    "setup_state": current.setup_state.value,
                    "record_revision": current.record_revision,
                    "already_complete": True,
                },
            )
            emit_envelope(
                ctx,
                command="config.profile.complete_setup",
                result=already,
                lines=[tr("cli.config.profile.complete_setup.already_complete")],
            )
            return

        try:
            promoted = profiles.complete_setup(
                profile_id,
                expected_revision=current.record_revision,
                expected_content_digest=current.content_digest,
            )
        except ProfileSchemaValidationError as exc:
            missing = _still_missing(current)
            raise bad(
                tr(
                    "cli.config.profile.complete_setup.incomplete",
                    paths=", ".join(missing) if missing else "-",
                ),
            ) from exc

        result = ProfileCompleteSetupResult.model_validate(
            {
                "profile_id": profile_id,
                "setup_state": promoted.setup_state.value,
                "record_revision": promoted.record_revision,
            },
        )
        emit_envelope(
            ctx,
            command="config.profile.complete_setup",
            result=result,
            lines=[tr("cli.config.profile.complete_setup.completed")],
        )

    profile_app.command(
        "complete-setup",
        help=tr("cli.config.profile.complete_setup.help"),
    )(profile_complete_setup)
