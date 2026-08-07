from __future__ import annotations

from pydantic import Field

from ._config_timeouts import CadrumoTimeoutSettings


class CadrumoRuntimeSettings(CadrumoTimeoutSettings):
    cadrumo_llm_openai_chat_completions_url: str = Field(
        default="https://api.openai.com/v1/chat/completions",
        description="OpenAI Chat Completions endpoint; override for OpenAI-compatible proxies",
    )
    cadrumo_llm_gemini_generate_content_template: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        description="Google Gemini generateContent endpoint template (``{model}`` is substituted)",
    )
    cadrumo_llm_ollama_chat_url: str = Field(
        default="http://127.0.0.1:11434/api/chat",
        description="Local Ollama /api/chat endpoint; override for non-localhost Ollama deployments",
    )
    cadrumo_llm_ollama_num_ctx: int = Field(
        default=8192,
        gt=0,
        description=(
            "Ollama context window (num_ctx) for local requests. The vision read sends "
            "the full registry allow-list prompt plus the encoded invoice image, which "
            "exceeds Ollama's 4096 default; 8192 fits the prompt + image + output with "
            "headroom and still runs on consumer hardware"
        ),
    )
    cadrumo_llm_vision_read_timeout_s: int = Field(
        default=300,
        gt=0,
        description=(
            "Per-request timeout for the on-host local vision read; larger than the "
            "general LLM timeout because a local vision model on consumer hardware "
            "(CPU or a modest GPU) can take one to several minutes to read an invoice"
        ),
    )
    cadrumo_llm_ollama_vision_model: str = Field(
        default="qwen2.5vl:3b",
        description=(
            "Local Ollama vision model used to read scanned/image evidence on-host "
            "(the default, gestor-allowed posture); must be a multimodal model pulled "
            "into the local Ollama runtime. Default qwen2.5vl:3b (~3 GB) is "
            "document/OCR-grade and runs on normal consumer hardware (modest GPU or "
            "CPU); override to qwen2.5vl:7b for an 8 GB+ GPU or moondream for "
            "CPU-only/low-memory hardware"
        ),
    )
    cadrumo_llm_ollama_text_model: str = Field(
        default="qwen2.5:3b",
        description=(
            "Local Ollama TEXT model used to classify a text-layer document on-host. "
            "Chosen under the same consumer-hardware constraint that binds the vision "
            "default rather than beside it: qwen2.5:3b is ~2 GB, comfortably under the "
            "declared memory floor, and is the text sibling of the qwen2.5vl:3b vision "
            "default, so a machine provisioned for one is provisioned for the other. "
            "This model reads only the extracted text and selects from the registry "
            "allow-list; it never emits a regulated number. Override upward "
            "(qwen2.5:7b) on a larger GPU"
        ),
    )
    cadrumo_llm_model_runtime_memory_floor_bytes: int = Field(
        default=8 * 1024**3,
        gt=0,
        description=(
            "Minimum total system memory the local model runtime needs before a "
            "vision read is worth attempting. Sized for the default vision model "
            "(qwen2.5vl:3b, ~3 GB of weights) plus the 8192-token context window "
            "and normal OS residency, which is why the floor sits well above the "
            "weight size alone. Below it the runtime does not refuse -- it loads "
            "and thrashes, or is killed mid-read, which reaches the operator as "
            "an unexplained timeout rather than as a hardware shortfall. Tunable "
            "because the floor tracks the configured model: lower it for "
            "moondream on low-memory hardware, raise it for qwen2.5vl:7b"
        ),
    )
    cadrumo_llm_default_max_tokens: int = Field(
        default=1024,
        gt=0,
        description="Default maximum output tokens when an LLM request omits ``max_tokens``",
    )
    cadrumo_llm_default_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Default sampling temperature when an LLM request omits ``temperature``",
    )
    cadrumo_browser_locale: str = Field(
        default="es-ES",
        min_length=2,
        description="Default browser locale passed to Playwright context (BCP-47 tag)",
    )
    cadrumo_browser_timezone: str = Field(
        default="Europe/Madrid",
        min_length=1,
        description="Default IANA timezone string passed to Playwright context",
    )
    cadrumo_browser_viewport_width: int = Field(
        default=1366,
        gt=0,
        description="Default Playwright viewport width (px) for AEAT sede sessions",
    )
    cadrumo_browser_viewport_height: int = Field(
        default=900,
        gt=0,
        description="Default Playwright viewport height (px) for AEAT sede sessions",
    )
    cadrumo_file_lock_timeout_s: float = Field(
        default=30.0,
        gt=0,
        description="Default exclusive file-lock acquisition timeout (seconds)",
    )
    cadrumo_file_lock_retry_backoff_s: float = Field(
        default=0.05,
        gt=0,
        description="Sleep interval (seconds) between non-blocking file-lock acquire attempts",
    )
    cadrumo_bucket_lock_poll_interval_s: float = Field(
        default=0.1,
        gt=0,
        description="Polling interval (seconds) for bucket lockfile acquisition retries",
    )
    cadrumo_bucket_default_idle_lock_minutes: int = Field(
        default=15,
        gt=0,
        description="Fallback idle-lock window (minutes) when a bucket manifest omits the value",
    )
    cadrumo_bucket_default_session_absolute_minutes: int = Field(
        default=240,
        gt=0,
        ge=60,
        le=720,
        description=(
            "Fallback absolute session-lifetime cap (minutes) when a bucket manifest omits "
            "session_absolute_minutes; fixed at login and never refreshed, so a touched-forever "
            "session still seals at this cap (default 4 h, 12 h hard ceiling)"
        ),
    )
    cadrumo_keyring_probe_timeout_s: float = Field(
        default=10.0,
        gt=0,
        le=120,
        description=(
            "Wall-clock budget (seconds) for the AUTO backend's OS-keychain read before it is "
            "treated as locked. macOS Keychain ACLs are per-binary, so a process distinct from "
            "the one that minted the item must answer an authorization dialog that a headless or "
            "background context can never show, and the read would otherwise block forever. "
            "Generous enough that a foreground operator can answer the prompt; short enough that "
            "a dialog-less context degrades promptly instead of hanging"
        ),
    )
    cadrumo_auth_clave_movil_lock_buffer_s: int = Field(
        default=90,
        gt=0,
        description="Headroom (seconds) added to ``cadrumo_clave_movil_timeout_ms`` for the acquisition lock TTL",
    )
    cadrumo_auth_certificate_lock_ttl_s: int = Field(
        default=180,
        gt=0,
        description="Acquisition lock TTL (seconds) for certificate-backed AEAT auth flows",
    )
    cadrumo_log_stderr_level: str = Field(
        default="ERROR",
        description="Log level for the stderr handler installed by ``cadrumo.core.logging``",
    )
    cadrumo_log_file_level: str = Field(
        default="DEBUG",
        description="Log level for the file handler installed by ``cadrumo.core.logging``",
    )
    cadrumo_log_file_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        description=("Size cap (bytes) for cadrumo.log before the rotating file handler rolls over; default 10 MiB"),
    )
    cadrumo_log_file_backup_count: int = Field(
        default=5,
        ge=0,
        description="Number of rotated cadrumo.log backups retained by the rotating file handler",
    )
    cadrumo_log_root_level: str = Field(
        default="DEBUG",
        description="Root logger level installed by ``cadrumo.core.logging``",
    )
    cadrumo_manuals_http_timeout_s: float = Field(
        default=60.0,
        gt=0,
        description="HTTP timeout (seconds) for AEAT manual PDF downloads",
    )
