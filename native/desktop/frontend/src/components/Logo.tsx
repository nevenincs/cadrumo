import { identity } from "virtual:desktop-content";
import { cn } from "@/components/ui/cn";
import mark from "../../../../../docs/_static/cadrumo-icon.svg";

const SIZES = {
  xs: { mark: "size-mark-xs", name: "text-base", gap: "gap-1.5" },
  sm: { mark: "size-mark-sm", name: "text-base", gap: "gap-2" },
  md: { mark: "size-mark-md", name: "text-md", gap: "gap-3" },
} as const;

/**
 * The application's lockup: its mark and its name. The mark is the
 * documentation's own artwork and the name is the product identity the build
 * was configured with, so neither is drawn or spelled a second time here.
 *
 * The mark is always the coloured tile. It is the one place colour belongs
 * to the brand, and at the size of a title bar the tile reads where a muted
 * copy sinks into the chrome. The name is set in the text face, in capitals,
 * semibold and tracked, as the documentation's wordmark is set in capitals.
 * The documentation's display serif is not used here: it is a display cut,
 * and at the sizes a window has for a name its hairlines fall below a device
 * pixel and the name goes faint.
 */
export function Logo({
  size = "md",
  className,
}: {
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      data-slot="logo"
      className={cn("inline-flex items-center", SIZES[size].gap, className)}
    >
      <img
        src={mark}
        alt=""
        draggable={false}
        className={cn("shrink-0 select-none", SIZES[size].mark)}
      />
      <span
        className={cn(
          "font-sans leading-none font-semibold tracking-brand text-foreground uppercase",
          SIZES[size].name,
        )}
      >
        {identity.name}
      </span>
    </span>
  );
}
