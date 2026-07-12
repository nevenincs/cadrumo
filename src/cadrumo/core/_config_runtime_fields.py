from __future__ import annotations

from pydantic import Field

from ._config_timeouts import AeatTimeoutSettings


class AeatRuntimeSettings(AeatTimeoutSettings):
    aeat_llm_openai_chat_completions_url: str = Field(
        default="https://api.openai.com/v1/chat/completions",
        description="OpenAI Chat Completions endpoint; override for OpenAI-compatible proxies",
    )
    aeat_llm_gemini_generate_content_template: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        description="Google Gemini generateContent endpoint template (``{model}`` is substituted)",
    )
    aeat_llm_ollama_chat_url: str = Field(
        default="http://127.0.0.1:11434/api/chat",
        description="Local Ollama /api/chat endpoint; override for non-localhost Ollama deployments",
    )
    aeat_llm_ollama_num_ctx: int = Field(
        default=8192,
        gt=0,
        description=(
            "Ollama context window (num_ctx) for local requests. The vision read sends "
            "the full registry allow-list prompt plus the encoded invoice image, which "
            "exceeds Ollama's 4096 default; 8192 fits the prompt + image + output with "
            "headroom and still runs on consumer hardware"
        ),
    )
    aeat_llm_vision_read_timeout_s: int = Field(
        default=300,
        gt=0,
        description=(
            "Per-request timeout for the on-host local vision read; larger than the "
            "general LLM timeout because a local vision model on consumer hardware "
            "(CPU or a modest GPU) can take one to several minutes to read an invoice"
        ),
    )
    aeat_llm_ollama_vision_model: str = Field(
        default="qwen2.5vl:3b",
        description=(
            "Local Ollama vision model used to read scanned/image evidence on-host "
            "(the default, gestor-allowed posture); must be a multimodal model pulled "
            "into the local Ollama runtime. Default qwen2.5vl:3b (~3 GB) is "
            "document/OCR-grade and runs on normal consumer hardware (modest GPU or "
            "CPU); override to qwen2.5vl:7b for an 8 GB+ GPU or moondream for "
            "CPU-only/low-memory (see the consumer-hardware vision-model ADR)"
        ),
    )
    aeat_llm_default_max_tokens: int = Field(
        default=1024,
        gt=0,
        description="Default maximum output tokens when an LLM request omits ``max_tokens``",
    )
    aeat_llm_default_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Default sampling temperature when an LLM request omits ``temperature``",
    )
    aeat_browser_locale: str = Field(
        default="es-ES",
        min_length=2,
        description="Default browser locale passed to Playwright context (BCP-47 tag)",
    )
    aeat_browser_timezone: str = Field(
        default="Europe/Madrid",
        min_length=1,
        description="Default IANA timezone string passed to Playwright context",
    )
    aeat_browser_viewport_width: int = Field(
        default=1366,
        gt=0,
        description="Default Playwright viewport width (px) for AEAT sede sessions",
    )
    aeat_browser_viewport_height: int = Field(
        default=900,
        gt=0,
        description="Default Playwright viewport height (px) for AEAT sede sessions",
    )
    aeat_file_lock_timeout_s: float = Field(
        default=30.0,
        gt=0,
        description="Default exclusive file-lock acquisition timeout (seconds)",
    )
    aeat_file_lock_retry_backoff_s: float = Field(
        default=0.05,
        gt=0,
        description="Sleep interval (seconds) between non-blocking file-lock acquire attempts",
    )
    aeat_bucket_lock_poll_interval_s: float = Field(
        default=0.1,
        gt=0,
        description="Polling interval (seconds) for bucket lockfile acquisition retries",
    )
    aeat_bucket_default_idle_lock_minutes: int = Field(
        default=15,
        gt=0,
        description="Fallback idle-lock window (minutes) when a bucket manifest omits the value",
    )
    aeat_auth_clave_movil_lock_buffer_s: int = Field(
        default=90,
        gt=0,
        description="Headroom (seconds) added to ``aeat_clave_movil_timeout_ms`` for the acquisition lock TTL",
    )
    aeat_auth_certificate_lock_ttl_s: int = Field(
        default=180,
        gt=0,
        description="Acquisition lock TTL (seconds) for certificate-backed AEAT auth flows",
    )
    aeat_log_stderr_level: str = Field(
        default="ERROR",
        description="Log level for the stderr handler installed by ``aeat.core.logging``",
    )
    aeat_log_file_level: str = Field(
        default="DEBUG",
        description="Log level for the file handler installed by ``aeat.core.logging``",
    )
    aeat_log_root_level: str = Field(
        default="DEBUG",
        description="Root logger level installed by ``aeat.core.logging``",
    )
    aeat_manuals_http_timeout_s: float = Field(
        default=60.0,
        gt=0,
        description="HTTP timeout (seconds) for AEAT manual PDF downloads",
    )
