# PDF summary typography assets

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-190` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope and assessment

This chunk inventories seven font/license files in the calculation-summary PDF resource tree: three Hanken Grotesk faces, two JetBrains Mono faces, and one SIL Open Font License text for each family. The five TrueType files were inspected through their SFNT headers and name tables without invoking a renderer. Metadata identifies Hanken Grotesk Regular, SemiBold, and Bold at version 3.014 and JetBrains Mono Regular and Bold at version 2.304. Each font's embedded license metadata and both accompanying license texts identify SIL Open Font License 1.1. The included license texts preserve the conditions concerning bundling and embedding, reserved names, attribution, redistribution, and the prohibition on selling font software by itself.

The set supplies proportional and monospaced typography suitable for a report layout, but this chunk alone does not establish which PDF elements use each face. It contains font data and license text, not executable behavior or taxpayer records. No security issue is evident from the inventory. Static metadata parsing does not test glyph coverage, font shaping, embedding, or PDF rendering, and does not independently establish upstream provenance. The full per-file inventory and sizes are below.

## Complete assigned-file coverage

- HankenGrotesk-Bold.ttf (`src/cadrumo/_data/calculation_summary_pdf/fonts/HankenGrotesk-Bold.ttf`) — 73,640 bytes; face/version/license metadata inspected.
- HankenGrotesk-OFL.txt (`src/cadrumo/_data/calculation_summary_pdf/fonts/HankenGrotesk-OFL.txt`) — 4,402 bytes, 94 lines; complete license text inspected.
- HankenGrotesk-Regular.ttf (`src/cadrumo/_data/calculation_summary_pdf/fonts/HankenGrotesk-Regular.ttf`) — 73,648 bytes; face/version/license metadata inspected.
- HankenGrotesk-SemiBold.ttf (`src/cadrumo/_data/calculation_summary_pdf/fonts/HankenGrotesk-SemiBold.ttf`) — 73,644 bytes; face/version/license metadata inspected.
- JetBrainsMono-Bold.ttf (`src/cadrumo/_data/calculation_summary_pdf/fonts/JetBrainsMono-Bold.ttf`) — 277,828 bytes; face/version/license metadata inspected.
- JetBrainsMono-OFL.txt (`src/cadrumo/_data/calculation_summary_pdf/fonts/JetBrainsMono-OFL.txt`) — 4,399 bytes, 93 lines; complete license text inspected.
- JetBrainsMono-Regular.ttf (`src/cadrumo/_data/calculation_summary_pdf/fonts/JetBrainsMono-Regular.ttf`) — 273,900 bytes; face/version/license metadata inspected.
<!-- /preserved:article -->
