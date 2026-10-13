"""The Anthropic-compatible gateway rows a lane can be built from."""

class AnthropicGateway:
    """One vendor's endpoint; only the field the script reads is declared."""

    @property
    def base_url_default(self) -> str | None: ...
