import { cn } from "@/components/ui/cn";

// A provider's mark is a neutral dashed ring and nothing else: no letters and
// no shape that could be taken for a logo. Cadrumo keeps no artwork of any
// provider; if the agent's catalog ever serves some, it is drawn from there.
// The provider's name always stands beside the mark, so the mark is
// decoration.

const SIZES = { sm: "size-icon-md", md: "size-icon-lg" } as const;

/**
 * The mark of the provider `provider`, wherever the provider is shown. It
 * takes the text colour of where it stands.
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
}
