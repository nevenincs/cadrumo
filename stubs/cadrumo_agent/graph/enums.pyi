"""The execution lanes a provider catalog is served for."""

from enum import StrEnum

from ..provider_definitions import Provider, ProviderTransport

class ExecutionLane(StrEnum):
    CLAUDE_API = "anthropic"
    ANTIGRAVITY = "antigravity"
    CLAUDE_CLI = "claude"
    CODEX_CLI = "codex"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    MINIMAX = "minimax"
    MOONSHOT = "moonshot"
    CODEX_API = "openai"
    QWEN = "qwen"
    ZAI = "zai"
    ZHIPU = "zhipu"

    @property
    def provider(self) -> Provider: ...
    @property
    def transport(self) -> ProviderTransport: ...
