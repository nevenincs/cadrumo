//! Retained AppKit status item; constructed only by the inactive host's run path.
#![allow(unsafe_code)]

use super::{Action, Queue, Row};
use objc2::rc::Retained;
use objc2::{DefinedClass, MainThreadOnly, define_class, msg_send, sel};
use objc2_app_kit::{NSMenu, NSMenuItem, NSStatusBar, NSStatusItem, NSVariableStatusItemLength};
use objc2_foundation::{MainThreadMarker, NSObject, NSObjectProtocol, NSString};
use std::io;

pub struct StatusMenu {
    bar: Retained<NSStatusBar>,
    item: Retained<NSStatusItem>,
    target: Retained<Target>,
    rows: Vec<Row>,
    mtm: MainThreadMarker,
}

impl StatusMenu {
    pub fn new(mtm: MainThreadMarker) -> io::Result<Self> {
        let bar = NSStatusBar::systemStatusBar();
        let item = bar.statusItemWithLength(NSVariableStatusItemLength);
        let Some(button) = item.button(mtm) else {
            bar.removeStatusItem(&item);
            return Err(io::Error::other("manager_status_item_unavailable"));
        };
        button.setTitle(&NSString::from_str(crate::identity::MANAGER_NAME));
        Ok(Self {
            bar,
            item,
            target: Target::new(mtm),
            rows: Vec::new(),
            mtm,
        })
    }

    pub fn take_action(&self) -> Option<Action> {
        self.target.ivars().pending.take()
    }
    pub fn take_rejection(&self) -> bool {
        self.target.ivars().rejected.replace(false)
    }

    pub fn update(&mut self, rows: Vec<Row>, accepting: bool) {
        self.target.ivars().admit(accepting);
        if rows == self.rows {
            return;
        }
        let menu = NSMenu::new(self.mtm);
        menu.setAutoenablesItems(false);
        for row in &rows {
            let item = self.menu_item(
                &row.label,
                row.enabled,
                row.checked,
                if row.warning.is_some() {
                    None
                } else {
                    row.action
                },
            );
            if let Some(warning) = &row.warning {
                let confirmation = NSMenu::new(self.mtm);
                confirmation.setAutoenablesItems(false);
                confirmation.addItem(&self.menu_item(warning, false, false, None));
                confirmation.addItem(&self.menu_item(&row.label, row.enabled, false, row.action));
                item.setSubmenu(Some(&confirmation));
            }
            menu.addItem(&item);
        }
        self.item.setMenu(Some(&menu));
        self.rows = rows;
    }

    fn menu_item(
        &self,
        title: &str,
        enabled: bool,
        checked: bool,
        action: Option<Action>,
    ) -> Retained<NSMenuItem> {
        let item = NSMenuItem::new(self.mtm);
        item.setTitle(&NSString::from_str(title));
        item.setEnabled(enabled);
        item.setState(if checked { 1 } else { 0 });
        if let Some(action) = action {
            item.setTag(match action {
                Action::Restart => 1,
                Action::Retry => 2,
                Action::OpenApplication => 3,
                Action::OpenLogs => 4,
                Action::SignIn => 5,
                Action::Quit => 6,
            });
            // SAFETY: The retained target outlives the menu. The selector has
            // exactly AppKit's sender signature and touches only its bounded queue.
            unsafe {
                item.setTarget(Some(&self.target));
                item.setAction(Some(sel!(selected:)));
            }
        }
        item
    }
}
impl Drop for StatusMenu {
    fn drop(&mut self) {
        self.target.ivars().admit(false);
        self.item.setMenu(None);
        self.bar.removeStatusItem(&self.item);
    }
}

define_class!(
    // SAFETY: NSObject has no extra subclass requirements. All ivars and
    // selection callbacks are confined to AppKit's main thread.
    #[unsafe(super = NSObject)]
    #[thread_kind = MainThreadOnly]
    #[ivars = Queue]
    #[name = "CadrumoManagerStatusMenuTarget"]
    struct Target;
    // SAFETY: NSObjectProtocol imposes no additional requirements.
    unsafe impl NSObjectProtocol for Target {}
    impl Target {
        #[unsafe(method(selected:))]
        fn selected(&self, sender: &NSMenuItem) {
            let action = match sender.tag() {
                1 => Action::Restart, 2 => Action::Retry, 3 => Action::OpenApplication,
                4 => Action::OpenLogs, 5 => Action::SignIn, 6 => Action::Quit,
                _ => { self.ivars().rejected.set(true); return; }
            };
            self.ivars().push(action);
        }
    }
);
impl Target {
    fn new(mtm: MainThreadMarker) -> Retained<Self> {
        let this = Self::alloc(mtm).set_ivars(Queue::default());
        // SAFETY: NSObject init has this signature and no additional invariants.
        unsafe { msg_send![super(this), init] }
    }
}
