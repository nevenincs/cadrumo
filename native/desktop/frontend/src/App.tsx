import { useEffect, useRef, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileText,
  FolderOpen,
  Home,
  Layers3,
  ListChecks,
  PanelBottom,
  PanelRight,
  Search,
  ShieldCheck,
  TerminalSquare,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { identity, mark } from "virtual:desktop-content";
import { Documentation } from "./Documentation";
import { TerminalPane } from "./TerminalPane";

type Page = "home" | "workbench" | "docs";
type Panel = "python" | "logs";
const navigation: { id: Page; label: string; icon: LucideIcon }[] = [
  { id: "workbench", label: "Textual workbench", icon: TerminalSquare },
  { id: "home", label: "Welcome", icon: Home },
];

export function App() {
  const [page, setPage] = useState<Page>("workbench");
  const [guide, setGuide] = useState(true);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panel, setPanel] = useState<Panel>("python");
  const [panelHeight, setPanelHeight] = useState(225);
  const [areaHeight, setAreaHeight] = useState(700);
  const [guideWidth, setGuideWidth] = useState(355);
  const [logVisible, setLogVisible] = useState(true);
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const active = navigation.find((item) => item.id === page);
  const maxPanelHeight = Math.max(150, areaHeight - 220);
  const visiblePanelHeight = Math.min(panelHeight, maxPanelHeight);

  useEffect(() => {
    if (!body.current) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setAreaHeight(entry.contentRect.height);
    });
    observer.observe(body.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        search.current?.focus();
        setSearchOpen(true);
      }
      if (event.key === "Escape") setSearchOpen(false);
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  function selectPage(next: Page) {
    setPage(next);
    setSearchOpen(false);
    setQuery("");
  }
  function openConsole(next: Panel) {
    setPanel(next);
    setPanelOpen(true);
  }
  function resize(height: number) {
    setPanelHeight(Math.max(150, Math.min(height, maxPanelHeight)));
  }
  const routes = [
    ...navigation,
    { id: "docs" as const, label: "User documentation", icon: BookOpen },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#home"
          className="brand"
          onClick={(event) => {
            event.preventDefault();
            selectPage("home");
          }}
          aria-label={`${identity.display_name} overview`}
        >
          <img src={mark} alt="" />
          <span>
            {identity.display_name}
            <small>YOUR TAX WORKSPACE</small>
          </span>
        </a>
        <div className="profile-card">
          <span className="profile-avatar">—</span>
          <span>
            No profile connected<small>Local workspace</small>
          </span>
          <ChevronDown size={14} />
        </div>
        <span className="nav-heading">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              aria-label={label}
              className={page === id ? "nav-item selected" : "nav-item"}
              aria-current={page === id ? "page" : undefined}
              onClick={() => selectPage(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {page === id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button
            aria-label="User documentation"
            className={`nav-item ${page === "docs" ? "selected" : ""}`}
            onClick={() => selectPage("docs")}
            aria-current={page === "docs" ? "page" : undefined}
          >
            <BookOpen size={18} />
            <span>User documentation</span>
            <span className="small-arrow">↗</span>
          </button>
          <button
            aria-label="Reading companion"
            className="nav-item"
            onClick={() => {
              setGuide((value) => !value);
            }}
          >
            <CircleHelp size={18} />
            <span>Reading companion</span>
          </button>
          <div className="local-note">
            <ShieldCheck size={16} />
            <span>
              Your work stays yours.
              <small>Review locally. File with AEAT.</small>
            </span>
          </div>
        </div>
      </aside>
      <div className="application">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <strong>{page === "docs" ? "Documentation" : active?.label}</strong>
          </div>
          <div className="global-search">
            <Search size={15} />
            <input
              ref={search}
              value={query}
              onFocus={() => setSearchOpen(true)}
              onChange={(event) => {
                setQuery(event.target.value);
                setSearchOpen(true);
              }}
              placeholder="Go to…"
              aria-label="Search workspace"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  const match = routes.find((item) =>
                    item.label.toLowerCase().includes(query.toLowerCase()),
                  );
                  if (match) selectPage(match.id);
                }
              }}
            />
            <kbd>Ctrl K</kbd>
            {searchOpen && (
              <div className="search-results">
                <div className="search-result-heading">
                  GO TO{" "}
                  <button
                    className="icon-button"
                    aria-label="Close search"
                    onClick={() => setSearchOpen(false)}
                  >
                    <X size={14} />
                  </button>
                </div>
                {routes
                  .filter((item) =>
                    item.label.toLowerCase().includes(query.toLowerCase()),
                  )
                  .map(({ id, label, icon: Icon }) => (
                    <button key={id} onClick={() => selectPage(id)}>
                      <Icon size={16} />
                      {label}
                      <ArrowRight size={14} />
                    </button>
                  ))}
                {!routes.some((item) =>
                  item.label.toLowerCase().includes(query.toLowerCase()),
                ) && <p>No matching pages.</p>}
              </div>
            )}
          </div>
          <span className="preview-badge">Frontend preview</span>
          <div className="toolbar-divider" />
          <button
            className={`icon-button ${guide ? "active" : ""}`}
            aria-label="Toggle documentation pane"
            aria-pressed={guide}
            onClick={() => setGuide((value) => !value)}
          >
            <PanelRight size={18} />
          </button>
          <button
            className={`icon-button ${panelOpen ? "active" : ""}`}
            aria-label="Toggle console panel"
            aria-pressed={panelOpen}
            onClick={() => setPanelOpen((value) => !value)}
          >
            <PanelBottom size={18} />
          </button>
        </header>
        <div className="work-area" ref={body}>
          <div className="upper-workspace">
            <main
              id="workspace"
              className={
                page === "docs"
                  ? "main-content docs-page"
                  : page === "workbench"
                    ? "main-content workbench-page"
                    : "main-content"
              }
            >
              {page === "docs" ? (
                <Documentation />
              ) : page === "home" ? (
                <>
                  <div className="page-heading">
                    <span className="eyebrow">
                      A LITTLE ORDER. A LOT MORE CLARITY.
                    </span>
                    <span className="local-tag">
                      <span /> Local workspace
                    </span>
                  </div>
                  <section className="welcome">
                    <div>
                      <h1>
                        Your records.
                        <br />
                        <span>A clearer picture.</span>
                      </h1>
                      <p>
                        Bring your records together, understand the figures,
                        <br className="wide-only" /> and prepare your next
                        declaration with confidence.
                      </p>
                      <button
                        className="primary-button"
                        onClick={() => selectPage("docs")}
                      >
                        Explore the field guide <ArrowRight size={16} />
                      </button>
                    </div>
                    <div className="paper-illustration" aria-hidden="true">
                      <div className="paper-back" />
                      <div className="paper-front">
                        <span className="paper-caption">
                          FROM RECORDS TO RETURN
                        </span>
                        <div className="paper-rule" />
                        <div className="paper-line long" />
                        <div className="paper-line" />
                        <div className="paper-line short" />
                        <div className="paper-box">
                          <Check size={17} />
                          <span>A little more certain.</span>
                        </div>
                        <div className="paper-stamp">
                          <ShieldCheck size={27} />
                        </div>
                      </div>
                      <span className="paper-spark">✳</span>
                    </div>
                  </section>
                  <section
                    className="connection-card"
                    aria-label="Workspace availability"
                  >
                    <div className="connection-icon">
                      <FolderOpen size={22} />
                    </div>
                    <div>
                      <h2>Your workspace is ready to explore</h2>
                      <p>
                        Connect a profile when the packaged environment is
                        available.
                        <br />
                        For now, explore the interface and read the local guide.
                      </p>
                    </div>
                    <span className="status-label">
                      <span /> Not connected
                    </span>
                  </section>
                  <div className="section-heading">
                    <h2>A clear path through your work</h2>
                    <span>ONE STEP AT A TIME</span>
                  </div>
                  <div className="journey-grid">
                    {[
                      {
                        number: "01",
                        title: "Gather your records",
                        text: "Keep transactions and their supporting documents together.",
                        icon: Layers3,
                        target: "workbench" as const,
                      },
                      {
                        number: "02",
                        title: "Prepare a declaration",
                        text: "Turn reviewed records into a modelo for the right period.",
                        icon: FileText,
                        target: "workbench" as const,
                      },
                      {
                        number: "03",
                        title: "Review, then export",
                        text: "Check your figures before you file through official channels.",
                        icon: ListChecks,
                        target: "docs" as const,
                      },
                    ].map(({ number, title, text, icon: Icon, target }) => (
                      <button
                        className="journey-card"
                        key={number}
                        onClick={() => selectPage(target)}
                      >
                        <div>
                          <Icon size={22} />
                          <span>{number}</span>
                        </div>
                        <h3>{title}</h3>
                        <p>{text}</p>
                        <ArrowRight className="journey-arrow" size={17} />
                      </button>
                    ))}
                  </div>
                  <section className="quick-access">
                    <div>
                      <TerminalSquare size={20} />
                      <div>
                        <h3>A familiar console, close at hand.</h3>
                        <p>
                          Python and the Textual workbench will use your bundled
                          environment.
                        </p>
                      </div>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => openConsole("python")}
                    >
                      Open console <ArrowRight size={15} />
                    </button>
                  </section>
                  <footer className="workspace-footer">
                    <span>
                      Prepare and review in {identity.prose_name}. File through
                      AEAT.
                    </span>
                    <button onClick={() => setGuide(true)}>
                      Understand the workflow <ArrowRight size={13} />
                    </button>
                  </footer>
                </>
              ) : (
                <section
                  className="tui-workspace"
                  aria-label="Textual workspace"
                >
                  <header className="tui-header">
                    <div>
                      <TerminalSquare size={18} />
                      <h1>Textual workbench</h1>
                    </div>
                    <span className="tui-session-state">No active session</span>
                  </header>
                  <div className="tui-availability">
                    <span className="availability-dot" />
                    <div>
                      <strong>The workbench will open here.</strong>
                      <p>
                        The bundled environment is not connected to this
                        preview. Read the guide alongside your work while
                        integration is in progress.
                      </p>
                    </div>
                  </div>
                  <div className="tui-terminal">
                    <TerminalPane mode="tui" />
                  </div>
                  <footer className="tui-footer">
                    <span>
                      Input will be enabled when a session is connected.
                    </span>
                    <button
                      className="text-button"
                      onClick={() => openConsole("python")}
                    >
                      Python console <ArrowRight size={14} />
                    </button>
                  </footer>
                </section>
              )}
            </main>
            {guide && page !== "docs" && (
              <>
                <div
                  className="guide-resize"
                  role="separator"
                  aria-label="Resize documentation pane"
                  aria-orientation="vertical"
                  aria-valuemin={260}
                  aria-valuemax={600}
                  aria-valuenow={guideWidth}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (
                      event.key === "ArrowLeft" ||
                      event.key === "ArrowRight"
                    ) {
                      event.preventDefault();
                      setGuideWidth(
                        Math.max(
                          260,
                          Math.min(
                            600,
                            guideWidth + (event.key === "ArrowLeft" ? 24 : -24),
                          ),
                        ),
                      );
                    }
                  }}
                  onPointerDown={(event) =>
                    event.currentTarget.setPointerCapture(event.pointerId)
                  }
                  onPointerMove={(event) => {
                    if (event.currentTarget.hasPointerCapture(event.pointerId))
                      setGuideWidth(
                        Math.max(
                          260,
                          Math.min(
                            600,
                            (body.current?.getBoundingClientRect().right ?? 0) -
                              event.clientX,
                          ),
                        ),
                      );
                  }}
                  onPointerUp={(event) =>
                    event.currentTarget.releasePointerCapture(event.pointerId)
                  }
                />
                <aside
                  className="guide-pane"
                  style={{
                    flexBasis: guideWidth,
                    width: `min(${guideWidth}px, calc(100vw - 62px))`,
                  }}
                >
                  <Documentation compact onClose={() => setGuide(false)} />
                </aside>
              </>
            )}
          </div>
          {panelOpen && (
            <>
              <div
                className="resize-handle"
                role="separator"
                aria-label="Resize console panel"
                aria-orientation="horizontal"
                aria-valuemin={150}
                aria-valuemax={maxPanelHeight}
                aria-valuenow={visiblePanelHeight}
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                    event.preventDefault();
                    resize(
                      visiblePanelHeight + (event.key === "ArrowUp" ? 24 : -24),
                    );
                  }
                }}
                onPointerDown={(event) => {
                  event.currentTarget.setPointerCapture(event.pointerId);
                }}
                onPointerMove={(event) => {
                  if (event.currentTarget.hasPointerCapture(event.pointerId))
                    resize(
                      (body.current?.getBoundingClientRect().bottom ?? 0) -
                        event.clientY,
                    );
                }}
                onPointerUp={(event) =>
                  event.currentTarget.releasePointerCapture(event.pointerId)
                }
              >
                <span />
              </div>
              <Tabs.Root
                className="bottom-panel"
                value={panel}
                onValueChange={(value) => {
                  if (value === "python" || value === "logs") setPanel(value);
                }}
                style={{ height: visiblePanelHeight }}
              >
                <div className="panel-header">
                  <Tabs.List aria-label="Console views">
                    <Tabs.Trigger value="python">
                      <TerminalSquare size={14} /> Python console
                    </Tabs.Trigger>
                    <Tabs.Trigger value="logs">
                      Logs {logVisible && <span className="log-count">1</span>}
                    </Tabs.Trigger>
                  </Tabs.List>
                  <span className="panel-status">
                    {panel === "logs"
                      ? "This window only"
                      : "Bundled environment · unavailable"}
                  </span>
                  <button
                    className="icon-button"
                    onClick={() => setPanelOpen(false)}
                    aria-label="Close console panel"
                  >
                    <X size={16} />
                  </button>
                </div>
                <Tabs.Content value="python" className="panel-content">
                  <TerminalPane mode="python" />
                </Tabs.Content>
                <Tabs.Content
                  value="logs"
                  className="panel-content log-content"
                >
                  <div className="log-toolbar">
                    <span>Window events</span>
                    <button
                      className="text-button"
                      onClick={() => setLogVisible(false)}
                    >
                      Clear view
                    </button>
                  </div>
                  {logVisible ? (
                    <div className="log-row">
                      <span className="log-level">INFO</span>
                      <code>
                        Frontend opened. Native environment is not connected.
                      </code>
                    </div>
                  ) : (
                    <p className="logs-empty">No events in this view.</p>
                  )}
                </Tabs.Content>
              </Tabs.Root>
            </>
          )}
        </div>
        <footer className="statusbar">
          <span>
            <span className="status-dot" /> No profile connected
          </span>
          <span>
            Documentation available offline{" "}
            <span className="statusbar-separator">/</span>{" "}
            {identity.display_name}
          </span>
        </footer>
      </div>
    </div>
  );
}
