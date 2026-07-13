# Recovery runbooks

Each runbook is a focused recovery procedure for one common failure or refusal.
When a command refuses or a check fails, find the runbook that matches the
message and follow its numbered steps. Every step runs locally; the tool never
submits anything to AEAT.

Each runbook has a stable id (`RB-NNN`) so a link to it does not break when its
title changes. For a single-page symptom index across every kind of local
problem, use [Diagnose and repair your local setup](../how-to/troubleshooting.md).

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} RB-001 Renew a certificate
:link: RB-001-certificate-expired
:link-type: doc

Your certificate expired or is close to expiring and live reads are blocked.
:::

:::{grid-item-card} RB-002 Live read refused
:link: RB-002-live-read-refused
:link-type: doc

A pull from AEAT refuses because authentication or connectivity is not ready.
:::

:::{grid-item-card} RB-003 Verification blocks export
:link: RB-003-verification-blocks-export
:link-type: doc

An export refuses because the draft is not verified, or verification reports
blocking findings.
:::

:::{grid-item-card} RB-004 Unreadable records
:link: RB-004-unreadable-records
:link-type: doc

A command reports corrupt or unreadable encrypted data.
:::

:::{grid-item-card} RB-005 Modelo not ready
:link: RB-005-modelo-not-ready
:link-type: doc

A modelo does not apply to your profile, or a calculation refuses because the
profile is incomplete.
:::

::::

```{toctree}
:hidden:

RB-001-certificate-expired
RB-002-live-read-refused
RB-003-verification-blocks-export
RB-004-unreadable-records
RB-005-modelo-not-ready
```
