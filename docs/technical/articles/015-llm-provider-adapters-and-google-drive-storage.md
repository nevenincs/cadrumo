# LLM provider adapters and Google Drive storage

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-015` · **Topic:** [External integrations and local runtime](../topics/external-integrations-and-local-runtime.md)

<!-- preserved:article -->
## Scope and capabilities

This chunk completes the LLM client surface with strict request/response records, the one agent provider adapter, PDF rasterisation, retention, and supply-nature proposals. It also covers the Google Drive bytes store and credential/backend factory, and shared hash/key/pagination rules. The analysis follows the code from request creation through the agent hand-off and from a storage call through Drive metadata checks.

## LLM request and provider flow

`LLMRequest` carries prompt, sampling controls, the model role, and optional typed image inputs. Image construction derives a SHA-256 content address from decoded bytes; the base64 payload is transient and omitted from cache persistence. There is one provider adapter: every tax model call goes to the agent service, which runs it on the lane and model the person selected for the role from cadrumo-agent's catalogue. Cadrumo names no model and holds no provider key. The adapter builds one bounded run request, sends it through the operation's model-run port, re-asks once when a reply that must be JSON holds no JSON object, and turns the service's typed refusals (no selection, unavailable lane, missing consent) into typed errors; a local lane that is not ready carries the local AI setup verdict, which the desktop owns. Request and image models (`src/cadrumo/adapters/outbound/llm/models.py`) Adapter contract (`src/cadrumo/adapters/outbound/llm/providers/base.py`) Agent adapter (`src/cadrumo/adapters/outbound/llm/providers/agent.py`) PDF rasterisation (`src/cadrumo/adapters/outbound/llm/pdf_rasterisation.py`)

Retention first removes records strictly older than the cutoff, then evicts the oldest remaining entries above a count cap. A scan-only PDF is rasterised on this computer, in memory, whatever lane later reads its pages. Retention selection (`src/cadrumo/adapters/outbound/llm/retention.py`)

Supply-nature inference is advisory. The prompt limits input to the first forty nonblank line descriptions, truncates each to 200 characters, and frames those descriptions as data rather than instructions. The parser accepts only the two domain natures or a separate `undetermined` reply token; malformed or out-of-vocabulary answers produce an empty proposal. The proposer names its model role and marks descriptions as evidence-derived. Text and vision transaction classifiers go through the agent by role, stamp `llm:agent-<reader>:<model>` provenance, and use allow-list-guarded domain parsers. Whether a read leaves this computer is the selected lane's typed `reads_off_host` catalogue flag, never a provider id or path. Bounded proposal prompt and parser (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) Evidence marker (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) Text classifier (`src/cadrumo/adapters/outbound/llm/text_classifier.py`) Vision classifier (`src/cadrumo/adapters/outbound/llm/vision_classifier.py`)

## Google Drive storage and runtime

`GoogleDriveProvider` organizes remote objects beneath an owned vault folder and one folder per namespace. Filenames expose only an eight-character HMAC prefix plus a sanitized label; the full HMAC and content hash live in `appProperties`. Lookups paginate by prefix but require the full HMAC and Cadrumo ownership marker before returning a match. Reads validate metadata size and timestamp, require a full SHA-256 digest, compare returned byte length, then recompute the payload digest before returning bytes. Create/update/delete operations are explicit, and a configurable handoff/acknowledgement pair surrounds provider calls. Drive provider and vault resolution (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Owned-object lookup (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Upload boundary (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Verified download (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Shared digest and byte-length checks (`src/cadrumo/adapters/outbound/storage/_integrity.py`)

The backend factory checks the active profile, selects local storage or Google Drive, resolves the profile's stored Drive root folder and refuses it unless Drive still shows it as a folder the application created, and hydrates credentials from the installation's Google client and the profile's stored sign-in token. Drive query literals are escaped; ownership and object-key HMAC checks are shared; repeated or non-string pagination tokens become typed failures. Credential selection (`src/cadrumo/adapters/outbound/storage/factory.py`) Provider construction (`src/cadrumo/adapters/outbound/storage/factory.py`) Shared key validation (`src/cadrumo/adapters/outbound/storage/_key_validation.py`) Pagination guard (`src/cadrumo/adapters/outbound/storage/drive_pagination.py`)

## Security and quality observations

The Drive read path has a useful fail-closed integrity check, but the write boundary accepts any nonblank `content_hash` while the read boundary rejects anything that is not a full SHA-256. A caller that supplies a short, MD5, or otherwise malformed nonempty value can receive a successful `put` result for an object that the same provider later refuses to read. Production callers appear designed to provide SHA-256 content addresses, and the fitness probe deliberately writes then deletes a short sentinel without reading it, so impact depends on external callers; validating the format and payload match at `put` would make the provider contract self-contained. Write-side hash presence check (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Read-side full digest requirement (`src/cadrumo/adapters/outbound/storage/_google_drive.py`)

Drive lookup is deterministic only up to the first match. `_first_drive_entry` returns the first row in the first nonempty Drive page, after which the provider adopts or refuses that one entry; it does not establish uniqueness among same-name matches. Duplicate vault/namespace names can therefore make selection depend on provider ordering, or cause a foreign first match to block a valid owned duplicate behind it. First-entry selection (`src/cadrumo/adapters/outbound/storage/_google_drive.py`) Ownership/adoption decision (`src/cadrumo/adapters/outbound/storage/_google_drive.py`)

Several APIs mark their requests as evidence-derived but offer no way to pass an `EvidenceConsentToken`: `SupplyNatureProposer` builds its `LLMRequest` without a token. This is safe by refusal at the shared dispatch gate, but a lane whose catalogue entry reads off the host cannot complete through this proposer; only a lane that stays on this computer can. Supply-nature request construction (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) Consent remains enforced by the client (`src/cadrumo/adapters/outbound/llm/models.py`)

The PDF rasterizer processes every page in memory and accepts a caller-selected render scale without a page-count or output-size ceiling. Combined with base64 image inputs, an unusually large or high-resolution document can consume substantial memory before the on-host inference concurrency guard runs. This is an operational resource bound to consider for untrusted or very large PDFs. PDF rasterization (`src/cadrumo/adapters/outbound/llm/pdf_rasterisation.py`) Transient image payload (`src/cadrumo/adapters/outbound/llm/models.py`)

One dispatch path, typed agent refusals, pagination-cycle detection and full Drive readback verification are strong boundary choices. Agent adapter (`src/cadrumo/adapters/outbound/llm/providers/agent.py`)

## Assessment and limits

This chunk shows clear provider and storage boundaries: every model call takes one agent path, consent follows the lane's typed flag, advisory proposals are contained, and Drive objects are keyed by full HMAC and integrity-checked on retrieval. Main review points are self-consistency of the Drive write/read hash contract, duplicate-name ambiguity, memory ceilings for PDF rendering, and integration of optional consent into evidence APIs. Static analysis only; no agent service, Drive account, local AI server, installer, PDF corpus, or external storage operation was exercised.

## Coverage appendix

- models.py (`src/cadrumo/adapters/outbound/llm/models.py`) — lines 1–400
- preconditions.py (`src/cadrumo/adapters/outbound/llm/preconditions.py`) — lines 1–74
- providers/__init__.py (`src/cadrumo/adapters/outbound/llm/providers/__init__.py`) — lines 1–8
- agent.py (`src/cadrumo/adapters/outbound/llm/providers/agent.py`) — lines 1–199
- base.py (`src/cadrumo/adapters/outbound/llm/providers/base.py`) — lines 1–149
- pdf_rasterisation.py (`src/cadrumo/adapters/outbound/llm/pdf_rasterisation.py`) — lines 1–96
- response_json.py (`src/cadrumo/adapters/outbound/llm/response_json.py`) — lines 1–36
- retention.py (`src/cadrumo/adapters/outbound/llm/retention.py`) — lines 1–60
- supply_nature_proposal.py (`src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`) — lines 1–369
- text_classifier.py (`src/cadrumo/adapters/outbound/llm/text_classifier.py`) — lines 1–139
- vision_classifier.py (`src/cadrumo/adapters/outbound/llm/vision_classifier.py`) — lines 1–158
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
