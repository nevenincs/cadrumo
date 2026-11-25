import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import artwork from "virtual:desktop-provider-icons";

// Artwork comes from the same bundled agent that declares the providers.
// A mask lets monochrome marks follow the current theme without inserting SVG
// markup into the document. The adjacent provider name supplies the label.
// A provider the agent ships no artwork for wears the generic agent mark.

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
  const icon = Object.hasOwn(artwork.providers, provider)
    ? artwork.providers[provider]
    : undefined;
  return (
    <span
      aria-hidden="true"
      data-slot="provider-mark"
      data-provider={provider}
      data-mark={icon ? "mono" : "generic"}
      style={icon ? { maskImage: `url("${icon.mono}")` } : undefined}
      className={cn(
        "inline-flex shrink-0 items-center justify-center",
        icon && "bg-current mask-contain mask-center mask-no-repeat",
        SIZES[size],
        className,
      )}
    >
      {!icon && <Icon name="agent" className="size-full" />}
    </span>
  );
}
