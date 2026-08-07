"""Operator surface for off-host consent: what was sent, and the way back on-host.

Two verbs under ``aeat app ledger evidence consent``. ``list`` enumerates the
profile's off-host dispatches and marks the artefacts derived from them;
``rederive`` re-reads one of those artefacts on this host from its cached
transcription.

**Both surfaces state that transmitted bytes cannot be recalled, every time.**
The statement is carried in the JSON payload as well as the rendered lines,
because an agent consuming the envelope never sees prose, and this is the one
caveat on this surface an operator must not act without. It is unconditional:
an empty history is still surfaced with the caveat, since an operator with no
history is precisely the one deciding whether to enable the route.

See Also:
    :func:`~application.ledger.survey_cloud_consent`
        The enumeration behind ``consent list``.
    :func:`~application.ledger.rederive_artefact_on_host`
        The on-host re-derivation behind ``consent rederive``.
"""

from __future__ import annotations

import typer

from ...application.ledger import (
    ConsentedDispatch,
    rederive_artefact_on_host,
    survey_cloud_consent,
)
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._common import _bad, _emit_envelope, _state, _tx_repo
from ._ledger_business_payloads import (
    EvidenceConsentListResult,
    EvidenceConsentRederiveResult,
)

_UNRECALLABLE_LOCALE_KEY = "cli.app.ledger.evidence.consent.bytes_unrecallable"
_LIST_HELP_LOCALE_KEY = "cli.app.ledger.evidence.consent.list_help"
_REDERIVE_HELP_LOCALE_KEY = "cli.app.ledger.evidence.consent.rederive_help"
_REDERIVED_LOCALE_KEY = "cli.app.ledger.evidence.consent.rederived"
_REDERIVE_REFUSED_LOCALE_KEY = "cli.app.ledger.evidence.consent.rederive_refused"
_GROUP_HELP_LOCALE_KEY = "cli.app.ledger.evidence.consent.group_help"

consent_app = typer.Typer(no_args_is_help=True)


def _unrecallable_notice() -> Notice:
    """Build the standing "this cannot be undone" notice.

    A :class:`Notice` rather than a bespoke ``result`` field, per the envelope
    contract, and WARNING rather than INFO because an operator who reads it as
    routine has misunderstood what withdrawal does.
    """
    return Notice(
        code="evidence_consent_bytes_unrecallable",
        severity=NoticeSeverity.WARNING,
        message=tr(_UNRECALLABLE_LOCALE_KEY),
    )


def register_evidence_consent_commands(evidence_app: typer.Typer) -> None:
    """Mount the consent verbs under the evidence group."""
    evidence_app.add_typer(
        consent_app,
        name="consent",
        help=tr(_GROUP_HELP_LOCALE_KEY),
    )
    _register_consent_list_command()
    _register_consent_rederive_command()


def _register_consent_list_command() -> None:
    @consent_app.command("list", help=tr(_LIST_HELP_LOCALE_KEY))
    def consent_list(ctx: typer.Context) -> None:
        """List off-host dispatches and the artefacts derived from them."""
        bucket_id = _tx_repo(_state()).bucket_id
        survey = survey_cloud_consent(bucket_id=bucket_id, settings=_state().settings)
        payload = {
            "bucket_id": bucket_id,
            "transmitted_bytes_are_unrecallable": survey.transmitted_bytes_are_unrecallable,
            "consented_dispatches": [_dispatch_payload(row) for row in survey.consented_dispatches],
            "cloud_derived_artefacts": [
                {
                    "evidence_reference": row.evidence_reference,
                    "provenance_stamp": row.provenance_stamp,
                    "transport": row.transport,
                    "drafted_at": row.drafted_at.isoformat(),
                    "rederivable_on_host": row.rederivable_on_host,
                }
                for row in survey.cloud_derived_artefacts
            ],
        }
        lines = ["evidence_reference\ttransport\trederivable_on_host\tprovenance_stamp"]
        lines.extend(
            f"{row.evidence_reference}\t{row.transport or '-'}\t"
            f"{'-' if row.rederivable_on_host is None else row.rederivable_on_host}\t{row.provenance_stamp}"
            for row in survey.cloud_derived_artefacts
        )
        _emit_envelope(
            ctx,
            command="ledger.evidence.consent.list",
            result=EvidenceConsentListResult.model_validate(payload),
            lines=lines,
            notices=[_unrecallable_notice()],
        )


def _dispatch_payload(dispatch: ConsentedDispatch) -> dict[str, str]:
    """Project one recorded dispatch onto its JSON shape."""
    return {
        "evidence_content_address": dispatch.evidence_content_address,
        "provider": dispatch.provider,
        "model": dispatch.model,
        "surface": dispatch.surface,
        "recorded_at": dispatch.recorded_at.isoformat(),
    }


def _register_consent_rederive_command() -> None:
    @consent_app.command("rederive", help=tr(_REDERIVE_HELP_LOCALE_KEY))
    def consent_rederive(
        ctx: typer.Context,
        evidence_reference: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.consent.evidence_reference_help"),
        ),
        content_address: str = typer.Option(
            ...,
            "--content-address",
            help=tr("cli.app.ledger.evidence.consent.content_address_help"),
        ),
        transcriber: str = typer.Option(
            ...,
            "--transcriber",
            help=tr("cli.app.ledger.evidence.consent.transcriber_help"),
        ),
    ) -> None:
        """Re-derive one artefact on this host from its cached transcription."""
        bucket_id = _tx_repo(_state()).bucket_id
        try:
            outcome = rederive_artefact_on_host(
                bucket_id=bucket_id,
                evidence_reference=evidence_reference,
                source_content_sha256=content_address,
                transcriber_cache_key=transcriber,
                settings=_state().settings,
                read_on_host=_on_host_reader(),
            )
        except ValueError as exc:
            _bad(tr(_REDERIVE_REFUSED_LOCALE_KEY, detail=str(exc)))
            return
        _emit_envelope(
            ctx,
            command="ledger.evidence.consent.rederive",
            result=EvidenceConsentRederiveResult.model_validate(
                {
                    "bucket_id": bucket_id,
                    "evidence_reference": outcome.evidence_reference,
                    "previous_provenance_stamp": outcome.previous_provenance_stamp,
                    "provenance_stamp": outcome.provenance_stamp,
                    "transcription_reused": outcome.transcription_reused,
                    "transmitted_bytes_are_unrecallable": True,
                },
            ),
            lines=[
                tr(
                    _REDERIVED_LOCALE_KEY,
                    reference=outcome.evidence_reference,
                    previous=outcome.previous_provenance_stamp,
                    current=outcome.provenance_stamp,
                ),
            ],
            notices=[_unrecallable_notice()],
        )


def _on_host_reader() -> object:
    """Resolve the on-host reader, deferred to keep the gated extra optional.

    Imported at call time rather than at module load so this CLI module stays
    importable on an install without the inference extra: the verb refuses with
    the extra's own instructive message, which is better than the whole ledger
    CLI failing to load.
    """
    from ...llm import TextInvoiceFieldExtractor

    def _read(transcribed_text: str, /) -> tuple[object, str]:
        extractor = TextInvoiceFieldExtractor()
        return extractor.extract(evidence_text=transcribed_text), extractor.decided_by

    return _read
