import { cn } from "@/components/ui/cn";
import { PROVIDER_MARKS, PROVIDER_MARK_GRID } from "./providerIcons";

// A provider's mark is the provider's own, drawn from the vendored artwork in
// providerIcons.ts and keyed by the id cadrumo-agent's catalog serves. A
// provider with no artwork gets a neutral dashed ring and nothing else: no
// letters and no shape that could be taken for a logo. The provider's name
// always stands beside the mark, so the mark is decoration.

const SIZES = { sm: "size-icon-md", md: "size-icon-lg" } as const;

/**
 * The mark of the provider `provider`, wherever the provider is shown. It
 * takes the text colour of where it stands, so it follows the theme, and a
 * forced-colours window draws every piece in that colour alone.
 */
export function ProviderMark({
  provider,
  size = "sm",
  className,
}: {
  /** The provider's id, which the mark belongs to. */
  provider: string;
  /** The provider's name. The mark never draws it: the name stands beside
   * the mark, and a caller that still passes it changes nothing. */
  name?: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const pieces = Object.hasOwn(PROVIDER_MARKS, provider)
    ? PROVIDER_MARKS[provider]
    : undefined;
  if (!pieces)
    return (
      <span
        aria-hidden="true"
        data-slot="provider-mark"
        data-provider={provider}
        data-mark="none"
        className={cn(
          "inline-block shrink-0 rounded-full border border-dashed border-border-strong",
          SIZES[size],
          className,
        )}
      />
    );
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      data-slot="provider-mark"
      data-provider={provider}
      data-mark="own"
      viewBox={`0 0 ${PROVIDER_MARK_GRID} ${PROVIDER_MARK_GRID}`}
      fillRule="evenodd"
      className={cn(
        "inline-block shrink-0 forced-colors:[&_path]:fill-current",
        SIZES[size],
        className,
      )}
    >
      {pieces.map((piece) => (
        <path key={piece.d} d={piece.d} fill={piece.accent ?? "currentColor"} />
      ))}
    </svg>
  );
}
