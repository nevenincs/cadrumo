//! StatusNotifier item with a bounded action queue and explicit interruption submenus.
use crate::{identity, strings::Strings};
use std::{
    collections::HashMap,
    io,
    sync::{
        Arc, Mutex,
        mpsc::{self, Receiver, SyncSender},
    },
    time::Duration,
};
use zbus::{
    blocking::{Connection, Proxy, connection::Builder},
    zvariant::{OwnedObjectPath, OwnedValue, Value},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    OpenApplication,
    OpenLogs,
    ToggleSignIn,
    Restart,
    Retry,
    Quit,
}

struct State {
    status: String,
    sign_in: bool,
}
struct Item {
    state: Arc<Mutex<State>>,
    actions: SyncSender<Action>,
}

#[zbus::interface(name = "org.kde.StatusNotifierItem")]
impl Item {
    #[zbus(property)]
    fn category(&self) -> &str {
        "SystemServices"
    }
    #[zbus(property)]
    fn id(&self) -> &str {
        identity::MANAGER_ID
    }
    #[zbus(property)]
    fn title(&self) -> &str {
        identity::MANAGER_NAME
    }
    #[zbus(property)]
    fn status(&self) -> String {
        self.state
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .status
            .clone()
    }
    #[zbus(property)]
    fn icon_name(&self) -> &str {
        identity::APPLICATION_ID
    }
    #[zbus(property)]
    fn item_is_menu(&self) -> bool {
        true
    }
    #[zbus(property)]
    fn menu(&self) -> OwnedObjectPath {
        OwnedObjectPath::try_from("/MenuBar").expect("constant object path")
    }
    fn activate(&self, _x: i32, _y: i32) {
        let _ = self.actions.try_send(Action::OpenApplication);
    }
    fn secondary_activate(&self, _x: i32, _y: i32) {
        let _ = self.actions.try_send(Action::OpenApplication);
    }
    fn context_menu(&self, _x: i32, _y: i32) {}
    fn scroll(&self, _delta: i32, _orientation: &str) {}
}

type Properties = HashMap<String, OwnedValue>;
type Layout = (i32, Properties, Vec<Value<'static>>);
struct Menu {
    state: Arc<Mutex<State>>,
    strings: Strings,
    actions: SyncSender<Action>,
}

impl Menu {
    fn row(&self, id: i32, label: &str, enabled: bool, children: Vec<Value<'static>>) -> Layout {
        let mut properties = HashMap::from([
            (
                "label".into(),
                OwnedValue::from(zbus::zvariant::Str::from(label.to_owned())),
            ),
            ("enabled".into(), OwnedValue::from(enabled)),
            ("visible".into(), OwnedValue::from(true)),
        ]);
        if matches!(id, 0 | 4 | 5) {
            properties.insert(
                "children-display".into(),
                OwnedValue::from(zbus::zvariant::Str::from("submenu")),
            );
        }
        if id == 3 {
            properties.insert(
                "toggle-type".into(),
                OwnedValue::from(zbus::zvariant::Str::from("checkmark")),
            );
            let state = self.state.lock().unwrap_or_else(|error| error.into_inner());
            properties.insert(
                "toggle-state".into(),
                OwnedValue::from(i32::from(state.sign_in)),
            );
        }
        (id, properties, children)
    }
    fn layout(&self, id: i32) -> Option<Layout> {
        self.layout_depth(id, -1, &[])
    }
    fn layout_depth(&self, id: i32, depth: i32, names: &[String]) -> Option<Layout> {
        let unavailable = self
            .state
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .status
            == "NeedsAttention";
        let (label, enabled) = match id {
            0 => (identity::MANAGER_NAME, true),
            1 => (self.strings.get("open_application"), true),
            2 => (self.strings.get("open_logs"), true),
            3 => (self.strings.get("start_at_sign_in"), true),
            4 | 41 => (self.strings.get("restart"), true),
            5 | 51 => (self.strings.get("quit"), true),
            6 => (self.strings.get("retry"), true),
            40 => (self.strings.get("restart_warning"), false),
            50 => (self.strings.get("quit_warning"), false),
            _ => return None,
        };
        let child_ids = match id {
            0 => vec![1, 2, 3, if unavailable { 6 } else { 4 }, 5],
            4 => vec![40, 41],
            5 => vec![50, 51],
            _ => vec![],
        };
        let children = if depth == 0 {
            vec![]
        } else {
            child_ids
                .into_iter()
                .filter_map(|id| {
                    self.layout_depth(id, if depth < 0 { -1 } else { depth - 1 }, names)
                })
                .map(Value::new)
                .collect()
        };
        let (id, mut properties, children) = self.row(id, label, enabled, children);
        if !names.is_empty() {
            properties.retain(|key, _| names.contains(key));
        }
        Some((id, properties, children))
    }
}

#[zbus::interface(name = "com.canonical.dbusmenu")]
impl Menu {
    #[zbus(property)]
    fn version(&self) -> u32 {
        4
    }
    #[zbus(property)]
    fn text_direction(&self) -> &str {
        "ltr"
    }
    #[zbus(property)]
    fn status(&self) -> &str {
        "normal"
    }
    fn get_layout(
        &self,
        parent_id: i32,
        recursion_depth: i32,
        property_names: Vec<String>,
    ) -> zbus::fdo::Result<(u32, Layout)> {
        if recursion_depth < -1 {
            return Err(zbus::fdo::Error::InvalidArgs(
                "invalid recursion depth".into(),
            ));
        }
        self.layout_depth(parent_id, recursion_depth, &property_names)
            .map(|layout| (1, layout))
            .ok_or_else(|| zbus::fdo::Error::InvalidArgs("unknown menu item".into()))
    }
    fn get_group_properties(
        &self,
        ids: Vec<i32>,
        property_names: Vec<String>,
    ) -> Vec<(i32, Properties)> {
        ids.into_iter()
            .take(32)
            .filter_map(|id| self.layout(id))
            .map(|(id, mut properties, _)| {
                if !property_names.is_empty() {
                    properties.retain(|key, _| property_names.contains(key));
                }
                (id, properties)
            })
            .collect()
    }
    fn get_property(&self, id: i32, name: &str) -> zbus::fdo::Result<OwnedValue> {
        self.layout(id)
            .and_then(|(_, mut properties, _)| properties.remove(name))
            .ok_or_else(|| zbus::fdo::Error::InvalidArgs("unknown menu property".into()))
    }
    fn about_to_show(&self, _id: i32) -> bool {
        true
    }
    fn about_to_show_group(&self, ids: Vec<i32>) -> (Vec<i32>, Vec<i32>) {
        ids.into_iter()
            .take(32)
            .partition(|id| self.layout(*id).is_some())
    }
    fn event(&self, id: i32, event_id: &str, _data: Value<'_>, _timestamp: u32) {
        if event_id != "clicked" {
            return;
        }
        let action = match id {
            1 => Action::OpenApplication,
            2 => Action::OpenLogs,
            3 => Action::ToggleSignIn,
            41 => Action::Restart,
            6 => Action::Retry,
            51 => Action::Quit,
            _ => return,
        };
        let _ = self.actions.try_send(action);
    }
    fn event_group(&self, events: Vec<(i32, String, OwnedValue, u32)>) -> Vec<i32> {
        let mut errors = Vec::new();
        for (id, event, data, timestamp) in events.into_iter().take(32) {
            if self.layout(id).is_none() {
                errors.push(id);
            } else {
                self.event(id, &event, data.into(), timestamp);
            }
        }
        errors
    }
}

pub struct Tray {
    connection: Connection,
    state: Arc<Mutex<State>>,
    pub actions: Receiver<Action>,
    watcher: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn destructive_actions_require_the_warning_submenu_confirmation_item() {
        let (send, receive) = mpsc::sync_channel(16);
        let menu = Menu {
            state: Arc::new(Mutex::new(State {
                status: "Active".into(),
                sign_in: true,
            })),
            strings: Strings::current().unwrap(),
            actions: send,
        };
        for id in [4, 5, 40, 50] {
            menu.event(id, "clicked", Value::from(0i32), 0);
        }
        assert!(receive.try_recv().is_err());
        menu.event(41, "clicked", Value::from(0i32), 0);
        assert_eq!(receive.try_recv().unwrap(), Action::Restart);
        menu.event(51, "clicked", Value::from(0i32), 0);
        assert_eq!(receive.try_recv().unwrap(), Action::Quit);
        assert_eq!(menu.layout(4).unwrap().2.len(), 2);
        assert!(menu.layout(99).is_none());
        let (_, properties, children) = menu.layout_depth(4, 0, &["label".into()]).unwrap();
        assert!(children.is_empty());
        assert_eq!(properties.len(), 1);
        assert!(properties.contains_key("label"));
        assert!(menu.get_layout(0, -2, vec![]).is_err());
        menu.event(6, "clicked", Value::from(0i32), 0);
        assert_eq!(receive.try_recv().unwrap(), Action::Retry);
    }
}

impl Tray {
    pub fn connect(sign_in: bool) -> io::Result<Self> {
        let state = Arc::new(Mutex::new(State {
            status: "Active".into(),
            sign_in,
        }));
        let (send, actions) = mpsc::sync_channel(16);
        let connection = Builder::session()
            .map_err(io::Error::other)?
            .method_timeout(Duration::from_secs(1))
            .max_queued(32)
            .serve_at(
                "/StatusNotifierItem",
                Item {
                    state: state.clone(),
                    actions: send.clone(),
                },
            )
            .map_err(io::Error::other)?
            .serve_at(
                "/MenuBar",
                Menu {
                    state: state.clone(),
                    strings: Strings::current()?,
                    actions: send,
                },
            )
            .map_err(io::Error::other)?
            .build()
            .map_err(io::Error::other)?;
        Ok(Self {
            connection,
            state,
            actions,
            watcher: None,
        })
    }

    /// Missing hosts are ordinary: retain the item and retry without changing lifecycle.
    pub fn poll_host(&mut self) -> io::Result<bool> {
        let bus = Proxy::new(
            &self.connection,
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
        )
        .map_err(io::Error::other)?;
        let owner: String = match bus.call("GetNameOwner", &("org.kde.StatusNotifierWatcher",)) {
            Ok(owner) => owner,
            Err(_) => {
                self.watcher = None;
                return Ok(false);
            }
        };
        let watcher = Proxy::new(
            &self.connection,
            owner.as_str(),
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
        )
        .map_err(io::Error::other)?;
        let hosted: bool = watcher
            .get_property("IsStatusNotifierHostRegistered")
            .map_err(io::Error::other)?;
        if !hosted {
            self.watcher = None;
            return Ok(false);
        }
        if self.watcher.as_ref() != Some(&owner) {
            watcher
                .call::<_, _, ()>("RegisterStatusNotifierItem", &("/StatusNotifierItem",))
                .map_err(io::Error::other)?;
            self.watcher = Some(owner.clone());
        }
        Ok(true)
    }

    pub fn update(&self, unavailable: bool, sign_in: bool) -> io::Result<()> {
        let status = if unavailable {
            "NeedsAttention"
        } else {
            "Active"
        };
        let mut state = self.state.lock().unwrap_or_else(|error| error.into_inner());
        let changed = state.status != status;
        state.status = status.into();
        state.sign_in = sign_in;
        drop(state);
        if changed {
            self.connection
                .emit_signal(
                    None::<&str>,
                    "/StatusNotifierItem",
                    "org.kde.StatusNotifierItem",
                    "NewStatus",
                    &(status,),
                )
                .map_err(io::Error::other)?;
        }
        self.connection
            .emit_signal(
                None::<&str>,
                "/MenuBar",
                "com.canonical.dbusmenu",
                "LayoutUpdated",
                &(1u32, 0i32),
            )
            .map_err(io::Error::other)
    }
}
