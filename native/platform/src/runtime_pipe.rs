//! The client side of the runtime's Windows named pipe, without its protocol.
//!
//! A runtime owns one pipe per storage root, named after the root's physical
//! identity and the account that owns it. This module connects to such a
//! pipe, verifies that the process on the other end is a live process of the
//! same account, and moves bytes across it under absolute deadlines. It also
//! reads the two facts a client needs before it connects or signs in: the
//! identity of a storage root, and the credential-store entry a stored
//! sign-in names. Frames, the handshake and every request belong to the
//! caller. Nothing here listens, starts or stops anything.

use std::{
    ffi::c_void,
    io,
    mem::size_of,
    os::windows::ffi::OsStrExt,
    path::{Path, PathBuf},
    ptr,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    time::Instant,
};

#[repr(C)]
#[derive(Default)]
struct Overlapped {
    internal: usize,
    internal_high: usize,
    offset: u32,
    offset_high: u32,
    event: *mut c_void,
}

#[repr(C)]
struct FileIdInformation {
    volume_serial_number: u64,
    file_id: [u8; 16],
}

#[repr(C)]
struct ByHandleFileInformation {
    attributes: u32,
    creation_time: [u32; 2],
    access_time: [u32; 2],
    write_time: [u32; 2],
    volume_serial_number: u32,
    size_high: u32,
    size_low: u32,
    links: u32,
    index_high: u32,
    index_low: u32,
}

#[repr(C)]
struct SidAndAttributes {
    sid: *mut c_void,
    attributes: u32,
}

#[repr(C)]
struct Credential {
    flags: u32,
    kind: u32,
    target_name: *mut u16,
    comment: *mut u16,
    last_written: u64,
    blob_size: u32,
    blob: *mut u8,
    persist: u32,
    attribute_count: u32,
    attributes: *mut c_void,
    target_alias: *mut u16,
    user_name: *mut u16,
}

#[link(name = "kernel32")]
unsafe extern "system" {
    fn CreateFileW(
        name: *const u16,
        access: u32,
        share: u32,
        attributes: *const c_void,
        creation: u32,
        flags: u32,
        template: *mut c_void,
    ) -> *mut c_void;
    fn SetEvent(event: *mut c_void) -> i32;
    fn WaitForMultipleObjects(
        count: u32,
        handles: *const *mut c_void,
        all: i32,
        milliseconds: u32,
    ) -> u32;
    fn GetNamedPipeServerProcessId(pipe: *mut c_void, process_id: *mut u32) -> i32;
    fn OpenProcess(access: u32, inherit: i32, process_id: u32) -> *mut c_void;
    fn GetCurrentProcess() -> *mut c_void;
    fn QueryFullProcessImageNameW(
        process: *mut c_void,
        flags: u32,
        name: *mut u16,
        size: *mut u32,
    ) -> i32;
    fn ReadFile(
        file: *mut c_void,
        buffer: *mut u8,
        size: u32,
        read: *mut u32,
        overlapped: *mut Overlapped,
    ) -> i32;
    fn WriteFile(
        file: *mut c_void,
        buffer: *const u8,
        size: u32,
        written: *mut u32,
        overlapped: *mut Overlapped,
    ) -> i32;
    fn GetOverlappedResult(
        file: *mut c_void,
        overlapped: *mut Overlapped,
        transferred: *mut u32,
        wait: i32,
    ) -> i32;
    fn CancelIoEx(file: *mut c_void, overlapped: *mut Overlapped) -> i32;
    fn CreateEventExW(
        attributes: *const c_void,
        name: *const u16,
        flags: u32,
        access: u32,
    ) -> *mut c_void;
    fn WaitForSingleObject(handle: *mut c_void, milliseconds: u32) -> u32;
    fn CloseHandle(handle: *mut c_void) -> i32;
    fn GetFileInformationByHandleEx(
        file: *mut c_void,
        class: i32,
        information: *mut c_void,
        size: u32,
    ) -> i32;
    fn GetFileInformationByHandle(
        file: *mut c_void,
        information: *mut ByHandleFileInformation,
    ) -> i32;
    fn LocalFree(memory: *mut c_void) -> *mut c_void;
}

#[repr(C)]
#[derive(Default)]
struct IoStatusBlock {
    status: usize,
    information: usize,
}

#[link(name = "ntdll")]
unsafe extern "system" {
    fn NtFsControlFile(
        file: *mut c_void,
        event: *mut c_void,
        apc: *mut c_void,
        context: *mut c_void,
        status: *mut IoStatusBlock,
        code: u32,
        input: *const u8,
        input_size: u32,
        output: *mut c_void,
        output_size: u32,
    ) -> i32;
    fn RtlNtStatusToDosError(status: i32) -> u32;
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
    fn CredReadW(
        target: *const u16,
        kind: u32,
        flags: u32,
        credential: *mut *mut Credential,
    ) -> i32;
    fn CredFree(buffer: *mut c_void);
}

const INVALID_HANDLE: isize = -1;
/// `FILE_READ_DATA | FILE_WRITE_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE | READ_CONTROL`:
/// the rights a client needs, without the generic rights that would also
/// admit creating a pipe instance.
const CLIENT_PIPE_ACCESS: u32 = 0x0012_0083;
const OPEN_EXISTING: u32 = 3;
const FILE_FLAG_OVERLAPPED: u32 = 0x4000_0000;
const FILE_FLAG_BACKUP_SEMANTICS: u32 = 0x0200_0000;
const SECURITY_SQOS_PRESENT: u32 = 0x0010_0000;
const SECURITY_IDENTIFICATION: u32 = 0x0001_0000;
const FILE_READ_ATTRIBUTES: u32 = 0x80;
const FILE_SHARE_ALL: u32 = 0x7;
const FILE_ID_INFO: i32 = 18;
const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x1000;
const SYNCHRONIZE: u32 = 0x0010_0000;
const TOKEN_QUERY: u32 = 0x0008;
const TOKEN_USER: i32 = 1;
const CRED_TYPE_GENERIC: u32 = 1;
const WAIT_OBJECT_0: u32 = 0;
const WAIT_TIMEOUT: u32 = 0x102;
const ERROR_FILE_NOT_FOUND: i32 = 2;
const ERROR_PIPE_BUSY: i32 = 231;
const ERROR_OPERATION_ABORTED: i32 = 995;
const ERROR_IO_PENDING: i32 = 997;
const CREATE_EVENT_MANUAL_RESET: u32 = 1;
const EVENT_ALL_ACCESS: u32 = 0x001F_0003;
const ERROR_NOT_FOUND: i32 = 1168;
// CTL_CODE(FILE_DEVICE_NAMED_PIPE, 6, METHOD_BUFFERED, FILE_ANY_ACCESS).
const FSCTL_PIPE_WAIT: u32 = 0x0011_0018;
/// The longest image path Windows reports, in UTF-16 units.
const IMAGE_PATH_UNITS: usize = 32_768;

fn wide(text: &str) -> Vec<u16> {
    text.encode_utf16().chain(std::iter::once(0)).collect()
}

fn wide_path(path: &Path) -> Vec<u16> {
    path.as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect()
}

fn checked(result: i32) -> io::Result<()> {
    if result == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

/// A kernel handle this module opened and closes exactly once.
#[derive(Debug)]
struct Handle(*mut c_void);

// SAFETY: a kernel object handle is a process-wide value any thread may use;
// `Handle` is its only closer.
unsafe impl Send for Handle {}
unsafe impl Sync for Handle {}

impl Handle {
    fn opened(raw: *mut c_void) -> io::Result<Self> {
        if raw.is_null() || raw as isize == INVALID_HANDLE {
            return Err(io::Error::last_os_error());
        }
        Ok(Self(raw))
    }
}

impl Drop for Handle {
    fn drop(&mut self) {
        // SAFETY: the handle was returned open by the kernel and is closed only here.
        unsafe {
            CloseHandle(self.0);
        }
    }
}

struct LocalMemory(*mut c_void);

impl Drop for LocalMemory {
    fn drop(&mut self) {
        // SAFETY: the pointer came from a LocalAlloc-backed conversion and is released once.
        unsafe {
            LocalFree(self.0);
        }
    }
}

/// A nul-terminated UTF-16 string the kernel wrote, copied out of its buffer.
///
/// # Safety
/// `text` points at a nul-terminated UTF-16 string that stays allocated for the call.
unsafe fn utf16_text(text: *const u16) -> io::Result<String> {
    if text.is_null() {
        return Ok(String::new());
    }
    // SAFETY: the caller guarantees a nul-terminated string behind `text`.
    let length = unsafe { (0..).take_while(|&i| *text.add(i) != 0).count() };
    // SAFETY: `length` units precede the terminator the scan stopped at.
    let units = unsafe { std::slice::from_raw_parts(text, length) };
    String::from_utf16(units).map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
}

/// The string form of the user SID of the token of `process`, which must be
/// open with `PROCESS_QUERY_LIMITED_INFORMATION`.
fn process_owner_sid(process: *mut c_void) -> io::Result<String> {
    let mut token = ptr::null_mut();
    // SAFETY: `process` is a live handle; the token handle the call writes is owned below.
    checked(unsafe { OpenProcessToken(process, TOKEN_QUERY, &mut token) })?;
    let token = Handle::opened(token)?;
    let mut needed = 0u32;
    // SAFETY: a null buffer of length zero asks only for the size.
    unsafe {
        GetTokenInformation(token.0, TOKEN_USER, ptr::null_mut(), 0, &mut needed);
    }
    if needed == 0 {
        return Err(io::Error::last_os_error());
    }
    let mut buffer = vec![0u64; (needed as usize).div_ceil(size_of::<u64>())];
    // SAFETY: the buffer is writable for the length passed and aligned for
    // `TOKEN_USER`, whose SID pointer then points inside it.
    checked(unsafe {
        GetTokenInformation(
            token.0,
            TOKEN_USER,
            buffer.as_mut_ptr().cast(),
            (buffer.len() * size_of::<u64>()) as u32,
            &mut needed,
        )
    })?;
    // SAFETY: the buffer holds the `TOKEN_USER` the system wrote, whose first
    // field is a `SID_AND_ATTRIBUTES`.
    let sid = unsafe { (*buffer.as_ptr().cast::<SidAndAttributes>()).sid };
    let mut text = ptr::null_mut();
    // SAFETY: `sid` points into the live buffer; the call writes a
    // nul-terminated LocalAlloc string, released after the copy.
    unsafe {
        checked(ConvertSidToStringSidW(sid, &mut text))?;
        let _text = LocalMemory(text.cast());
        utf16_text(text)
    }
}

/// The string form of this process's user SID.
pub fn current_user_sid() -> io::Result<String> {
    // SAFETY: the pseudo handle needs no closing.
    process_owner_sid(unsafe { GetCurrentProcess() })
}

fn process_image_path(process: *mut c_void) -> io::Result<PathBuf> {
    let mut buffer = vec![0u16; IMAGE_PATH_UNITS];
    let mut size = buffer.len() as u32;
    // SAFETY: the buffer is writable for `size` units, which the call updates
    // to the length it wrote.
    checked(unsafe { QueryFullProcessImageNameW(process, 0, buffer.as_mut_ptr(), &mut size) })?;
    let units = buffer.get(..size as usize).unwrap_or_default();
    String::from_utf16(units)
        .map(PathBuf::from)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
}

/// What a storage root's physical identity is made of, as the runtime and its
/// Python clients read it: the owning account, the volume and the file id.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StorageIdentity {
    pub owner_sid: String,
    pub volume_serial_number: u64,
    pub file_id: u128,
}

impl StorageIdentity {
    /// The text every peer hashes into the endpoint name: `owner:volume:file`,
    /// each number in decimal.
    pub fn text(&self) -> String {
        format!(
            "{}:{}:{}",
            self.owner_sid, self.volume_serial_number, self.file_id
        )
    }
}

/// The identity of the directory `root`, followed through links as the
/// runtime follows it. The 128-bit file identity is read where the volume
/// reports one; elsewhere the 64-bit index stands in, as it does for the
/// runtime's own reading.
pub fn storage_identity(root: &Path) -> io::Result<StorageIdentity> {
    let canonical = root.canonicalize()?;
    if !canonical.is_dir() {
        return Err(io::ErrorKind::NotADirectory.into());
    }
    let name = wide_path(&canonical);
    // SAFETY: the name is nul-terminated; the handle is owned below. Backup
    // semantics are what opening a directory requires.
    let directory = Handle::opened(unsafe {
        CreateFileW(
            name.as_ptr(),
            FILE_READ_ATTRIBUTES,
            FILE_SHARE_ALL,
            ptr::null(),
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            ptr::null_mut(),
        )
    })?;
    let mut extended = FileIdInformation {
        volume_serial_number: 0,
        file_id: [0; 16],
    };
    // SAFETY: the record is writable for its declared size.
    let (volume_serial_number, file_id) = if unsafe {
        GetFileInformationByHandleEx(
            directory.0,
            FILE_ID_INFO,
            (&raw mut extended).cast(),
            size_of::<FileIdInformation>() as u32,
        )
    } != 0
    {
        (
            extended.volume_serial_number,
            u128::from_le_bytes(extended.file_id),
        )
    } else {
        let mut basic = ByHandleFileInformation {
            attributes: 0,
            creation_time: [0; 2],
            access_time: [0; 2],
            write_time: [0; 2],
            volume_serial_number: 0,
            size_high: 0,
            size_low: 0,
            links: 0,
            index_high: 0,
            index_low: 0,
        };
        // SAFETY: the record is writable and has the API's layout.
        checked(unsafe { GetFileInformationByHandle(directory.0, &mut basic) })?;
        (
            u64::from(basic.volume_serial_number),
            u128::from((u64::from(basic.index_high) << 32) | u64::from(basic.index_low)),
        )
    };
    Ok(StorageIdentity {
        owner_sid: current_user_sid()?,
        volume_serial_number,
        file_id,
    })
}

/// The process behind a connected pipe, read from the kernel, never from the wire.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Peer {
    pub process_id: u32,
    pub owner_sid: String,
    pub image: PathBuf,
}

/// Why a connection could not be made.
#[derive(Debug)]
pub enum ConnectRefusal {
    /// No pipe of that name exists, or none of its instances became free in time.
    NotReady,
    /// The pipe's server is not a live process of the expected account.
    PeerUntrusted,
    /// The deadline passed before the pipe answered.
    Deadline,
    Cancelled,
    Failed(io::Error),
}

impl std::fmt::Display for ConnectRefusal {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotReady => formatter.write_str("runtime endpoint not ready"),
            Self::PeerUntrusted => formatter.write_str("runtime peer untrusted"),
            Self::Deadline => formatter.write_str("runtime connect deadline exceeded"),
            Self::Cancelled => formatter.write_str("runtime connect cancelled"),
            Self::Failed(error) => write!(formatter, "runtime connect failed: {error}"),
        }
    }
}

impl std::error::Error for ConnectRefusal {}

fn remaining_milliseconds(deadline: Instant) -> Option<u32> {
    let remaining = deadline.checked_duration_since(Instant::now())?;
    Some(remaining.as_millis().min(u128::from(u32::MAX - 1)) as u32)
}

/// An owned, persistent cancellation signal, registered before connecting.
#[derive(Debug)]
pub struct ConnectCancellation {
    event: Handle,
    cancelled: AtomicBool,
}

impl ConnectCancellation {
    pub fn new() -> io::Result<Self> {
        // SAFETY: an unnamed manual-reset event, retained for every observing I/O.
        let event = Handle::opened(unsafe {
            CreateEventExW(
                ptr::null(),
                ptr::null(),
                CREATE_EVENT_MANUAL_RESET,
                EVENT_ALL_ACCESS,
            )
        })?;
        Ok(Self {
            event,
            cancelled: AtomicBool::new(false),
        })
    }

    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Release);
        // SAFETY: this owned event remains live until every observing operation settles.
        unsafe {
            SetEvent(self.event.0);
        }
    }

    pub fn cancelled(&self) -> bool {
        self.cancelled.load(Ordering::Acquire)
    }
}

/// Wait once on the named-pipe filesystem's availability notification. Unlike
/// WaitNamedPipe, asynchronous FSCTL_PIPE_WAIT can share the owner's cancellation.
fn wait_available(
    name: &str,
    deadline: Instant,
    cancellation: &ConnectCancellation,
) -> io::Result<()> {
    wait_available_observed(name, deadline, cancellation, || {})
}

fn wait_available_observed(
    name: &str,
    deadline: Instant,
    cancellation: &ConnectCancellation,
    pending: impl FnOnce(),
) -> io::Result<()> {
    let pipe_name = name
        .strip_prefix(r"\\.\pipe\")
        .ok_or(io::ErrorKind::InvalidInput)?;
    let root = wide(r"\\.\pipe\");
    // SAFETY: an asynchronous handle to the local named-pipe filesystem root.
    let root = Handle::opened(unsafe {
        CreateFileW(
            root.as_ptr(),
            FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            FILE_SHARE_ALL,
            ptr::null(),
            OPEN_EXISTING,
            FILE_FLAG_OVERLAPPED,
            ptr::null_mut(),
        )
    })?;
    let event = Handle::opened(unsafe {
        // SAFETY: an unnamed manual-reset completion event owned through settlement.
        CreateEventExW(
            ptr::null(),
            ptr::null(),
            CREATE_EVENT_MANUAL_RESET,
            EVENT_ALL_ACCESS,
        )
    })?;
    let name: Vec<u16> = pipe_name.encode_utf16().collect();
    let mut input = Vec::with_capacity(14 + name.len() * 2);
    // Local NPFS substitutes the server default when TimeoutSpecified is
    // false. Pass the same owner's remaining timeout in NT relative 100 ns
    // units; the completion wait below still uses the original deadline.
    let remaining = deadline
        .checked_duration_since(Instant::now())
        .ok_or(io::ErrorKind::TimedOut)?;
    if remaining.is_zero() {
        return Err(io::ErrorKind::TimedOut.into());
    }
    let timeout = -i64::try_from(remaining.as_nanos().div_ceil(100)).unwrap_or(i64::MAX);
    input.extend_from_slice(&timeout.to_le_bytes());
    input.extend_from_slice(
        &(u32::try_from(name.len() * 2).map_err(|_| io::ErrorKind::InvalidInput)?).to_le_bytes(),
    );
    input.extend_from_slice(&[1, 0]);
    for unit in name {
        input.extend_from_slice(&unit.to_le_bytes());
    }
    let mut status = IoStatusBlock::default();
    // SAFETY: the input/status/event stay owned until completion, including cancellation.
    let result = unsafe {
        NtFsControlFile(
            root.0,
            event.0,
            ptr::null_mut(),
            ptr::null_mut(),
            &mut status,
            FSCTL_PIPE_WAIT,
            input.as_ptr(),
            input.len() as u32,
            ptr::null_mut(),
            0,
        )
    };
    if result == 0x103 {
        pending();
        // STATUS_PENDING
        let handles = [cancellation.event.0, event.0];
        let milliseconds = remaining_milliseconds(deadline).unwrap_or(0);
        // SAFETY: both events remain retained until this request settles.
        let wake = unsafe { WaitForMultipleObjects(2, handles.as_ptr(), 0, milliseconds) };
        if wake != WAIT_OBJECT_0 + 1 {
            let failure = match wake {
                WAIT_OBJECT_0 => io::ErrorKind::ConnectionAborted.into(),
                WAIT_TIMEOUT => io::ErrorKind::TimedOut.into(),
                _ => io::Error::last_os_error(),
            };
            // SAFETY: this root handle owns only this request. Await cancellation
            // before releasing the input or status memory the kernel can write.
            unsafe {
                CancelIoEx(root.0, ptr::null_mut());
                WaitForSingleObject(event.0, u32::MAX);
            }
            return Err(failure);
        }
    } else if result < 0 {
        // SAFETY: conversion of the returned NTSTATUS carries no ownership.
        return Err(io::Error::from_raw_os_error(
            unsafe { RtlNtStatusToDosError(result) } as i32,
        ));
    }
    let result = status.status as i32;
    if result < 0 {
        // SAFETY: the operation settled before its NTSTATUS is inspected.
        return Err(io::Error::from_raw_os_error(
            unsafe { RtlNtStatusToDosError(result) } as i32,
        ));
    }
    Ok(())
}

/// One connected pipe: bounded reads and writes from any thread, and a close
/// that ends a read another thread is blocked in.
#[derive(Debug)]
pub struct Pipe {
    handle: Mutex<Option<Arc<Handle>>>,
    cancellation: Arc<ConnectCancellation>,
    process: Handle,
    peer: Peer,
}

impl Pipe {
    /// Connects to `name` before `deadline` and verifies its server as a live
    /// process owned by `expected_owner`. A busy pipe is waited for within the
    /// deadline; an absent one is reported as not ready, never created.
    pub fn connect(
        name: &str,
        expected_owner: &str,
        deadline: Instant,
    ) -> Result<Self, ConnectRefusal> {
        Self::connect_cancellable(
            name,
            expected_owner,
            deadline,
            Arc::new(ConnectCancellation::new().map_err(ConnectRefusal::Failed)?),
        )
    }

    pub fn connect_cancellable(
        name: &str,
        expected_owner: &str,
        deadline: Instant,
        cancellation: Arc<ConnectCancellation>,
    ) -> Result<Self, ConnectRefusal> {
        let wide_name = wide(name);
        let handle = loop {
            if cancellation.cancelled() {
                return Err(ConnectRefusal::Cancelled);
            }
            // SAFETY: the name is nul-terminated and the attributes and
            // template are absent; the handle is owned below.
            let raw = unsafe {
                CreateFileW(
                    wide_name.as_ptr(),
                    CLIENT_PIPE_ACCESS,
                    0,
                    ptr::null(),
                    OPEN_EXISTING,
                    FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION,
                    ptr::null_mut(),
                )
            };
            match Handle::opened(raw) {
                Ok(handle) => break handle,
                Err(error) => match error.raw_os_error() {
                    Some(ERROR_PIPE_BUSY) => {
                        wait_available(name, deadline, &cancellation).map_err(|error| {
                            if cancellation.cancelled() {
                                ConnectRefusal::Cancelled
                            } else if error.kind() == io::ErrorKind::TimedOut {
                                ConnectRefusal::Deadline
                            } else if error.raw_os_error() == Some(ERROR_FILE_NOT_FOUND) {
                                ConnectRefusal::NotReady
                            } else {
                                ConnectRefusal::Failed(error)
                            }
                        })?;
                    }
                    Some(ERROR_FILE_NOT_FOUND) => return Err(ConnectRefusal::NotReady),
                    _ => return Err(ConnectRefusal::PeerUntrusted),
                },
            }
        };
        let mut process_id = 0u32;
        // SAFETY: `handle` is a connected pipe; the id is written to a local.
        if unsafe { GetNamedPipeServerProcessId(handle.0, &mut process_id) } == 0 || process_id == 0
        {
            return Err(ConnectRefusal::PeerUntrusted);
        }
        // SAFETY: opens a query-only, synchronizable handle; no control rights.
        let process = Handle::opened(unsafe {
            OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                0,
                process_id,
            )
        })
        .map_err(|_| ConnectRefusal::PeerUntrusted)?;
        let owner_sid = process_owner_sid(process.0).map_err(|_| ConnectRefusal::PeerUntrusted)?;
        // SAFETY: a zero wait on a live process handle reports only its state.
        if owner_sid != expected_owner
            || unsafe { WaitForSingleObject(process.0, 0) } != WAIT_TIMEOUT
        {
            return Err(ConnectRefusal::PeerUntrusted);
        }
        let image = process_image_path(process.0).map_err(|_| ConnectRefusal::PeerUntrusted)?;
        Ok(Self {
            handle: Mutex::new(Some(Arc::new(handle))),
            cancellation,
            process,
            peer: Peer {
                process_id,
                owner_sid,
                image,
            },
        })
    }

    pub fn peer(&self) -> &Peer {
        &self.peer
    }

    /// Whether the verified server process still runs.
    pub fn peer_alive(&self) -> bool {
        // SAFETY: a zero wait on the retained process handle reports only its state.
        unsafe { WaitForSingleObject(self.process.0, 0) == WAIT_TIMEOUT }
    }

    fn retained_handle(&self) -> io::Result<Arc<Handle>> {
        self.handle
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .as_ref()
            .cloned()
            .ok_or_else(|| io::ErrorKind::ConnectionAborted.into())
    }

    /// Fills `buffer` before `deadline`; a peer that closes first is an unexpected end.
    pub fn read_exact(&self, buffer: &mut [u8], deadline: Instant) -> io::Result<()> {
        self.read_until(buffer, Some(deadline))
    }

    /// Waits for input or closure without a periodic timer. Protocol callers
    /// use this for the first byte only, then bound the remainder of a frame.
    pub fn read_idle_byte(&self, byte: &mut u8) -> io::Result<()> {
        self.read_until(std::slice::from_mut(byte), None)
    }

    fn read_until(&self, buffer: &mut [u8], deadline: Option<Instant>) -> io::Result<()> {
        let retained = self.retained_handle()?;
        let handle = retained.0;
        let mut filled = 0usize;
        while filled < buffer.len() {
            let remaining = &mut buffer[filled..];
            let size = remaining.len().min(u32::MAX as usize) as u32;
            let received = transfer(handle, deadline, &self.cancellation, |overlapped| {
                // SAFETY: the buffer outlives the operation, which `transfer`
                // settles before it returns.
                unsafe {
                    ReadFile(
                        handle,
                        remaining.as_mut_ptr(),
                        size,
                        ptr::null_mut(),
                        overlapped,
                    )
                }
            })?;
            if received == 0 {
                return Err(io::ErrorKind::UnexpectedEof.into());
            }
            filled += received as usize;
        }
        Ok(())
    }

    /// Writes all of `bytes` before `deadline`.
    pub fn write_all(&self, bytes: &[u8], deadline: Instant) -> io::Result<()> {
        self.write_until(bytes, Some(deadline))
    }

    /// Writes all of `bytes` for as long as the connection lives. A peer that
    /// stops reading holds the write; the peer's end fails it, and a close
    /// from any thread ends it.
    pub fn write_all_while_open(&self, bytes: &[u8]) -> io::Result<()> {
        self.write_until(bytes, None)
    }

    fn write_until(&self, bytes: &[u8], deadline: Option<Instant>) -> io::Result<()> {
        let retained = self.retained_handle()?;
        let handle = retained.0;
        let mut written = 0usize;
        while written < bytes.len() {
            let remaining = &bytes[written..];
            let size = remaining.len().min(u32::MAX as usize) as u32;
            let sent = transfer(handle, deadline, &self.cancellation, |overlapped| {
                // SAFETY: the bytes outlive the operation, which `transfer`
                // settles before it returns.
                unsafe {
                    WriteFile(
                        handle,
                        remaining.as_ptr(),
                        size,
                        ptr::null_mut(),
                        overlapped,
                    )
                }
            })?;
            if sent == 0 {
                return Err(io::ErrorKind::WriteZero.into());
            }
            written += sent as usize;
        }
        Ok(())
    }

    /// Ends every pending transfer and releases the pipe; later calls report
    /// an aborted connection. The verified peer process stays observable.
    pub fn close(&self) {
        self.cancellation.cancel();
        let taken = self
            .handle
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .take();
        if let Some(handle) = taken {
            // SAFETY: cancelling this process's own operations on a handle it
            // still holds; the handle closes when `handle` drops.
            unsafe {
                CancelIoEx(handle.0, ptr::null_mut());
            }
        }
    }
}

impl Drop for Pipe {
    fn drop(&mut self) {
        self.close();
    }
}

/// Runs one overlapped operation to completion within `deadline`, returning
/// the bytes transferred. A deadline cancels the operation and waits for the
/// cancellation to settle, so the caller's buffer is free once this returns.
fn transfer(
    handle: *mut c_void,
    deadline: Option<Instant>,
    cancellation: &ConnectCancellation,
    start: impl FnOnce(*mut Overlapped) -> i32,
) -> io::Result<u32> {
    if cancellation.cancelled() {
        return Err(io::ErrorKind::ConnectionAborted.into());
    }
    // SAFETY: an anonymous manual-reset event, owned for the operation.
    let event = Handle::opened(unsafe {
        CreateEventExW(
            ptr::null(),
            ptr::null(),
            CREATE_EVENT_MANUAL_RESET,
            EVENT_ALL_ACCESS,
        )
    })?;
    let mut overlapped = Overlapped {
        event: event.0,
        ..Overlapped::default()
    };
    if start(&mut overlapped) == 0 {
        let error = io::Error::last_os_error();
        if error.raw_os_error() != Some(ERROR_IO_PENDING) {
            return Err(error);
        }
        let milliseconds =
            deadline.map_or(u32::MAX, |end| remaining_milliseconds(end).unwrap_or(0));
        let events = [cancellation.event.0, event.0];
        // SAFETY: both events remain retained until this operation settles.
        let wake = unsafe { WaitForMultipleObjects(2, events.as_ptr(), 0, milliseconds) };
        if wake != WAIT_OBJECT_0 + 1 {
            let failure = match wake {
                WAIT_OBJECT_0 => io::ErrorKind::ConnectionAborted.into(),
                WAIT_TIMEOUT => io::ErrorKind::TimedOut.into(),
                _ => io::Error::last_os_error(),
            };
            let mut settled = 0u32;
            // SAFETY: the operation is cancelled and then awaited, so no
            // completion can touch the caller's buffer after this returns.
            unsafe {
                CancelIoEx(handle, &mut overlapped);
                GetOverlappedResult(handle, &mut overlapped, &mut settled, 1);
            }
            return Err(failure);
        }
    }
    let mut transferred = 0u32;
    // SAFETY: the operation has signalled; this reads its result.
    checked(unsafe { GetOverlappedResult(handle, &mut overlapped, &mut transferred, 1) }).map_err(
        |error| {
            // A close from another thread cancels the operation; that is the
            // connection ending, never a deadline.
            if error.raw_os_error() == Some(ERROR_OPERATION_ABORTED) {
                io::ErrorKind::ConnectionAborted.into()
            } else {
                error
            }
        },
    )?;
    Ok(transferred)
}

/// One generic credential, as the credential store holds it.
pub struct StoredCredential {
    pub user_name: String,
    pub blob: Vec<u8>,
}

/// Reads this user's generic credential `target`, or `None` when the store
/// holds none. The blob is returned as stored; the caller owns its lifetime.
pub fn read_generic_credential(target: &str) -> io::Result<Option<StoredCredential>> {
    let wide_target = wide(target);
    let mut credential: *mut Credential = ptr::null_mut();
    // SAFETY: the target is nul-terminated; the call allocates the record,
    // released below with `CredFree`.
    if unsafe { CredReadW(wide_target.as_ptr(), CRED_TYPE_GENERIC, 0, &mut credential) } == 0 {
        let error = io::Error::last_os_error();
        return if error.raw_os_error() == Some(ERROR_NOT_FOUND) {
            Ok(None)
        } else {
            Err(error)
        };
    }
    struct Freed(*mut Credential);
    impl Drop for Freed {
        fn drop(&mut self) {
            // SAFETY: the record came from `CredReadW` and is released once.
            unsafe { CredFree(self.0.cast()) }
        }
    }
    let freed = Freed(credential);
    // SAFETY: `CredReadW` succeeded, so the record is readable until it is freed.
    let (user_name, blob) = unsafe {
        let record = &*freed.0;
        let blob = if record.blob.is_null() || record.blob_size == 0 {
            Vec::new()
        } else {
            std::slice::from_raw_parts(record.blob, record.blob_size as usize).to_vec()
        };
        (utf16_text(record.user_name)?, blob)
    };
    Ok(Some(StoredCredential { user_name, blob }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateNamedPipeW(
            name: *const u16,
            open_mode: u32,
            pipe_mode: u32,
            instances: u32,
            out_buffer: u32,
            in_buffer: u32,
            default_timeout: u32,
            attributes: *const c_void,
        ) -> *mut c_void;
        fn ConnectNamedPipe(pipe: *mut c_void, overlapped: *mut Overlapped) -> i32;
        fn DisconnectNamedPipe(pipe: *mut c_void) -> i32;
        fn WaitNamedPipeW(name: *const u16, milliseconds: u32) -> i32;
        fn GetCurrentProcessId() -> u32;
    }

    const PIPE_ACCESS_DUPLEX: u32 = 3;
    const FILE_FLAG_FIRST_PIPE_INSTANCE: u32 = 0x0008_0000;
    const PIPE_REJECT_REMOTE_CLIENTS: u32 = 0x8;
    const ERROR_NO_DATA: i32 = 232;
    const ERROR_PIPE_CONNECTED: i32 = 535;

    /// A one-instance byte pipe this test process serves synchronously.
    struct Server(Handle);

    impl Server {
        fn listen(name: &str) -> Self {
            Self::listen_with_timeout(name, 0)
        }

        fn listen_with_timeout(name: &str, default_timeout: u32) -> Self {
            let wide_name = wide(name);
            // SAFETY: a fresh first instance with default security; owned by `Handle`.
            let handle = Handle::opened(unsafe {
                CreateNamedPipeW(
                    wide_name.as_ptr(),
                    PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
                    PIPE_REJECT_REMOTE_CLIENTS,
                    1,
                    65_536,
                    65_536,
                    default_timeout,
                    ptr::null(),
                )
            })
            .expect("create the test pipe");
            Self(handle)
        }

        fn accept(&self) {
            // SAFETY: a synchronous connect on a non-overlapped instance.
            // A client that connected and left before this accept is also a connection.
            if unsafe { ConnectNamedPipe(self.0.0, ptr::null_mut()) } == 0 {
                assert!(matches!(
                    io::Error::last_os_error().raw_os_error(),
                    Some(ERROR_PIPE_CONNECTED | ERROR_NO_DATA)
                ));
            }
        }

        fn read(&self, count: usize) -> Vec<u8> {
            let mut buffer = vec![0u8; count];
            let mut filled = 0;
            while filled < count {
                let mut read = 0u32;
                // SAFETY: synchronous read into a buffer that outlives the call.
                checked(unsafe {
                    ReadFile(
                        self.0.0,
                        buffer[filled..].as_mut_ptr(),
                        (count - filled) as u32,
                        &mut read,
                        ptr::null_mut(),
                    )
                })
                .expect("server read");
                assert!(read > 0, "client closed early");
                filled += read as usize;
            }
            buffer
        }

        fn write(&self, bytes: &[u8]) {
            let mut written = 0u32;
            // SAFETY: synchronous write of a buffer that outlives the call.
            checked(unsafe {
                WriteFile(
                    self.0.0,
                    bytes.as_ptr(),
                    bytes.len() as u32,
                    &mut written,
                    ptr::null_mut(),
                )
            })
            .expect("server write");
            assert_eq!(written as usize, bytes.len());
        }
    }

    fn pipe_name(tag: &str) -> String {
        // SAFETY: no arguments; the id of this process.
        let process = unsafe { GetCurrentProcessId() };
        format!(r"\\.\pipe\cadrumo-platform-test-{tag}-{process}")
    }

    fn soon() -> Instant {
        Instant::now() + Duration::from_secs(5)
    }

    #[test]
    fn a_busy_pipe_wait_survives_the_server_default_and_connects_on_availability() {
        let name = pipe_name("busy-available");
        let server = Arc::new(Server::listen_with_timeout(&name, 1));
        let pipe = Pipe::connect(&name, &current_user_sid().unwrap(), soon()).unwrap();
        server.accept();
        let cancellation = Arc::new(ConnectCancellation::new().unwrap());
        let (pending, reached) = std::sync::mpsc::channel();
        let (answer, answered) = std::sync::mpsc::channel();
        let (release, released) = std::sync::mpsc::channel();
        let waiter = {
            let name = name.clone();
            let cancellation = cancellation.clone();
            std::thread::spawn(move || {
                let result = wait_available_observed(&name, soon(), &cancellation, || {
                    pending.send(()).unwrap();
                })
                .and_then(|()| {
                    Pipe::connect(&name, &current_user_sid().unwrap(), soon())
                        .map_err(|_| io::ErrorKind::ConnectionRefused.into())
                });
                let _ = answer.send(result.as_ref().map(|_| ()).map_err(|error| error.kind()));
                let _ = released.recv();
                drop(result);
            })
        };
        reached.recv_timeout(Duration::from_secs(5)).unwrap();
        // This guard deliberately exceeds the server's 1 ms default. There
        // is no producer signal yet, so a normal timeout must not finish it.
        let early = answered.recv_timeout(Duration::from_millis(50));
        // SAFETY: the exact test-owned instance is connected to `pipe`.
        checked(unsafe { DisconnectNamedPipe(server.0.0) }).unwrap();
        drop(pipe);
        let acceptor = {
            let server = server.clone();
            std::thread::spawn(move || server.accept())
        };
        let result = match early {
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                answered.recv_timeout(Duration::from_secs(5))
            }
            other => other,
        };
        let fallback = if !matches!(result, Ok(Ok(()))) {
            cancellation.cancel();
            // Cleanup uses the independent Win32 wait, so the assertion below
            // still detects a wrong production filesystem control.
            checked(unsafe { WaitNamedPipeW(wide(&name).as_ptr(), 5000) }).unwrap();
            Some(Pipe::connect(&name, &current_user_sid().unwrap(), soon()).unwrap())
        } else {
            None
        };
        release.send(()).unwrap();
        waiter.join().unwrap();
        acceptor.join().unwrap();
        drop(fallback);
        assert_eq!(result.unwrap(), Ok(()));
    }

    #[test]
    fn a_busy_pipe_wait_is_cancelled_before_its_wait_starts() {
        let name = pipe_name("cancel-busy");
        let server = Server::listen(&name);
        let pipe = Pipe::connect(&name, &current_user_sid().unwrap(), soon()).unwrap();
        server.accept();
        let cancellation = Arc::new(ConnectCancellation::new().unwrap());
        let (pending, reached) = std::sync::mpsc::channel();
        let (resume, resumed) = std::sync::mpsc::channel();
        let (answer, answered) = std::sync::mpsc::channel();
        let waiter = {
            let cancellation = cancellation.clone();
            std::thread::spawn(move || {
                let result = wait_available_observed(
                    &name,
                    Instant::now() + Duration::from_secs(600),
                    &cancellation,
                    || {
                        pending.send(()).unwrap();
                        let _ = resumed.recv();
                    },
                );
                answer.send(result.map_err(|error| error.kind())).unwrap();
            })
        };
        reached.recv_timeout(Duration::from_secs(5)).unwrap();
        cancellation.cancel();
        resume.send(()).unwrap();
        assert_eq!(
            answered.recv_timeout(Duration::from_secs(5)).unwrap(),
            Err(io::ErrorKind::ConnectionAborted)
        );
        waiter.join().unwrap();
        drop(pipe);
        drop(server);
    }

    #[test]
    fn a_client_exchanges_bytes_with_a_verified_same_account_server() {
        let name = pipe_name("exchange");
        let server = Server::listen(&name);
        let serving = std::thread::spawn(move || {
            server.accept();
            let received = server.read(5);
            server.write(b"pong!");
            received
        });
        let owner = current_user_sid().unwrap();
        let pipe = Pipe::connect(&name, &owner, soon()).unwrap();
        // SAFETY: no arguments; the id of this process.
        assert_eq!(pipe.peer().process_id, unsafe { GetCurrentProcessId() });
        assert_eq!(pipe.peer().owner_sid, owner);
        assert_eq!(
            pipe.peer().image.canonicalize().unwrap(),
            std::env::current_exe().unwrap().canonicalize().unwrap()
        );
        assert!(pipe.peer_alive());
        pipe.write_all(b"ping!", soon()).unwrap();
        let mut reply = [0u8; 5];
        pipe.read_exact(&mut reply, soon()).unwrap();
        assert_eq!(&reply, b"pong!");
        assert_eq!(serving.join().unwrap(), b"ping!");
        // The server dropped its instance: the next read ends, it does not hang.
        let mut more = [0u8; 1];
        let ended = pipe.read_exact(&mut more, soon()).unwrap_err();
        assert!(
            matches!(
                ended.kind(),
                io::ErrorKind::UnexpectedEof | io::ErrorKind::BrokenPipe
            ) || ended.raw_os_error().is_some(),
            "{ended}"
        );
    }

    #[test]
    fn another_accounts_server_and_an_absent_pipe_are_refused() {
        let name = pipe_name("owner");
        let server = Server::listen(&name);
        let serving = std::thread::spawn(move || {
            server.accept();
            // Hold the instance until the client has judged it.
            std::thread::sleep(Duration::from_millis(200));
        });
        let refused = Pipe::connect(&name, "S-1-5-21-0-0-0-9999", soon()).unwrap_err();
        assert!(
            matches!(refused, ConnectRefusal::PeerUntrusted),
            "{refused}"
        );
        serving.join().unwrap();
        let absent = Pipe::connect(&pipe_name("absent"), "S-1-0-0", soon()).unwrap_err();
        assert!(matches!(absent, ConnectRefusal::NotReady), "{absent}");
    }

    #[test]
    fn a_read_past_its_deadline_times_out_and_a_close_ends_a_pending_read() {
        let name = pipe_name("deadline");
        let server = Server::listen(&name);
        let (release, released) = std::sync::mpsc::channel::<()>();
        let serving = std::thread::spawn(move || {
            server.accept();
            // Keep the instance open and silent until the client is done.
            let _ = released.recv();
        });
        let owner = current_user_sid().unwrap();
        let pipe = std::sync::Arc::new(Pipe::connect(&name, &owner, soon()).unwrap());
        let mut byte = [0u8; 1];
        let started = Instant::now();
        let timed_out = pipe
            .read_exact(&mut byte, Instant::now() + Duration::from_millis(150))
            .unwrap_err();
        assert_eq!(timed_out.kind(), io::ErrorKind::TimedOut);
        assert!(started.elapsed() < Duration::from_secs(3));

        let reader = {
            let pipe = pipe.clone();
            std::thread::spawn(move || {
                let mut byte = 0;
                pipe.read_idle_byte(&mut byte)
            })
        };
        std::thread::sleep(Duration::from_millis(100));
        pipe.close();
        let ended = reader.join().unwrap().unwrap_err();
        assert_eq!(ended.kind(), io::ErrorKind::ConnectionAborted, "{ended}");
        assert_eq!(
            pipe.write_all(b"x", soon()).unwrap_err().kind(),
            io::ErrorKind::ConnectionAborted
        );
        release.send(()).unwrap();
        serving.join().unwrap();
    }

    #[test]
    fn a_write_the_peer_holds_waits_until_a_close_or_the_peers_end() {
        let name = pipe_name("held-write");
        let server = Server::listen(&name);
        let (drop_instance, dropped) = std::sync::mpsc::channel::<()>();
        let serving = std::thread::spawn(move || {
            server.accept();
            // Read nothing, so the client's writes fill the pipe and wait.
            let _ = dropped.recv();
            drop(server);
        });
        let owner = current_user_sid().unwrap();
        let pipe = std::sync::Arc::new(Pipe::connect(&name, &owner, soon()).unwrap());
        // More than the pipe's buffers hold, so the write must wait for a reader.
        let bytes = vec![7u8; 1 << 20];
        let write = |pipe: std::sync::Arc<Pipe>| {
            let bytes = bytes.clone();
            let (done, finished) = std::sync::mpsc::channel();
            std::thread::spawn(move || {
                let _ = done.send(pipe.write_all_while_open(&bytes));
            });
            finished
        };
        let finished = write(pipe.clone());
        assert!(
            finished.recv_timeout(Duration::from_millis(300)).is_err(),
            "a peer that does not read holds the write"
        );
        drop_instance.send(()).unwrap();
        serving.join().unwrap();
        let ended = finished
            .recv_timeout(Duration::from_secs(3))
            .expect("the peer's end fails the held write")
            .unwrap_err();
        assert_ne!(ended.kind(), io::ErrorKind::TimedOut, "{ended}");

        let name = pipe_name("held-write-close");
        let server = Server::listen(&name);
        let (release, released) = std::sync::mpsc::channel::<()>();
        let serving = std::thread::spawn(move || {
            server.accept();
            let _ = released.recv();
        });
        let pipe = std::sync::Arc::new(Pipe::connect(&name, &owner, soon()).unwrap());
        let finished = write(pipe.clone());
        assert!(finished.recv_timeout(Duration::from_millis(300)).is_err());
        pipe.close();
        let ended = finished
            .recv_timeout(Duration::from_secs(3))
            .expect("a close ends the held write")
            .unwrap_err();
        assert_eq!(ended.kind(), io::ErrorKind::ConnectionAborted, "{ended}");
        release.send(()).unwrap();
        serving.join().unwrap();
    }

    #[test]
    fn a_directorys_identity_is_stable_and_distinguishes_directories() {
        let base = std::env::temp_dir().join(format!(
            "cadrumo-platform-identity-{}",
            // SAFETY: no arguments; the id of this process.
            unsafe { GetCurrentProcessId() }
        ));
        let first = base.join("first");
        let second = base.join("second");
        std::fs::create_dir_all(&first).unwrap();
        std::fs::create_dir_all(&second).unwrap();
        let identity = storage_identity(&first).unwrap();
        assert_eq!(identity, storage_identity(&first).unwrap());
        assert_ne!(identity, storage_identity(&second).unwrap());
        assert_eq!(identity.owner_sid, current_user_sid().unwrap());
        assert!(identity.owner_sid.starts_with("S-1-"));
        let text = identity.text();
        assert_eq!(
            text.split(':').count(),
            2 + identity.owner_sid.matches(':').count() + 1
        );
        assert!(storage_identity(&base.join("missing")).is_err());
        let _ = std::fs::remove_dir_all(&base);
        // The runtime's own reading of a root, when a run supplies it:
        // CADRUMO_PLATFORM_IDENTITY_CHECK=<path>|<st_dev>|<st_ino> from Python's os.stat.
        if let Ok(check) = std::env::var("CADRUMO_PLATFORM_IDENTITY_CHECK") {
            let parts: Vec<&str> = check.split('|').collect();
            let observed = storage_identity(Path::new(parts[0])).unwrap();
            assert_eq!(observed.volume_serial_number.to_string(), parts[1]);
            assert_eq!(observed.file_id.to_string(), parts[2]);
        }
    }

    #[test]
    fn an_absent_credential_is_none() {
        let target = format!(
            "cadrumo-platform-test:absent:{}",
            // SAFETY: no arguments; the id of this process.
            unsafe { GetCurrentProcessId() }
        );
        assert!(read_generic_credential(&target).unwrap().is_none());
    }
}
