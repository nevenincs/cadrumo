import { cn } from "@/components/ui/cn";

/** The box number as printed on the official form; nothing when it has
 * none. */
export function BoxNumber({
  box,
  size = "md",
}: {
  box: string | null;
  size?: "sm" | "md";
}) {
  if (!box) return null;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-sm border border-border-strong font-mono text-muted-foreground tabular-nums",
        size === "md"
          ? "h-6 min-w-10 px-1 text-sm"
          : "h-5 min-w-8 px-0.5 text-xs",
      )}
    >
      {box}
    </span>
  );
}
