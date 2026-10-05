import { useMemo, type ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import { TooltipProvider } from "@/components/ui/tooltip";
import { StringsContext, translator } from "@/shell/strings";

/** The shell surface a story sits on. */
export type Surface = "background" | "chrome" | "card";

const SURFACES: Record<Surface, string> = {
  background: "bg-background",
  chrome: "bg-chrome",
  card: "bg-card",
};

/**
 * What surrounds every story: a shell surface and the providers the
 * application mounts at its root. `fill` gives the story the whole canvas.
 */
export function Frame({
  surface,
  locale,
  fill,
  children,
}: {
  surface: Surface;
  locale: string;
  fill: boolean;
  children: ReactNode;
}) {
  const translate = useMemo(() => translator(locale), [locale]);
  return (
    <StringsContext.Provider value={translate}>
      <TooltipProvider>
        <div
          className={cn(
            "min-h-dvh text-foreground",
            SURFACES[surface],
            !fill && "p-6",
          )}
        >
          {children}
        </div>
      </TooltipProvider>
    </StringsContext.Provider>
  );
}

/** A titled group of specimens in a story. */
export function Specimen({
  title,
  note,
  children,
  className,
}: {
  title: string;
  note?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className="grid gap-2 border-b py-4 first:pt-0 last:border-b-0">
      <header className="grid gap-0.5">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {note && <p className="text-sm text-muted-foreground">{note}</p>}
      </header>
      <div className={cn("flex flex-wrap items-center gap-3", className)}>
        {children}
      </div>
    </section>
  );
}
