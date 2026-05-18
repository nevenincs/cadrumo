"""Engineer-only diagnostics surface for AEAT internals.

Reachable as ``python -m aeat.diagnostics`` (see ``__main__.py``).
Hosts verbs that are useful for forensic / debugging work against
the secure-object backend, profile-fact lookup, and bucket-event
history, none of which belong on the operator-facing
``aeat config`` surface. The operator CLI keeps a strict
operator-vocabulary verb list; engineers reach for this entrypoint
when they need direct access to internal namespaces or scripted
field-at-a-time reads / writes that should never appear in
operator help text.
"""
