import type { EntryReading } from "@/components/editors/EntryInput";
import {
  formatDecimal,
  heldDecimal,
  isTwoWayDecimal,
  readLocaleDecimal,
  writtenPlaces,
} from "@/shared/numbers";

const WRITTEN = /^-?\d+(\.\d+)?$/;

/** Whether a held value is a decimal the editor read, not text left unread.
 * Text in the two-way shape can only be unread: a read one is held longer. */
export const isReadDecimal = (value: string): boolean =>
  WRITTEN.test(value) && !isTwoWayDecimal(value);

/** How a decimal editor reads: the language's marks going in, every digit kept
 * and shown, trailing zeros too, and unread text shown as it came. */
export function decimalReading(
  locale: string,
  shown: (value: string) => string = (value) =>
    formatDecimal(locale, value, { minFraction: writtenPlaces(value) }),
): EntryReading {
  return {
    read(typed) {
      if (typed.trim() === "") return "";
      const reading = readLocaleDecimal(locale, typed);
      return reading === null ? null : heldDecimal(reading);
    },
    shown: (value) => (isReadDecimal(value) ? shown(value) : value),
    typed: (value) =>
      isReadDecimal(value)
        ? formatDecimal(locale, value, {
            grouping: false,
            minFraction: writtenPlaces(value),
          })
        : value,
  };
}
