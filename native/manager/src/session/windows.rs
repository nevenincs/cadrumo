//! Windows calls behind session ownership: the token user and the per-session mutex.
//!
//! The mutex lives in the session's `Local\` namespace with a descriptor that names this
//! user as owner and grants only this user access. An object of that name that another
//! account owns, that this user cannot open fully, or that has another type is refused, so
//! a squatter can neither hold nor answer for the lock. Every handle is wrapped in an
//! [`OwnedHandle`] at once, so it is closed exactly once.
#![allow(unsafe_code)]

use std::cell::RefCell;
use std::ffi::c_void;
use std::io;
use std::marker::PhantomData;
use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle, RawHandle};
use std::time::{Duration, Instant};

type Handle = *mut c_void;

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
const TOKEN_USER_CLASS: u32 = 1;
const SDDL_REVISION_1: u32 = 1;
const SE_KERNEL_OBJECT: i32 = 6;
const OWNER_SECURITY_INFORMATION: u32 = 0x0000_0001;
const WAIT_OBJECT_0: u32 = 0;
const WAIT_ABANDONED: u32 = 0x80;
const WAIT_TIMEOUT: u32 = 0x102;
const ERROR_INVALID_HANDLE: i32 = 6;
/// The pause between attempts on a lock another manager holds.
const LOCK_POLL: Duration = Duration::from_millis(25);

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetCurrentProcess() -> Handle;
    fn CreateMutexW(
        attributes: *const SecurityAttributes,
        initial_owner: i32,
        name: *const u16,
    ) -> Handle;
    fn ReleaseMutex(mutex: Handle) -> i32;
    fn WaitForSingleObject(handle: Handle, milliseconds: u32) -> u32;
    fn LocalFree(memory: *mut c_void) -> *mut c_void;
}

#[link(name = "advapi32")]
unsafe extern "system" {
    fn OpenProcessToken(process: Handle, access: u32, token: *mut Handle) -> i32;
    fn GetTokenInformation(
        token: Handle,
        class: u32,
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
        handle: Handle,
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
    /// Lock names this thread holds. A mutex is recursive for its owning thread, so
    /// without this a second claim on one thread would succeed as a second holder.
    static HELD: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
}

fn wide(text: &str) -> Vec<u16> {
    text.encode_utf16().chain([0]).collect()
}

fn checked(result: i32) -> io::Result<()> {
    if result == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

/// Take ownership of a handle a successful call returned; null means the call failed.
fn owned(handle: Handle) -> io::Result<OwnedHandle> {
    if handle.is_null() {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: `handle` was just returned open by the system to this process, is not null,
    // and nothing else holds or closes it, so the OwnedHandle becomes its only owner.
    Ok(unsafe { OwnedHandle::from_raw_handle(handle as RawHandle) })
}

fn raw(handle: &OwnedHandle) -> Handle {
    handle.as_raw_handle().cast()
}

/// Memory the system allocated with `LocalAlloc`, released on drop.
struct LocalMemory(*mut c_void);

impl Drop for LocalMemory {
    fn drop(&mut self) {
        // SAFETY: the pointer came from a call documented to return LocalAlloc memory and
        // is released only here.
        unsafe {
            LocalFree(self.0);
        }
    }
}

/// The token user of this process: its SID and the SID's string form.
pub(crate) struct User {
    /// `TOKEN_USER` storage, 8-byte aligned for its pointer field.
    token_user: Vec<u64>,
    pub(crate) sid: String,
}

impl User {
    pub(crate) fn current() -> io::Result<Self> {
        let mut token: Handle = std::ptr::null_mut();
        // SAFETY: the pseudo handle needs no closing; the token handle written to the
        // local is owned by `owned` below.
        checked(unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) })?;
        let token = owned(token)?;
        let mut needed = 0_u32;
        // SAFETY: a null buffer of length zero only asks for the size, written to `needed`.
        unsafe {
            GetTokenInformation(
                raw(&token),
                TOKEN_USER_CLASS,
                std::ptr::null_mut(),
                0,
                &mut needed,
            );
        }
        if needed == 0 {
            return Err(io::Error::last_os_error());
        }
        let words = usize::try_from(needed)
            .map_err(io::Error::other)?
            .div_ceil(size_of::<u64>());
        let mut token_user = vec![0_u64; words];
        let length =
            u32::try_from(token_user.len() * size_of::<u64>()).map_err(io::Error::other)?;
        // SAFETY: the buffer is writable for `length` bytes and aligned for TOKEN_USER,
        // whose SID pointer then points inside the same buffer.
        checked(unsafe {
            GetTokenInformation(
                raw(&token),
                TOKEN_USER_CLASS,
                token_user.as_mut_ptr().cast(),
                length,
                &mut needed,
            )
        })?;
        let mut user = Self {
            token_user,
            sid: String::new(),
        };
        let mut text: *mut u16 = std::ptr::null_mut();
        // SAFETY: `sid_pointer` points into the live TOKEN_USER buffer. The call writes a
        // NUL-terminated LocalAlloc string that `LocalMemory` releases after the copy, so
        // the length scan stays inside it.
        user.sid = unsafe {
            checked(ConvertSidToStringSidW(user.sid_pointer(), &mut text))?;
            let _text = LocalMemory(text.cast());
            let length = (0..).take_while(|&index| *text.add(index) != 0).count();
            String::from_utf16(std::slice::from_raw_parts(text, length))
                .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?
        };
        Ok(user)
    }

    fn sid_pointer(&self) -> *mut c_void {
        // SAFETY: the buffer holds the TOKEN_USER the system wrote, whose first field is a
        // SID_AND_ATTRIBUTES.
        unsafe { (*self.token_user.as_ptr().cast::<SidAndAttributes>()).sid }
    }

    /// Whether this user owns the object behind `handle`, open with `READ_CONTROL`.
    fn owns(&self, handle: &OwnedHandle) -> io::Result<bool> {
        let mut owner: *mut c_void = std::ptr::null_mut();
        let mut descriptor: *mut c_void = std::ptr::null_mut();
        // SAFETY: the handle is open with READ_CONTROL, which full access includes. The
        // owner SID points into the returned descriptor, which stays allocated until
        // `_descriptor` drops after the comparison.
        unsafe {
            let status = GetSecurityInfo(
                raw(handle),
                SE_KERNEL_OBJECT,
                OWNER_SECURITY_INFORMATION,
                &mut owner,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                &mut descriptor,
            );
            if status != 0 {
                return Err(io::Error::from_raw_os_error(
                    i32::try_from(status).map_err(io::Error::other)?,
                ));
            }
            let _descriptor = LocalMemory(descriptor);
            Ok(!owner.is_null() && EqualSid(owner, self.sid_pointer()) != 0)
        }
    }
}

/// A descriptor owned by `sid` that grants only `sid` access.
fn owner_only(sid: &str) -> io::Result<LocalMemory> {
    let text = wide(&format!("O:{sid}D:P(A;;GA;;;{sid})"));
    let mut descriptor: *mut c_void = std::ptr::null_mut();
    // SAFETY: the SDDL text is NUL-terminated; the call writes one LocalAlloc descriptor
    // that `LocalMemory` releases.
    checked(unsafe {
        ConvertStringSecurityDescriptorToSecurityDescriptorW(
            text.as_ptr(),
            SDDL_REVISION_1,
            &mut descriptor,
            std::ptr::null_mut(),
        )
    })?;
    Ok(LocalMemory(descriptor))
}

/// The per-session mutex, held by the thread that claimed it.
pub(crate) struct SessionMutex {
    mutex: OwnedHandle,
    name: String,
    /// Mutex ownership belongs to the claiming thread, so the lock never leaves it.
    _thread: PhantomData<*const ()>,
}

/// Claim the mutex called `name` for `user`, polling until `patience` ends.
///
/// `Ok(None)` means another holder still has it. An abandoned mutex, left by a holder that
/// ended without releasing it, is claimed.
pub(crate) fn claim(
    name: &str,
    user: &User,
    patience: Duration,
) -> io::Result<Option<SessionMutex>> {
    if HELD.with(|held| held.borrow().iter().any(|held| held == name)) {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "this thread already holds the session lock",
        ));
    }
    let descriptor = owner_only(&user.sid)?;
    let attributes = SecurityAttributes {
        length: u32::try_from(size_of::<SecurityAttributes>()).map_err(io::Error::other)?,
        descriptor: descriptor.0,
        inherit: 0,
    };
    let text = wide(name);
    // SAFETY: the attributes and their descriptor outlive the call and the name is
    // NUL-terminated. An existing object is opened with full access; null is a failure.
    let created = unsafe { CreateMutexW(&attributes, 0, text.as_ptr()) };
    let mutex = owned(created).map_err(|error| match error.raw_os_error() {
        // Another object type under the name makes the create fail this way.
        Some(ERROR_INVALID_HANDLE) => io::Error::new(
            io::ErrorKind::PermissionDenied,
            "an object of another type holds the session lock name",
        ),
        _ => error,
    })?;
    if !user.owns(&mutex)? {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "another account owns the session lock",
        ));
    }
    let deadline = Instant::now() + patience;
    loop {
        // SAFETY: the mutex handle is open for the duration of the call; a zero timeout
        // only polls.
        match unsafe { WaitForSingleObject(raw(&mutex), 0) } {
            WAIT_OBJECT_0 | WAIT_ABANDONED => {
                HELD.with(|held| held.borrow_mut().push(name.to_owned()));
                return Ok(Some(SessionMutex {
                    mutex,
                    name: name.to_owned(),
                    _thread: PhantomData,
                }));
            }
            WAIT_TIMEOUT => {}
            _ => return Err(io::Error::last_os_error()),
        }
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return Ok(None);
        }
        std::thread::sleep(LOCK_POLL.min(remaining));
    }
}

impl Drop for SessionMutex {
    fn drop(&mut self) {
        // SAFETY: this thread owns the mutex: it was acquired by a wait on this thread and
        // the value cannot leave it.
        unsafe {
            ReleaseMutex(raw(&self.mutex));
        }
        HELD.with(|held| held.borrow_mut().retain(|held| held != &self.name));
    }
}

#[cfg(test)]
pub(crate) mod squat {
    //! Objects standing in for ones another account placed under a lock name first.
    use super::*;

    const EVENT_MANUAL_RESET: i32 = 1;

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateEventW(
            attributes: *const SecurityAttributes,
            manual_reset: i32,
            initial_state: i32,
            name: *const u16,
        ) -> Handle;
    }

    pub(crate) enum Kind {
        Mutex,
        Event,
    }

    /// Create `name` as `kind` with the security `sddl`; the object lives while the handle.
    pub(crate) fn squat(kind: Kind, name: &str, sddl: &str) -> OwnedHandle {
        let text = wide(sddl);
        let mut descriptor: *mut c_void = std::ptr::null_mut();
        // SAFETY: as in `owner_only`.
        checked(unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                text.as_ptr(),
                SDDL_REVISION_1,
                &mut descriptor,
                std::ptr::null_mut(),
            )
        })
        .expect("descriptor");
        let descriptor = LocalMemory(descriptor);
        let attributes = SecurityAttributes {
            length: u32::try_from(size_of::<SecurityAttributes>()).expect("size"),
            descriptor: descriptor.0,
            inherit: 0,
        };
        let name = wide(name);
        // SAFETY: as in `claim`.
        let handle = unsafe {
            match kind {
                Kind::Mutex => CreateMutexW(&attributes, 0, name.as_ptr()),
                Kind::Event => CreateEventW(&attributes, EVENT_MANUAL_RESET, 0, name.as_ptr()),
            }
        };
        owned(handle).expect("squatting object")
    }

    #[test]
    fn ownership_is_compared_with_the_token_user() {
        let user = User::current().expect("user");
        let mine = squat(
            Kind::Event,
            &format!("Local\\cadrumo-manager-test.owned.{}", std::process::id()),
            &format!("O:{0}D:P(A;;GA;;;{0})", user.sid),
        );
        assert!(user.owns(&mine).expect("owner"));
        // A system file belongs to TrustedInstaller, never to this user.
        let system = std::env::var_os("SystemRoot").expect("SystemRoot");
        let foreign =
            std::fs::File::open(std::path::Path::new(&system).join("System32\\kernel32.dll"))
                .expect("system file");
        let foreign = OwnedHandle::from(foreign);
        assert!(!user.owns(&foreign).expect("owner"));
    }
}
