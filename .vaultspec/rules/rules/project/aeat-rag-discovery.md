---
name: aeat-rag-discovery
---

# AEAT RAG discovery

**Standing mandate — RAG-first code grounding for every worker.** Before any non-trivial code work — locating an implementation, discovering all sites of a concept, scoping a feature surface, or grounding a change — run a vaultspec-rag code search FIRST, then narrow with grep. This binds the coordinator, every dispatched subagent, and every future worker. Every dispatch brief that involves touching code MUST instruct the worker to ground via `vaultspec-rag search "<concise noun phrase>" --type code --port 8766 --max-results 12 --timeout 30` before editing, then verify exact symbols with grep. Discovery in this codebase is unreliable solo-grep-only; RAG surfaces conceptually identical sites grep misses (see the cross-vocabulary examples below). The `--timeout 30` flag is REQUIRED on every `vaultspec-rag search` invocation to avoid the model-warmup/first-query timeouts that otherwise abort the search.

Use vaultspec-rag for semantic search before grep when you know the concept but not the project's chosen vocabulary. Run `vaultspec-rag search "<query>" --type code|vault --port 8766 --max-results N --timeout 30`. The RAG indexes source chunks and `.vault/` documents under one embedding model and surfaces conceptually identical locations across vocabulary mismatches that grep cannot recover. Use grep only to pin the exact symbol, path, or literal string once RAG has located the surface (RAG for discovery, grep for confirmation).

Scope new feature surfaces with both passes. `--type code` returns implementation chunks. `--type vault` binds them to the ADR, plan, exec, and audit trail that justifies the code. Inspect the highest-score hit per directory. Ignore the long 0.0x tail.

Route every command through the resident service. Check `vaultspec-rag server status` first (exit 0 = running; start it with `vaultspec-rag server start` if stopped). Pass `--port 8766` and `--timeout 30` to every `search`, and `--port 8766` to every `index`, so they delegate through the service rather than each spawning a competing qdrant lock holder. Local-file qdrant is single-writer; concurrent stdio MCP children strand each other on the lock.

Reindex after substantial edits and before consequential reasoning: `vaultspec-rag index --type all --port 8766`. Incremental ingest is under 15s on this codebase and the service holds the GPU models warm.

Treat the CLI `--language`, `--function-name`, `--class-name`, and `--node-type` flags as no-ops against the HTTP fast path; they return identical results for nonsense filter values. For AST-level narrowing, call the `search_codebase` MCP tool directly with the filter fields and verify the response shape.

Phrase queries as one concise sentence or noun phrase. Do not write verbose multi-clause paragraphs; they dilute the embedding signal sharply. A 50-word natural-English description caps top scores around 0.02 even when the right module is in the top hits, while the same concept phrased as a six-word noun phrase scores 0.5 to 0.9 on the same surface.

Read directory clustering across the top results, not just the single highest score. When absolute scores collapse below 0.1, look for the same module or `.vault/` feature folder repeating across three to five hits; that cluster is usually the right surface even when no single result clears the visible noise floor.

Expect concept-as-thing queries to score high and concept-as-event-flow queries to score low. "Where is X evaluated", "what is the reconciliation surface", and "where do we project invoices" return tight clusters with strong scores. "What triggers Y when Z happens" and "how does this connect to that" return correct topology with weak scores. Lean on the cluster pattern when the score signal is thin.

Plan for translation-file and test-docstring crowding in result tables. This codebase ships parallel `locales/{en,es,ca,hu}.yml` files; the same translated string returns four near-identical hits per concept and consumes most of `--max-results`. Test docstrings often outrank the production module they exercise because tests spell out the concept more explicitly. Raise `--max-results` to 12 to 20 for code searches, skip past locale and test rows when you need the production surface, and treat the same string in four languages as one signal, not four.

Phrase vault queries toward the document-title and heading vocabulary actually used under `.vault/`; colloquial paraphrase degrades vault score quality sharply. Code queries tolerate paraphrase and partial misspellings; the hybrid dense and sparse index recovers most jargon, distinctive single tokens, and typos.

Default to RAG for cross-vocabulary concept lookups. Grep returns the test scaffolding and misses the authority surface when the codebase and the developer use different terms for the same idea (for example "duplicate" vs "fingerprint", "guard" vs "gate", "fake" vs "stub", "soft delete" vs "archive").