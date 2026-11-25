/** An account number as the person typed it, without spaces, in capitals. */
export const ibanText = (raw: string) => raw.replace(/\s+/g, "").toUpperCase();

/** An account number in groups of four, as it is printed. */
export const ibanGroups = (raw: string) =>
  ibanText(raw).replace(/(.{4})(?=.)/g, "$1 ");

/** Whether typed text is not even written as an account number. Whether it is
 * one, its control digits included, is the backend's to answer. */
export const ibanMalformed = (raw: string): boolean =>
  !/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(ibanText(raw));
