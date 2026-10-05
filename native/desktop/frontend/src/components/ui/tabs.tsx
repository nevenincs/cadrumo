import * as React from "react";
import { Tabs as TabsPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";

/**
 * A tab row whose chosen tab is underlined in the brand colour. The list is
 * one tab stop; arrow keys move and choose. A view that must never unmount
 * (a live terminal) renders its own panel and names it on the trigger with
 * `aria-controls`.
 */
function Tabs({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn("flex min-h-0 flex-col", className)}
      {...props}
    />
  );
}

function TabsList({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn("flex h-control-lg items-stretch gap-0.5", className)}
      {...props}
    />
  );
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex cursor-pointer items-center gap-1.5 px-3 text-base font-medium whitespace-nowrap text-muted-foreground select-none",
        "-outline-offset-2 transition-colors hover:text-foreground disabled:pointer-events-none disabled:opacity-50",
        "data-[state=active]:text-foreground",
        "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-brand after:opacity-0 after:transition-opacity data-[state=active]:after:opacity-100 forced-colors:after:bg-[Highlight]",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("min-h-0 flex-1 outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsContent, TabsList, TabsTrigger };
