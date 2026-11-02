// How a story's play writes into a field: as a person does, in the window's
// language, and leaves it, so the field shows the form it settles into at rest
// and not the text it was being typed in.

import { userEvent } from "storybook/test";
import { formatDayFigures } from "../shared/dateFormats";
import { formatDecimal, writtenPlaces } from "../shared/numbers";

/** What a person writes for `canonical` in the field `input` belongs to: a day
 * in the window's order, an amount with its marks, as the field offers them
 * for typing. Any other text is written as it is. */
function writtenIn(input: HTMLInputElement, canonical: string): string {
  const locale = input.ownerDocument.documentElement.lang || "en";
  if (input.closest('[data-slot="date-editor"]'))
    return formatDayFigures(locale, canonical);
  if (input.inputMode === "decimal" && /^-?\d+\.\d+$/.test(canonical))
    return formatDecimal(locale, canonical, {
      grouping: false,
      minFraction: writtenPlaces(canonical),
    });
  return canonical;
}

/** Replaces what `input` holds with `canonical`, written in the window's
 * language, then leaves the field. A day or an amount is given as a backend
 * writes it. */
export async function typeAsAPerson(
  input: HTMLInputElement,
  canonical: string,
): Promise<void> {
  await userEvent.clear(input);
  await userEvent.type(input, writtenIn(input, canonical));
  input.blur();
}
