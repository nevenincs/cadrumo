import * as React from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";

type PasswordInputProps = Omit<React.ComponentProps<typeof Input>, "type"> & {
  /** Whether the characters are shown; the owner decides and resets it. */
  revealed: boolean;
  onRevealedChange: (revealed: boolean) => void;
  /** The names of the reveal control in its two states. */
  showLabel: string;
  hideLabel: string;
};

/**
 * A password field with a control that shows or hides what was typed. It
 * stays a native password input, so paste and password managers work, and it
 * never reads, keeps or logs its own value: the owner takes it from the
 * element when it is needed.
 */
function PasswordInput({
  className,
  revealed,
  onRevealedChange,
  showLabel,
  hideLabel,
  disabled,
  autoComplete = "current-password",
  ...props
}: PasswordInputProps) {
  return (
    <div data-slot="password-input" className="relative">
      <Input
        type={revealed ? "text" : "password"}
        autoComplete={autoComplete}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        disabled={disabled}
        className={cn(
          "pr-[calc(var(--spacing-control-xs)+--spacing(2))]",
          className,
        )}
        {...props}
      />
      <IconButton
        label={revealed ? hideLabel : showLabel}
        side="top"
        disabled={disabled}
        onClick={() => onRevealedChange(!revealed)}
        className="absolute top-1/2 right-1 -translate-y-1/2"
      >
        <Icon name={revealed ? "eyeOff" : "eye"} />
      </IconButton>
    </div>
  );
}

export { PasswordInput, type PasswordInputProps };
