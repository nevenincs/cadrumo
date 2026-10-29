---
name: worktree-temporary-output
---

# Worktree temporary output and native build ownership

## Rule

Put all general developer, agent and programmatic scratch, temporary files, captures and disposable reports under the owning worktree's root `.tmp/`. Put every native build artifact, including native build scratch, under its enrolled CMake `build/<preset>/` tree. Never write build output into `native/` or another source directory.

## Why

The operator explicitly replaced the earlier `scratch/` convention on 2026-10-29 after audit output proliferated across the checkout and a home directory. The same instruction requires existing scratch/temp locations to be vacated and a separate native build-boundary check. The current policy amends the developer-workspace placement in `2026-07-13-data-output-standardization-adr`; installed application state retains its separate custody contract.

## How

- Resolve the owning worktree before writing. Use `.tmp/<date>-<owner>-<purpose>/` for general one-off work and collision-resistant child directories for programmatic runs. Do not create alternate `scratch/`, `.artifacts/`, `.logs/`, `.tmp-*`, provider-local temp roots or home/other-drive audit folders.
- Native compilation, generated sources, frontend assets, screenshots, test results and native verification scratch must be declared and admitted by the selected CMake binary directory. Direct Cargo, Vite, Tauri or capture commands must not fall back to source-local `target/`, `dist/`, caches or output paths. Reject output traversal, links and arbitrary external destinations before writing.
- Keep machine-managed dependency/tool caches, installed product state and destination-adjacent atomic-publication transactions under their respective contracts. These are not permission to create ad-hoc workspaces or to put build artifacts outside the enrolled build tree.
- Keep only the output needed by active runs or an ongoing review during the task; clean it when the task/session finishes and leave `.tmp/` vacated. Promote a needed durable result through its actual documentation/governance owner instead of preserving a scratch tree or citing scratch as decision authority. Do not create an evidence bundle or external directory unless the operator requested that destination.
- Before removal, verify the exact resolved targets remain in the intended worktree. Never follow links into dependencies, another worktree or user state. Do not silently claim a locked path was removed.