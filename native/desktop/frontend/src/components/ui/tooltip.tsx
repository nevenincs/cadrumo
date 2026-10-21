import * as React from "react";
import { Tooltip as TooltipPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";

const TooltipContainerContext = React.createContext<{
  container: HTMLElement | undefined;
  setContainer: (container: HTMLElement | undefined) => void;
}>({ container: undefined, setContainer: () => {} });

/** One provider at the application root: a short delay before the first
 * tooltip, none when moving between neighbouring controls. */
function TooltipProvider({
  delayDuration = 400,
  skipDelayDuration = 300,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      data-slot="tooltip-provider"
      delayDuration={delayDuration}
      skipDelayDuration={skipDelayDuration}
      {...props}
    />
  );
}

function Tooltip(props: React.ComponentProps<typeof TooltipPrimitive.Root>) {
  const [container, setContainer] = React.useState<HTMLElement>();
  const context = React.useMemo(
    () => ({ container, setContainer }),
    [container],
  );
  return (
    <TooltipContainerContext.Provider value={context}>
      <TooltipPrimitive.Root data-slot="tooltip" {...props} />
    </TooltipContainerContext.Provider>
  );
}

function TooltipTrigger({
  ref,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Trigger>) {
  const { setContainer } = React.useContext(TooltipContainerContext);
  const triggerRef = React.useCallback(
    (node: HTMLButtonElement | null) => {
      // Keep descriptions within the trigger's owning landmark. A fixed
      // popper still escapes an overflowing rail, without orphaning its
      // accessible text at the document body.
      setContainer(
        node?.closest<HTMLElement>(
          'nav, main, aside, header, footer, search, [role="navigation"], [role="main"], [role="complementary"], [role="banner"], [role="contentinfo"], [role="region"], [role="search"], [role="form"]',
        ) ?? undefined,
      );
      if (typeof ref === "function") return ref(node);
      if (ref) ref.current = node;
    },
    [ref, setContainer],
  );
  return (
    <TooltipPrimitive.Trigger
      data-slot="tooltip-trigger"
      ref={triggerRef}
      {...props}
    />
  );
}

function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Content>) {
  const { container } = React.useContext(TooltipContainerContext);
  return (
    <TooltipPrimitive.Portal container={container}>
      <TooltipPrimitive.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "z-(--layer-tooltip) flex w-fit max-w-64 origin-(--radix-tooltip-content-transform-origin) items-center gap-2 rounded-md bg-foreground px-2 py-1 text-sm text-background shadow-overlay",
          // It arrives by a transition from its starting style and leaves at
          // once. A keyframe animation would keep it mounted while it ends,
          // and a tooltip on its way out is still the topmost layer: it would
          // take an Escape meant for the dialog beneath it.
          "transition-[opacity,scale] starting:scale-95 starting:opacity-0",
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger };
