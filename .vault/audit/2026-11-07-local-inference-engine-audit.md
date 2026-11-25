---
tags:
  - '#audit'
  - '#local-inference-engine'
date: '2026-11-07'
modified: '2026-11-07'
body_schema: 'body-v2'
body_hash: 'sha256:a76b769beb7109989d5807a42a0037cd6856c35a10166978e553a5c37cd8a2ce'
related:
  - '[[2026-11-07-local-inference-engine-research]]'
  - '[[2026-11-07-local-inference-engine-adr]]'
---

# `local-inference-engine` audit: `Ollama qwen3-vl thinking defect in the ollama_api lane`

## Scope

The audit covers the CPU measurement pass of 2026-11-07 (`2026-11-07-local-inference-engine-research`, CPU pass) and how cadrumo-agent's `ollama_api` lane handles a thinking model in structured extraction. The lane code was read in cadrumo-agent and was not changed. Paths prefixed `cadrumo-agent:` are relative to that repository's `src/cadrumo_agent/`. The pass called Ollama directly, not through the lane, so the lane's behaviour below comes from reading the code, not from a lane run.

## Findings

### ollama-thinking-tag-empty-extraction | high | Ollama qwen3-vl:2b ignores think:false, spends the output budget thinking and returns no content for most invoice extractions

**Observed.** Ollama 0.40.13 on CPU was asked to extract eight fields from five synthetic invoice PNGs with `qwen3-vl:2b`, a tag with the `thinking` capability. Each request sent `think: false`, a JSON-schema `format` and `num_predict` 2048.

- Three of the five replies had empty content, after 170.6 s, 188.7 s and 217.4 s.
- Only 2 of 5 replies were schema-valid, and field accuracy was 0.375.
- The two valid replies took 131.5 s and 56.8 s.
- At the measured 15-18 generated tokens per second, the empty replies' durations match a full 2048-token budget. The model thought until the ceiling and wrote no answer, which shows that `think: false` was ignored.
- The same documents through llama-server with a Hugging Face Qwen3-VL-2B-Instruct GGUF and `enable_thinking: false` were 1.0 schema-valid at 0.95 accuracy, at 14-18 s each.
- cadrumo-agent already notes that qwen3-vl:2b thinks whatever `think` says (`cadrumo-agent:providers/_background_lane_proofs.py:209-212`).

This is a document-processing defect: a supported local vision model fails most invoice reads and takes minutes to do it.

**Repro.**

1. Start Ollama 0.40.13 (Windows CPU) with `OLLAMA_HOST=127.0.0.1:23798`, `OLLAMA_MODELS=WORKSPACE/ollama-models`, `OLLAMA_LLM_LIBRARY=cpu`, `CUDA_VISIBLE_DEVICES=-1`, `HIP_VISIBLE_DEVICES=-1`, `GGML_VK_VISIBLE_DEVICES=-1` and `OLLAMA_NUM_PARALLEL=1`. Pull `qwen3-vl:2b`.
2. For each synthetic invoice PNG, send this request to `POST /api/chat`. The fields are those of the harness's `bench.py` `ollama_extract`, run with `QNPRED=2048` and `THREADS=8`:
   - `model`: `qwen3-vl:2b`
   - `stream`: false
   - `think`: false
   - `format`: an object schema with string fields `issuer_name`, `issuer_nif`, `invoice_number` and `date`, number fields `base`, `iva_rate`, `iva_amount` and `total`, all required, and `additionalProperties` false
   - `options`: `temperature` 0, `seed` 42, `num_predict` 2048, `num_thread` 8
   - `messages`: one user message whose `content` is the extraction instruction and whose `images` holds the base64 PNG
3. Expect `message.content` to be empty on most documents, after more than 2 minutes each. The harness's `probe_ollama_vl.py` (arguments: workspace, think 0, format 1) sends one such request and prints `done_reason`, `eval_count`, the content and the start of `message.thinking`. It is the single-request check for whether the budget went to thinking.

**How the lane meets it (code reading).**

- The lane requests thinking on purpose for such a model. The request body sets `"think": chat.thinks` (`cadrumo-agent:providers/ollama_chat_model.py:788-807`, at `:800`). `thinks` is true whenever `/api/show` reports the `thinking` capability (`cadrumo-agent:providers/ollama_probe.py:83`, `cadrumo-agent:providers/_lane_models.py:512`). A structured extraction with a `response_schema` therefore also asks qwen3-vl:2b to think. `num_predict` is the whole reply ceiling, so it does not bound the thinking.
- The frame parser keeps only `message.content` and `message.tool_calls` (`cadrumo-agent:providers/ollama_chat_model.py:652-675`, read at `:834-844`). It drops `message.thinking`, so the lane cannot tell a think-only reply from an empty one.
- The lane does not return empty data. A `done_reason` of `length` raises "Ollama's reply reached the output ceiling" (`:869`), and empty content raises "Ollama returned no final text" (`:887`). Both use the default condition `INVALID_REQUEST` (`:104`). That condition states that the request must change (`cadrumo-agent:graph/enums.py:336-351`), and neither error names thinking as the cause. On the tax side, an unmapped background refusal becomes `run_failed` (`src/cadrumo_agent_service/adapters/agent_background_runs.py:341`).
- Nothing bounds a reply that never produces content. The chat client has no read timeout (`cadrumo-agent:providers/ollama_chat_model.py:535-541`, `cadrumo-agent:providers/ollama_residency.py:84-91`), and only the run's step deadline ends the turn. The 60 s bound in `cadrumo-agent:api/routes/_gateway_run_start.py:160` and `:497-511` covers the admission load, not the reply.
- No retry exists. A think-only reply fails the run on its first attempt.

## Recommendations

These are for cadrumo-agent's `ollama_api` lane. Each item names a decision for cadrumo-agent's owners to make. None is made here.

- **Thinking control.** Decide the thinking policy per request kind. A structured extraction (a `response_schema` is present) should request no thinking. The lane should detect the `thinking` capability, collect `message.thinking` in the frame parser, and detect an ignored `think: false`: thinking tokens with no content. It should bound the thinking budget separately from the answer ceiling. Decide whether that bound is a token count, a share of `num_predict`, or a stop on the first thinking frame past a limit.
- **Empty-response guard.** An empty or think-only completion must become a typed refusal, never empty data. Decide whether it is a new lane condition, such as a refusal meaning "the model produced reasoning but no answer", or `output_invalid`. It should not be `INVALID_REQUEST`, whose remedy (change the request) misleads here.
- **Timeout.** Decide a no-content deadline: the longest the lane waits without a content or tool-call frame before refusing. It should be separate from the step deadline, and it should be measured on CPU and GPU.
- **Retry.** Decide on one bounded retry after a think-only reply, either with thinking suppressed by the model's own switch (for example a no-think directive where the template honours it) or with a larger budget. The retry must be visible in the run's record and must never be silent. A second failure refuses.
- **Refusal vocabulary.** Map the new conditions onto codes the tax side already handles: `output_invalid` or `run_failed` in `src/cadrumo_client/contracts/model_runs.py:98-99`, through `src/cadrumo_agent_service/adapters/agent_background_runs.py:68-75`. A new tax-side code needs its own decision.
- **Tests.** Add a fake-server test that streams thinking frames, then `done: true` with `done_reason: length` and no content. Assert the typed refusal, the retry and the deadline. Add a fake-server test where the server ignores `think: false`.
- **Catalogue.** Decide whether cadrumo-agent keeps recommending `qwen3-vl:2b` on the Ollama lane for document reads until the guard lands. On llama-server, the measured Hugging Face route did not show the defect (`2026-11-07-local-inference-engine-adr` D4).
