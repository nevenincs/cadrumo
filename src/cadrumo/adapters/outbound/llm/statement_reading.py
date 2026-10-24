"""Bank-statement movement reading with the on-host models.

A statement page in any bank's layout and language is a text representation of
its movements, so reading it is a transcription-anchored semantic task, the
same shape as reading an invoice: the model is handed the page's text and
copies out what each movement prints. It never calculates, converts or
reformats a value, and it is never trusted to have done so. Every string it
returns is a proposal that the inbound statement provider anchors to a printed
line and reconciles against the printed balances before anything reaches the
ledger, so a value the page does not print is dropped there, whatever the model
said.

**On-host only.** Ledger import offers no off-host consent step, so this reader
names the LOCAL provider on every request and marks every request as derived
from taxpayer evidence. A configuration that pointed the client at a hosted
vendor would therefore refuse at the client's consent gate rather than send a
statement off the machine.

**Language-neutral.** The prompt names movement concepts (booking date, amount,
running balance) and lets the model find them under whatever heading and in
whatever language the page uses. No bank, heading or narrative is named.

**Scanned pages.** A page that carries no text layer is rasterised on-host and
transcribed by the local vision model in transcription role; the text model
then reads that transcription exactly as it reads a text layer.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping

from pydantic import TypeAdapter, ValidationError

from ....application.ledger.document_transcription import DocumentTranscription
from ....application.ledger.statement_reading import (
    ProposedDirection,
    ProposedStatementMovement,
    ProposedStatementPage,
)
from ....application.user_profile.capabilities import resolve_active_capability
from ....core.capabilities import ServiceCapability
from ....core.config import Settings, load_settings
from ....core.config_support import LLMProvider
from ....core.image_media_type import ImageMediaType
from ....core.model_catalogue import ModelRole
from ....core.optional_extras import LLM_EXTRA, require_optional_extra
from ....core.provenance_stamp import build_provenance_stamp
from .client import LLMClient
from .evidence_draft_vision import LocalVisionDocumentTranscriber
from .models import LLMRequest, MultimodalImageInput
from .providers.local import rasterise_pdf_pages_to_base64_png
from .response_json import first_json_object

__all__ = [
    "STATEMENT_READING_PROMPT_ID",
    "LocalStatementReader",
    "build_statement_page_prompt",
    "parse_statement_page_response",
]

#: Identifier under which this capability's calls are recorded in LLM usage and
#: run records, so a statement read is attributable separately from other reads.
STATEMENT_READING_PROMPT_ID = "bank-statement-movements"

#: Ceiling on one page's reply. A dense statement page carries a few dozen
#: movements of a few short strings each, which this bounds generously while
#: still stopping a runaway generation.
_MAX_REPLY_TOKENS = 4096

#: Copying printed values has one right answer; sampling variety buys nothing.
_READING_TEMPERATURE = 0.0

#: A decoded JSON object, validated to string keys so every lookup is typed.
_JSON_OBJECT: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])

#: A decoded JSON array of arbitrary members.
_JSON_ARRAY: TypeAdapter[list[object]] = TypeAdapter(list[object])

_EMPTY_PAGE = ProposedStatementPage(movements=(), opening_balance=None, closing_balance=None, currency=None)
_UNUSABLE_PAGE = ProposedStatementPage(
    movements=(),
    opening_balance=None,
    closing_balance=None,
    currency=None,
    reply_usable=False,
)


def build_statement_page_prompt(page_text: str) -> str:
    """Build the instruction the model receives for one statement page.

    Separate from the transport so the exact instruction is assertable without
    dispatching a request.

    Args:
        page_text: The page transcription, printed forms intact.

    Returns:
        The full prompt: the task, the copying rules, the reply shape, then the
        page text under a delimiter that marks where the instructions end.
    """
    return (
        "Read one page of a bank account statement and list every account movement printed on it.\n\n"
        "A movement is one booked transaction that moves money into or out of the account. A movement "
        "line prints its own date and its own amount. Never list an opening or closing balance, a total, "
        "a subtotal, a fee or interest summary, a heading or a note. If the page prints no movement, "
        "reply with an empty list.\n\n"
        "Copy every value exactly as printed: the same characters, digits, separators and signs. Never "
        "calculate, convert, translate or reformat a value. Use null for anything the page does not print.\n\n"
        "For each movement give:\n"
        "- booked_date: the booking or transaction date\n"
        "- value_date: the separate value date, if printed\n"
        "- description: the movement's printed text (concept, reference, remittance information), "
        "lines joined with a space\n"
        "- counterparty: the other party's name, if printed apart from the description\n"
        "- amount: the movement amount\n"
        '- direction: "in" when money enters the account, "out" when it leaves; read it from the sign, '
        "the debit or credit column, or the wording printed with the amount\n"
        "- balance: the running account balance printed on the movement's line, if any\n\n"
        "Also give, when this page prints them: opening_balance (the balance before the first movement), "
        "closing_balance (the balance after the last movement) and currency (the currency code or symbol "
        "the amounts are printed in).\n\n"
        "Reply with this JSON object and nothing else:\n"
        '{"movements": [{"booked_date": "", "value_date": null, "description": "", "counterparty": null, '
        '"amount": "", "direction": "in", "balance": null}], "opening_balance": null, '
        '"closing_balance": null, "currency": null}\n\n'
        "PAGE TEXT:\n"
        f"{page_text}"
    )


def _text(payload: Mapping[str, object], key: str) -> str | None:
    """Return ``payload[key]`` when it is a non-blank string, else ``None``.

    A number in place of a printed form is not the printed form -- ``8.55``
    where the page prints ``8,55`` -- so it is treated as absent rather than
    stringified into something the page never showed.
    """
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _direction(payload: Mapping[str, object]) -> ProposedDirection | None:
    """Return the proposed direction when it is one of the two permitted tokens."""
    value = _text(payload, "direction")
    if value is None:
        return None
    try:
        return ProposedDirection(value.strip().casefold())
    except ValueError:
        return None


def _objects(value: object) -> list[dict[str, object]]:
    """Return the JSON objects of an array, skipping members that are not objects."""
    try:
        members = _JSON_ARRAY.validate_python(value)
    except ValidationError:
        return []
    objects: list[dict[str, object]] = []
    for member in members:
        try:
            objects.append(_JSON_OBJECT.validate_python(member))
        except ValidationError:
            continue
    return objects


def parse_statement_page_response(text: str) -> ProposedStatementPage:
    """Turn one model reply into the page's proposal.

    Never raises for a malformed reply. A reply carrying no JSON object, or an
    object of the wrong shape, yields a page marked unusable, which the
    provider reports; a movement entry that is not an object is skipped. Every
    value is kept verbatim for the grounding stage to judge.

    Args:
        text: The model's reply, in whatever wrapping it arrived.

    Returns:
        The page proposal.
    """
    payload = first_json_object(text)
    if payload is None:
        return _UNUSABLE_PAGE
    try:
        decoded = _JSON_OBJECT.validate_python(json.loads(payload))
    except (ValueError, ValidationError):
        return _UNUSABLE_PAGE
    entries = tuple(_objects(decoded.get("movements")))
    movements = tuple(
        ProposedStatementMovement(
            booked_date=_text(entry, "booked_date"),
            value_date=_text(entry, "value_date"),
            description=_text(entry, "description"),
            counterparty=_text(entry, "counterparty"),
            amount=_text(entry, "amount"),
            direction=_direction(entry),
            balance=_text(entry, "balance"),
        )
        for entry in entries
    )
    return ProposedStatementPage(
        movements=movements,
        opening_balance=_text(decoded, "opening_balance"),
        closing_balance=_text(decoded, "closing_balance"),
        currency=_text(decoded, "currency"),
    )


class LocalStatementReader:
    """Read statement pages with the on-host text model and, for scans, the vision model.

    Args:
        model: Optional text model identifier; ``None`` uses the configured
            LOCAL text model.
        client: Injected :class:`~llm.LLMClient`; default-constructed against
            the resolved settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        vision_transcriber: Injected vision transcriber for scanned pages;
            built on first use otherwise.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        vision_transcriber: LocalVisionDocumentTranscriber | None = None,
    ) -> None:
        """Build the reader, refusing first when the ``llm`` extra is absent."""
        require_optional_extra(LLM_EXTRA)
        self._settings = settings if settings is not None else load_settings()
        self._model = model if model is not None else self._settings.cadrumo_llm_ollama_text_model
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=self._settings,
                caller="cadrumo.adapters.outbound.llm.statement_reading",
                prompt_id=STATEMENT_READING_PROMPT_ID,
            )
        )
        self._vision_transcriber = vision_transcriber

    @property
    def decided_by(self) -> str:
        """Provenance stamp naming the transport and text model of the read."""
        return build_provenance_stamp(provider=LLMProvider.LOCAL, reader="statement-read", model=self._model)

    def propose_page(self, transcription: DocumentTranscription) -> ProposedStatementPage:
        """Propose the movements printed on one transcribed page.

        Args:
            transcription: The page transcription.

        Returns:
            The page proposal; an empty one for a page whose text is blank,
            which is never sent to a model that would be invited to invent.
        """
        if not transcription.text.strip():
            return _EMPTY_PAGE
        response = asyncio.run(self._client.complete(self._build_request(transcription.text)))
        return parse_statement_page_response(response.text)

    def transcribe_scanned_pages(
        self,
        pdf_bytes: bytes,
        *,
        page_numbers: tuple[int, ...],
        source_content_sha256: str,
    ) -> Mapping[int, DocumentTranscription]:
        """Transcribe the named one-based pages with the on-host vision model.

        Returns nothing when the operator has turned on-host vision reading
        off, so the provider refuses the statement as incomplete rather than
        reading it short.
        """
        transcriptions: dict[int, DocumentTranscription] = {}
        if not page_numbers:
            return transcriptions
        if not resolve_active_capability(ServiceCapability.LLM_VISION, settings=self._settings).enabled:
            return transcriptions
        renders = rasterise_pdf_pages_to_base64_png(pdf_bytes)
        transcriber = self._vision()
        for page_number in page_numbers:
            if not 1 <= page_number <= len(renders):
                continue
            image = MultimodalImageInput.from_base64(renders[page_number - 1], ImageMediaType.PNG)
            transcriptions[page_number] = transcriber.transcribe(
                evidence_images=(image,),
                source_content_sha256=source_content_sha256,
            )
        return transcriptions

    def _vision(self) -> LocalVisionDocumentTranscriber:
        """Return the vision transcriber, building it on first use."""
        if self._vision_transcriber is None:
            self._vision_transcriber = LocalVisionDocumentTranscriber(settings=self._settings)
        return self._vision_transcriber

    def _build_request(self, page_text: str) -> LLMRequest:
        """Build the completion request for one page's text."""
        return LLMRequest(
            prompt=build_statement_page_prompt(page_text),
            max_tokens=_MAX_REPLY_TOKENS,
            temperature=_READING_TEMPERATURE,
            provider_override=LLMProvider.LOCAL,
            model_override=self._model,
            evidence_derived=True,
            model_role=ModelRole.TEXT_EXTRACTION,
            expects_json=True,
        )
