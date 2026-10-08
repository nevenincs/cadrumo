import { identity } from "virtual:desktop-content";
import { cn } from "@/components/ui/cn";
import mark from "../../../../../docs/_static/cadrumo-favicon.svg";

const SIZES = {
  sm: { mark: "size-control-xs", name: "text-base" },
  md: { mark: "size-control-lg", name: "text-lg" },
} as const;

/**
 * The application's mark and name. The mark is the documentation's own
 * artwork and the name is the product identity the build was configured with,
 * so neither is drawn or spelled a second time here.
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
      className={cn("inline-flex items-center gap-2.5", className)}
    >
      <img
        src={mark}
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
