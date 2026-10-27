---
tags:
  - '#research'
  - '#robust-logging'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:c526d25605fbe284b03cf4d1d96994fb6be0042677b0ee605a7c0c4404ccd2f8'
related: []
---

# Logging stalls and shared producer paths

## Evidence

On 2026-10-27, a real Windows worker probe concurrently queried activity and operation contracts while synthetic leases expired and were reinstalled. It reproduced two activity deadline failures. The extended reproduction had zero queue delay and elapsed 20.010 seconds. Profiling at 20 Hz captured 398 event-loop samples in diagnostic file flush (19.9 seconds), and 227 samples in diagnostic-extra redaction opening registry authority (11.35 seconds). The operation channel then closed. Suppressing ordinary logs completed 32 cycles, 6588 activity and 6498 discovery queries, with worst replies 75 and 90 milliseconds. Sixteen existing native-operation and transport tests passed. Original retired workers' exact historical stacks are unavailable.

## Shared paths and constraints

Logger-attached filters synchronously render and redact in `src/cadrumo/core/logging.py`; `src/cadrumo/core/log_file_handler.py` synchronously appends and flushes. Native `native/application/src/diagnostics/mod.rs` appends while holding the event/status mutex, and panic logging also writes synchronously. Worker logging does not register runtime/client namespaces. These are best-effort diagnostics, distinct from authoritative journals.

Preserve redaction before outputs, emission identity, routing, rotation, thread safety and supervisor stream hygiene. Isolate arbitrary formatting, registry and sink stalls behind bounded queues; measure explicit loss and bound shutdown. Verify blocked sinks/filters, saturation, recursion, threaded writes, exception snapshots, healthy rotation, native worker responsiveness and producer latency. The operator explicitly authorized fixing these defects throughout the codebase and requested benchmarks and py-spy/handle analysis.
