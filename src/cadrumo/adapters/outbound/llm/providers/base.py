"""Provider adapter contract for the LLM outbound subpackage.

Defines the normalized request and response shapes that every concrete provider
adapter consumes and produces, so the higher-level :class:`~llm.LLMClient` can stay
provider-agnostic. Adapters live in sibling modules under
:mod:`llm.providers`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from .....core.config_support import LLMProvider
from .....core.models import STRICT_FROZEN_CONFIG
from ..models import MultimodalImageInput


class ProviderRequest(BaseModel):
    """Normalized inbound payload passed to a provider adapter.

    Attributes:
        request_id: Stable opaque hash identifying the public request, suitable
            for cross-referencing cache and usage records.
        model: Fully resolved provider model identifier.
        prompt: Rendered prompt text sent to the provider.
        system: Optional system prompt prepended to the conversation.
        max_tokens: Maximum number of output tokens to request, or ``None``
            meaning the run states no bound and the lane's own behaviour
            applies. Cadrumo supplies no value of its own.
        temperature: Sampling temperature in the inclusive range ``[0.0, 1.0]``,
            or ``None`` meaning the parameter is OMITTED from the wire rather
            than sent at some default. The distinction is load-bearing: a
            vendor's newer models reject an explicitly-sent ``temperature``
            with a 400, so "no preference" cannot be expressed as a number.
        timeout_s: Per-request timeout in seconds.
        images: On-host-prepared image inputs for a multimodal read (empty for a
            text-only request), each carrying its base64 payload AND its declared
            media type -- a cloud provider needs the type on the wire, so the
            adapter cannot receive a bare string. Transient and in-memory only;
            an adapter forwards them to a vision model and they are never
            persisted (sensitive-financial-data-secure-storage-only).
    """

    model_config = STRICT_FROZEN_CONFIG

    request_id: str = Field(description="Stable public request hash.")
    model: str = Field(description="Resolved provider model.")
    prompt: str = Field(description="Rendered prompt text.")
    system: str | None = Field(default=None, description="Optional system prompt.")
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Maximum output tokens, or None to state no bound.",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Sampling temperature, or None to omit the parameter entirely.",
    )
    timeout_s: int = Field(ge=1, description="Per-request timeout in seconds.")
    images: tuple[MultimodalImageInput, ...] = Field(
        default=(),
        description="On-host image inputs for a multimodal request; empty for text-only.",
    )


class ProviderCompletion(BaseModel):
    """Normalized provider response returned to the public client.

    Attributes:
        text: Generated text payload.
        model: Provider model that actually served the request (may differ from
            the requested model when a vendor performs upstream routing).
        input_tokens: Provider-reported prompt token count.
        output_tokens: Provider-reported output token count.
        provider_request_id: Provider-native request or message id when
            available, otherwise ``None``.
    """

    model_config = STRICT_FROZEN_CONFIG

    text: str = Field(description="Generated text.")
    model: str = Field(description="Provider model that served the request.")
    input_tokens: int = Field(ge=0, description="Provider-reported prompt token count.")
    output_tokens: int = Field(ge=0, description="Provider-reported output token count.")
    provider_request_id: str | None = Field(default=None, description="Provider-native request or message id.")


class ProviderAdapter(ABC):
    """The interface every concrete provider adapter implements.

    Public because it is a shared contract, not an implementation detail: the
    client type-hints against it, each vendor module subclasses it, and the
    outbound-adapter tests build their own conforming double. A name that says
    private while four packages depend on it teaches the wrong thing about
    where the boundary is.

    Concrete subclasses bind :attr:`provider` to a member of
    :class:`~llm.LLMProvider` and implement
    :meth:`complete` to translate the normalized
    :class:`ProviderRequest` into a vendor-specific call.

    Attributes:
        provider: Identifier of the LLM vendor this adapter speaks to.
        supports_images: Whether :meth:`complete` actually forwards
            :attr:`ProviderRequest.images` to the vendor. Declared as DATA on
            the class rather than left to each adapter to remember, and
            enforced once at the client's single dispatch point. Defaults to ``False`` so a newly added adapter is
            text-only until it has genuinely implemented the image path; the
            failure of the opposite default is silent and unbounded.
    """

    provider: LLMProvider
    supports_images: bool = False

    def unsupported_parameters(self, model: str) -> frozenset[str]:
        """Return the request parameters this adapter must NOT put on the wire for *model*.

        The second half of the capability axis :attr:`supports_images` opened.
        Both defects are one shape -- a request field the transport assumed was
        universal -- and they failed in opposite directions: ``images`` was
        silently DROPPED by adapters that could not carry it, and
        ``temperature`` is unconditionally SENT to models that reject it. One
        was dropped without telling anyone; one is sent without asking.

        Declared per MODEL rather than per adapter because that is where vendors
        actually differ: one adapter may serve models that accept a parameter
        and models that refuse it, so an adapter-wide flag cannot express the
        constraint. An adapter whose SDK has no such parameter at all, as the
        Anthropic SDK has no ``temperature``, declares it for every model.

        Defaults to the empty set -- an adapter carries every parameter until it
        declares otherwise. That is the opposite default from
        :attr:`supports_images`, deliberately: silently dropping an image makes
        a model answer from nothing, which is unbounded harm, while omitting a
        sampling parameter falls back to the vendor's own default. The
        restrictive default belongs where the failure is silent, not where it is
        merely a different temperature.
        """
        del model
        return frozenset[str]()

    @abstractmethod
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request against the underlying provider.

        Args:
            request: Normalized request payload.

        Returns:
            Normalized :class:`ProviderCompletion` response.
        """
