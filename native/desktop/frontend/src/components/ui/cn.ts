import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The shell's own scale names (src/tokens.css), so a later class replaces an
// earlier one of the same kind: without them `text-md` reads as a colour and
// `h-control-md` as an unknown size.
const merge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["2xs", "xs", "sm", "base", "md", "lg"],
      radius: ["xs", "sm", "md", "lg", "xl", "2xl"],
      shadow: ["raised", "overlay"],
      spacing: [
        "control-xs",
        "control-sm",
        "control-md",
        "control-lg",
        "icon-xs",
        "icon-sm",
        "icon-md",
        "icon-lg",
        "rail",
        "palette",
        "palette-max",
        "dialog",
        "settings",
        "menu",
        "field",
        "badge",
      ],
    },
  },
});

/** Joins class names, letting a later utility replace an earlier one. */
export function cn(...inputs: ClassValue[]): string {
  return merge(clsx(inputs));
}
