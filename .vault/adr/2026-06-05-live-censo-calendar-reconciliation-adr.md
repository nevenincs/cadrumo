---
tags:
  - '#adr'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-research]]'
---

# `live-censo-calendar-reconciliation` adr: `Calendar obligations resolve from live censo, fall back to profile, or refuse` | (**status:** `accepted`)

## Problem Statement

Modelo obligations must derive from the taxpayer's legal situation, and the calendar must prove whether it used live censo-backed facts, profile facts, or refused because the necessary facts were absent. Without a provenance contract the calendar can silently present obligations on stale or assumed facts.

## Decision

The calendar resolves each obligation from live censo-backed facts when present, falls back to profile facts otherwise, and refuses (never silently defaults) when the necessary facts are absent. Every emitted obligation stamps which source it used, so the operator can see the basis of each deadline.

## Status

Accepted.
