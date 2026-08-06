---
name: aeat-agent-delivery
trigger: always_on
---

# AEAT agent delivery

Delegate one issue at a time. Keep handovers agent-agnostic. Do not hard-code Claude, Codex, Gemini, or launcher commands into project instructions.

Balance active work across Track A for AEAT remote synchronisation and Track B for financial-input processing. Keep six-agent capacity balanced. Do not starve either track.

Bind financial-input work to the Transaction Data Pipeline step it serves. Preserve provenance from ingest through handoff. Treat Google Sheets as a one-way export mirror, never an authority.

There is no GitHub project board; the AEAT board was retired on 2026-07-21 as dead weight. Track work through GitHub issues, live git worktrees, and the vault pipeline only. Treat an issue as actively worked only when a worktree and a delegation exist for it. Do not reintroduce a project board, and do not mark charters, placeholders, or intent as active execution.
