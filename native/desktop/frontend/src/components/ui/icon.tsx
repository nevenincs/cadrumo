import * as React from "react";
import {
  ArrowLeftRight,
  ArrowRight,
  BookA,
  BookOpen,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleCheck,
  CircleUser,
  ClipboardPaste,
  Clock,
  Columns2,
  Copy,
  Eye,
  EyeOff,
  FileText,
  Info,
  Landmark,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  Logs,
  Maximize2,
  Minimize2,
  PanelsTopLeft,
  RotateCcw,
  Rows2,
  Search,
  Settings,
  SquareTerminal,
  TriangleAlert,
  Unplug,
  X,
  ZoomIn,
  ZoomOut,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/components/ui/cn";

// The Python mark has no counterpart in the library, so it is drawn here, on
// the library's own terms: stroked, round-capped, in the current colour.
function PythonMark(props: React.ComponentProps<"svg">) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M10 2.8c-3 0-3.2 1.3-3.2 2.4v1.7H10v.6H5.4c-1.4 0-2.6 1-2.6 3.2s1.1 3.2 2.4 3.2h1.3v-1.8c0-1.4 1.2-2.6 2.6-2.6h3.1c1.2 0 2.1-1 2.1-2.2V5.2c0-1.2-1-2.4-3.2-2.4z" />
      <path d="M10 17.2c3 0 3.2-1.3 3.2-2.4v-1.7H10v-.6h4.6c1.4 0 2.6-1 2.6-3.2s-1.1-3.2-2.4-3.2h-1.3v1.8" />
      <circle cx="8.4" cy="4.8" r=".5" fill="currentColor" />
      <circle cx="11.6" cy="15.2" r=".5" fill="currentColor" />
    </svg>
  );
}

/**
 * The shell's icons, by the name the shell uses for them. Every icon comes
 * from one library, bundled as inline SVG; this is the only module that
 * imports it, so a name maps to one glyph everywhere.
 */
const ICONS = {
  alert: TriangleAlert,
  arrow: ArrowRight,
  back: ChevronLeft,
  book: BookOpen,
  calendar: CalendarDays,
  check: CircleCheck,
  chevronDown: ChevronDown,
  chevronUp: ChevronUp,
  clock: Clock,
  close: X,
  console: SquareTerminal,
  copy: Copy,
  eye: Eye,
  eyeOff: EyeOff,
  forward: ChevronRight,
  info: Info,
  loader: LoaderCircle,
  lock: LockKeyhole,
  logs: Logs,
  maximize: Maximize2,
  office: Landmark,
  page: FileText,
  paste: ClipboardPaste,
  python: PythonMark,
  reset: RotateCcw,
  restore: Minimize2,
  search: Search,
  settings: Settings,
  signOut: LogOut,
  splitColumn: Rows2,
  splitRow: Columns2,
  swap: ArrowLeftRight,
  term: BookA,
  tui: PanelsTopLeft,
  unplug: Unplug,
  user: CircleUser,
  zoomIn: ZoomIn,
  zoomOut: ZoomOut,
} satisfies Record<string, LucideIcon | typeof PythonMark>;

export type IconName = keyof typeof ICONS;
export type IconSize = "xs" | "sm" | "md" | "lg";

/** Every icon name, for the catalogue. */
export const ICON_NAMES = Object.keys(ICONS) as IconName[];

const SIZES: Record<IconSize, string> = {
  xs: "size-icon-xs",
  sm: "size-icon-sm",
  md: "size-icon-md",
  lg: "size-icon-lg",
};

/** Decorative by default: the control or text beside an icon names it. */
export function Icon({
  name,
  size = "sm",
  className,
  ...props
}: Omit<React.ComponentProps<"svg">, "ref" | "name"> & {
  name: IconName;
  size?: IconSize;
}) {
  const Glyph = ICONS[name];
  return (
    <Glyph
      data-slot="icon"
      aria-hidden="true"
      className={cn("shrink-0", SIZES[size], className)}
      {...props}
    />
  );
}
