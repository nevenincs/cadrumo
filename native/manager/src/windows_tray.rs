//! Windows notification-area surface for this user's admitted manager.
#![allow(unsafe_code)]

use crate::{
    preferences::Preferences, strings::Strings, supervision::environment::ManagedLocations,
};
use std::{ffi::c_void, io, mem, os::windows::ffi::OsStrExt, path::PathBuf, ptr};

type Handle = *mut c_void;
pub const CALLBACK: u32 = 0x8001;
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    Retry,
    Restart,
    Quit,
}
pub struct Configuration {
    root: PathBuf,
    desktop: Option<PathBuf>,
    preferences: Preferences,
    strings: Strings,
}
impl Configuration {
    pub fn new(locations: &ManagedLocations, preferences: Preferences) -> io::Result<Self> {
        let contract: cadrumo_application::installation::DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?;
        let desktop = contract
            .layout
            .application_images
            .iter()
            .find(|image| image.target == "desktop-host-build")
            .map(|image| {
                if image.placement != "." {
                    return Err(io::Error::from(io::ErrorKind::InvalidData));
                }
                let relative = cadrumo_application::value::RelativePath::new(format!(
                    "{}{}",
                    image.name, contract.layout.entrypoint_suffix
                ))
                .map_err(io::Error::other)?;
                Ok(relative.under(locations.package_root()))
            })
            .transpose()?
            .filter(|path| path.is_file());
        Ok(Self {
            root: locations.storage_root().into(),
            desktop,
            preferences,
            strings: Strings::current()?,
        })
    }
}

#[repr(C)]
struct Guid {
    first: u32,
    second: u16,
    third: u16,
    last: [u8; 8],
}
#[repr(C)]
struct IconData {
    size: u32,
    window: Handle,
    id: u32,
    flags: u32,
    callback: u32,
    icon: Handle,
    tip: [u16; 128],
    state: u32,
    state_mask: u32,
    info: [u16; 256],
    version: u32,
    info_title: [u16; 64],
    info_flags: u32,
    guid: Guid,
    balloon_icon: Handle,
}
#[repr(C)]
#[derive(Default)]
struct Point {
    x: i32,
    y: i32,
}

#[link(name = "shell32")]
unsafe extern "system" {
    fn Shell_NotifyIconW(message: u32, data: *const IconData) -> i32;
    fn ShellExecuteW(
        window: Handle,
        operation: *const u16,
        file: *const u16,
        parameters: *const u16,
        directory: *const u16,
        show: i32,
    ) -> Handle;
}
#[link(name = "user32")]
unsafe extern "system" {
    fn LoadIconW(instance: Handle, resource: *const u16) -> Handle;
    fn RegisterWindowMessageW(name: *const u16) -> u32;
    fn CreatePopupMenu() -> Handle;
    fn AppendMenuW(menu: Handle, flags: u32, id: usize, text: *const u16) -> i32;
    fn DestroyMenu(menu: Handle) -> i32;
    fn TrackPopupMenu(
        menu: Handle,
        flags: u32,
        x: i32,
        y: i32,
        reserved: i32,
        owner: Handle,
        rectangle: *const c_void,
    ) -> u32;
    fn GetCursorPos(point: *mut Point) -> i32;
    fn SetForegroundWindow(window: Handle) -> i32;
    fn PostMessageW(window: Handle, message: u32, wparam: usize, lparam: isize) -> i32;
    fn MessageBoxW(window: Handle, text: *const u16, caption: *const u16, flags: u32) -> i32;
}

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain([0]).collect()
}
fn checked(value: i32) -> io::Result<()> {
    if value == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}
struct Menu(Handle);
impl Drop for Menu {
    fn drop(&mut self) {
        // SAFETY: this is the popup menu owned by this value, destroyed exactly once.
        unsafe {
            DestroyMenu(self.0);
        }
    }
}

pub struct Tray {
    window: Handle,
    configuration: Configuration,
    taskbar_created: u32,
    present: bool,
    status: String,
}
impl Tray {
    pub fn install(window: Handle, configuration: Configuration) -> io::Result<Self> {
        let name = wide("TaskbarCreated");
        // SAFETY: static registered-message name is terminated and live for the call.
        let taskbar_created = unsafe { RegisterWindowMessageW(name.as_ptr()) };
        if taskbar_created == 0 {
            return Err(io::Error::last_os_error());
        }
        let mut tray = Self {
            window,
            configuration,
            taskbar_created,
            present: false,
            status: String::new(),
        };
        tray.update("starting")?;
        Ok(tray)
    }

    fn icon(&self, status: &str) -> IconData {
        // SAFETY: zero is the documented unused state for all scalar/native fields.
        let mut data: IconData = unsafe { mem::zeroed() };
        data.size = mem::size_of::<IconData>() as u32;
        data.window = self.window;
        data.id = 1;
        data.flags = 1 | 2 | 4 | 0x80; // message, icon, tooltip, show tooltip
        data.callback = CALLBACK;
        // SAFETY: predefined shared icon resource; it must not be destroyed by us.
        data.icon = unsafe { LoadIconW(ptr::null_mut(), 32512_usize as *const u16) };
        let tooltip = format!(
            "{}: {}",
            crate::identity::MANAGER_NAME,
            self.configuration.strings.get(status)
        );
        let mut offset = 0;
        for character in tooltip.chars() {
            let mut encoded = [0; 2];
            let units = character.encode_utf16(&mut encoded);
            if offset + units.len() >= data.tip.len() {
                break;
            }
            data.tip[offset..offset + units.len()].copy_from_slice(units);
            offset += units.len();
        }
        data
    }

    pub fn update(&mut self, status: &str) -> io::Result<()> {
        if self.present && self.status == status {
            return Ok(());
        }
        let mut data = self.icon(status);
        // SAFETY: NOTIFYICONDATA has the current ABI size, live strings and our HWND.
        checked(unsafe { Shell_NotifyIconW(if self.present { 1 } else { 0 }, &data) })?;
        self.present = true;
        data.version = 4;
        // SAFETY: sets behavior only for this window's just-added notification icon.
        checked(unsafe { Shell_NotifyIconW(4, &data) })?;
        self.present = true;
        self.status = status.into();
        Ok(())
    }

    pub fn taskbar_recreated(&mut self, message: u32) -> bool {
        if message != self.taskbar_created {
            return false;
        }
        self.present = false;
        true
    }

    pub fn selected(message: isize) -> bool {
        matches!((message as u32) & 0xffff, 0x0205 | 0x007b | 0x0400 | 0x0401)
    }

    pub fn error(&self) {
        let text = wide(self.configuration.strings.get("action_failed"));
        let title = wide(crate::identity::MANAGER_NAME);
        // SAFETY: only authored labels are shown; no diagnostics or secrets enter UI.
        unsafe {
            MessageBoxW(self.window, text.as_ptr(), title.as_ptr(), 0x10);
        }
    }

    fn menu(&self, status: &str) -> io::Result<Menu> {
        // SAFETY: a new popup menu has one scoped owner and is destroyed after tracking.
        let menu = Menu(unsafe { CreatePopupMenu() });
        if menu.0.is_null() {
            return Err(io::Error::last_os_error());
        }
        let options = [
            (0, status),
            (
                if status == "unavailable" { 6 } else { 1 },
                if status == "unavailable" {
                    "retry"
                } else {
                    "restart"
                },
            ),
            (2, "open_application"),
            (3, "open_logs"),
            (4, "start_at_sign_in"),
            (5, "quit"),
        ];
        for (id, key) in options {
            let label = wide(self.configuration.strings.get(key));
            let flags = if id == 0 || (id == 2 && self.configuration.desktop.is_none()) {
                2
            } else if id == 4 && self.configuration.preferences.start_at_sign_in {
                8
            } else {
                0
            };
            // SAFETY: native menu borrows the terminated label only for this call.
            checked(unsafe { AppendMenuW(menu.0, flags, id, label.as_ptr()) })?;
        }
        Ok(menu)
    }

    pub fn reveal(&mut self, status: &str) -> io::Result<Option<Action>> {
        let menu = self.menu(status)?;
        let mut position = Point::default();
        // SAFETY: our invisible top-level window owns this menu; foreground activation
        // and the trailing null message allow outside-click dismissal on Windows.
        let selection = unsafe {
            checked(GetCursorPos(&mut position))?;
            SetForegroundWindow(self.window);
            let result = TrackPopupMenu(
                menu.0,
                0x100 | 2,
                position.x,
                position.y,
                0,
                self.window,
                ptr::null(),
            );
            PostMessageW(self.window, 0, 0, 0);
            result
        };
        match selection {
            6 => Ok(Some(Action::Retry)),
            1 | 5 => {
                let warning = wide(self.configuration.strings.get(if selection == 1 {
                    "restart_warning"
                } else {
                    "quit_warning"
                }));
                let title = wide(crate::identity::MANAGER_NAME);
                // SAFETY: confirmation contains only authored product text and defaults
                // to No. Warn even when current operation counts are unavailable.
                let confirmed = unsafe {
                    MessageBoxW(
                        self.window,
                        warning.as_ptr(),
                        title.as_ptr(),
                        4 | 0x30 | 0x100,
                    )
                } == 6;
                Ok(confirmed.then_some(if selection == 1 {
                    Action::Restart
                } else {
                    Action::Quit
                }))
            }
            2 => {
                self.open(
                    self.configuration
                        .desktop
                        .as_ref()
                        .ok_or_else(|| io::Error::from(io::ErrorKind::NotFound))?,
                )?;
                Ok(None)
            }
            3 => {
                self.open(
                    self.configuration
                        .root
                        .join(crate::contract::MANAGER_LOG)
                        .parent()
                        .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?,
                )?;
                Ok(None)
            }
            4 => {
                let mut preferences = self.configuration.preferences;
                preferences.start_at_sign_in = !preferences.start_at_sign_in;
                preferences.store(&self.configuration.root)?;
                self.configuration.preferences = preferences;
                Ok(None)
            }
            _ => Ok(None),
        }
    }

    fn open(&self, path: &std::path::Path) -> io::Result<()> {
        let operation = wide("open");
        let path: Vec<u16> = path.as_os_str().encode_wide().chain([0]).collect();
        // SAFETY: only the admitted desktop image or the canonical log directory is
        // passed as a separate shell target; no command line is assembled.
        let result = unsafe {
            ShellExecuteW(
                self.window,
                operation.as_ptr(),
                path.as_ptr(),
                ptr::null(),
                ptr::null(),
                1,
            )
        } as isize;
        if result <= 32 {
            Err(io::ErrorKind::Other.into())
        } else {
            Ok(())
        }
    }
}
impl Drop for Tray {
    fn drop(&mut self) {
        if self.present {
            let data = self.icon("stopping");
            // SAFETY: remove only the notification icon owned by our window/id.
            unsafe {
                Shell_NotifyIconW(2, &data);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[link(name = "user32")]
    unsafe extern "system" {
        fn GetMenuState(menu: Handle, id: u32, flags: u32) -> u32;
        fn GetMenuItemCount(menu: Handle) -> i32;
    }
    #[test]
    fn native_menu_has_supported_actions_and_persisted_checkbox() {
        let mut tray = Tray {
            window: ptr::null_mut(),
            configuration: Configuration {
                root: PathBuf::new(),
                desktop: None,
                preferences: Preferences::default(),
                strings: Strings::current().unwrap(),
            },
            taskbar_created: 0,
            present: false,
            status: String::new(),
        };
        let menu = tray.menu("waiting").unwrap();
        // SAFETY: the menu was created on this thread and remains owned for inspection.
        unsafe {
            assert_eq!(GetMenuItemCount(menu.0), 6);
            assert_ne!(GetMenuState(menu.0, 0, 0) & 2, 0);
            assert_ne!(GetMenuState(menu.0, 2, 0) & 2, 0);
            assert_ne!(GetMenuState(menu.0, 4, 0) & 8, 0);
            assert_eq!(GetMenuState(menu.0, 1, 0), 0);
            assert_eq!(GetMenuState(menu.0, 5, 0), 0);
        }
        tray.configuration.preferences.start_at_sign_in = false;
        let menu = tray.menu("unavailable").unwrap();
        // SAFETY: as above, no interactive desktop or shell action is invoked.
        assert_eq!(unsafe { GetMenuState(menu.0, 4, 0) } & 8, 0);
        // SAFETY: the failed-state menu replaces destructive Restart with Retry.
        unsafe {
            assert_eq!(GetMenuState(menu.0, 6, 0), 0);
            assert_eq!(GetMenuState(menu.0, 1, 0), u32::MAX);
        }
        assert!(Tray::selected((1 << 16) | 0x401));
        assert!(!Tray::selected(0x200));
    }
}
