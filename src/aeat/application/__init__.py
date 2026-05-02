"""Application layer of the hexagonal architecture.

Hosts orchestration services that compose pure :mod:`aeat.domain`
logic with :mod:`aeat.adapters` boundaries (filing draft assembly,
financial aggregation, attachment management, sync workflows,
reconciliation). No code in this package should reach into outbound
adapters directly; consumers compose through the entrypoints layer.
"""
