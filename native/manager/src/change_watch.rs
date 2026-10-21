//! Directory and registry change notifications a host loop waits on beside its other handles.
//!
//! A notification only says that something under the watched path may have
//! changed; the owner reads its state again. A path that cannot be watched yet,
//! such as a directory not yet created, is observed again at a bounded pace
//! until it can be.
#![allow(unsafe_code)]

use crate::wake::windows::Readiness;
use std::{
    ffi::c_void,
    io,
    os::windows::{
        ffi::OsStrExt,
        io::{AsHandle, AsRawHandle, BorrowedHandle, FromRawHandle, OwnedHandle},
    },
    path::PathBuf,
    ptr,
    time::{Duration, Instant},
};
use windows_sys::Win32::System::Threading::{CreateEventW, ResetEvent};

type Handle = *mut c_void;
type Key = *mut c_void;

const INVALID_HANDLE_VALUE: Handle = -1isize as Handle;
const WAIT_OBJECT_0: u32 = 0;
const FILE_NOTIFY_CHANGE_FILE_NAME: u32 = 0x1;
const FILE_NOTIFY_CHANGE_DIR_NAME: u32 = 0x2;
const FILE_NOTIFY_CHANGE_LAST_WRITE: u32 = 0x10;
const KEY_NOTIFY: u32 = 0x10;
const KEY_WOW64_64KEY: u32 = 0x100;
const REG_NOTIFY_CHANGE_NAME: u32 = 0x1;
const REG_NOTIFY_CHANGE_LAST_SET: u32 = 0x4;
// The notification outlives the registering thread, so any thread may own the loop.
const REG_NOTIFY_THREAD_AGNOSTIC: u32 = 0x1000_0000;
/// Win32 predefined keys are sign-extended constants and are never closed.
pub const CURRENT_USER: u32 = 0x8000_0001;
pub const LOCAL_MACHINE: u32 = 0x8000_0002;

// Pacing: a path that cannot be watched yet publishes no notification until it can.
const UNWATCHED_PACE: Duration = Duration::from_secs(5);

#[link(name = "kernel32")]
unsafe extern "system" {
    fn WaitForSingleObject(handle: Handle, timeout: u32) -> u32;
    fn FindFirstChangeNotificationW(path: *const u16, subtree: i32, filter: u32) -> Handle;
    fn FindNextChangeNotification(handle: Handle) -> i32;
    fn FindCloseChangeNotification(handle: Handle) -> i32;
}
#[link(name = "advapi32")]
unsafe extern "system" {
    fn RegOpenKeyExW(
        root: Key,
        subkey: *const u16,
        options: u32,
        access: u32,
        key: *mut Key,
    ) -> i32;
    fn RegNotifyChangeKeyValue(
        key: Key,
        subtree: i32,
        filter: u32,
        event: Handle,
        asynchronous: i32,
    ) -> i32;
    fn RegCloseKey(key: Key) -> i32;
}

fn wide(text: &std::ffi::OsStr) -> Vec<u16> {
    text.encode_wide().chain(std::iter::once(0)).collect()
}

fn signaled(handle: Handle) -> bool {
    // SAFETY: the handle is open for the duration of the call; a zero timeout only polls.
    unsafe { WaitForSingleObject(handle, 0) == WAIT_OBJECT_0 }
}

/// One directory's change notification handle, closed only by its own close function.
struct Notification(Handle);

impl Drop for Notification {
    fn drop(&mut self) {
        // SAFETY: returned open by FindFirstChangeNotificationW and closed only here.
        unsafe {
            FindCloseChangeNotification(self.0);
        }
    }
}

struct Directory {
    path: PathBuf,
    subtree: bool,
    open: Option<Notification>,
}

impl Directory {
    fn open(&mut self) -> bool {
        let path = wide(self.path.as_os_str());
        // SAFETY: `path` is NUL-terminated and outlives the call.
        let handle = unsafe {
            FindFirstChangeNotificationW(
                path.as_ptr(),
                i32::from(self.subtree),
                FILE_NOTIFY_CHANGE_FILE_NAME
                    | FILE_NOTIFY_CHANGE_DIR_NAME
                    | FILE_NOTIFY_CHANGE_LAST_WRITE,
            )
        };
        let opened = handle != INVALID_HANDLE_VALUE && !handle.is_null();
        self.open = opened.then_some(Notification(handle));
        opened
    }

    /// Whether a change was reported since the last call; the handle is armed again.
    fn take(&mut self) -> bool {
        match &self.open {
            None => false,
            Some(notification) if signaled(notification.0) => {
                // SAFETY: the handle is an open change notification owned by `self`.
                if unsafe { FindNextChangeNotification(notification.0) } == 0 {
                    // The directory itself went away; watch it again once it can be.
                    self.open = None;
                    self.open();
                }
                true
            }
            Some(_) => false,
        }
    }
}

/// One registry key's change notification: an owned event the key signals.
struct RegistryKey {
    root: u32,
    subkey: Vec<u16>,
    filter: u32,
    event: OwnedHandle,
    key: Option<Key>,
    /// An absent optional key is no gap: its parent's watch reports its creation.
    optional: bool,
}

impl RegistryKey {
    fn new(root: u32, subkey: &str, filter: u32, optional: bool) -> io::Result<Self> {
        // SAFETY: creates a private, noninheritable, unnamed manual-reset event, so a
        // wait that ends on it leaves it signaled for `take` to see and reset.
        let event = unsafe { CreateEventW(ptr::null(), 1, 0, ptr::null()) };
        if event.is_null() {
            return Err(io::Error::last_os_error());
        }
        let mut key = Self {
            root,
            subkey: subkey.encode_utf16().chain([0]).collect(),
            filter,
            // SAFETY: successful creation transferred this distinct owned handle.
            event: unsafe { OwnedHandle::from_raw_handle(event) },
            key: None,
            optional,
        };
        key.open();
        Ok(key)
    }

    fn open(&mut self) -> bool {
        self.close();
        let mut key: Key = ptr::null_mut();
        // SAFETY: the subkey is NUL-terminated and `key` receives an owned handle on success.
        let opened = unsafe {
            RegOpenKeyExW(
                self.root as i32 as isize as Key,
                self.subkey.as_ptr(),
                0,
                KEY_NOTIFY | KEY_WOW64_64KEY,
                &mut key,
            )
        } == 0;
        if !opened {
            return false;
        }
        self.key = Some(key);
        self.arm()
    }

    fn arm(&mut self) -> bool {
        let Some(key) = self.key else {
            return false;
        };
        // SAFETY: the key and the event stay open while the notification can fire.
        let armed = unsafe {
            RegNotifyChangeKeyValue(
                key,
                0,
                self.filter | REG_NOTIFY_THREAD_AGNOSTIC,
                self.event.as_raw_handle(),
                1,
            )
        } == 0;
        if !armed {
            self.close();
        }
        armed
    }

    fn close(&mut self) {
        if let Some(key) = self.key.take() {
            // SAFETY: the key was opened by RegOpenKeyExW and is closed only here.
            unsafe {
                RegCloseKey(key);
            }
        }
    }

    fn take(&mut self) -> bool {
        if self.key.is_none() {
            return self.open();
        }
        if !signaled(self.event.as_raw_handle()) {
            return false;
        }
        // SAFETY: the owned event is open for this call; it stays signaled until reset.
        unsafe {
            ResetEvent(self.event.as_raw_handle());
        }
        // A deleted key signals once; it is opened again when it exists.
        if !self.arm() {
            self.open();
        }
        true
    }
}

impl Drop for RegistryKey {
    fn drop(&mut self) {
        self.close();
    }
}

/// The directories and registry keys one owner reads its state from.
#[derive(Default)]
pub struct ChangeWatch {
    directories: Vec<Directory>,
    keys: Vec<RegistryKey>,
    unwatched_retry: Option<Instant>,
}

impl ChangeWatch {
    /// Watch the names and writes in `path`, and below it when `subtree`.
    pub fn directory(&mut self, path: PathBuf, subtree: bool) {
        let mut directory = Directory {
            path,
            subtree,
            open: None,
        };
        directory.open();
        self.directories.push(directory);
    }

    /// Watch the values of `root\parent\name` in the 64-bit view, and its
    /// creation or deletion through the subkey names of `parent`.
    pub fn registry_key(&mut self, root: u32, parent: &str, name: &str) -> io::Result<()> {
        self.keys.push(RegistryKey::new(
            root,
            parent,
            REG_NOTIFY_CHANGE_NAME,
            false,
        )?);
        self.keys.push(RegistryKey::new(
            root,
            &format!("{parent}\\{name}"),
            REG_NOTIFY_CHANGE_NAME | REG_NOTIFY_CHANGE_LAST_SET,
            true,
        )?);
        Ok(())
    }

    /// Whether anything watched may have changed since the last call. A path
    /// that became watchable counts as changed, since its change went unseen.
    pub fn take(&mut self) -> bool {
        let retry_due = self
            .unwatched_retry
            .is_none_or(|retry| Instant::now() >= retry);
        let mut changed = false;
        for directory in &mut self.directories {
            changed |= if directory.open.is_some() {
                directory.take()
            } else {
                retry_due && directory.open()
            };
        }
        for key in &mut self.keys {
            changed |= if key.key.is_some() {
                key.take()
            } else {
                (key.optional || retry_due) && key.open()
            };
        }
        if !self.unwatched() {
            self.unwatched_retry = None;
        } else if retry_due {
            self.unwatched_retry = Some(Instant::now() + UNWATCHED_PACE);
        }
        changed
    }

    fn unwatched(&self) -> bool {
        self.directories.iter().any(|item| item.open.is_none())
            || self
                .keys
                .iter()
                .any(|item| item.key.is_none() && !item.optional)
    }

    /// Add every armed notification, and the retry for one not yet watchable.
    pub fn readiness<'a>(&'a self, into: &mut Readiness<'a>) {
        for directory in &self.directories {
            if let Some(notification) = &directory.open {
                // SAFETY: the notification outlives the borrow `into` holds.
                into.handle(unsafe { BorrowedHandle::borrow_raw(notification.0) });
            }
        }
        for key in self.keys.iter().filter(|item| item.key.is_some()) {
            into.handle(key.event.as_handle());
        }
        if self.unwatched() {
            into.at(self.unwatched_retry.unwrap_or_else(Instant::now));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unique() -> u128 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    }

    fn scratch(label: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "cadrumo-change-watch-{label}-{}-{}",
            std::process::id(),
            unique()
        ));
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).unwrap();
        path
    }

    fn signaled_within(watch: &mut ChangeWatch, bound: Duration) -> bool {
        let deadline = Instant::now() + bound;
        loop {
            {
                let mut readiness = Readiness::default();
                watch.readiness(&mut readiness);
                readiness.at(deadline);
                readiness.wait().unwrap();
            }
            if watch.take() {
                return true;
            }
            if Instant::now() >= deadline {
                return false;
            }
        }
    }

    #[test]
    fn a_new_entry_in_a_watched_directory_wakes_the_wait_and_nothing_else_does() {
        let root = scratch("directory");
        let mut watch = ChangeWatch::default();
        watch.directory(root.clone(), false);
        assert!(!watch.take(), "nothing changed yet");
        assert!(!signaled_within(&mut watch, Duration::from_millis(300)));
        std::fs::write(root.join("state.json"), b"{}").unwrap();
        assert!(signaled_within(&mut watch, Duration::from_secs(5)));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn a_subtree_watch_sees_a_file_written_inside_a_new_directory() {
        let root = scratch("subtree");
        let mut watch = ChangeWatch::default();
        watch.directory(root.clone(), true);
        std::fs::create_dir(root.join("1.2.3")).unwrap();
        assert!(signaled_within(&mut watch, Duration::from_secs(5)));
        while watch.take() {}
        std::fs::write(root.join("1.2.3").join("manifest.json"), b"{}").unwrap();
        assert!(signaled_within(&mut watch, Duration::from_secs(5)));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn a_directory_created_later_is_watched_once_it_exists() {
        let parent = scratch("later");
        let root = parent.join("versions");
        let mut watch = ChangeWatch::default();
        watch.directory(root.clone(), false);
        assert!(!watch.take(), "a missing directory reports nothing");
        std::fs::create_dir(&root).unwrap();
        // The next attempt to watch it is paced; make it due now.
        watch.unwatched_retry = Some(Instant::now());
        // Becoming watchable is itself reported, since what happened before went unseen.
        assert!(watch.take());
        assert!(!watch.take());
        std::fs::write(root.join("entry"), b"").unwrap();
        assert!(signaled_within(&mut watch, Duration::from_secs(5)));
        let _ = std::fs::remove_dir_all(&parent);
    }

    #[link(name = "advapi32")]
    unsafe extern "system" {
        fn RegCreateKeyExW(
            root: Key,
            subkey: *const u16,
            reserved: u32,
            class: *const u16,
            options: u32,
            access: u32,
            attributes: *const c_void,
            key: *mut Key,
            disposition: *mut u32,
        ) -> i32;
        fn RegSetValueExW(
            key: Key,
            name: *const u16,
            reserved: u32,
            kind: u32,
            data: *const u8,
            size: u32,
        ) -> i32;
        fn RegDeleteTreeW(key: Key, subkey: *const u16) -> i32;
    }

    const KEY_WRITE_ACCESS: u32 = 0x2_0006;

    fn wide_text(text: &str) -> Vec<u16> {
        text.encode_utf16().chain([0]).collect()
    }

    /// Create `CURRENT_USER\subkey` and return it open for writing.
    fn create_key(subkey: &str) -> Key {
        let path = wide_text(subkey);
        let mut created: Key = ptr::null_mut();
        // SAFETY: a NUL-terminated name; the caller closes the created key.
        let status = unsafe {
            RegCreateKeyExW(
                CURRENT_USER as i32 as isize as Key,
                path.as_ptr(),
                0,
                ptr::null(),
                0,
                KEY_WRITE_ACCESS | KEY_WOW64_64KEY,
                ptr::null(),
                &mut created,
                ptr::null_mut(),
            )
        };
        assert_eq!(status, 0);
        created
    }

    #[test]
    fn a_key_created_later_and_its_changed_value_each_wake_the_wait() {
        let parent = format!(
            "Software\\cadrumo-change-watch-test-{}-{}",
            std::process::id(),
            unique()
        );
        let scope = create_key(&parent);
        let mut watch = ChangeWatch::default();
        watch.registry_key(CURRENT_USER, &parent, "Entry").unwrap();
        assert!(!watch.take(), "nothing changed yet");
        assert!(!signaled_within(&mut watch, Duration::from_millis(300)));

        let entry = create_key(&format!("{parent}\\Entry"));
        assert!(signaled_within(&mut watch, Duration::from_secs(5)));
        while watch.take() {}

        let name = wide_text("EntryPoint");
        let data: Vec<u8> = "C:\\x\0"
            .encode_utf16()
            .flat_map(u16::to_le_bytes)
            .collect();
        // SAFETY: the open key, a NUL-terminated name and a REG_SZ buffer of the stated size.
        let status =
            unsafe { RegSetValueExW(entry, name.as_ptr(), 0, 1, data.as_ptr(), data.len() as u32) };
        assert_eq!(status, 0);
        assert!(signaled_within(&mut watch, Duration::from_secs(5)));
        // SAFETY: closes the keys created above, then removes this test's tree.
        unsafe {
            RegCloseKey(entry);
            RegCloseKey(scope);
            RegDeleteTreeW(
                CURRENT_USER as i32 as isize as Key,
                wide_text(&parent).as_ptr(),
            );
        }
    }
}
