import * as React from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";

function Dialog(props: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />;
}

function DialogTrigger(
  props: React.ComponentProps<typeof DialogPrimitive.Trigger>,
) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />;
}

function DialogClose(
  props: React.ComponentProps<typeof DialogPrimitive.Close>,
) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />;
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 z-(--layer-modal) bg-scrim",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
        className,
      )}
      {...props}
    />
  );
}

/**
 * The dialog surface, portalled to the document body over a scrim. Focus is
 * trapped inside while it is open and returns to the opener when it closes.
 * `closeLabel` names the corner close button; leave it out for a dialog that
 * offers its own way out.
 */
function DialogContent({
  className,
  children,
  closeLabel,
  placement = "center",
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  closeLabel?: string;
  /** `top` suits a surface whose height changes as it is used. */
  placement?: "center" | "top";
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          "fixed left-1/2 z-(--layer-modal) grid w-dialog max-w-[calc(100%-2rem)] -translate-x-1/2 gap-4 rounded-xl border bg-card p-5 text-card-foreground shadow-overlay outline-none",
          placement === "center"
            ? "top-1/2 max-h-[calc(100%-2rem)] -translate-y-1/2 overflow-y-auto"
            : "top-(--overlay-top) max-h-[calc(100dvh-2*var(--overlay-top))]",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          className,
        )}
        {...props}
      >
        {children}
        {closeLabel && (
          <DialogPrimitive.Close asChild>
            <IconButton
              label={closeLabel}
              size="sm"
              className="absolute top-3 right-3"
            >
              <Icon name="close" />
            </IconButton>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-1 pr-8", className)}
      {...props}
    />
  );
}

function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn("flex flex-wrap items-center justify-end gap-2", className)}
      {...props}
    />
  );
}

function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("font-serif text-lg text-foreground", className)}
      {...props}
    />
  );
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-base text-muted-foreground", className)}
      {...props}
    />
  );
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
  DialogTrigger,
};
