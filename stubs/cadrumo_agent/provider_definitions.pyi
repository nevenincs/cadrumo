"""Canonical provider identities, as ``ExecutionLane`` names them."""

from enum import StrEnum

class Provider(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"
    ANTIGRAVITY = "antigravity"
    KIMI = "kimi"
    ZAI = "zai"
    ZHIPU = "zhipu"
    DEEPSEEK = "deepseek"
    MOONSHOT = "moonshot"
    MINIMAX = "minimax"
    QWEN = "qwen"

class ProviderTransport(StrEnum):
    API = "api"
    CLI = "cli"
