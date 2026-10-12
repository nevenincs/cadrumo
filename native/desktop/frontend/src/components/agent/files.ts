import type { IconName } from "@/components/ui/icon";
import type { FileKind } from "./types";

/** The glyph a file of each kind is drawn with where it has no preview. */
export const KIND_GLYPH: Record<FileKind, IconName> = {
  image: "image",
  sheet: "sheet",
  text: "page",
  archive: "fileArchive",
  document: "page",
};

// Decimal steps, so the unit the platform names is the unit that was used.
const UNITS = ["byte", "kilobyte", "megabyte", "gigabyte"] as const;
const STEP = 1000;

const formats = new Map<string, Intl.NumberFormat>();

function unitFormat(
  locale: string,
  unit: (typeof UNITS)[number],
  fraction: number,
): Intl.NumberFormat {
  const key = `${locale}|${unit}|${fraction}`;
  let format = formats.get(key);
  if (!format) {
    format = new Intl.NumberFormat(locale, {
      style: "unit",
      unit,
      unitDisplay: "short",
      maximumFractionDigits: fraction,
    });
    formats.set(key, format);
  }
  return format;
}

/** A file size in the largest unit that keeps the number at least one, in
 * the platform's own wording for the locale. */
export function formatSize(locale: string, bytes: number): string {
  let value = Math.max(0, bytes);
  let index = 0;
  while (value >= STEP && index < UNITS.length - 1) {
    value /= STEP;
    index += 1;
  }
  const unit = UNITS[index] ?? "byte";
  // One decimal while the number is small enough for it to matter.
  const fraction = index > 0 && value < 10 ? 1 : 0;
  return unitFormat(locale, unit, fraction).format(value);
}

const percents = new Map<string, Intl.NumberFormat>();

/** A share from 0 to 1 as a whole percentage, in the locale's own form. */
export function formatPercent(locale: string, share: number): string {
  let format = percents.get(locale);
  if (!format) {
    format = new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 0,
    });
    percents.set(locale, format);
  }
  return format.format(clampShare(share));
}

/** A progress share held to 0 to 1; anything unreadable counts as none. */
export function clampShare(share: number | undefined): number {
  if (share === undefined || !Number.isFinite(share)) return 0;
  return Math.max(0, Math.min(1, share));
}

/** The extension as a tile or row shows it: upper case, without its dot. */
export function extensionLabel(extension: string): string {
  return extension.replace(/^\./, "").toUpperCase();
}
