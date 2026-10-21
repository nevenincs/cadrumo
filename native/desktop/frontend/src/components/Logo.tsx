import { identity } from "virtual:desktop-content";
import { cn } from "@/components/ui/cn";
import colorMark from "../../../../../docs/_static/cadrumo-icon.svg";
import monoMark from "../../../../../docs/_static/cadrumo-favicon.svg";

const SIZES = {
  sm: { mark: "size-control-xs", name: "text-base" },
  md: { mark: "size-control-lg", name: "text-lg" },
} as const;

const MARKS = { color: colorMark, mono: monoMark } as const;

/**
 * The application's mark and name. The mark is the documentation's own
 * artwork and the name is the product identity the build was configured with,
 * so neither is drawn or spelled a second time here. Where the brand is
 * secondary to the surface around it, the mono mark keeps it quiet.
 */
export function Logo({
  size = "md",
  tone = "color",
  className,
}: {
  size?: keyof typeof SIZES;
  tone?: keyof typeof MARKS;
  className?: string;
}) {
  return (
    <span
      data-slot="logo"
      className={cn("inline-flex items-center gap-2.5", className)}
    >
      <img
        src={MARKS[tone]}
        alt=""
        draggable={false}
        className={cn("shrink-0 select-none", SIZES[size].mark)}
      />
      <span
        className={cn(
          "font-serif leading-none tracking-wide text-foreground",
          SIZES[size].name,
        )}
      >
        {identity.name}
      </span>
    </span>
  );
}
