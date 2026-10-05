//! Windows desktop admission and the per-user desktop instance lock. Query
//! existing desktop objects; never create or register a session.
use std::{
    ffi::c_void,
    io,
    marker::PhantomData,
    mem::size_of,
    ptr,
    sync::Arc,
    time::{Duration, Instant},
};

#[repr(C)]
struct UserObjectFlags {
    inherit: i32,
    reserved: i32,
    flags: u32,
}

#[link(name = "user32")]
unsafe extern "system" {
    fn GetProcessWindowStation() -> *mut c_void;
    fn GetUserObjectInformationW(
        object: *mut c_void,
        index: i32,
        information: *mut c_void,
        length: u32,
        needed: *mut u32,
    ) -> i32;
    fn OpenInputDesktop(flags: u32, inherit: i32, access: u32) -> *mut c_void;
    fn CloseDesktop(desktop: *mut c_void) -> i32;
}
type ConsoleHandler = unsafe extern "system" fn(u32) -> i32;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn FreeConsole() -> i32;
    fn SetConsoleCtrlHandler(handler: Option<ConsoleHandler>, add: i32) -> i32;
}

pub fn available() -> bool {
    let mut flags = UserObjectFlags {
        inherit: 0,
        reserved: 0,
        flags: 0,
    };
    // SAFETY: the process owns the station; the writable buffer has the API's
    // documented layout and size. Every acquired desktop handle is closed here.
    unsafe {
        let station = GetProcessWindowStation();
        if station.is_null()
            || GetUserObjectInformationW(
                station,
                1,
                ptr::from_mut(&mut flags).cast(),
                size_of::<UserObjectFlags>() as u32,
                ptr::null_mut(),
            ) == 0
            || flags.flags & 1 == 0
        {
            return false;
        }
        let desktop = OpenInputDesktop(0, 0, 1);
        if desktop.is_null() {
            return false;
        }
        CloseDesktop(desktop) != 0
    }
}

/// Sets or clears this process's "ignore Ctrl+C" console attribute.
///
/// Every child created afterwards inherits it, console or not. A process
/// started in a new process group begins with it set, and an interactive
/// child would then ignore Ctrl+C until it cleared the attribute itself;
/// clearing it before starting terminal children restores normal Ctrl+C.
pub fn ignore_console_interrupts(ignore: bool) -> std::io::Result<()> {
    // SAFETY: with a null handler routine the call only changes this process's
    // Ctrl+C attribute; no pointer is passed or retained.
    if unsafe { SetConsoleCtrlHandler(None, i32::from(ignore)) } == 0 {
        return Err(std::io::Error::last_os_error());
    }
    Ok(())
}

pub fn detach_console() {
    // SAFETY: this detaches only the current process, after GUI mode was selected.
    unsafe {
        FreeConsole();
    }
}

/// A WebView2 interface the desktop host requires of the installed runtime.
#[cfg(feature = "webview2")]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WebviewInterface {
    /// `ICoreWebView2_22`: iframe and worker requests reach custom schemes.
    Webview22,
    /// `ICoreWebView2Settings3`: browser accelerator keys can be turned off.
    Settings3,
}

/// The first required WebView2 interface the runtime behind `controller`
/// lacks, or `None` when it has them all. A refused interface cast is the
/// answer, not a failure; failing to reach the webview or its settings is.
#[cfg(feature = "webview2")]
pub fn missing_webview_interface(
    controller: &webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Controller,
) -> std::io::Result<Option<WebviewInterface>> {
    use webview2_com::Microsoft::Web::WebView2::Win32::{ICoreWebView2_22, ICoreWebView2Settings3};
    use windows_core::Interface;
    // SAFETY: `controller` is a live COM reference the caller holds for the
    // duration of the call. Each getter returns an owned reference or an
    // HRESULT and writes through no other pointer.
    let (webview, settings) = unsafe {
        let webview = controller.CoreWebView2().map_err(std::io::Error::other)?;
        let settings = webview.Settings().map_err(std::io::Error::other)?;
        (webview, settings)
    };
    if webview.cast::<ICoreWebView2_22>().is_err() {
        return Ok(Some(WebviewInterface::Webview22));
    }
    if settings.cast::<ICoreWebView2Settings3>().is_err() {
        return Ok(Some(WebviewInterface::Settings3));
    }
    Ok(None)
}

/// Turns off the browser accelerator keys (reload, print, find, zoom,
/// developer tools) and the default context menus of the webview behind
/// `controller`, then reads both settings back.
///
/// A runtime without `ICoreWebView2Settings3` is refused with
/// [`std::io::ErrorKind::Unsupported`] before any setting changes.
#[cfg(feature = "webview2")]
pub fn disable_browser_features(
    controller: &webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Controller,
) -> std::io::Result<()> {
    use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Settings3;
    use windows_core::{BOOL, Interface};
    let failed = std::io::Error::other;
    // SAFETY: `controller` is a live COM reference the caller holds for the
    // duration of the call. The setters take plain values; each getter writes
    // only the `BOOL` it is given, which lives on this stack frame.
    unsafe {
        let settings = controller
            .CoreWebView2()
            .and_then(|webview| webview.Settings())
            .map_err(failed)?;
        let keys = settings
            .cast::<ICoreWebView2Settings3>()
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Unsupported, e))?;
        settings
            .SetAreDefaultContextMenusEnabled(false)
            .map_err(failed)?;
        keys.SetAreBrowserAcceleratorKeysEnabled(false)
            .map_err(failed)?;
        let mut menus_enabled = BOOL(1);
        let mut keys_enabled = BOOL(1);
        settings
            .AreDefaultContextMenusEnabled(&mut menus_enabled)
            .map_err(failed)?;
        keys.AreBrowserAcceleratorKeysEnabled(&mut keys_enabled)
            .map_err(failed)?;
        if menus_enabled.as_bool() || keys_enabled.as_bool() {
            return Err(std::io::Error::other(
                "WebView2 kept a browser feature enabled",
            ));
        }
    }
    Ok(())
}

/// How a desktop instance claim ended.
pub enum InstanceClaim {
    /// This thread holds the per-user instance lock.
    Primary(InstanceLock),
    /// The instance holding the lock acknowledged an activation request.
    Activated,
    /// The instance holding the lock runs in another session of this user,
    /// where no window of this session can be brought forward.
    OtherSession,
}

/// The per-user desktop instance lock, held by the thread that claimed it.
///
/// The lock is a named mutex in the machine-wide `Global\` namespace, so it
/// spans every session of the user. Its name joins the caller's family with
/// the user's SID, and its security descriptor names that user as owner with
/// the only access entry, so another account can neither open nor answer for
/// it, and an object of that name another account created first is refused.
///
/// Activation travels on named auto-reset events that carry the holder's
/// session number in their names, and only the holder creates them. A second
/// instance opens its own session's activation event, sets it and waits on
/// that session's acknowledgement event. When the lock is held but its own
/// session has no activation event, the holder is in another session. An
/// event has no content, so a request carries nothing from the second
/// instance but the request.
///
/// The second instance consumes any acknowledgement already set before it
/// sends each request, so a late acknowledgement of a claim that stopped
/// waiting cannot answer it. An acknowledgement still cannot name its
/// request: one the holder sets for a request it took before that point
/// answers the second instance too.
pub struct InstanceLock {
    mutex: Owned,
    activate: Arc<Owned>,
    acknowledge: Arc<Owned>,
    name: String,
    server: Option<Server>,
    /// Mutex ownership belongs to the claiming thread, so the lock never
    /// leaves it.
    _thread: PhantomData<*const ()>,
}

struct Server {
    stop: Arc<Owned>,
    thread: std::thread::JoinHandle<()>,
}

/// An owned kernel handle, closed once on drop.
struct Owned(*mut c_void);

// SAFETY: a kernel object handle is a process-wide value that any thread may
// use. `Owned` is its only closer, and every thread that borrows it through
// an `Arc` is joined before the last reference drops.
unsafe impl Send for Owned {}
// SAFETY: as above; the handle value itself is never mutated.
unsafe impl Sync for Owned {}

impl Drop for Owned {
    fn drop(&mut self) {
        // SAFETY: the handle was returned open by the kernel and is closed
        // only here.
        unsafe {
            CloseHandle(self.0);
        }
    }
}

/// Memory the system allocated with `LocalAlloc`, released on drop.
struct LocalMemory(*mut c_void);

impl Drop for LocalMemory {
    fn drop(&mut self) {
        // SAFETY: the pointer came from a system call documented to return
        // `LocalAlloc` memory and is released only here.
        unsafe {
            LocalFree(self.0);
        }
    }
}

#[repr(C)]
struct SecurityAttributes {
    length: u32,
    descriptor: *mut c_void,
    inherit: i32,
}

#[repr(C)]
struct SidAndAttributes {
    sid: *mut c_void,
    attributes: u32,
}

const TOKEN_QUERY: u32 = 0x0008;
const TOKEN_USER_CLASS: i32 = 1;
const SDDL_REVISION_1: u32 = 1;
const SE_KERNEL_OBJECT: i32 = 6;
const OWNER_SECURITY_INFORMATION: u32 = 1;
const WAIT_OBJECT_0: u32 = 0;
const WAIT_ABANDONED: u32 = 0x80;
const WAIT_TIMEOUT: u32 = 0x102;
const INFINITE: u32 = u32::MAX;
const EVENT_ALL_ACCESS: u32 = 0x001F_0003;
const ERROR_FILE_NOT_FOUND: i32 = 2;
const ERROR_INVALID_HANDLE: i32 = 6;
/// How long a second instance waits for each acknowledgement before it
/// checks the lock again.
const ACKNOWLEDGEMENT_ROUND: Duration = Duration::from_millis(500);
/// How long a held lock may go without an activation event for the caller's
/// session before the holder counts as being in another session. It covers
/// the moment between a holder taking the lock and creating its events.
const HOLDER_GRACE: Duration = Duration::from_millis(500);
/// The pause between checks while that grace runs.
const HOLDER_POLL: Duration = Duration::from_millis(25);

#[link(name = "kernel32")]
unsafe extern "system" {
    fn CreateMutexW(
        attributes: *const SecurityAttributes,
        initial_owner: i32,
        name: *const u16,
    ) -> *mut c_void;
    fn ReleaseMutex(mutex: *mut c_void) -> i32;
    fn CreateEventW(
        attributes: *const SecurityAttributes,
        manual_reset: i32,
        initial_state: i32,
        name: *const u16,
    ) -> *mut c_void;
    fn OpenEventW(access: u32, inherit: i32, name: *const u16) -> *mut c_void;
    fn SetEvent(event: *mut c_void) -> i32;
    fn ResetEvent(event: *mut c_void) -> i32;
    fn WaitForSingleObject(handle: *mut c_void, milliseconds: u32) -> u32;
    fn WaitForMultipleObjects(
        count: u32,
        handles: *const *mut c_void,
        wait_all: i32,
        milliseconds: u32,
    ) -> u32;
    fn CloseHandle(handle: *mut c_void) -> i32;
    fn GetCurrentProcess() -> *mut c_void;
    fn GetCurrentProcessId() -> u32;
    fn ProcessIdToSessionId(process: u32, session: *mut u32) -> i32;
    fn LocalFree(memory: *mut c_void) -> *mut c_void;
}

#[link(name = "advapi32")]
unsafe extern "system" {
    fn OpenProcessToken(process: *mut c_void, access: u32, token: *mut *mut c_void) -> i32;
    fn GetTokenInformation(
        token: *mut c_void,
        class: i32,
        information: *mut c_void,
        length: u32,
        needed: *mut u32,
    ) -> i32;
    fn ConvertSidToStringSidW(sid: *mut c_void, text: *mut *mut u16) -> i32;
    fn ConvertStringSecurityDescriptorToSecurityDescriptorW(
        text: *const u16,
        revision: u32,
        descriptor: *mut *mut c_void,
        size: *mut u32,
    ) -> i32;
    fn GetSecurityInfo(
        handle: *mut c_void,
        object_type: i32,
        information: u32,
        owner: *mut *mut c_void,
        group: *mut *mut c_void,
        dacl: *mut *mut c_void,
        sacl: *mut *mut c_void,
        descriptor: *mut *mut c_void,
    ) -> u32;
    fn EqualSid(first: *mut c_void, second: *mut c_void) -> i32;
}

thread_local! {
    /// Lock names this thread holds. A mutex is recursive for its owning
    /// thread, so without this a second claim on the same thread would
    /// succeed as a second primary.
    static HELD: std::cell::RefCell<Vec<String>> = const { std::cell::RefCell::new(Vec::new()) };
}

fn wide(text: &str) -> Vec<u16> {
    text.encode_utf16().chain(std::iter::once(0)).collect()
}

fn checked(result: i32) -> io::Result<()> {
    if result == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

/// The token user of this process: its SID and the SID's string form.
struct User {
    /// `TOKEN_USER` storage, 8-byte aligned for its pointer field.
    token_user: Vec<u64>,
    text: String,
}

impl User {
    fn current() -> io::Result<Self> {
        let mut token = ptr::null_mut();
        // SAFETY: the pseudo handle needs no closing; the token handle the
        // call writes is owned by `Owned` below.
        checked(unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) })?;
        let token = Owned(token);
        let mut needed = 0u32;
        // SAFETY: a null buffer of length zero asks only for the size, which
        // the call writes to `needed`.
        unsafe {
            GetTokenInformation(token.0, TOKEN_USER_CLASS, ptr::null_mut(), 0, &mut needed);
        }
        if needed == 0 {
            return Err(io::Error::last_os_error());
        }
        let mut token_user = vec![0u64; (needed as usize).div_ceil(size_of::<u64>())];
        // SAFETY: the buffer is writable for the length passed and aligned
        // for `TOKEN_USER`, whose SID pointer then points inside it.
        checked(unsafe {
            GetTokenInformation(
                token.0,
                TOKEN_USER_CLASS,
                token_user.as_mut_ptr().cast(),
                (token_user.len() * size_of::<u64>()) as u32,
                &mut needed,
            )
        })?;
        let mut user = User {
            token_user,
            text: String::new(),
        };
        let mut text = ptr::null_mut();
        // SAFETY: `sid()` points into the live `TOKEN_USER` buffer. The call
        // writes a nul-terminated `LocalAlloc` string that `LocalMemory`
        // releases after the copy, so the length scan stays inside it.
        user.text = unsafe {
            checked(ConvertSidToStringSidW(user.sid(), &mut text))?;
            let _text = LocalMemory(text.cast());
            let length = (0..).take_while(|&i| *text.add(i) != 0).count();
            String::from_utf16(std::slice::from_raw_parts(text, length))
                .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?
        };
        Ok(user)
    }

    fn sid(&self) -> *mut c_void {
        // SAFETY: the buffer holds the `TOKEN_USER` the system wrote, whose
        // first field is a `SID_AND_ATTRIBUTES`.
        unsafe { (*self.token_user.as_ptr().cast::<SidAndAttributes>()).sid }
    }

    /// Whether this user owns the object behind `handle`, which must be
    /// open with `READ_CONTROL`.
    fn owns(&self, handle: *mut c_void) -> io::Result<bool> {
        let mut owner = ptr::null_mut();
        let mut descriptor = ptr::null_mut();
        // SAFETY: the caller's handle is open with `READ_CONTROL`. The owner
        // SID points into the returned descriptor,
        // which stays allocated until `_descriptor` drops after the
        // comparison.
        unsafe {
            let status = GetSecurityInfo(
                handle,
                SE_KERNEL_OBJECT,
                OWNER_SECURITY_INFORMATION,
                &mut owner,
                ptr::null_mut(),
                ptr::null_mut(),
                ptr::null_mut(),
                &mut descriptor,
            );
            if status != 0 {
                return Err(io::Error::from_raw_os_error(status as i32));
            }
            let _descriptor = LocalMemory(descriptor);
            Ok(!owner.is_null() && EqualSid(owner, self.sid()) != 0)
        }
    }
}

/// A security descriptor owned by `sid` that grants only `sid` access.
fn owner_only(sid: &str) -> io::Result<LocalMemory> {
    let text = wide(&format!("O:{sid}D:P(A;;GA;;;{sid})"));
    let mut descriptor = ptr::null_mut();
    // SAFETY: the SDDL string is nul-terminated; the call writes a
    // `LocalAlloc` descriptor that `LocalMemory` releases.
    checked(unsafe {
        ConvertStringSecurityDescriptorToSecurityDescriptorW(
            text.as_ptr(),
            SDDL_REVISION_1,
            &mut descriptor,
            ptr::null_mut(),
        )
    })?;
    Ok(LocalMemory(descriptor))
}

/// The machine-wide base name of `family`'s instance objects for the user
/// whose SID string is `sid`.
fn instance_name(family: &str, sid: &str) -> io::Result<String> {
    let valid = !family.is_empty()
        && family.len() <= 128
        && family
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'_'))
        && !family.starts_with('.')
        && !family.ends_with('.');
    if !valid {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "instance family is not a reverse-DNS identifier",
        ));
    }
    Ok(format!("Global\\{family}.desktop.{sid}"))
}

/// The names of the activation and acknowledgement events a holder in
/// `session` serves.
fn session_names(base: &str, session: u32) -> (String, String) {
    (
        format!("{base}.session.{session}.activate"),
        format!("{base}.session.{session}.acknowledge"),
    )
}

fn current_session() -> io::Result<u32> {
    let mut session = 0u32;
    // SAFETY: the call writes only the `u32` it is given.
    checked(unsafe { ProcessIdToSessionId(GetCurrentProcessId(), &mut session) })?;
    Ok(session)
}

enum Kind {
    Mutex,
    Event,
}

/// Refuses an object this user does not own. `handle` must be open with
/// `READ_CONTROL`, which full access includes.
fn owned(handle: Owned, user: &User) -> io::Result<Owned> {
    if !user.owns(handle.0)? {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "another account owns the instance object",
        ));
    }
    Ok(handle)
}

/// Creates or opens a named object and refuses one this user does not own.
fn open_owned(
    kind: Kind,
    name: &str,
    attributes: &SecurityAttributes,
    user: &User,
) -> io::Result<Owned> {
    let name = wide(name);
    // SAFETY: the attributes and their descriptor outlive the call and the
    // name is nul-terminated. An existing object is opened with full access,
    // and a null result is a failure the caller reports.
    let handle = unsafe {
        match kind {
            Kind::Mutex => CreateMutexW(attributes, 0, name.as_ptr()),
            Kind::Event => CreateEventW(attributes, 0, 0, name.as_ptr()),
        }
    };
    if handle.is_null() {
        return Err(io::Error::last_os_error());
    }
    owned(Owned(handle), user)
}

/// Opens an existing named event without creating it: `None` when no
/// object of that name exists.
fn open_existing_event(name: &str, user: &User) -> io::Result<Option<Owned>> {
    let name = wide(name);
    // SAFETY: the name is nul-terminated; a null result is reported below.
    let handle = unsafe { OpenEventW(EVENT_ALL_ACCESS, 0, name.as_ptr()) };
    if handle.is_null() {
        let error = io::Error::last_os_error();
        return match error.raw_os_error() {
            Some(ERROR_FILE_NOT_FOUND) => Ok(None),
            _ => Err(error),
        };
    }
    owned(Owned(handle), user).map(Some)
}

/// Claims the desktop instance for `family`, or hands activation to the
/// instance that holds it.
///
/// A second instance in the holder's session asks for activation and waits
/// for the holder to acknowledge it. Without an acknowledgement it checks
/// the lock again, so a holder that is exiting passes the lock on instead of
/// swallowing the request. A second instance in another session sends no
/// request and returns [`InstanceClaim::OtherSession`]. After `patience`
/// without an outcome the claim fails with [`io::ErrorKind::TimedOut`].
pub fn claim_instance(family: &str, patience: Duration) -> io::Result<InstanceClaim> {
    claim_in_session(family, current_session()?, patience)
}

fn claim_in_session(family: &str, session: u32, patience: Duration) -> io::Result<InstanceClaim> {
    let user = User::current()?;
    let name = instance_name(family, &user.text)?;
    if HELD.with(|held| held.borrow().contains(&name)) {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "this thread already holds the instance lock",
        ));
    }
    let descriptor = owner_only(&user.text)?;
    let attributes = SecurityAttributes {
        length: size_of::<SecurityAttributes>() as u32,
        descriptor: descriptor.0,
        inherit: 0,
    };
    let (activate_name, acknowledge_name) = session_names(&name, session);
    // An object of another type under the lock name, such as an event another
    // account created first, makes the mutex create fail with
    // ERROR_INVALID_HANDLE; that is refused like an object owned by another
    // account.
    let mutex =
        open_owned(Kind::Mutex, &format!("{name}.lock"), &attributes, &user).map_err(|error| {
            match error.raw_os_error() {
                Some(ERROR_INVALID_HANDLE) => io::Error::new(
                    io::ErrorKind::PermissionDenied,
                    "an object of another type holds the instance name",
                ),
                _ => error,
            }
        })?;
    let deadline = Instant::now() + patience;
    let mut absent_since = None;
    loop {
        // SAFETY: the mutex handle is open for the duration of the call.
        match unsafe { WaitForSingleObject(mutex.0, 0) } {
            WAIT_OBJECT_0 | WAIT_ABANDONED => {
                let activate = open_owned(Kind::Event, &activate_name, &attributes, &user)?;
                let acknowledge = open_owned(Kind::Event, &acknowledge_name, &attributes, &user)?;
                // Requests left for a holder that never answered them are
                // not this instance's to acknowledge.
                // SAFETY: both handles are open.
                unsafe {
                    ResetEvent(activate.0);
                    ResetEvent(acknowledge.0);
                }
                HELD.with(|held| held.borrow_mut().push(name.clone()));
                return Ok(InstanceClaim::Primary(InstanceLock {
                    mutex,
                    activate: Arc::new(activate),
                    acknowledge: Arc::new(acknowledge),
                    name,
                    server: None,
                    _thread: PhantomData,
                }));
            }
            WAIT_TIMEOUT => {}
            _ => return Err(io::Error::last_os_error()),
        }
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return Err(io::ErrorKind::TimedOut.into());
        }
        // Opened afresh each round, so this instance's own handles never
        // keep alive the events of a holder that has gone.
        let events = match open_existing_event(&activate_name, &user)? {
            Some(activate) => open_existing_event(&acknowledge_name, &user)?
                .map(|acknowledge| (activate, acknowledge)),
            None => None,
        };
        let Some((activate, acknowledge)) = events else {
            let since = *absent_since.get_or_insert_with(Instant::now);
            if since.elapsed() >= HOLDER_GRACE {
                return Ok(InstanceClaim::OtherSession);
            }
            std::thread::sleep(HOLDER_POLL.min(remaining));
            continue;
        };
        absent_since = None;
        // An acknowledgement already set answers an earlier request that no
        // claim waited for any longer, this claim's previous round included,
        // so it is consumed before this request is sent and only one given
        // afterwards counts.
        // SAFETY: both handles are open for the duration of these calls.
        match unsafe { WaitForSingleObject(acknowledge.0, 0) } {
            WAIT_OBJECT_0 | WAIT_TIMEOUT => {}
            _ => return Err(io::Error::last_os_error()),
        }
        // SAFETY: as above.
        checked(unsafe { SetEvent(activate.0) })?;
        let round = remaining.min(ACKNOWLEDGEMENT_ROUND).as_millis() as u32;
        // SAFETY: as above.
        match unsafe { WaitForSingleObject(acknowledge.0, round) } {
            WAIT_OBJECT_0 => return Ok(InstanceClaim::Activated),
            WAIT_TIMEOUT => {}
            _ => return Err(io::Error::last_os_error()),
        }
    }
}

impl InstanceLock {
    /// Answers activation requests on a worker thread until the lock drops.
    ///
    /// `on_activation` returns whether it accepted the request. A refused
    /// request is not acknowledged, so the second instance keeps waiting for
    /// the lock; a holder that is closing refuses.
    pub fn serve(&mut self, on_activation: impl Fn() -> bool + Send + 'static) -> io::Result<()> {
        if self.server.is_some() {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "the instance lock already serves activation",
            ));
        }
        // SAFETY: an unnamed manual-reset event with default security; a
        // null result is a failure reported below.
        let stop = unsafe { CreateEventW(ptr::null(), 1, 0, ptr::null()) };
        if stop.is_null() {
            return Err(io::Error::last_os_error());
        }
        let stop = Arc::new(Owned(stop));
        let (halt, activate, acknowledge) = (
            stop.clone(),
            self.activate.clone(),
            self.acknowledge.clone(),
        );
        let thread = std::thread::Builder::new()
            .name("desktop-activation".into())
            .spawn(move || {
                // The stop event comes first, so it wins when both are set.
                let handles = [halt.0, activate.0];
                loop {
                    // SAFETY: both handles stay open while this thread holds
                    // their `Arc`s; the array outlives the call.
                    match unsafe { WaitForMultipleObjects(2, handles.as_ptr(), 0, INFINITE) } {
                        1 => {
                            if on_activation() {
                                // SAFETY: as above.
                                unsafe {
                                    SetEvent(acknowledge.0);
                                }
                            }
                        }
                        _ => return,
                    }
                }
            })?;
        self.server = Some(Server { stop, thread });
        Ok(())
    }
}

impl Drop for InstanceLock {
    fn drop(&mut self) {
        if let Some(server) = self.server.take() {
            // SAFETY: the stop event is open while `server` holds it.
            unsafe {
                SetEvent(server.stop.0);
            }
            let _ = server.thread.join();
        }
        // SAFETY: this thread owns the mutex: the lock is created only by a
        // successful wait on this thread and cannot leave it.
        unsafe {
            ReleaseMutex(self.mutex.0);
        }
        HELD.with(|held| held.borrow_mut().retain(|name| name != &self.name));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{
        atomic::{AtomicUsize, Ordering},
        mpsc,
    };
    use std::time::{SystemTime, UNIX_EPOCH};

    /// A family no real installation uses, unique to one test.
    fn family(label: &str) -> String {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        format!("test.cadrumo.{label}-{}-{nanos}", std::process::id())
    }

    fn primary(family: &str) -> InstanceLock {
        match claim_instance(family, Duration::from_secs(5)).unwrap() {
            InstanceClaim::Primary(lock) => lock,
            InstanceClaim::Activated | InstanceClaim::OtherSession => {
                panic!("{family}: expected the lock")
            }
        }
    }

    fn outcome(claim: InstanceClaim) -> &'static str {
        match claim {
            InstanceClaim::Primary(_) => "primary",
            InstanceClaim::Activated => "activated",
            InstanceClaim::OtherSession => "other-session",
        }
    }

    /// Claims on a fresh thread, which never owns the mutex already.
    fn claim_elsewhere(family: &str, patience: Duration) -> io::Result<&'static str> {
        let family = family.to_owned();
        std::thread::spawn(move || claim_instance(&family, patience).map(outcome))
            .join()
            .unwrap()
    }

    /// Claims on a fresh thread as if from `session`.
    fn claim_from_session(
        family: &str,
        session: u32,
        patience: Duration,
    ) -> io::Result<&'static str> {
        let family = family.to_owned();
        std::thread::spawn(move || claim_in_session(&family, session, patience).map(outcome))
            .join()
            .unwrap()
    }

    fn counting(lock: &mut InstanceLock, accept: bool) -> Arc<AtomicUsize> {
        let count = Arc::new(AtomicUsize::new(0));
        let seen = count.clone();
        lock.serve(move || {
            seen.fetch_add(1, Ordering::SeqCst);
            accept
        })
        .unwrap();
        count
    }

    #[test]
    fn names_are_machine_wide_per_user_and_per_family() {
        let user = User::current().unwrap();
        assert!(user.text.starts_with("S-1-5-"), "{}", user.text);
        let stable = instance_name("md.neve.cadrumo", &user.text).unwrap();
        let preview = instance_name("md.neve.cadrumo.preview", &user.text).unwrap();
        assert_eq!(
            stable,
            format!("Global\\md.neve.cadrumo.desktop.{}", user.text)
        );
        assert_eq!(
            session_names(&stable, 3),
            (
                format!("{stable}.session.3.activate"),
                format!("{stable}.session.3.acknowledge")
            )
        );
        current_session().unwrap();
        assert_ne!(stable, preview);
        assert_ne!(
            stable,
            instance_name("md.neve.cadrumo", "S-1-5-21-1-2-3-1001").unwrap()
        );
        for invalid in [
            "",
            ".md.neve",
            "md.neve.",
            "md\\neve",
            "Global\\md",
            "md neve",
            "md/neve",
            &"a".repeat(129),
        ] {
            assert_eq!(
                instance_name(invalid, &user.text).unwrap_err().kind(),
                io::ErrorKind::InvalidInput,
                "{invalid}"
            );
        }
    }

    #[test]
    fn second_claim_hands_activation_to_the_holder() {
        let family = family("activation");
        let mut lock = primary(&family);
        let count = counting(&mut lock, true);
        assert_eq!(
            claim_elsewhere(&family, Duration::from_secs(5)).unwrap(),
            "activated"
        );
        assert_eq!(count.load(Ordering::SeqCst), 1);
        assert_eq!(
            claim_elsewhere(&family, Duration::from_secs(5)).unwrap(),
            "activated"
        );
        assert_eq!(count.load(Ordering::SeqCst), 2);
    }

    #[test]
    fn families_do_not_contend() {
        let stable = family("stable");
        let _lock = primary(&stable);
        assert_eq!(
            claim_elsewhere(&format!("{stable}.preview"), Duration::from_secs(5)).unwrap(),
            "primary"
        );
    }

    #[test]
    fn released_and_abandoned_locks_pass_to_the_next_claim() {
        let family = family("release");
        let mut lock = primary(&family);
        counting(&mut lock, true);
        drop(lock);
        assert_eq!(
            claim_elsewhere(&family, Duration::from_secs(5)).unwrap(),
            "primary"
        );
        // A holder that ends without releasing, as a crashed process does,
        // leaves the mutex abandoned; the next claim takes it.
        let abandoned = family.clone();
        std::thread::spawn(move || std::mem::forget(primary(&abandoned)))
            .join()
            .unwrap();
        assert_eq!(
            claim_elsewhere(&family, Duration::from_secs(5)).unwrap(),
            "primary"
        );
    }

    #[test]
    fn an_unacknowledged_request_times_out_while_the_lock_is_held() {
        let family = family("closing");
        let mut lock = primary(&family);
        let count = counting(&mut lock, false);
        let error = claim_elsewhere(&family, Duration::from_millis(1200)).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        assert!(count.load(Ordering::SeqCst) >= 1);
    }

    #[test]
    fn a_waiting_claim_takes_the_lock_once_the_holder_releases_it() {
        let family = family("handover");
        let mut lock = primary(&family);
        counting(&mut lock, false);
        let (sender, receiver) = mpsc::channel();
        let waiting = family.clone();
        let claimant = std::thread::spawn(move || {
            sender.send(()).unwrap();
            claim_instance(&waiting, Duration::from_secs(10)).map(outcome)
        });
        receiver.recv().unwrap();
        std::thread::sleep(Duration::from_millis(700));
        drop(lock);
        assert_eq!(claimant.join().unwrap().unwrap(), "primary");
    }

    #[test]
    fn a_holder_in_another_session_is_reported_without_a_request() {
        let family = family("sessions");
        let mut lock = match claim_in_session(&family, 7, Duration::from_secs(5)).unwrap() {
            InstanceClaim::Primary(lock) => lock,
            _ => panic!("expected the lock"),
        };
        let count = counting(&mut lock, true);
        let started = Instant::now();
        assert_eq!(
            claim_from_session(&family, 8, Duration::from_secs(5)).unwrap(),
            "other-session"
        );
        assert!(started.elapsed() < Duration::from_secs(2));
        assert_eq!(count.load(Ordering::SeqCst), 0);
        assert_eq!(
            claim_from_session(&family, 7, Duration::from_secs(5)).unwrap(),
            "activated"
        );
        assert_eq!(count.load(Ordering::SeqCst), 1);
    }

    /// The lock and attributes a test uses to act as a holder by hand.
    fn holder_objects(family: &str) -> (User, LocalMemory, String) {
        let user = User::current().unwrap();
        let descriptor = owner_only(&user.text).unwrap();
        let base = instance_name(family, &user.text).unwrap();
        (user, descriptor, base)
    }

    #[test]
    fn the_grace_covers_a_holder_that_has_not_created_its_events_yet() {
        let family = family("grace");
        let (ready, holding) = mpsc::channel();
        let (finish, finished) = mpsc::channel::<()>();
        let held = family.clone();
        let holder = std::thread::spawn(move || {
            let (user, descriptor, base) = holder_objects(&held);
            let attributes = SecurityAttributes {
                length: size_of::<SecurityAttributes>() as u32,
                descriptor: descriptor.0,
                inherit: 0,
            };
            let mutex =
                open_owned(Kind::Mutex, &format!("{base}.lock"), &attributes, &user).unwrap();
            // SAFETY: the mutex handle is open.
            assert_eq!(unsafe { WaitForSingleObject(mutex.0, 0) }, WAIT_OBJECT_0);
            ready.send(()).unwrap();
            // Held, with no events yet, for part of the grace.
            std::thread::sleep(Duration::from_millis(150));
            let (activate, acknowledge) = session_names(&base, 5);
            let activate = open_owned(Kind::Event, &activate, &attributes, &user).unwrap();
            let acknowledge = open_owned(Kind::Event, &acknowledge, &attributes, &user).unwrap();
            // SAFETY: both event handles are open.
            unsafe {
                assert_eq!(WaitForSingleObject(activate.0, 5000), WAIT_OBJECT_0);
                SetEvent(acknowledge.0);
            }
            finished.recv().unwrap();
            // SAFETY: this thread owns the mutex.
            unsafe {
                ReleaseMutex(mutex.0);
            }
        });
        holding.recv().unwrap();
        assert_eq!(
            claim_from_session(&family, 5, Duration::from_secs(5)).unwrap(),
            "activated"
        );
        finish.send(()).unwrap();
        holder.join().unwrap();
    }

    #[test]
    fn a_session_event_another_account_could_have_placed_is_refused() {
        let family = family("squat-session");
        let _lock = match claim_in_session(&family, 3, Duration::from_secs(5)).unwrap() {
            InstanceClaim::Primary(lock) => lock,
            _ => panic!("expected the lock"),
        };
        let (_, _, base) = holder_objects(&family);
        let user = User::current().unwrap();
        let _squatter = squat(
            Kind::Event,
            &session_names(&base, 4).0,
            &format!("D:P(A;;0x00100000;;;{})", user.text),
        );
        let error = claim_from_session(&family, 4, Duration::from_secs(2)).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::PermissionDenied, "{error}");
    }

    const HOLDER_VARIABLE: &str = "CADRUMO_PLATFORM_INSTANCE_HOLDER";
    /// Marks the holder's reports among the test harness's own output.
    const REPORT: &str = "@holder-report ";

    /// Runs as a holder process when the parent test selects a family. It
    /// reports each activation request and answers it as its standard input
    /// says: `accept` acknowledges the pending request, and `close` refuses
    /// it and every later one, as a closing window does. End of input
    /// releases the lock.
    #[test]
    fn holder() {
        use std::io::BufRead;
        use std::sync::{Mutex, atomic::AtomicBool};
        let Ok(family) = std::env::var(HOLDER_VARIABLE) else {
            return;
        };
        let mut lock = primary(&family);
        let (decide, decisions) = mpsc::channel::<bool>();
        let decisions = Mutex::new(decisions);
        let closing = Arc::new(AtomicBool::new(false));
        let closed = closing.clone();
        lock.serve(move || {
            println!("{REPORT}request");
            !closed.load(Ordering::SeqCst) && decisions.lock().unwrap().recv().unwrap_or(false)
        })
        .unwrap();
        println!("{REPORT}primary");
        for line in std::io::stdin().lock().lines() {
            match line.unwrap().as_str() {
                "accept" => decide.send(true).unwrap(),
                "close" => {
                    closing.store(true, Ordering::SeqCst);
                    decide.send(false).unwrap();
                }
                other => panic!("unknown holder command {other}"),
            }
        }
        // A request still waiting for a decision is refused, so the
        // activation thread can be joined.
        drop(decide);
        drop(lock);
    }

    /// A holder process that a failed assertion must not leave running.
    struct Running(std::process::Child);
    impl Drop for Running {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    /// Reads the holder's output until it reports `expected`.
    fn until_report(lines: &mut impl Iterator<Item = String>, expected: &str) {
        assert!(
            lines.any(|line| line
                .rsplit_once(REPORT)
                .is_some_and(|(_, report)| report == expected)),
            "the holder never reported {expected}"
        );
    }

    /// An acknowledgement the holder gives after the claim that asked for
    /// it has given up must not answer a later claim: the holder may have
    /// started closing in between, and that claim then has to wait for the
    /// lock instead of reporting an activation that never happened.
    #[test]
    fn a_late_acknowledgement_does_not_answer_a_later_claim() {
        use std::io::{BufRead, BufReader, Write};
        use std::process::{Command, Stdio};
        let family = family("late-acknowledgement");
        let mut holder = Running(
            Command::new(std::env::current_exe().unwrap())
                .args([
                    "--exact",
                    "desktop::tests::holder",
                    "--nocapture",
                    "--test-threads=1",
                ])
                .env(HOLDER_VARIABLE, &family)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::inherit())
                .spawn()
                .unwrap(),
        );
        let mut input = holder.0.stdin.take().unwrap();
        let mut lines = BufReader::new(holder.0.stdout.take().unwrap())
            .lines()
            .map_while(Result::ok);
        until_report(&mut lines, "primary");

        // The first claim gives up while the holder still deliberates.
        let error = claim_elsewhere(&family, Duration::from_millis(300)).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        until_report(&mut lines, "request");
        // Its acknowledgement now arrives with nobody waiting for it.
        writeln!(input, "accept").unwrap();

        // The holder answers requests one at a time, so once it reports this
        // bare request it has set the late acknowledgement.
        let (user, _, base) = holder_objects(&family);
        let activate =
            open_existing_event(&session_names(&base, current_session().unwrap()).0, &user)
                .unwrap()
                .unwrap();
        // SAFETY: the event handle is open.
        checked(unsafe { SetEvent(activate.0) }).unwrap();
        until_report(&mut lines, "request");
        // From here on the holder is closing and refuses every request.
        writeln!(input, "close").unwrap();

        let error = claim_elsewhere(&family, Duration::from_millis(1500)).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut, "{error}");

        drop(input);
        assert!(holder.0.wait().unwrap().success());
        assert_eq!(
            claim_elsewhere(&family, Duration::from_secs(5)).unwrap(),
            "primary"
        );
    }

    #[test]
    fn the_holding_thread_cannot_claim_again() {
        let family = family("recursive");
        let _lock = primary(&family);
        let error = claim_instance(&family, Duration::from_secs(1))
            .err()
            .unwrap();
        assert_eq!(error.kind(), io::ErrorKind::AlreadyExists);
    }

    #[test]
    fn serving_twice_is_refused() {
        let family = family("serve");
        let mut lock = primary(&family);
        counting(&mut lock, true);
        assert_eq!(
            lock.serve(|| true).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
    }

    /// Creates `name` as `kind` with `sddl`, standing in for an object that
    /// another account placed first.
    fn squat(kind: Kind, name: &str, sddl: &str) -> Owned {
        let text = wide(sddl);
        let mut descriptor = ptr::null_mut();
        // SAFETY: as in `owner_only`.
        checked(unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                text.as_ptr(),
                SDDL_REVISION_1,
                &mut descriptor,
                ptr::null_mut(),
            )
        })
        .unwrap();
        let descriptor = LocalMemory(descriptor);
        let attributes = SecurityAttributes {
            length: size_of::<SecurityAttributes>() as u32,
            descriptor: descriptor.0,
            inherit: 0,
        };
        let name = wide(name);
        // SAFETY: as in `open_owned`.
        let handle = unsafe {
            match kind {
                Kind::Mutex => CreateMutexW(&attributes, 0, name.as_ptr()),
                Kind::Event => CreateEventW(&attributes, 0, 0, name.as_ptr()),
            }
        };
        assert!(!handle.is_null(), "{}", io::Error::last_os_error());
        Owned(handle)
    }

    #[test]
    fn ownership_is_compared_with_the_token_user() {
        use std::os::windows::io::AsRawHandle;
        let user = User::current().unwrap();
        let mine = squat(
            Kind::Event,
            &format!(
                "{}.owned",
                instance_name(&family("owner"), &user.text).unwrap()
            ),
            &format!("O:{0}D:P(A;;GA;;;{0})", user.text),
        );
        assert!(user.owns(mine.0).unwrap());
        // A system file belongs to TrustedInstaller, never to this user.
        let system = std::env::var_os("SystemRoot").unwrap();
        let foreign =
            std::fs::File::open(std::path::Path::new(&system).join(r"System32\kernel32.dll"))
                .unwrap();
        assert!(!user.owns(foreign.as_raw_handle()).unwrap());
    }

    #[test]
    fn objects_this_user_cannot_fully_open_are_refused() {
        let user = User::current().unwrap();
        // Only SYNCHRONIZE for this user: the claim cannot open it fully.
        let family_a = family("squat-access");
        let base = instance_name(&family_a, &user.text).unwrap();
        let _squatter = squat(
            Kind::Mutex,
            &format!("{base}.lock"),
            &format!("D:P(A;;0x00100000;;;{})", user.text),
        );
        let error = claim_elsewhere(&family_a, Duration::from_secs(1)).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::PermissionDenied, "{error}");
        // An object of another type under the lock name is refused too.
        let family_b = family("squat-type");
        let base = instance_name(&family_b, &user.text).unwrap();
        let _squatter = squat(
            Kind::Event,
            &format!("{base}.lock"),
            &format!("D:P(A;;GA;;;{})", user.text),
        );
        let error = claim_elsewhere(&family_b, Duration::from_secs(1)).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::PermissionDenied, "{error}");
    }
}
