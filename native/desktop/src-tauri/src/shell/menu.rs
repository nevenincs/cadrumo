//! Native context menus the shell describes and the host shows.
//!
//! The shell sends the items; the host validates them, namespaces their ids
//! for this popup, shows the menu and returns the chosen item's own id, or
//! nothing when the menu closed without a choice. One popup is open at a
//! time.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::Deserialize;
use std::{
    collections::BTreeSet,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, AtomicU64, Ordering},
    },
};
use tauri::LogicalPosition;

const PREFIX: &str = "ctx";
const ITEMS: usize = 64;
const ID_CHARS: usize = 128;
const LABEL_CHARS: usize = 256;
const SHORTCUT_CHARS: usize = 64;
/// Bound on a logical coordinate; anything further is off every display.
const COORDINATE: f64 = 1.0e6;

fn refused() -> ApplicationError {
    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview)
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SeparatorRequest {
    separator: bool,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ActionRequest {
    id: String,
    label: String,
    enabled: bool,
    #[serde(default)]
    shortcut: Option<String>,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum ItemRequest {
    Separator(SeparatorRequest),
    Action(ActionRequest),
}

#[derive(Debug, Eq, PartialEq)]
pub enum Entry {
    Separator,
    Action {
        /// The id the native menu reports: `ctx/<popup>/<item id>`.
        native: String,
        /// The label as the native menu reads it.
        label: String,
        enabled: bool,
    },
}

/// One validated popup: its sequence number and entries in display order.
#[derive(Debug)]
pub struct Menu {
    sequence: u64,
    entries: Vec<Entry>,
}

fn text(value: &str, limit: usize) -> bool {
    let count = value.chars().count();
    (1..=limit).contains(&count) && !value.chars().any(char::is_control)
}

/// Native menus read `&` as a mnemonic marker and `&&` as a literal
/// ampersand on every backend. Labels are shown literally, so every `&` is
/// doubled. A tab starts the right-aligned accelerator column, where the
/// display-only shortcut goes; no accelerator is registered.
fn native_label(label: &str, shortcut: Option<&str>) -> String {
    let escaped = label.replace('&', "&&");
    match shortcut {
        Some(shortcut) => format!("{escaped}\t{}", shortcut.replace('&', "&&")),
        None => escaped,
    }
}

impl Menu {
    pub fn new(sequence: u64, items: Vec<serde_json::Value>) -> Result<Self> {
        if items.is_empty() || items.len() > ITEMS {
            return Err(refused());
        }
        let mut seen = BTreeSet::new();
        let mut entries = Vec::with_capacity(items.len());
        for item in items {
            let item: ItemRequest =
                serde_json::from_value(item).map_err(|e| refused().caused_by(e))?;
            entries.push(match item {
                ItemRequest::Separator(SeparatorRequest { separator: true }) => Entry::Separator,
                ItemRequest::Separator(_) => return Err(refused()),
                ItemRequest::Action(action) => {
                    if !text(&action.id, ID_CHARS)
                        || !text(&action.label, LABEL_CHARS)
                        || action
                            .shortcut
                            .as_deref()
                            .is_some_and(|shortcut| !text(shortcut, SHORTCUT_CHARS))
                        || !seen.insert(action.id.clone())
                    {
                        return Err(refused());
                    }
                    Entry::Action {
                        native: format!("{PREFIX}/{sequence}/{}", action.id),
                        label: native_label(&action.label, action.shortcut.as_deref()),
                        enabled: action.enabled,
                    }
                }
            });
        }
        if seen.is_empty() {
            return Err(refused());
        }
        Ok(Self { sequence, entries })
    }

    pub fn entries(&self) -> &[Entry] {
        &self.entries
    }

    /// The shell's id for a native menu event, when it names an enabled item
    /// of this popup. Events of another popup or another menu yield nothing.
    pub fn chosen(&self, native: &str) -> Option<String> {
        let id = native
            .strip_prefix(PREFIX)?
            .strip_prefix('/')?
            .strip_prefix(self.sequence.to_string().as_str())?
            .strip_prefix('/')?;
        self.entries.iter().find_map(|entry| match entry {
            Entry::Action {
                native: candidate,
                enabled: true,
                ..
            } if candidate == native => Some(id.to_owned()),
            _ => None,
        })
    }
}

/// Both coordinates, or neither for a menu at the cursor.
pub fn position(x: Option<f64>, y: Option<f64>) -> Result<Option<LogicalPosition<f64>>> {
    match (x, y) {
        (None, None) => Ok(None),
        (Some(x), Some(y))
            if [x, y]
                .iter()
                .all(|v| v.is_finite() && v.abs() <= COORDINATE) =>
        {
            Ok(Some(LogicalPosition::new(x, y)))
        }
        _ => Err(refused()),
    }
}

/// The popup state shared by the command and the host's menu events.
#[derive(Default)]
pub struct Popups {
    open: AtomicBool,
    sequence: AtomicU64,
    /// The last context-menu event since the open popup was shown.
    event: Mutex<Option<String>>,
}

/// Holds the single popup slot until dropped.
pub struct Claim(Arc<Popups>);

impl Drop for Claim {
    fn drop(&mut self) {
        self.0.open.store(false, Ordering::Release);
    }
}

impl Popups {
    /// Takes the popup slot, refusing while another popup is open.
    pub fn claim(self: &Arc<Self>) -> Result<Claim> {
        self.open
            .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .map_err(|_| {
                ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Webview)
            })?;
        Ok(Claim(self.clone()))
    }

    pub fn next_sequence(&self) -> u64 {
        self.sequence.fetch_add(1, Ordering::Relaxed)
    }

    /// Records a native menu event that belongs to a context menu.
    pub fn record(&self, native: &str) {
        if native.starts_with(PREFIX) && native[PREFIX.len()..].starts_with('/') {
            *self.slot() = Some(native.to_owned());
        }
    }

    fn take(&self) -> Option<String> {
        self.slot().take()
    }

    fn slot(&self) -> std::sync::MutexGuard<'_, Option<String>> {
        self.event.lock().unwrap_or_else(|e| e.into_inner())
    }
}

/// Shows `menu` on `window` and returns the chosen item, blocking the calling
/// thread until the menu has closed and every event it raised is recorded.
///
/// On Windows the popup runs a modal loop on the main thread and returns only
/// when the menu closes; a chosen item's event is queued to the event loop
/// before that. The sentinel queued afterwards on the same loop therefore
/// runs after the event was recorded, so a dismissal reads as `None`.
#[cfg(windows)]
pub fn show<R: tauri::Runtime>(
    window: &tauri::Window<R>,
    popups: &Popups,
    menu: &Menu,
    position: Option<LogicalPosition<f64>>,
) -> Result<Option<String>> {
    use tauri::menu::{IsMenuItem, MenuItem, PredefinedMenuItem};
    let failed = || ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview);
    let popup = tauri::menu::Menu::new(window).map_err(|e| failed().caused_by(e))?;
    // The items stay alive until the popup has closed.
    let mut items: Vec<Box<dyn IsMenuItem<R>>> = Vec::with_capacity(menu.entries().len());
    for entry in menu.entries() {
        let item: Box<dyn IsMenuItem<R>> = match entry {
            Entry::Separator => {
                Box::new(PredefinedMenuItem::separator(window).map_err(|e| failed().caused_by(e))?)
            }
            Entry::Action {
                native,
                label,
                enabled,
            } => Box::new(
                MenuItem::with_id(window, native.as_str(), label, *enabled, None::<&str>)
                    .map_err(|e| failed().caused_by(e))?,
            ),
        };
        popup
            .append(item.as_ref())
            .map_err(|e| failed().caused_by(e))?;
        items.push(item);
    }
    popups.take();
    match position {
        Some(position) => window.popup_menu_at(&popup, position),
        None => window.popup_menu(&popup),
    }
    .map_err(|e| failed().caused_by(e))?;
    let (settled, sentinel) = std::sync::mpsc::channel();
    window
        .run_on_main_thread(move || {
            let _ = settled.send(());
        })
        .map_err(|e| failed().caused_by(e))?;
    sentinel.recv().map_err(|e| failed().caused_by(e))?;
    Ok(popups.take().and_then(|event| menu.chosen(&event)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn action(id: &str, label: &str) -> serde_json::Value {
        json!({"id": id, "label": label, "enabled": true})
    }

    #[test]
    fn item_ids_are_namespaced_by_popup_and_mapped_back() {
        let menu = Menu::new(
            7,
            vec![
                action("copy", "Copy"),
                json!({"separator": true}),
                json!({"id": "paste", "label": "Paste", "enabled": false, "shortcut": "Ctrl+Shift+V"}),
                action("docs/home", "Docs home"),
            ],
        )
        .unwrap();
        assert_eq!(
            menu.entries(),
            &[
                Entry::Action {
                    native: "ctx/7/copy".into(),
                    label: "Copy".into(),
                    enabled: true
                },
                Entry::Separator,
                Entry::Action {
                    native: "ctx/7/paste".into(),
                    label: "Paste\tCtrl+Shift+V".into(),
                    enabled: false
                },
                Entry::Action {
                    native: "ctx/7/docs/home".into(),
                    label: "Docs home".into(),
                    enabled: true
                },
            ]
        );
        assert_eq!(menu.chosen("ctx/7/copy").as_deref(), Some("copy"));
        assert_eq!(menu.chosen("ctx/7/docs/home").as_deref(), Some("docs/home"));
        for foreign in [
            "ctx/7/paste",
            "ctx/6/copy",
            "ctx/70/copy",
            "ctx/7/cut",
            "ctx/7/",
            "ctx/7copy",
            "copy",
            "menu/7/copy",
            "",
        ] {
            assert_eq!(menu.chosen(foreign), None, "{foreign}");
        }
    }

    #[test]
    fn ampersands_are_shown_literally() {
        let menu = Menu::new(
            0,
            vec![json!({"id": "a", "label": "Copy && paste & go", "enabled": true, "shortcut": "Ctrl+&"})],
        )
        .unwrap();
        assert_eq!(
            menu.entries(),
            &[Entry::Action {
                native: "ctx/0/a".into(),
                label: "Copy &&&& paste && go\tCtrl+&&".into(),
                enabled: true
            }]
        );
    }

    #[test]
    fn malformed_menus_are_refused() {
        let long = |n: usize| "x".repeat(n);
        let cases: Vec<Vec<serde_json::Value>> = vec![
            vec![],
            vec![json!({"separator": true})],
            vec![json!({"separator": false}), action("a", "A")],
            vec![json!({"separator": true, "id": "a"}), action("b", "B")],
            vec![action("a", "A"), action("a", "Again")],
            vec![action("", "A")],
            vec![action("a", "")],
            vec![action("a\n", "A")],
            vec![action("a", "Tab\there")],
            vec![action(&long(ID_CHARS + 1), "A")],
            vec![action("a", &long(LABEL_CHARS + 1))],
            vec![json!({"id": "a", "label": "A", "enabled": true, "shortcut": ""})],
            vec![
                json!({"id": "a", "label": "A", "enabled": true, "shortcut": long(SHORTCUT_CHARS + 1)}),
            ],
            vec![json!({"id": "a", "label": "A"})],
            vec![json!({"id": "a", "label": "A", "enabled": "yes"})],
            vec![json!({"id": "a", "label": "A", "enabled": true, "icon": "x"})],
            vec![json!("copy")],
            (0..=ITEMS).map(|i| action(&i.to_string(), "A")).collect(),
        ];
        for items in cases {
            let shown = format!("{items:?}");
            assert_eq!(
                Menu::new(0, items).unwrap_err().code,
                ErrorCode::InvalidArguments,
                "{shown}"
            );
        }
        let widest = Menu::new(0, vec![action(&long(ID_CHARS), &long(LABEL_CHARS))]);
        assert!(widest.is_ok());
        assert!(Menu::new(0, (0..ITEMS).map(|i| action(&i.to_string(), "A")).collect()).is_ok());
    }

    #[test]
    fn positions_take_both_coordinates_or_neither() {
        assert_eq!(position(None, None).unwrap(), None);
        assert_eq!(
            position(Some(12.5), Some(-3.0)).unwrap(),
            Some(LogicalPosition::new(12.5, -3.0))
        );
        for (x, y) in [
            (Some(1.0), None),
            (None, Some(1.0)),
            (Some(f64::NAN), Some(1.0)),
            (Some(1.0), Some(f64::INFINITY)),
            (Some(COORDINATE * 2.0), Some(0.0)),
        ] {
            assert_eq!(
                position(x, y).unwrap_err().code,
                ErrorCode::InvalidArguments
            );
        }
    }

    #[test]
    fn a_second_popup_is_refused_while_one_is_open() {
        let popups = Arc::new(Popups::default());
        let first = popups.claim().unwrap();
        let refused = popups.claim().err().unwrap();
        assert_eq!(refused.code, ErrorCode::SessionUnavailable);
        assert_eq!(refused.operation, Operation::Webview);
        drop(first);
        let again = popups.claim().unwrap();
        drop(again);
        assert_ne!(popups.next_sequence(), popups.next_sequence());
    }

    #[test]
    fn only_context_menu_events_are_recorded() {
        let popups = Popups::default();
        popups.record("window/quit");
        popups.record("ctxmenu/1/a");
        assert_eq!(popups.take(), None);
        popups.record("ctx/3/copy");
        assert_eq!(popups.take().as_deref(), Some("ctx/3/copy"));
        assert_eq!(popups.take(), None);
    }
}
