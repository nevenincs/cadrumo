---
tags:
  - '#research'
  - '#single-binary-process-tree'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:bc90e43bd7c91b1a00b75a82d22c87eda58eb1149d3459b6c14d33fa43d052a0'
related: []
---

# `single-binary-process-tree` research: `Windows process grouping and a single Cadrumo binary`

## Findings

## Sources

## Context

## Question

Why do Cadrumo's processes appear as separate rows in Windows Task Manager instead of one Cadrumo application, and what process architecture makes them one application while keeping worker containment.

## Findings

### Package identity does not produce the grouping

With the Debug stage registered as a package with external location, every Debug process carried the same package full name and application user model id (`md.neve.cadrumo_1dy2cdv7j9a4w!Cadrumo`), measured with `GetPackageFullName` and `GetApplicationUserModelId` on 2026-10-17 at 10:35. The operator observed Task Manager at the same time: the processes were not grouped under the Cadrumo application. Identity is therefore not the grouping mechanism for these processes.

### Package identity weakens containment

Measured on Windows 11 build 26300 on 2026-10-17 against the registered Debug stage:

- A packaged child in a kill-on-close job started an unpackaged grandchild (`PING.EXE`) that was outside the job, even when the launcher itself was packaged. Without identity the grandchild stayed in the job.
- `PROC_THREAD_ATTRIBUTE_DESKTOP_APP_POLICY` with `PROCESS_CREATION_DESKTOP_APP_BREAKAWAY_DISABLE_PROCESS_TREE` set by a packaged launcher kept the grandchild in the job; set by an unpackaged launcher it had no effect.
- `PROC_THREAD_ATTRIBUTE_JOB_LIST` launches of packaged images from an unpackaged launcher failed with `ERROR_ACCESS_DENIED` in 35 of 60 launches while other packaged processes held their own jobs; create-suspended then `AssignProcessToJobObject` failed in 0 of 860.
- The build session's investigation found that Windows places packaged processes started from outside the package in one shared OS job, which can nest under an unrelated Cadrumo job; closing that job then kills unrelated packaged processes. Its scripts and logs were kept in that session's scratch directory `accessdenied`.

### Observed Task Manager grouping

The operator's Task Manager capture of the Release stage on 2026-10-17 at 10:31, without a search filter, showed:

- two `python.exe` interpreter processes grouped as one row with a count;
- `msedgewebview2.exe` renderer grouped under the `msedgewebview2.exe` WebView2 manager;
- `cadrumo-runtime.exe` and `cadrumo-agent-service.exe`, children of `cadrumo.exe`, each as their own row;
- the `cadrumo.exe` row holding only its window.

Every grouped pair shares one executable; every split pair crosses to a different executable. Captures taken later with a Task Manager search filter active are not evidence, because a search shows matching processes without their groups.

### The established pattern is one executable with roles

Chromium runs its browser, renderer, GPU and utility processes from one executable, selecting the role with a `--type` switch; Electron applications, Visual Studio Code and Microsoft Edge follow the same model. These applications appear as one Task Manager application with their helpers nested.

### Cadrumo starts several executables today

- `cadrumo.exe`, the Rust desktop, hosts the manager core and starts `bin/cadrumo-runtime.exe` (`native/manager/src/supervision/launch.rs:152`, `runtime_image` at `:207`).
- The desktop starts the agent service image (`native/desktop/src-tauri/src/agent/`), which starts `cadrumo-agent`.
- The runtime starts workers and the KDF child through `sys.executable`, which the entrypoint host sets to the package `python.exe` (`native/interpreter/windows/host.c:31-35`).
- Entrypoint and bundled images are declared in `native/package-layout.json` (`entrypoints`, `bundled_images`).

### The interpreter hosts are thin and reusable

Each C host establishes restricted DLL search, loads the bundled CPython DLL and `cadrumo_python_bridge`, applies the launch profile, and calls the exported `cadrumo_python_main` (`native/interpreter/windows/host.c:66-131`, `native/interpreter/python.c:28`). The role differences are compile-time defines (`CADRUMO_ENTRYPOINT`, `CADRUMO_BUNDLED_IMAGE`, `CADRUMO_FIXED_MODULE`). The same logic can be compiled once and selected at run time.

### Accepted decisions that name separate images

- `2026-10-04-runtime-manager-architecture-adr` chose a separate `cadrumo-manager` image, partly because termination targeting, startup approval and macOS login items identify a process by its image.
- `2026-10-12-desktop-agent-host-adr` binds service admission to image, module and invocation plus kernel peer evidence.
- `2026-10-16-application-distribution-windows-package-identity-adr` decided package identity for grouping.

## Sources

- Chromium multi-process architecture: https://www.chromium.org/developers/design-documents/multi-process-architecture/
- Application User Model IDs: https://learn.microsoft.com/en-us/windows/win32/shell/appids
- Job objects and nested jobs: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- UpdateProcThreadAttribute (desktop app policy): https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
