import type { Meta, StoryObj } from "@storybook/react-vite";
import { cn } from "@/components/ui/cn";
import { Icon, ICON_NAMES } from "@/components/ui/icon";
import { Specimen } from "./Frame";

const meta = {
  title: "Foundations/Tokens",
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

// Each swatch names the role it shows; the class is written out in full so
// the stylesheet build finds it.
const SURFACES = [
  ["background", "bg-background", "The canvas: documentation and terminals"],
  ["chrome", "bg-chrome", "Rail, pane headers, panel"],
  ["card", "bg-card", "Dialogs, popovers, fields"],
  ["muted", "bg-muted", "A quiet block inside a surface"],
  ["secondary", "bg-secondary", "A control's own resting surface"],
  ["primary", "bg-primary", "The strongest action: ink on paper"],
] as const;

// Hover and the chosen surface are washes of ink, so each is shown over the
// surfaces it can sit on.
const UNDER = [
  ["background", "bg-background"],
  ["chrome", "bg-chrome"],
  ["card", "bg-card"],
] as const;
const STATES = [
  ["accent", "bg-accent", "Hovered"],
  ["selected", "bg-selected", "Pressed, or the chosen item"],
] as const;

const TEXT = [
  ["foreground", "text-foreground", "Primary text"],
  ["muted-foreground", "text-muted-foreground", "Secondary text and labels"],
  ["faint", "text-faint", "Placeholders, hints and meta"],
  ["brand", "text-brand", "Emphasis and the chosen indicator"],
  ["success", "text-success", "A good outcome"],
  ["warning", "text-warning", "Attention without failure"],
  ["destructive", "text-destructive", "Failure and refusal"],
] as const;

const LINES = [
  ["border", "border-border", "Dividers between areas"],
  ["border-strong", "border-border-strong", "A splitter, a keycap"],
  ["input", "border-input", "A field's edge: three to one on its surface"],
  ["ring", "border-ring", "Keyboard focus"],
] as const;

export const Colour: Story = {
  render: () => (
    <div>
      <Specimen
        title="Surfaces"
        note="Every value comes from the generated documentation palette."
        className="items-start"
      >
        {SURFACES.map(([name, className, use]) => (
          <figure key={name} className="grid w-40 gap-1">
            <div className={cn("h-12 rounded-md border", className)} />
            <figcaption className="grid">
              <code className="font-mono text-xs">{name}</code>
              <span className="text-xs text-muted-foreground">{use}</span>
            </figcaption>
          </figure>
        ))}
      </Specimen>
      <Specimen
        title="States"
        note="A wash of ink over whatever it sits on, so it shows on every surface. The chosen item also carries a bar: no state rests on a tint alone."
        className="items-start"
      >
        {STATES.map(([name, className, use]) => (
          <figure key={name} className="grid w-64 gap-1">
            <div className="flex overflow-hidden rounded-md border">
              {UNDER.map(([surface, under]) => (
                <div key={surface} className={cn("flex-1", under)}>
                  <div
                    className={cn(
                      "grid h-12 place-items-center text-xs text-muted-foreground",
                      className,
                    )}
                  >
                    {surface}
                  </div>
                </div>
              ))}
            </div>
            <figcaption className="grid">
              <code className="font-mono text-xs">{name}</code>
              <span className="text-xs text-muted-foreground">{use}</span>
            </figcaption>
          </figure>
        ))}
        <figure className="grid w-40 gap-1">
          <div className="flex h-12 items-center rounded-md bg-secondary p-1">
            <div className="grid h-full flex-1 place-items-center rounded-sm bg-raised text-xs shadow-raised">
              raised
            </div>
            <div className="grid flex-1 place-items-center text-xs text-muted-foreground">
              track
            </div>
          </div>
          <figcaption className="grid">
            <code className="font-mono text-xs">raised</code>
            <span className="text-xs text-muted-foreground">
              The chosen segment, lifted above its track
            </span>
          </figcaption>
        </figure>
      </Specimen>
      <Specimen title="Text" className="items-start">
        {TEXT.map(([name, className, use]) => (
          <figure key={name} className="grid w-40 gap-1">
            <span className={cn("text-md font-medium", className)}>Aa 123</span>
            <figcaption className="grid">
              <code className="font-mono text-xs">{name}</code>
              <span className="text-xs text-muted-foreground">{use}</span>
            </figcaption>
          </figure>
        ))}
      </Specimen>
      <Specimen title="Lines" className="items-start">
        {LINES.map(([name, className, use]) => (
          <figure key={name} className="grid w-40 gap-1">
            <div className={cn("h-8 rounded-md border-2", className)} />
            <figcaption className="grid">
              <code className="font-mono text-xs">{name}</code>
              <span className="text-xs text-muted-foreground">{use}</span>
            </figcaption>
          </figure>
        ))}
      </Specimen>
    </div>
  ),
};

const SIZES = [
  ["text-2xs", "Counters"],
  ["text-xs", "Meta, key hints"],
  ["text-sm", "Labels, secondary text, tooltips"],
  ["text-base", "Body and controls"],
  ["text-md", "The palette's input"],
  ["text-lg", "Dialog and settings titles"],
] as const;

export const Type: Story = {
  render: () => (
    <div>
      <Specimen title="Scale" className="grid justify-items-start gap-2">
        {SIZES.map(([className, use]) => (
          <p key={className} className={className}>
            <code className="mr-3 font-mono text-xs text-faint">
              {className}
            </code>
            Cadrumo turns local records into checked filing artifacts.
            <span className="ml-3 text-xs text-muted-foreground">{use}</span>
          </p>
        ))}
      </Specimen>
      <Specimen title="Families" className="grid justify-items-start gap-2">
        <p className="font-sans text-md">Hanken Grotesk for the interface</p>
        <p className="font-serif text-lg">Newsreader for titles</p>
        <p className="font-mono text-base">JetBrains Mono for terminals</p>
      </Specimen>
    </div>
  ),
};

const RADII = [
  "rounded-xs",
  "rounded-sm",
  "rounded-md",
  "rounded-lg",
  "rounded-xl",
  "rounded-2xl",
  "rounded-full",
] as const;

const CONTROLS = [
  ["h-control-xs", "An icon button in a header"],
  ["h-control-sm", "A control in a toolbar"],
  ["h-control-md", "A control in a dialog or header row"],
  ["h-control-lg", "A rail button or a tab row"],
] as const;

export const Shape: Story = {
  render: () => (
    <div>
      <Specimen title="Radii">
        {RADII.map((className) => (
          <figure key={className} className="grid gap-1">
            <div
              className={cn(
                "size-control-lg border border-border-strong bg-card",
                className,
              )}
            />
            <code className="font-mono text-xs">
              {className.replace("rounded-", "")}
            </code>
          </figure>
        ))}
      </Specimen>
      <Specimen title="Density" note="The height of a control.">
        {CONTROLS.map(([className, use]) => (
          <figure key={className} className="grid gap-1">
            <div
              className={cn(
                "flex w-40 items-center rounded-md border border-border-strong bg-card px-2 text-sm",
                className,
              )}
            >
              {className.replace("h-control-", "")}
            </div>
            <span className="text-xs text-muted-foreground">{use}</span>
          </figure>
        ))}
      </Specimen>
      <Specimen title="Elevation">
        <div className="rounded-md bg-card px-4 py-3 text-sm shadow-raised">
          raised: a chosen segment
        </div>
        <div className="rounded-xl bg-card px-4 py-3 text-sm shadow-overlay">
          overlay: dialogs, popovers, menus
        </div>
      </Specimen>
    </div>
  ),
};

export const Icons: Story = {
  render: () => (
    <Specimen
      title="Icons"
      note="One library, read through one registry, in four sizes."
    >
      {ICON_NAMES.map((name) => (
        <figure key={name} className="grid w-24 justify-items-center gap-1">
          <span className="flex items-end gap-1.5 text-muted-foreground">
            <Icon name={name} size="xs" />
            <Icon name={name} size="sm" />
            <Icon name={name} size="md" />
            <Icon name={name} size="lg" />
          </span>
          <code className="font-mono text-xs">{name}</code>
        </figure>
      ))}
    </Specimen>
  ),
};
