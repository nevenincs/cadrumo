---
tags:
  - '#adr'
  - '#desktop-service-installation'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:401e90fcc9f30df9b5d32991265400c3bc90c18eee72e60423d30b9d4663e470'
related:
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-07-application-distribution-windows-versioned-msi-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-application-distribution-audit]]"
---

# `desktop-service-installation` adr: `Desktop scoped manager installation` | (**status:** `accepted`)

## Problem Statement

A complete unregistered package cannot start its manager because desktop discovery requires a published installation. The operator requests an internal Tauri installation command for user or machine scope when no manager is running.

## Considerations

`native/desktop/src-tauri/src/manager.rs` dispatches only an existing compatible installation. `native/installer/src/runner.rs` already owns hash-bound two-MSI transactional publication and validates the maintenance runner against immutable MSI metadata. The staged GUI harness prestarts a runtime and cannot prove bootstrap.

## Considered options

- Reuse the native transaction runner with a verified companion installation kit: chosen; preserves MSI ownership and elevation separation.
- Start a runtime directly from the GUI: excludes durable login registration and couples supervision to a window; rejected for this scope.
- Introduce an SCM service: conflicts with interactive-session runtime admission; outside the requested installation-command implementation.

## Constraints

Authorized 2026-10-09 by the operator's explicit implementation request. This scoped instruction authorizes the desktop provisioning extension; interactive manager/runtime ownership is unchanged.

The desktop may install or ensure the manager through a token-checked internal command with a closed user/machine scope. The command admits a companion kit against the actively running package identity and inventory, verifies the runner and MSI artifacts before execution, and never takes executable paths from the webview. User installation is unelevated; machine installation uses the native elevation prompt. Native commitment plus catalogue rediscovery is required before success. Cancellation or ambiguous maintenance never implies publication. Runtime and manager remain unelevated interactive-user processes; profile, password and runtime transport authority are excluded.

The kit lives beside the immutable package, since embedding a release MSI inside the package it installs would create a recursive inventory. Layout declares the sibling directory and descriptor. Default launch ensures user installation only when manager discovery finds no usable installation; a user can explicitly request machine installation. Existing valid installations are started without installation. Development or storage/authority overrides remain unmanaged.

## Implementation

We will add shared installer bootstrap admission and native runner execution to `native/installer`, emit a portable companion kit from verified MSI outputs, and expose `manager_install(scope)` in Tauri. Automatic GUI startup may use this bootstrap for the user scope when discovery is unavailable. Native maintenance finishes independently of a dropped IPC answer. The desktop re-discovers and shell-dispatches the published manager after installation and retains typed installation failures.

The manager architecture's desktop-shell-dispatch and login-registration sections gain an explicit provisioning exception: the desktop may invoke scoped native installation before manager dispatch; supervision remains exclusively with the manager. The desktop-shell restriction on runtime controls likewise permits this scoped installation command. The Windows immutable-product ADR extends delivery with the verified companion kit and desktop invocation of its existing transaction runner; two native MSI roles, publication and removal invariants remain binding.

### Authenticated native installation admission

The implementation trace additionally found that a literal-false LaunchCondition and the runner's legacy-product check refuse all presently generated MSI installations, even through the native owner. The operator's instruction to implement usable user/machine installation authorizes replacing that unconditional block only for products authored with the existing native owner and adapter. Mandatory scope/owner callbacks, protected broker state, synchronous operation authentication, native transaction settlement and publication remain required; standalone launches without the owner continue to fail before file ownership changes. Products without the native owner retain the literal-false block. Signing and disposable-host acceptance still govern release readiness; this source change does not claim their completion.

## Rationale

This implements the operator's 2026-10-09 instruction using existing package and native maintenance owners. A companion kit permits first-launch provisioning without weakening immutable package inventory or runner authentication.

## Consequences

Launching an unregistered distribution can establish login startup and start its manager. Delivery adds a companion kit; missing/damaged kits produce explicit installation refusal. Actual login registration acceptance requires a disposable interactive Windows host. This decision does not establish that acceptance.
