# LLM provider adapters and Google Drive storage

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-015` · **Topic:** [External integrations and local runtime](../topics/external-integrations-and-local-runtime.md)

<!-- preserved:article -->
## Scope and capabilities

This chunk completes the LLM client surface with strict request/response records, provider transport adapters, pricing, retention, local-model fitness, and supply-nature proposals. It also covers the Google Drive bytes store and credential/backend factory, shared hash/key/pagination rules, and detached local-runtime process control. The analysis follows the code from request creation through provider normalization and from a storage call through Drive metadata checks.

## LLM request and provider flow

`LLMRequest` carries prompt, sampling controls, provider/model overrides, and optional typed image inputs. Image construction derives a SHA-256 content address from decoded bytes; the base64 payload is transient and omitted from cache persistence. Provider adapters normalize vendor responses into text, model, and token counts. Anthropic uses its async SDK behind the optional-extra gate; OpenAI and Gemini build HTTP requests through the shared `httpx` boundary; the Ollama adapter sends text or image payloads to its configured local endpoint. The client-facing base adapter classifies rate limits, 5xx errors, other non-2xx responses, transport failures, and malformed success bodies into typed errors. Request and image models (`src/cadrumo/adapters/outbound/llm/models.py`) Anthropic payload and adapter (`src/cadrumo/adapters/outbound/llm/providers/anthropic.py`) Shared HTTP boundary (`src/cadrumo/adapters/outbound/llm/providers/base.py`) Status mapping (`src/cadrumo/adapters/outbound/llm/providers/base.py`) Gemini adapter (`src/cadrumo/adapters/outbound/llm/providers/gemini.py`) Local adapter and PDF rasterizer (`src/cadrumo/adapters/outbound/llm/providers/local.py`) OpenAI adapter (`src/cadrumo/adapters/outbound/llm/providers/openai.py`)

Pricing returns a Decimal estimate for known provider/model prefixes, zero for local inference, and `None` when the table does not price a model. Retention first removes records strictly older than the cutoff, then evicts the oldest remaining entries above a count cap. The fitness probe sends a synthetic invoice using the real text-extraction prompt to the local adapter and checks that the reply parses and selected values ground; it avoids cache and profile dependencies. Cost estimation (`src/cadrumo/adapters/outbound/llm/pricing.py`) Retention selection (`src/cadrumo/adapters/outbound/llm/retention.py`) Text-reader fitness probe (`src/cadrumo/adapters/outbound/llm/role_fitness.py`)

Supply-nature inference is advisory. The prompt limits input to the first forty nonblank line descriptions, truncates each to 200 characters, and frames those descriptions as data rather than instructions. The parser accepts only the two domain natures or a separate `undetermined` reply token; malformed or out-of-vocabulary answers produce an empty proposal. The proposer defaults to role-selected local inference and marks descriptions as evidence-derived. Text and vision transaction classifiers pin requests to LOCAL and use allow-list-guarded domain parsers. Bounded proposal prompt and parser (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) Proposal model routing (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) Evidence marker (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) Local text classifier (`src/cadrumo/adapters/outbound/llm/text_classifier.py`) Local vision classifier (`src/cadrumo/adapters/outbound/llm/vision_classifier.py`)

## Google Drive storage and runtime

`GoogleDriveProvider` organizes remote objects beneath an owned vault folder and one folder per namespace. Filenames expose only an eight-character HMAC prefix plus a sanitized label; the full HMAC and content hash live in `appProperties`. Lookups paginate by prefix but require the full HMAC and Cadrumo ownership marker before returning a match. Reads validate metadata size and timestamp, require a full SHA-256 digest, compare returned byte length, then recompute the payload digest before returning bytes. Create/update/delete operations are explicit, and a configurable handoff/acknowledgement pair surrounds provider calls. Drive provider and vault resolution (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Owned-object lookup (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Upload boundary (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Verified download (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Shared digest and byte-length checks (`src/cadrumo/adapters/outbound/storage/_integrity.py`)

The backend factory checks the active profile, selects local storage or Google Drive, resolves the configured root, and hydrates either per-profile Desktop OAuth records or service-account impersonation credentials. Drive query literals are escaped; ownership and object-key HMAC checks are shared; repeated or non-string pagination tokens become typed failures. Runtime installation uses fixed argument vectors and no shell, with output detached; server spawning intentionally leaves the runtime running after the application exits. Credential selection (`src/cadrumo/adapters/outbound/storage/factory.py`) Provider construction (`src/cadrumo/adapters/outbound/storage/factory.py`) Shared key validation (`src/cadrumo/adapters/outbound/storage/_key_validation.py`) Pagination guard (`src/cadrumo/adapters/outbound/storage/drive_pagination.py`) Detached runtime process control (`src/cadrumo/adapters/outbound/model_runtime/process_control.py`)

## Security and quality observations

The Drive read path has a useful fail-closed integrity check, but the write boundary accepts any nonblank `content_hash` while the read boundary rejects anything that is not a full SHA-256. A caller that supplies a short, MD5, or otherwise malformed nonempty value can receive a successful `put` result for an object that the same provider later refuses to read. Production callers appear designed to provide SHA-256 content addresses, and the fitness probe deliberately writes then deletes a short sentinel without reading it, so impact depends on external callers; validating the format and payload match at `put` would make the provider contract self-contained. Write-side hash presence check (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Read-side full digest requirement (`src/cadrumo/adapters/outbound/storage/_google_drive.py`)

Drive lookup is deterministic only up to the first match. `_first_drive_entry` returns the first row in the first nonempty Drive page, after which the provider adopts or refuses that one entry; it does not establish uniqueness among same-name matches. Duplicate vault/namespace names can therefore make selection depend on provider ordering, or cause a foreign first match to block a valid owned duplicate behind it. First-entry selection (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Ownership/adoption decision (`src/cadrumo/adapters/outbound/storage/_google_drive.py`)

Several APIs offer a provider override for evidence-derived descriptions but no way to pass an `EvidenceConsentToken`: `SupplyNatureProposer` marks its request as evidence-derived and creates `LLMRequest` without a token. This is safe by refusal at the shared dispatch gate, but the advertised hosted-provider path cannot complete through this proposer without a lower-level client/request route. The same kind of wrapper limitation appears in the image-transcription convenience API. Supply-nature request construction (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) Provider-level consent remains enforced by the client (`src/cadrumo/adapters/outbound/llm/models.py`)

The local PDF rasterizer processes every page in memory and accepts a caller-selected render scale without a page-count or output-size ceiling. Combined with base64 image inputs, an unusually large or high-resolution document can consume substantial memory before the local inference concurrency guard runs. This is an operational resource bound to consider for untrusted or very large PDFs. PDF rasterization (`src/cadrumo/adapters/outbound/llm/providers/local.py`) Transient image payload (`src/cadrumo/adapters/outbound/llm/models.py`)

Shared transport status mapping, image capability defaults, pagination-cycle detection, full Drive readback verification, and explicit distinction between unpriced and free LLM calls are strong boundary choices. A few configuration paths resolve endpoint URLs again from global settings inside Gemini/OpenAI/local adapters rather than receiving them from the `LLMClient` settings instance; injected settings may therefore not control those endpoints in the same way they control model, key, and timeout. The role-fitness probe also bypasses the regular client’s local inference admission and usage/telemetry path to avoid cached results; its synthetic input narrows privacy concerns, but concurrent probing and production local inference are not coordinated here. Gemini endpoint selection (`src/cadrumo/adapters/outbound/llm/providers/gemini.py`) OpenAI endpoint selection (`src/cadrumo/adapters/outbound/llm/providers/openai.py`) Probe dispatch (`src/cadrumo/adapters/outbound/llm/role_fitness.py`)

## Assessment and limits

This chunk shows clear provider and storage boundaries: model replies and transport errors are normalized, on-host classifiers are pinned local, advisory proposals are contained, and Drive objects are keyed by full HMAC and integrity-checked on retrieval. Main review points are self-consistency of the Drive write/read hash contract, duplicate-name ambiguity, memory ceilings for PDF rendering, and integration of optional consent into provider-overridable evidence APIs. Static analysis only; no provider, Drive account, local inference server, installer, PDF corpus, or external storage operation was exercised.

## Coverage appendix

- models.py (`src/cadrumo/adapters/outbound/llm/models.py`) — lines 1–395
- preconditions.py (`src/cadrumo/adapters/outbound/llm/preconditions.py`) — lines 1–74
- pricing.py (`src/cadrumo/adapters/outbound/llm/pricing.py`) — lines 1–77
- providers/__init__.py (`src/cadrumo/adapters/outbound/llm/providers/__init__.py`) — lines 1–8
- anthropic.py (`src/cadrumo/adapters/outbound/llm/providers/anthropic.py`) — lines 1–312
- base.py (`src/cadrumo/adapters/outbound/llm/providers/base.py`) — lines 1–410
- gemini.py (`src/cadrumo/adapters/outbound/llm/providers/gemini.py`) — lines 1–148
- local.py (`src/cadrumo/adapters/outbound/llm/providers/local.py`) — lines 1–235
- openai.py (`src/cadrumo/adapters/outbound/llm/providers/openai.py`) — lines 1–153
- response_json.py (`src/cadrumo/adapters/outbound/llm/response_json.py`) — lines 1–36
- retention.py (`src/cadrumo/adapters/outbound/llm/retention.py`) — lines 1–60
- role_fitness.py (`src/cadrumo/adapters/outbound/llm/role_fitness.py`) — lines 1–198
- supply_nature_proposal.py (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) — lines 1–373
- text_classifier.py (`src/cadrumo/adapters/outbound/llm/text_classifier.py`) — lines 1–145
- vision_classifier.py (`src/cadrumo/adapters/outbound/llm/vision_classifier.py`) — lines 1–142
- model_runtime/__init__.py (`src/cadrumo/adapters/outbound/model_runtime/__init__.py`) — lines 1–1
- process_control.py (`src/cadrumo/adapters/outbound/model_runtime/process_control.py`) — lines 1–101
- storage/__init__.py (`src/cadrumo/adapters/outbound/storage/__init__.py`) — lines 1–12
- _google_drive.py (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) — lines 1–1271
- _google_drive_metadata.py (`src/cadrumo/adapters/outbound/storage/_google_drive_metadata.py`) — lines 1–186
- _integrity.py (`src/cadrumo/adapters/outbound/storage/_integrity.py`) — lines 1–167
- _key_validation.py (`src/cadrumo/adapters/outbound/storage/_key_validation.py`) — lines 1–115
- _object_name.py (`src/cadrumo/adapters/outbound/storage/_object_name.py`) — lines 1–32
- drive_pagination.py (`src/cadrumo/adapters/outbound/storage/drive_pagination.py`) — lines 1–37
- errors.py (`src/cadrumo/adapters/outbound/storage/errors.py`) — lines 1–150
- factory.py (`src/cadrumo/adapters/outbound/storage/factory.py`) — lines 1–343
<!-- /preserved:article -->
