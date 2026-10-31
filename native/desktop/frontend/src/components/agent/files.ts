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

/** A progress share held to 0 to 1; anything unreadable counts as none. */
export function clampShare(share: number | undefined): number {
  if (share === undefined || !Number.isFinite(share)) return 0;
  return Math.max(0, Math.min(1, share));
}

/** The extension as a tile or row shows it: upper case, without its dot. */
export function extensionLabel(extension: string): string {
  return extension.replace(/^\./, "").toUpperCase();
}
