//! Waits until a file in one of a few log directories changes, a waker wakes
//! the wait, or a timeout passes.
//!
//! On Windows each directory carries a change notification for names, sizes
//! and write times. A writer that keeps its file open changes no directory
//! entry Windows reports until it closes the file, so such a writer also sets
//! a named event for the directory after each append ([`announce_append`]),
//! and the wait includes that event. Elsewhere no notification source is used
//! yet, and every wait ends within [`OBSERVATION`], so callers observe the
//! files on that interval.
//!
//! A wake reports only that something may have changed: the caller reads the
//! files to learn what.
use std::{
    path::{Path, PathBuf},
    time::Duration,
};

/// The longest wait while a directory is not watched: one that does not exist
/// yet, or a platform without a notification source.
pub const OBSERVATION: Duration = Duration::from_millis(100);

/// Why a wait ended.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Wake {
    /// A file in a watched directory changed or a writer announced an append.
    Changed,
    /// The [`Waker`] was woken.
    Woken,
    /// The timeout passed, or an unwatched directory's observation is due.
    Elapsed,
}

/// The directories whose files a caller follows.
pub struct FileChanges {
    inner: imp::FileChanges,
}

/// Ends the current or next wait of its [`FileChanges`] from any thread.
#[derive(Clone)]
pub struct Waker {
    inner: imp::Waker,
}

impl FileChanges {
    /// Watches each directory; one that does not exist yet is watched once it does.
    pub fn new(directories: Vec<PathBuf>) -> Self {
        Self {
            inner: imp::FileChanges::new(directories),
        }
    }

    pub fn waker(&self) -> Waker {
        Waker {
            inner: self.inner.waker(),
        }
    }

    /// Waits for a change, a wake or `timeout`; `None` waits for either of the
    /// first two only. Changes that arrive while no wait is in progress end the
    /// next wait at once.
    pub fn wait(&mut self, timeout: Option<Duration>) -> Wake {
        self.inner.wait(timeout)
    }
}

impl Waker {
    pub fn wake(&self) {
        self.inner.wake();
    }
}

/// The session-local event name a writer sets after appending to a file in
/// `directory`. Python's file log handler derives the same name: the path
/// without a `\\?\` prefix, with `\` separators, no trailing separator and
/// ASCII letters lowered, hashed with 64-bit FNV-1a over its UTF-8 bytes.
pub fn append_signal_name(directory: &Path) -> String {
    let text = directory.to_string_lossy();
    let text = text
        .strip_prefix(r"\\?\")
        .unwrap_or(&text)
        .replace('/', "\\");
    let text = text.trim_end_matches('\\');
    format!(
        "Local\\cadrumo-log-append-{:016x}",
        fnv1a(&text.as_bytes().to_ascii_lowercase())
    )
}

fn fnv1a(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0xcbf2_9ce4_8422_2325, |hash, byte| {
        (hash ^ u64::from(*byte)).wrapping_mul(0x0000_0100_0000_01b3)
    })
}

/// Tells a [`FileChanges`] following `directory` that a file in it grew,
/// for a writer that keeps the file open. Without a follower it does nothing.
pub fn announce_append(directory: &Path) {
    imp::announce_append(directory);
}

#[cfg(windows)]
mod imp {
    use super::{OBSERVATION, Wake, append_signal_name};
    use std::{
        ffi::c_void,
        os::windows::ffi::OsStrExt,
        path::{Path, PathBuf},
        ptr,
        sync::Arc,
        time::Duration,
    };

    const INVALID_HANDLE_VALUE: *mut c_void = -1isize as *mut c_void;
    const FILE_NOTIFY_CHANGE_FILE_NAME: u32 = 0x0000_0001;
    const FILE_NOTIFY_CHANGE_SIZE: u32 = 0x0000_0008;
    const FILE_NOTIFY_CHANGE_LAST_WRITE: u32 = 0x0000_0010;
    const CREATE_EVENT_MANUAL_RESET: u32 = 0x0000_0001;
    const EVENT_MODIFY_STATE: u32 = 0x0000_0002;
    const SYNCHRONIZE: u32 = 0x0010_0000;
    const WAIT_OBJECT_0: u32 = 0;
    const WAIT_TIMEOUT: u32 = 0x102;
    const INFINITE: u32 = u32::MAX;

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn FindFirstChangeNotificationW(path: *const u16, subtree: i32, filter: u32)
        -> *mut c_void;
        fn FindNextChangeNotification(handle: *mut c_void) -> i32;
        fn FindCloseChangeNotification(handle: *mut c_void) -> i32;
        fn CreateEventExW(
            attributes: *const c_void,
            name: *const u16,
            flags: u32,
            access: u32,
        ) -> *mut c_void;
        fn SetEvent(event: *mut c_void) -> i32;
        fn ResetEvent(event: *mut c_void) -> i32;
        fn WaitForMultipleObjects(
            count: u32,
            handles: *const *mut c_void,
            wait_all: i32,
            milliseconds: u32,
        ) -> u32;
        fn CloseHandle(handle: *mut c_void) -> i32;
    }

    fn wide(text: &std::ffi::OsStr) -> Vec<u16> {
        text.encode_wide().chain(std::iter::once(0)).collect()
    }

    /// An event handle: the unnamed wake, or a directory's named append signal.
    struct Event(*mut c_void);

    // SAFETY: an event handle is a process-wide kernel object that any thread
    // may signal or wait on. `Event` is its only closer.
    unsafe impl Send for Event {}
    // SAFETY: as above; the handle value itself is never mutated.
    unsafe impl Sync for Event {}

    impl Event {
        /// An unnamed auto-reset event, or the named manual-reset append
        /// signal, opened if another process created it first.
        fn create(name: Option<&str>) -> Option<Self> {
            let name = name.map(|name| wide(name.as_ref()));
            let flags = if name.is_some() {
                CREATE_EVENT_MANUAL_RESET
            } else {
                0
            };
            // SAFETY: no attributes; `name` is NUL-terminated and outlives
            // the call. The handle is owned by the returned `Event`.
            let handle = unsafe {
                CreateEventExW(
                    ptr::null(),
                    name.as_ref().map_or(ptr::null(), |name| name.as_ptr()),
                    flags,
                    EVENT_MODIFY_STATE | SYNCHRONIZE,
                )
            };
            (!handle.is_null()).then_some(Self(handle))
        }

        fn set(&self) {
            // SAFETY: the event is open for as long as `self` lives.
            unsafe {
                SetEvent(self.0);
            }
        }

        fn reset(&self) {
            // SAFETY: as for `set`.
            unsafe {
                ResetEvent(self.0);
            }
        }
    }

    impl Drop for Event {
        fn drop(&mut self) {
            // SAFETY: the handle was returned open by CreateEventExW and is
            // closed only here.
            unsafe {
                CloseHandle(self.0);
            }
        }
    }

    /// One directory's change notification.
    struct Watch(*mut c_void);

    // SAFETY: a change notification handle is a process-wide kernel object;
    // the thread that owns its `FileChanges` is its only user and closer.
    unsafe impl Send for Watch {}

    impl Watch {
        fn open(directory: &Path) -> Option<Self> {
            let path = wide(directory.as_os_str());
            // SAFETY: `path` is NUL-terminated and outlives the call.
            let handle = unsafe {
                FindFirstChangeNotificationW(
                    path.as_ptr(),
                    0,
                    FILE_NOTIFY_CHANGE_FILE_NAME
                        | FILE_NOTIFY_CHANGE_SIZE
                        | FILE_NOTIFY_CHANGE_LAST_WRITE,
                )
            };
            (handle != INVALID_HANDLE_VALUE && !handle.is_null()).then_some(Self(handle))
        }

        /// Asks for the next change after one was reported.
        fn rearm(&self) -> bool {
            // SAFETY: the handle is an open change notification owned by `self`.
            unsafe { FindNextChangeNotification(self.0) != 0 }
        }
    }

    impl Drop for Watch {
        fn drop(&mut self) {
            // SAFETY: the handle was returned open by FindFirstChangeNotificationW
            // and is closed only here.
            unsafe {
                FindCloseChangeNotification(self.0);
            }
        }
    }

    /// What ended a wait, by its position among the waited handles.
    enum Source {
        Wake,
        Signal,
        Watch(usize),
    }

    pub struct FileChanges {
        directories: Vec<PathBuf>,
        watches: Vec<Option<Watch>>,
        /// Each directory's append signal; one that could not be opened leaves
        /// its directory observed on an interval.
        signals: Vec<Option<Event>>,
        wake: Option<Arc<Event>>,
    }

    #[derive(Clone)]
    pub struct Waker(Option<Arc<Event>>);

    impl Waker {
        pub fn wake(&self) {
            if let Some(event) = &self.0 {
                event.set();
            }
        }
    }

    pub fn announce_append(directory: &Path) {
        if let Some(signal) = Event::create(Some(&append_signal_name(directory))) {
            signal.set();
        }
    }

    impl FileChanges {
        pub fn new(mut directories: Vec<PathBuf>) -> Self {
            directories.sort();
            directories.dedup();
            let watches = directories
                .iter()
                .map(|directory| Watch::open(directory))
                .collect();
            let signals = directories
                .iter()
                .map(|directory| Event::create(Some(&append_signal_name(directory))))
                .collect();
            Self {
                directories,
                watches,
                signals,
                wake: Event::create(None).map(Arc::new),
            }
        }

        pub fn waker(&self) -> Waker {
            Waker(self.wake.clone())
        }

        pub fn wait(&mut self, timeout: Option<Duration>) -> Wake {
            for (directory, watch) in self.directories.iter().zip(self.watches.iter_mut()) {
                if watch.is_none() {
                    *watch = Watch::open(directory);
                }
            }
            let unwatched = self.wake.is_none()
                || self.watches.iter().any(Option::is_none)
                || self.signals.iter().any(Option::is_none);
            let timeout = if unwatched {
                Some(timeout.map_or(OBSERVATION, |timeout| timeout.min(OBSERVATION)))
            } else {
                timeout
            };
            let mut handles = Vec::new();
            let mut sources = Vec::new();
            if let Some(wake) = &self.wake {
                handles.push(wake.0);
                sources.push(Source::Wake);
            }
            for signal in self.signals.iter().flatten() {
                handles.push(signal.0);
                sources.push(Source::Signal);
            }
            for (index, watch) in self.watches.iter().enumerate() {
                if let Some(watch) = watch {
                    handles.push(watch.0);
                    sources.push(Source::Watch(index));
                }
            }
            if handles.is_empty() {
                std::thread::sleep(timeout.unwrap_or(OBSERVATION));
                return Wake::Elapsed;
            }
            let milliseconds = timeout.map_or(INFINITE, |timeout| {
                u32::try_from(timeout.as_millis().saturating_add(1))
                    .map_or(INFINITE - 1, |ms| ms.min(INFINITE - 1))
            });
            // SAFETY: every handle in `handles` is open and owned by `self`,
            // which outlives the call; the count matches the slice.
            let result = unsafe {
                WaitForMultipleObjects(handles.len() as u32, handles.as_ptr(), 0, milliseconds)
            };
            if result == WAIT_TIMEOUT {
                return Wake::Elapsed;
            }
            let Some(source) = sources.get(result.wrapping_sub(WAIT_OBJECT_0) as usize) else {
                // A failed wait; bound the retry so a lasting failure cannot spin.
                std::thread::sleep(OBSERVATION);
                return Wake::Elapsed;
            };
            match *source {
                Source::Wake => Wake::Woken,
                Source::Signal => {
                    // Cleared before the caller reads, so an append after this
                    // point sets it again and is never lost.
                    for signal in self.signals.iter().flatten() {
                        signal.reset();
                    }
                    Wake::Changed
                }
                Source::Watch(index) => {
                    if !self.watches[index].as_ref().is_some_and(Watch::rearm) {
                        // The directory went away; it is watched again once it exists.
                        self.watches[index] = None;
                    }
                    Wake::Changed
                }
            }
        }
    }
}

#[cfg(not(windows))]
mod imp {
    use super::{OBSERVATION, Wake};
    use std::{
        path::{Path, PathBuf},
        sync::{Arc, Condvar, Mutex},
        time::Duration,
    };

    pub struct FileChanges {
        wake: Arc<(Mutex<bool>, Condvar)>,
    }

    #[derive(Clone)]
    pub struct Waker(Arc<(Mutex<bool>, Condvar)>);

    impl Waker {
        pub fn wake(&self) {
            let (woken, signal) = &*self.0;
            *woken.lock().unwrap_or_else(|e| e.into_inner()) = true;
            signal.notify_all();
        }
    }

    pub fn announce_append(_directory: &Path) {}

    impl FileChanges {
        pub fn new(_directories: Vec<PathBuf>) -> Self {
            Self {
                wake: Arc::new((Mutex::new(false), Condvar::new())),
            }
        }

        pub fn waker(&self) -> Waker {
            Waker(self.wake.clone())
        }

        pub fn wait(&mut self, timeout: Option<Duration>) -> Wake {
            let limit = timeout.map_or(OBSERVATION, |timeout| timeout.min(OBSERVATION));
            let (woken, signal) = &*self.wake;
            let guard = woken.lock().unwrap_or_else(|e| e.into_inner());
            let (mut guard, _) = signal
                .wait_timeout_while(guard, limit, |woken| !*woken)
                .unwrap_or_else(|e| e.into_inner());
            if std::mem::take(&mut *guard) {
                Wake::Woken
            } else {
                Wake::Elapsed
            }
        }
    }
}

#[cfg(test)]
mod name_tests {
    use super::*;

    #[test]
    fn the_hash_is_fnv1a_64() {
        // The published FNV-1a 64 test vectors.
        assert_eq!(fnv1a(b""), 0xcbf2_9ce4_8422_2325);
        assert_eq!(fnv1a(b"a"), 0xaf63_dc4c_8601_ec8c);
        assert_eq!(fnv1a(b"foobar"), 0x8594_4171_f739_67e8);
    }

    #[test]
    fn spellings_of_one_directory_share_a_name_and_python_derives_the_same() {
        let name = append_signal_name(Path::new(r"C:\Users\Example\AppData\Local\cadrumo\logs"));
        // Pinned by the Python handler's test as well.
        assert_eq!(name, r"Local\cadrumo-log-append-c2f24f27d31c8a0a");
        for spelling in [
            r"c:\users\example\appdata\local\cadrumo\logs",
            r"C:/Users/Example/AppData/Local/cadrumo/logs",
            r"C:\Users\Example\AppData\Local\cadrumo\logs\",
            r"\\?\C:\Users\Example\AppData\Local\cadrumo\logs",
        ] {
            assert_eq!(append_signal_name(Path::new(spelling)), name, "{spelling}");
        }
        assert_ne!(
            append_signal_name(Path::new(
                r"C:\Users\Example\AppData\Local\cadrumo-dev\logs"
            )),
            name
        );
    }
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;
    use std::{
        fs::{self, OpenOptions},
        io::Write,
        time::Instant,
    };

    fn scratch(name: &str) -> PathBuf {
        let directory = std::env::temp_dir().join(format!(
            "cadrumo-file-changes-{name}-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).unwrap();
        directory
    }

    #[test]
    fn a_quiet_directory_waits_out_the_timeout() {
        let directory = scratch("quiet");
        let mut changes = FileChanges::new(vec![directory.clone()]);
        let started = Instant::now();
        assert_eq!(
            changes.wait(Some(Duration::from_millis(300))),
            Wake::Elapsed
        );
        assert!(started.elapsed() >= Duration::from_millis(300));
        fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn an_announced_append_by_a_writer_that_keeps_its_file_open_ends_the_wait() {
        let directory = scratch("announced");
        let mut writer = OpenOptions::new()
            .create(true)
            .append(true)
            .open(directory.join("cadrumo.log"))
            .unwrap();
        let mut changes = FileChanges::new(vec![directory.clone()]);
        let announced = directory.clone();
        let appending = std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(200));
            writer.write_all(b"one record\n").unwrap();
            announce_append(&announced);
            writer
        });
        let started = Instant::now();
        assert_eq!(changes.wait(Some(Duration::from_secs(10))), Wake::Changed);
        assert!(started.elapsed() < Duration::from_secs(5));
        let writer = appending.join().unwrap();
        // The signal was cleared for the next append; the writer stays open so
        // closing it reports nothing in the meantime.
        assert_eq!(
            changes.wait(Some(Duration::from_millis(200))),
            Wake::Elapsed
        );
        drop(writer);
        fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn an_append_by_a_writer_that_closes_its_file_ends_the_wait() {
        let directory = scratch("closed");
        let path = directory.join("cadrumo-native.jsonl");
        fs::write(&path, b"first\n").unwrap();
        let mut changes = FileChanges::new(vec![directory.clone()]);
        let appending = std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(200));
            let mut file = OpenOptions::new().append(true).open(path).unwrap();
            file.write_all(b"second\n").unwrap();
        });
        assert_eq!(changes.wait(Some(Duration::from_secs(10))), Wake::Changed);
        appending.join().unwrap();
        fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn a_waker_on_another_thread_ends_a_wait_with_no_deadline() {
        let directory = scratch("woken");
        let mut changes = FileChanges::new(vec![directory.clone()]);
        let waker = changes.waker();
        let waking = std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(200));
            waker.wake();
        });
        assert_eq!(changes.wait(None), Wake::Woken);
        waking.join().unwrap();
        fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn a_directory_created_later_is_watched_once_it_exists() {
        let parent = scratch("later");
        let directory = parent.join("logs");
        let mut changes = FileChanges::new(vec![directory.clone()]);
        // Unwatched, a wait is only an observation interval.
        assert_eq!(changes.wait(None), Wake::Elapsed);
        fs::create_dir_all(&directory).unwrap();
        assert_eq!(changes.wait(Some(Duration::from_millis(50))), Wake::Elapsed);
        fs::write(directory.join("cadrumo.log"), b"first\n").unwrap();
        assert_eq!(changes.wait(Some(Duration::from_secs(10))), Wake::Changed);
        fs::remove_dir_all(parent).unwrap();
    }
}
