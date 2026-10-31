/** An account number as the person typed it, without spaces, in capitals. */
export const ibanText = (raw: string) => raw.replace(/\s+/g, "").toUpperCase();

/** An account number in groups of four, as it is printed. */
export const ibanGroups = (raw: string) =>
  ibanText(raw).replace(/(.{4})(?=.)/g, "$1 ");

/** Why a typed account number cannot be one, checked here before it is
 * sent: its shape and its control digits. The product checks it again. */
export function ibanProblem(raw: string): "shape" | "check" | null {
  const iban = ibanText(raw);
  if (!/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(iban)) return "shape";
  const moved = iban.slice(4) + iban.slice(0, 4);
  let rest = 0;
  for (const char of moved) {
    const digits = /\d/.test(char) ? char : String(char.charCodeAt(0) - 55);
    for (const digit of digits) rest = (rest * 10 + Number(digit)) % 97;
  }
  return rest === 1 ? null : "check";
}
