---
tags:
  - '#adr'
  - '#provider-settings'
date: '2026-10-19'
modified: '2026-10-19'
body_schema: 'body-v2'
body_hash: 'sha256:921f6d641537ce3c24179560394c401fb2aef4225934a86d05f30e8e84effb0f'
related:
  - "[[2026-10-13-provider-settings-adr]]"
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - '[[2026-10-13-provider-settings-reference]]'
---

# `provider-settings` adr: `LLMClient reaches every cadrumo-agent lane through one agent adapter; the tax app's own vendor adapters and API keys are retired` | (**status:** `accepted`)

## Problem Statement

The tax application calls three model vendors itself. It reads their keys from three process-environment settings, `cadrumo_llm_anthropic_api_key`, `cadrumo_llm_openai_api_key` and `cadrumo_llm_gemini_api_key` (`src/cadrumo/core/config_llm_fields.py:52-63`, with a blank-to-unset validator at `src/cadrumo/core/config.py:845-854`). It speaks each vendor's wire protocol through its own adapters (`src/cadrumo/adapters/outbound/llm/client.py:943-968`, `src/cadrumo/adapters/outbound/llm/providers/`).

The installed desktop strips `CADRUMO_` names from its children (`src/cadrumo/core/storage_environment.py:650-660`), so this path works only from a development checkout or a hand-run CLI. Meanwhile each signed-in profile already selects and authorizes its model providers through the agent service and cadrumo-agent, on every lane the agent supports (`2026-10-13-provider-settings-adr`). The tax path is a second provider stack, installation-wide, beside the per-profile one.

The operator ruled on 2026-10-19: "Migrate now". The tax app's key path is a legacy duplicate to be retired. The same day the operator asked for "the simplest, most straightforward cadrumo-agent capable integration for classification work: reading, classifying, categorizing, separating, ingesting", using cadrumo-agent as it is.

## Considerations

- `2026-10-13-provider-settings-adr` constraint 3 says "No tax-extraction consumer is added". Its constraint 11 history keeps Cadrumo's own document reading on its existing keys "until the owner rules on it". These rulings are that decision.
- `.importlinter` contract `tax-has-no-agent-or-harness-dependency` forbids `cadrumo` and `cadrumo_runtime` from importing `cadrumo_agent_service`.
- The runtime reaches the service only over the connection the service opens (`src/cadrumo_client/transport/service_client.py`). Today that connection carries record requests from the service and session events pushed by the runtime. It has no request/reply in the other direction.
- The agent gateway's port and bearer live only in the service and the desktop (`src/cadrumo_agent_service/service.py:553-600`, `ServiceStartupFrame` in `src/cadrumo_agent_service/contracts.py`). The desktop already starts runs on it with `POST /v1/runs` (`native/desktop/src-tauri/src/agent/gateway.rs:196`).
- cadrumo-agent is adding background runs over the existing run path. Only the hosting service may start them, never the desktop caller. They carry no tools, skills, terminal or persona, so they raise no permission prompts. They stay out of the conversation listing but can be read by id. Text works on every lane. Attachments (images and PDFs) go straight into the model input on every lane that can take them, as native content on the API lanes and through each CLI's own input channel where it accepts them. The agent refuses a lane or media type that cannot take them before the run starts (CADRUMO-AGENT, 2026-10-19).
- Off-host evidence consent is bound to source bytes, checked and ledgered in `LLMClient._require_evidence_consent` (`src/cadrumo/adapters/outbound/llm/client.py:728-808`), and minted per call by `ledger.evidence.extract` (`src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:164-235`). Under `2026-06-10-llm-evidence-classification-adr` the ledger entry names provider and model.
- Column-role mapping sends `evidence_derived=False` (`src/cadrumo/adapters/outbound/llm/column_role_mapping.py:655`). If it gets an explicit model with no provider, it falls to the configured default provider without consent (`:556`).
- Model output is a proposal. Registry logic owns regulated arithmetic, and human review stays separate (`00-architecture`).

## Considered options

- **One cadrumo-agent adapter in `LLMClient`, served by a service handler that starts a background run.** Chosen. It reaches every lane, keeps the consumers unchanged and moves no secret.
- **A new structured-output route in cadrumo-agent.** Not needed. The existing run path with background runs gives prompt in and reply text out, and Cadrumo validates the JSON itself.
- **The desktop answers model runs through an operation interaction.** Rejected. It works only from the desktop, needs a new interaction kind, and passes evidence-derived prompts through the desktop process.
- **The worker calls the gateway directly.** Rejected. The worker would need the gateway bearer, which is a secret.
- **A tax-side key port filled by a runtime secret broker.** Withdrawn. It moved a secret in a new direction and served API lanes only.
- **Keep the environment keys.** Rejected by the operator's ruling.

## Constraints

1. **Retirement.** These are deleted with no compatibility alias and no developer-key fallback:
   - the settings `cadrumo_llm_anthropic_api_key`, `cadrumo_llm_openai_api_key` and `cadrumo_llm_gemini_api_key`, with their validator entries;
   - the vendor adapters `providers/anthropic.py`, `providers/openai.py` and `providers/gemini.py`, and the settings only they read;
   - the `LLMProvider` members that name those vendors;
   - the `env/.env.example` lines for `CADRUMO_LLM_ANTHROPIC_API_KEY`, `CADRUMO_LLM_OPENAI_API_KEY` and `CADRUMO_LLM_GEMINI_API_KEY`;
   - their tests.

   `LocalAdapter` stays. The environment reference, the how-to and the locale catalogues are changed through their owners.
2. **`LLMClient` stays; one agent adapter replaces the vendors.** `LLMClient` remains the tax-side abstraction its consumers call, with its cache, usage and run records, retry policy, image boundary, admission and consent gate. `LLMProvider` keeps `LOCAL` and gains one off-host member for cadrumo-agent.

   The agent adapter sends one `ModelRunRequest` and names no lane or model. The request carries:
   - the `ModelRole`;
   - the system and prompt text;
   - an optional bounded attachment list (images and PDFs);
   - output token and byte bounds;
   - a deadline.

   The consumers' prompts, parsers, grounding and review flow are unchanged. The consumers are:
   - classification of text and of images, including transaction splitting;
   - invoice evidence drafts from text, and transcription from images;
   - the supply-nature proposal;
   - column-role mapping.

   No tax code speaks a vendor protocol, holds a key or bearer, or imports `cadrumo_agent_service`.
3. **Output handling.** The adapter returns the run's final reply text. For structured consumers, Cadrumo takes the JSON from a fenced block, or else from the outermost object, and validates it with the consumer's existing parser. On a parse or schema failure it asks once more with the same request and the validation summary, then refuses. Free-text consumers, such as transcription, take the reply text as is.
4. **New protocol direction: runtime to service, requests only.** The request travels from the tax worker on its existing runtime channel. The runtime forwards it to the exact profile's admitted service connection, under the `model-run` capability the service declares in its descriptor. The runtime binds the runtime boot, profile, session, service lease and operation request id. It treats the body as opaque, and it never persists or logs it. No key, bearer or credential appears in either direction. This is a new direction on that connection, accepted explicitly by the operator.
5. **Service handler.** The service checks the lease and the settings generation. It resolves the lane and model from the profile's provider settings: a per-`ModelRole` selection when one exists, otherwise the default selection. Any catalog lane is eligible, CLI or API, at parity with chat.

   The service starts a background run on the existing run path (`POST /v1/runs`) with its own bearer. It waits for the run to finish within the deadline, reads the final assistant message from `/v1/runs/{id}/history`, and replies with the text plus `provider_id`, `transport`, `model` and `agent_version`. The exact background marking, body and refusal codes are whatever cadrumo-agent commits, kept behind one service adapter. A per-role selection interface is a follow-on and is not part of this record.
6. **Lane lookup before dispatch.** On the same capability, the tax side first asks for the resolved `provider_id`, `transport` and `model` for the role. That answer is non-secret. The run request then carries the triple, and the service refuses `consent_missing` if the lane it would use differs. Whether a lane takes an attachment is read from catalog data alone, never inferred from its transport. The provider catalog reports for each lane whether background requests accept documents, per media type (image, PDF), with a proven or unproven label. The lookup returns that support for the resolved lane, behind its adapter. A consumer whose request carries a media type the lane does not accept refuses `input_not_supported` before dispatch. The agent's own refusal at admission maps to the same code. A lane refuses only when it cannot take the input.
7. **Typed refusals.** A run that yields no usable output refuses with exactly one closed code:

   | Code | Meaning |
   | --- | --- |
   | `service_unavailable` | No service is admitted for the profile |
   | `not_signed_in` | The profile has no active sign-in |
   | `profile_locked` | The profile is locked |
   | `no_selection` | No lane is selected for the role |
   | `lane_unavailable` | The selected lane cannot be used |
   | `input_not_supported` | The agent refused the lane or media type at admission |
   | `run_failed` | The run did not complete |
   | `output_invalid` | The reply still fails validation after the one re-ask |
   | `deadline_exceeded` | The deadline passed |
   | `refused_by_provider` | The provider refused the request |
   | `consent_missing` | The lane differs from the one the token was bound to |

   Each consumer maps these to its existing typed errors. A refusal never falls back to another lane, to the environment or to the on-host model. A result that is ambiguous after dispatch is not retried as though it never ran.
8. **Consent stays with its deterministic owner and binds to the lane.**
   - Every off-host agent run of taxpayer material goes through the digest-bound, per-invocation consent of `2026-06-10-llm-evidence-classification-adr`. The gestor-mode bar and the ledger append both run before dispatch.
   - The token and the ledger entry bind to the triple from constraint 6.
   - Column-role mapping always goes through that consent when it runs off-host. Its requests are marked evidence-derived, and the configured-default-provider route without consent is removed.
   - The supply-nature proposal and the classifiers reach the agent only with a token their caller passes. Without one they stay on-host or refuse.
   - A usable lane grants no consent, and consent grants no lane. Agent conversation grants remain separate (`2026-10-13-agent-attachments-adr`).
9. **Operation contract change.** `ledger.evidence.extract` replaces its `off_host_provider` choice among vendor `LLMProvider` values with one agent choice. The person chooses between on-host and the agent, and the service resolves the lane. The person-act refusal for frontends that may not acknowledge off-host reads is unchanged (`invoice_evidence_extract_operation.py:273-285`). This changes a registered operation's request schema, and its CLI, TUI and desktop forms move with it.
10. **Output stays a proposal.** The validated output enters the existing grounding and human review exactly as a vendor response did. Usage and run records name the lane and model the service reported.

## Implementation

We will add `ModelRunRequest`, its reply, the lane lookup and the agent adapter to `src/cadrumo/adapters/outbound/llm`, and the JSON extraction with one re-ask to the client. The runtime gets a request/reply frame under the `model-run` descriptor capability. The service gets a handler that starts and reads a background run.

The tax-LLM migration session builds all three sides. CADRUMO-AGENT agreed in writing on 2026-10-19, within its stated file boundaries, and cadrumo-agent owns background runs.

Callers that build `LLMClient` keep doing so: `text_classifier.py`, `vision_classifier.py`, `supply_nature_proposal.py`, `evidence_draft_text.py`, `evidence_draft_vision.py`, `column_role_mapping.py` and `src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py`. `role_fitness.py` probes `LocalAdapter` only and is unaffected.

Hypotheses that may change within the constraints: frame and field names, the byte and image bounds, and whether the lookup and the run share one frame type.

## Rationale

The service is the only owner of provider choice and credentials, and cadrumo-agent already reaches every lane the person configured. A request the service runs as a background run is the smallest bridge that keeps secrets out of the tax side, needs no new agent route, and leaves the consumers and their review untouched. Fixing the lane before consent keeps the person's consent bound to the dispatch that actually runs.

## Consequences

- Off-host model work needs a signed-in profile with an admitted agent service. Without one it refuses `service_unavailable`, so the CLI alone no longer reaches a vendor. On-host work is unchanged.
- Off-host reading of images and PDFs works wherever the selected lane accepts that media, as the agent decides at admission. Elsewhere it refuses `input_not_supported`.
- A developer who kept a tax-app key in `env/.env` loses that path. The live-agent lane's `dev/desktop_agent_live/provider_key.py` read those template names. Its owner is removing that file.
- The runtime gains a request/reply direction to the service. It carries prompts and images that may be taxpayer evidence, in memory only, and it needs platform and race testing like the other channels.
- Cost and latency follow the lane the person selected.
- Reconsider if the operator wants an off-host path without the service, or a per-request lane choice.

Accepted 2026-10-19 on the operator's first-hand approval, given in the coordinating session: "lgtm, go". That approval explicitly covers the runtime-to-service `model-run` frame in constraint 4. The record was proposed earlier that day for the operator's review. Basis:
- the operator rulings of 2026-10-19: "migrate now"; CLI and API parity; "the simplest, most straightforward cadrumo-agent capable integration for classification work: reading, classifying, categorizing, separating, ingesting"; and the decision to keep `LLMClient` with one cadrumo-agent adapter and to use background runs;
- CADRUMO-AGENT's written agreement the same day to the request path, the per-role resolution, the refusal set, the consent binding, the background-run shape and attachment admission.

Acceptance records the decision. It is not evidence that any of it is built.
