# Installed TUI-only journey, run 1: failed (2026-09-23)

This is failure evidence, not proof. It is not promoted.

Pinned identities:

- Source commit `393da09995`. It includes the create-or-reopen route `a8c5b42266`, the pinned-authority create fix in the same commit, and the work_create locale keys `81037765b3`.
- The wheel was built from a detached checkout of that commit. Wheel SHA-256: `779c7119044d1a224a09d3d0e31f6f318f41d903e29d846a22150a1845b92e82`.
- Installed `cadrumo/__init__.py` SHA-256: `930e3f61c79bd2e3ff1f8aa11d1abd5d16bfbaab360ea739ae41f519f71b0ae7`.
- Installed launcher SHA-256: `2bcd144d71966656b03831cf965654c2b6fb46a9f7c7c8ceb6b4ae697fb261bd`, identical in source and installed.
- Served authority: the wheel-embedded one, `logical_generation` `4fa84c26a651ebd7a60499c4b5edb1a682329d07c8663336f82df1fa6720dd15`. It is format v1 with v1 reader code, which is consistent, and it predates the format-v2 cutover.

What the run proved before stopping, all through installed TUI controls with a fresh encrypted store:

- profile setup
- two Ledger invoices
- the Withholding route
- the required-detail refusal
- professional and urban-rent capture
- Declarations created all five source declarations (111 2T; 115 1T to 4T)
- reuse of 111 2T
- refusal of 111 0A
- Modelo 111 2T calculate, verify, export and local file
- Modelo 115 1T calculate, verify and file
- Modelo 115 2T calculate, verify and export

Export artifacts were written for 111 2T (1346 bytes) and 115 2T (846 bytes). They were not independently validated, because the parent validates only after a proven child.

Where it stopped: `tui_only_file:115|2T_failed:destination_home_palette_offer_failed:ModeloWorkspaceOverviewScreen`. The palette did not open within the driver's fixed 180-cycle poll. This is a driver defect. The palette wait now uses the wall-clock budget, identifies the palette by its Textual type, and presses `ctrl+p` again if the palette has not opened. No product defect is implied.

No CLI step was used, and no AEAT submission was made.