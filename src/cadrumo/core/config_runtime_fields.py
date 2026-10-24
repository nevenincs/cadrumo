"""LLM provider endpoint and runtime tuning settings layered on top of timeout config.

Defines :class:`CadrumoRuntimeSettings`, which adds the local Ollama endpoint
URL and model-runtime tuning fields (context window, per-request timeouts) consumed by
the LLM-backed invoice-read pipeline.
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from .config_timeouts import CadrumoTimeoutSettings
from .model_catalogue import ModelRole, default_model_runtime_id

#: The loopback address the runtime manager's local AI server listens on. The package's
#: environment declaration states the same address for the native side; a package-side
#: test keeps the two equal.
LOCAL_AI_SERVER_ADDRESS: Final = "127.0.0.1:23743"
#: The chat endpoint of that server, the readers' default.
LOCAL_AI_CHAT_URL: Final = f"http://{LOCAL_AI_SERVER_ADDRESS}/api/chat"


class CadrumoRuntimeSettings(CadrumoTimeoutSettings):
    """LLM provider endpoints and runtime tuning fields layered on top of timeouts."""

    cadrumo_llm_ollama_chat_url: str = Field(
        default=LOCAL_AI_CHAT_URL,
        description=(
            "Local Ollama /api/chat endpoint; defaults to the server the runtime manager runs, "
            "override for non-localhost Ollama deployments"
        ),
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
        default=default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION),
        description=(
            "Local Ollama vision model used to read scanned/image evidence on-host "
            "(the default, gestor-allowed posture); must be a multimodal model pulled "
            "into the local Ollama runtime. The default is the weakest catalogued "
            "candidate that clears the capability bars under a COMMERCIAL licence "
            "posture -- qwen3-vl:2b, Apache-2.0, ~1.9 GB. It replaces qwen2.5vl:3b, "
            "which is measured-equivalent at this discipline but carries the Qwen "
            "Research licence and therefore bars commercial use. Every accepted value "
            "and its licence are declared in the core model catalogue; overriding to a "
            "research-licensed candidate is permitted and surfaces a licence advisory"
        ),
    )
    cadrumo_llm_ollama_text_model: str = Field(
        default=default_model_runtime_id(ModelRole.TEXT_EXTRACTION),
        description=(
            "Local Ollama TEXT model used to classify a text-layer document on-host. "
            "Chosen under the same constraints that bind the vision default rather "
            "than beside it: qwen3:1.7b is Apache-2.0 and ~1.4 GB, comfortably under "
            "the declared memory floor, so a machine provisioned for the vision "
            "default is provisioned for this one. It replaces qwen2.5:3b, which is one "
            "of the two Qwen2.5 sizes released under the Qwen Research licence rather "
            "than Apache-2.0 -- easy to miss, and the reason the licence flag is "
            "declared per candidate. This model reads only the extracted text and "
            "selects from the registry allow-list; it never emits a regulated number"
        ),
    )
    cadrumo_llm_ollama_mapping_model: str = Field(
        default=default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING),
        description=(
            "Local Ollama model used to name what each column of a delimited table "
            "holds, from its header strings alone. Deliberately its own setting rather "
            "than sharing the text one: column-role mapping is strictly EASIER than the "
            "text read -- a selection over a short closed vocabulary given a handful of "
            "short headers, not a document read -- so it must be sizeable DOWN "
            "independently. Sharing the field would silently drag it upward the next "
            "time the text role needs a larger model. It defaults to the same qwen3:1.7b "
            "(Apache-2.0, ~1.4 GB), so it introduces no new hardware floor and no second "
            "model to pull. This model never emits a regulated number; it selects from "
            "the closed column-role vocabulary"
        ),
    )
    cadrumo_llm_ollama_supply_nature_model: str = Field(
        default=default_model_runtime_id(ModelRole.SUPPLY_NATURE_PROPOSAL),
        description=(
            "Local Ollama model used to propose whether an invoice's lines describe "
            "goods or services, for the person to confirm. Its own setting for the "
            "same reason as the mapping one: the proposal is a choice between two "
            "values from a few short lines, so it must be sizeable DOWN independently "
            "of the text read. Left at its default, the catalogue picks the smallest "
            "candidate this computer can run; a different value names the model "
            "outright. The proposal is advisory and never emits a regulated number"
        ),
    )
    cadrumo_llm_model_runtime_memory_floor_bytes: int = Field(
        default=8 * 1024**3,
        gt=0,
        description=(
            "Minimum total system memory the local model runtime needs before a "
            "vision read is worth attempting. Sized for the default vision model "
            "(qwen3-vl:2b, ~1.9 GB of weights) plus the 8192-token context window "
            "and normal OS residency, which is why the floor sits well above the "
            "weight size alone. Below it the runtime does not refuse -- it loads "
            "and thrashes, or is killed mid-read, which reaches the operator as "
            "an unexplained timeout rather than as a hardware shortfall. Tunable "
            "because the floor tracks the configured model: raise it when "
            "overriding upward to a larger catalogued candidate"
        ),
    )
    cadrumo_llm_contention_safety_margin_bytes: int = Field(
        default=1024**3,
        ge=0,
        description=(
            "Headroom kept free ABOVE a model's declared memory requirement before "
            "a load is admitted. A model does not occupy exactly its weight size: "
            "the KV cache grows with the context window, the runtime allocates "
            "scratch buffers, and the display server keeps taking frames while the "
            "read runs. Admitting a load that fits with zero margin is how a "
            "measured-safe load still ends as an OOM kill mid-read. 1 GiB covers "
            "the default 8192-token context plus normal desktop churn; raise it on "
            "a machine that also drives a display, lower it on a headless box"
        ),
    )
    cadrumo_llm_contention_check_override: bool = Field(
        default=False,
        description=(
            "Admit a local model load even when free headroom could not be "
            "measured. Default false: an unreadable free figure fails CLOSED at "
            "the act, because 'could not tell' is not evidence of headroom. Set "
            "true only on a machine known to have capacity that this build cannot "
            "read (a non-NVIDIA accelerator, or NVML absent because cadrumo[llm] "
            "is not installed). It does not override a MEASURED shortfall -- a "
            "load whose requirement exceeds measured free memory is refused "
            "regardless of this setting"
        ),
    )
    cadrumo_llm_local_inference_concurrency: int = Field(
        default=1,
        ge=1,
        description=(
            "How many on-host inference requests this process may run at once. "
            "Default one, because two concurrent reads on consumer hardware are "
            "the same out-of-memory kill the contention check exists to prevent, "
            "reached by another route: each load individually fits the measured "
            "headroom, and together they do not. A request arriving while the "
            "arena is full is REFUSED rather than queued -- a queued request "
            "would wait holding its decoded pages in the memory under pressure, "
            "and would run against headroom measured before it waited. Raise it "
            "only on a machine with headroom for a second concurrent model load; "
            "it does not bound off-host dispatch, which occupies none of this "
            "machine's device memory"
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
        # Capped where the REQUEST model caps it, not where a provider API
        # elsewhere allows. This value is fed straight into an LlmRequest whose
        # own temperature is bounded at one, so a configured 1.5 validated here
        # as settings and then failed at request construction -- a configuration
        # the app called valid and could never use.
        le=1.0,
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
