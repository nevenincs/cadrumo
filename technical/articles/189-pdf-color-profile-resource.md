# PDF color profile resource

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-189` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope and assessment

This chunk contains one binary asset, `sRGB-IEC61966-2.1.icc` (`src/cadrumo/_data/calculation_summary_pdf/color/sRGB-IEC61966-2.1.icc`), at 588 bytes. I inspected its ICC header and tag directory: it has the `acsp` profile signature, RGB color space with XYZ profile connection space, an `mntr` class, and an English/US `sRGB built-in` description. The 11 tags include the expected description/copyright, white point, chromatic adaptation, primary colorants, transfer curves, and chromaticity data. This supports its role as a compact color-management reference for calculation-summary PDF output, as indicated by its bundled path; this chunk alone does not prove which renderer embeds or applies it.

The asset contains no executable behavior or taxpayer information. Static parsing establishes the file structure and profile identity but does not validate PDF rendering, color conversion fidelity, or downstream resource loading. No security finding is supported by this single file. Its SHA-256 is `a725926a3e8a9743234c77fba555624880d2f1074851bfd0487708d186b6d8f5`.

## Complete assigned-file coverage

- sRGB-IEC61966-2.1.icc (`src/cadrumo/_data/calculation_summary_pdf/color/sRGB-IEC61966-2.1.icc`) — 588 bytes; header and tag inventory inspected.
<!-- /preserved:article -->
