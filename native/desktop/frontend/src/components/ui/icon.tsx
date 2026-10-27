import * as React from "react";
import {
  Archive,
  ArchiveRestore,
  ArrowDown,
  ArrowDownLeft,
  ArrowDownToLine,
  ArrowLeftRight,
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  Ban,
  BookA,
  BookOpen,
  Bookmark,
  Bot,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  ChevronUp,
  Circle,
  CircleCheck,
  CircleDashed,
  CircleOff,
  CirclePause,
  CirclePlay,
  CircleUser,
  ClipboardPaste,
  Clock,
  Columns2,
  Columns3,
  Copy,
  CopyCheck,
  Download,
  Ellipsis,
  Eraser,
  ExternalLink,
  Eye,
  EyeOff,
  FileArchive,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Globe,
  House,
  IdCard,
  Image,
  Info,
  Keyboard,
  KeyRound,
  Landmark,
  Link,
  ListChecks,
  ListTree,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  Logs,
  Mail,
  MapPin,
  Maximize2,
  Merge,
  Minimize2,
  NotebookTabs,
  PackageOpen,
  PanelsTopLeft,
  Paperclip,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  RotateCcw,
  Rows2,
  Rows3,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Smartphone,
  Split,
  Square,
  SquareDashed,
  SquareTerminal,
  Trash2,
  TriangleAlert,
  Unlink2,
  Unplug,
  Upload,
  User,
  UserPlus,
  Users,
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
  agent: Bot,
  alert: TriangleAlert,
  archive: Archive,
  arrow: ArrowRight,
  attach: Paperclip,
  back: ChevronLeft,
  book: BookOpen,
  bookmark: Bookmark,
  calendar: CalendarDays,
  canvas: SquareDashed,
  check: CircleCheck,
  chevronDown: ChevronDown,
  chevronUp: ChevronUp,
  clock: Clock,
  close: X,
  collapseAll: ChevronsDownUp,
  columns: Columns3,
  console: SquareTerminal,
  copy: Copy,
  copyAll: CopyCheck,
  density: Rows3,
  device: Smartphone,
  directionIn: ArrowDownLeft,
  directionOut: ArrowUpRight,
  download: Download,
  downloadAll: PackageOpen,
  edit: Pencil,
  erase: Eraser,
  expandAll: ChevronsUpDown,
  external: ExternalLink,
  eye: Eye,
  eyeOff: EyeOff,
  fileArchive: FileArchive,
  fillDown: ArrowDownToLine,
  filter: SlidersHorizontal,
  folder: FolderOpen,
  forward: ChevronRight,
  globe: Globe,
  group: ListTree,
  home: House,
  idCard: IdCard,
  image: Image,
  info: Info,
  key: KeyRound,
  ledger: NotebookTabs,
  link: Link,
  keyboard: Keyboard,
  loader: LoaderCircle,
  lock: LockKeyhole,
  logs: Logs,
  mail: Mail,
  maximize: Maximize2,
  merge: Merge,
  more: Ellipsis,
  noRate: CircleOff,
  office: Landmark,
  page: FileText,
  paste: ClipboardPaste,
  pause: CirclePause,
  pending: Circle,
  person: User,
  phone: Phone,
  place: MapPin,
  play: CirclePlay,
  plus: Plus,
  python: PythonMark,
  refused: Ban,
  reset: RotateCcw,
  restore: Minimize2,
  search: Search,
  selectAll: ListChecks,
  send: ArrowUp,
  settings: Settings,
  sheet: FileSpreadsheet,
  shield: ShieldCheck,
  signOut: LogOut,
  sortAsc: ArrowUp,
  sortDesc: ArrowDown,
  split: Split,
  splitColumn: Rows2,
  splitRow: Columns2,
  stop: Square,
  swap: ArrowLeftRight,
  sync: RefreshCw,
  term: BookA,
  tick: Check,
  trash: Trash2,
  tui: PanelsTopLeft,
  unarchive: ArchiveRestore,
  unknown: CircleDashed,
  unlinked: Unlink2,
  unplug: Unplug,
  upload: Upload,
  user: CircleUser,
  userAdd: UserPlus,
  users: Users,
  windowMaximize: Square,
  windowRestore: Copy,
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
      data-icon={name}
      aria-hidden="true"
      className={cn("shrink-0", SIZES[size], className)}
      {...props}
    />
  );
}
