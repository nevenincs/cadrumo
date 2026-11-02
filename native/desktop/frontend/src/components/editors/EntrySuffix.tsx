import type { ReactNode } from "react";

/** An entry box with a mark at its end that is not part of what is typed: a
 * `%`, or the currency an amount is in. The box leaves room for it. */
export function EntrySuffix({
  mark,
  slot,
  children,
}: {
  mark: string;
  slot: string;
  children: ReactNode;
}) {
  return (
    <div data-slot={slot} className="relative">
      {children}
      <span
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-muted-foreground"
      >
        {mark}
      </span>
    </div>
  );
}

/** The class that keeps typed text clear of a suffix of this many characters. */
export const suffixRoom = (mark: string) =>
  mark.length > 1 ? "pr-11" : "pr-7";
