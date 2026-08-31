# Modelo export mirrors official structure

- A modelo export derives its record order, field positions, widths, repetitions, encodings, and conditional sections from the official record design or schema for the selected revision.
- One canonical export builder and formula path owns both preview and emitted filing data. Do not maintain a second hand-built serializer or recompute values differently for display.
- Every exported field maps to a validated registry concept and carries the same typed meaning, formatting, sign, rounding, and provenance used by calculation.
- Fixed-width completeness is value-aware: distinguish absent, required blank, permitted blank, zero, and populated values. Padding a missing required value does not make a record complete.
- Conditional records and repeated groups are emitted only when their official conditions and cardinalities are satisfied. Reject overflow, truncation, illegal characters, inconsistent totals, and unsupported revision layouts.
- Generated export references and fixtures are CLI-owned. Change the source/generator, regenerate, and verify byte-for-byte or schema parity against the official structure; do not hand-edit generated artifacts.
- Tests cover official examples where available, boundary widths, encoding, required absence, conditional sections, totals, and parse/serialize semantic round trips.
