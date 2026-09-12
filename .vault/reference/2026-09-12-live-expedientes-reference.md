---
tags:
  - '#reference'
  - '#live-expedientes'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:7f40bc17c924590c84097d2b113f5e22574fb12462f80ddab88ddb4ad1c3867c'
related: []
---

# `live-expedientes` reference: application-owned expedientes snapshot capabilities

## Summary

`ExpedientesService` is the application lifecycle around a bucket-scoped,
encrypted, stateless snapshot. Its current constructor and module-level helper
resolve the secure snapshot repository directly, while the capture verbs also
construct the AEAT declarations walker directly. The six concrete edges are the
snapshot repository, secure-object repository factory, snapshot storage
namespace, declarations register opener, shared Playwright context, and the
declarations payload type imported from the adapter tree.

The nearest accepted live-snapshot architecture keeps lifecycle and payload
models in `application/live/` and puts encrypted storage binding at an outer
composition root. The expedientes service should therefore receive one required
application-owned bundle per bucket: a snapshot repository capability plus a
read-only declarations capability. The declarations capability should expose
application DTOs (declarations, source URL, authenticated identity) and
application errors; adapter DOM/register objects must not cross the boundary.

The production chain found by semantic and exact-symbol search is the CLI root
composition, the live expedientes CLI entrypoint, and the application capture
and bulk-capture functions. Any operation-definition or TUI/CLI helper that
constructs these functions is a production caller and must receive or construct
the same bundle from the root factory. The composition root may retain the
adapter imports and translate adapter register failures into the application
capability's typed errors.
