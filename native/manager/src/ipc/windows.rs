//! Bounded, owner/session-qualified Windows manager pipe.
#![allow(unsafe_code)]

use super::{MAXIMUM_FRAME_BYTES, Request, Response, decode};
use crate::session::ManagerSession;
use std::{
    ffi::{OsString, c_void},
    fs, io, mem,
    os::windows::{
        ffi::{OsStrExt, OsStringExt},
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
    },
    path::{Path, PathBuf},
    ptr,
    sync::Arc,
    time::{Duration, Instant},
};

type Handle = *mut c_void;
const IO_PENDING: i32 = 997;
const IO_INCOMPLETE: i32 = 996;
const PIPE_CONNECTED: i32 = 535;
const TIMEOUT: Duration = Duration::from_secs(2);

#[repr(C)]
#[derive(Default)]
struct Overlapped {
    internal: usize,
    internal_high: usize,
    offset: u32,
    offset_high: u32,
    event: Handle,
}
#[repr(C)]
struct Attributes {
    length: u32,
    descriptor: Handle,
    inherit: i32,
}
#[repr(C)]
struct TokenUser {
    sid: Handle,
    attributes: u32,
}

#[link(name = "kernel32")]
unsafe extern "system" {
    fn CreateNamedPipeW(
        name: *const u16,
        open: u32,
        mode: u32,
        instances: u32,
        output: u32,
        input: u32,
        timeout: u32,
        attributes: *const Attributes,
    ) -> Handle;
    fn CreateFileW(
        name: *const u16,
        access: u32,
        share: u32,
        attributes: *const Attributes,
        creation: u32,
        flags: u32,
        template: Handle,
    ) -> Handle;
    fn SetNamedPipeHandleState(
        pipe: Handle,
        mode: *const u32,
        count: *const u32,
        timeout: *const u32,
    ) -> i32;
    fn ConnectNamedPipe(pipe: Handle, overlapped: *mut Overlapped) -> i32;
    fn DisconnectNamedPipe(pipe: Handle) -> i32;
    fn GetNamedPipeClientProcessId(pipe: Handle, pid: *mut u32) -> i32;
    fn WaitNamedPipeW(name: *const u16, timeout: u32) -> i32;
    fn GetNamedPipeServerProcessId(pipe: Handle, pid: *mut u32) -> i32;
    fn PeekNamedPipe(
        pipe: Handle,
        buffer: Handle,
        size: u32,
        read: *mut u32,
        available: *mut u32,
        left: *mut u32,
    ) -> i32;
    fn ReadFile(
        file: Handle,
        buffer: Handle,
        size: u32,
        read: *mut u32,
        overlapped: *mut Overlapped,
    ) -> i32;
    fn WriteFile(
        file: Handle,
        buffer: *const c_void,
        size: u32,
        written: *mut u32,
        overlapped: *mut Overlapped,
    ) -> i32;
    fn GetOverlappedResult(
        file: Handle,
        overlapped: *mut Overlapped,
        transferred: *mut u32,
        wait: i32,
    ) -> i32;
    fn CancelIoEx(file: Handle, overlapped: *mut Overlapped) -> i32;
    fn CreateEventW(
        attributes: *const Attributes,
        manual: i32,
        initial: i32,
        name: *const u16,
    ) -> Handle;
    fn WaitForSingleObject(handle: Handle, timeout: u32) -> u32;
    fn OpenProcess(access: u32, inherit: i32, pid: u32) -> Handle;
    fn QueryFullProcessImageNameW(
        process: Handle,
        flags: u32,
        name: *mut u16,
        size: *mut u32,
    ) -> i32;
    fn LocalFree(memory: Handle) -> Handle;
    fn CompareStringOrdinal(
        first: *const u16,
        first_length: i32,
        second: *const u16,
        second_length: i32,
        ignore_case: i32,
    ) -> i32;
}
#[link(name = "advapi32")]
unsafe extern "system" {
    fn OpenProcessToken(process: Handle, access: u32, token: *mut Handle) -> i32;
    fn GetTokenInformation(
        token: Handle,
        class: u32,
        information: Handle,
        size: u32,
        needed: *mut u32,
    ) -> i32;
    fn ConvertSidToStringSidW(sid: Handle, text: *mut *mut u16) -> i32;
    fn ConvertStringSecurityDescriptorToSecurityDescriptorW(
        text: *const u16,
        revision: u32,
        descriptor: *mut Handle,
        size: *mut u32,
    ) -> i32;
}

fn raw(handle: &OwnedHandle) -> Handle {
    handle.as_raw_handle()
}
fn owned(handle: Handle) -> io::Result<OwnedHandle> {
    if handle.is_null() || handle as isize == -1 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: successful native creation transferred this distinct non-pseudo handle.
    Ok(unsafe { OwnedHandle::from_raw_handle(handle) })
}
fn checked(result: i32) -> io::Result<()> {
    if result == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}
fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain([0]).collect()
}
struct LocalMemory(Handle);
impl Drop for LocalMemory {
    fn drop(&mut self) {
        // SAFETY: returned by a LocalAlloc-backed native conversion; released once.
        unsafe {
            LocalFree(self.0);
        }
    }
}

/// The name never includes a caller-supplied image path or installation version.
pub fn endpoint(manager_id: &str, session: &ManagerSession) -> io::Result<String> {
    for part in [manager_id, session.user.as_str(), session.session.as_str()] {
        if part.is_empty()
            || part.len() > 184
            || !part
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'_'))
        {
            return Err(io::ErrorKind::InvalidInput.into());
        }
    }
    Ok(format!(
        r"\\.\pipe\{manager_id}.{}.session.{}",
        session.user, session.session
    ))
}

struct Peer {
    _process: OwnedHandle,
    image: PathBuf,
}

fn image_spelling(path: &Path) -> Vec<u16> {
    let value: Vec<_> = path.as_os_str().encode_wide().collect();
    let prefix: Vec<_> = r"\\?\".encode_utf16().collect();
    let unc: Vec<_> = r"\\?\UNC\".encode_utf16().collect();
    if value.starts_with(&unc) {
        [vec![92, 92], value[unc.len()..].to_vec()].concat()
    } else if value.starts_with(&prefix) {
        value[prefix.len()..].to_vec()
    } else {
        value
    }
}

pub(crate) fn same_image(actual: &Path, expected: &Path) -> bool {
    let first = image_spelling(actual);
    let second = image_spelling(expected);
    if first.len() > 32_768 || second.len() > 32_768 {
        return false;
    }
    // SAFETY: bounded native image spellings; ordinal comparison does no I/O.
    unsafe {
        CompareStringOrdinal(
            first.as_ptr(),
            first.len() as i32,
            second.as_ptr(),
            second.len() as i32,
            1,
        ) == 2
    }
}

fn token_number(token: &OwnedHandle, class: u32) -> io::Result<u32> {
    let mut value = 0_u32;
    let mut length = 0;
    // SAFETY: token has QUERY access, and both outputs name writable locals.
    checked(unsafe {
        GetTokenInformation(raw(token), class, (&raw mut value).cast(), 4, &mut length)
    })?;
    if length != 4 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok(value)
}

fn inspect_peer(pid: u32, expected: &ManagerSession, images: &[PathBuf]) -> io::Result<Peer> {
    // SAFETY: opens a query-only, synchronizable process handle; no control rights.
    let process = owned(unsafe { OpenProcess(0x0010_1000, 0, pid) })?;
    let mut token = ptr::null_mut();
    // SAFETY: process remains held throughout inspection and token receives one handle.
    checked(unsafe { OpenProcessToken(raw(&process), 8, &mut token) })?;
    let token = owned(token)?;
    if token_number(&token, 12)?.to_string() != expected.session || token_number(&token, 18)? == 2 {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    // TOKEN_USER fits in a bounded buffer (a Windows SID is at most 68 bytes).
    let mut user = [0_usize; 32];
    let mut length = 0;
    // SAFETY: usize storage is aligned for TOKEN_USER and covers the bounded SID.
    checked(unsafe {
        GetTokenInformation(
            raw(&token),
            1,
            user.as_mut_ptr().cast(),
            mem::size_of_val(&user) as u32,
            &mut length,
        )
    })?;
    let mut text = ptr::null_mut();
    // SAFETY: successful TOKEN_USER contains a SID inside the still-live buffer.
    checked(unsafe {
        ConvertSidToStringSidW((*(user.as_ptr().cast::<TokenUser>())).sid, &mut text)
    })?;
    let allocation = LocalMemory(text.cast());
    let mut count = 0;
    // SAFETY: ConvertSidToStringSidW returned a terminated SID string; bounded by
    // the documented SID maximum. No untrusted pointer is supplied by the peer.
    while count < 184 && unsafe { *text.add(count) } != 0 {
        count += 1;
    }
    if count == 184 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    // SAFETY: bounded scan established this allocated string's readable extent.
    let sid = String::from_utf16(unsafe { std::slice::from_raw_parts(text, count) })
        .map_err(io::Error::other)?;
    drop(allocation);
    if sid != expected.user {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let mut path = vec![0_u16; 32_768];
    let mut size = path.len() as u32;
    // SAFETY: query buffer has exactly the advertised number of UTF-16 elements.
    checked(unsafe { QueryFullProcessImageNameW(raw(&process), 0, path.as_mut_ptr(), &mut size) })?;
    path.truncate(size as usize);
    let image = PathBuf::from(OsString::from_wide(&path));
    // SAFETY: poll the held process only; nonzero WAIT_TIMEOUT means still live.
    if !images.iter().any(|expected| same_image(&image, expected))
        || unsafe { WaitForSingleObject(raw(&process), 0) } != 258
    {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(Peer {
        _process: process,
        image,
    })
}

pub(crate) fn verify_process(pid: u32, image: &Path) -> io::Result<()> {
    inspect_peer(pid, &ManagerSession::current()?, &[image.to_path_buf()]).map(|_| ())
}

enum Kind {
    Connect,
    Read,
    Write,
}
struct Operation {
    file: Arc<OwnedHandle>,
    _event: OwnedHandle,
    overlapped: Box<Overlapped>,
    buffer: Box<[u8; MAXIMUM_FRAME_BYTES]>,
    complete: Option<u32>,
}
impl Operation {
    fn start(file: Arc<OwnedHandle>, kind: Kind, bytes: &[u8]) -> io::Result<Self> {
        if bytes.len() > MAXIMUM_FRAME_BYTES {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        // SAFETY: creates a private, noninheritable manual-reset event.
        let event = owned(unsafe { CreateEventW(ptr::null(), 1, 0, ptr::null()) })?;
        let mut operation = Self {
            file,
            overlapped: Box::new(Overlapped {
                event: raw(&event),
                ..Default::default()
            }),
            _event: event,
            buffer: Box::new([0; MAXIMUM_FRAME_BYTES]),
            complete: Some(0),
        };
        operation.buffer[..bytes.len()].copy_from_slice(bytes);
        let mut transferred = 0;
        // SAFETY: pinned heap buffers/OVERLAPPED/event remain alive until completion;
        // Drop cancels and joins outstanding I/O before releasing any storage.
        let result = unsafe {
            match kind {
                Kind::Connect => ConnectNamedPipe(raw(&operation.file), &mut *operation.overlapped),
                Kind::Read => ReadFile(
                    raw(&operation.file),
                    operation.buffer.as_mut_ptr().cast(),
                    MAXIMUM_FRAME_BYTES as u32,
                    &mut transferred,
                    &mut *operation.overlapped,
                ),
                Kind::Write => WriteFile(
                    raw(&operation.file),
                    operation.buffer.as_ptr().cast(),
                    bytes.len() as u32,
                    &mut transferred,
                    &mut *operation.overlapped,
                ),
            }
        };
        if result != 0 {
            operation.complete = Some(transferred);
        } else {
            let error = io::Error::last_os_error();
            match error.raw_os_error() {
                Some(IO_PENDING) => operation.complete = None,
                Some(PIPE_CONNECTED) if matches!(kind, Kind::Connect) => {}
                _ => return Err(error),
            }
        }
        Ok(operation)
    }
    fn poll(&mut self) -> io::Result<Option<u32>> {
        if self.complete.is_some() {
            return Ok(self.complete);
        }
        let mut transferred = 0;
        // SAFETY: all operation storage is held; FALSE performs a nonblocking query.
        if unsafe {
            GetOverlappedResult(raw(&self.file), &mut *self.overlapped, &mut transferred, 0)
        } == 0
        {
            let error = io::Error::last_os_error();
            if error.raw_os_error() == Some(IO_INCOMPLETE) {
                return Ok(None);
            }
            self.complete = Some(0);
            return Err(error);
        }
        self.complete = Some(transferred);
        Ok(self.complete)
    }
    fn wait(&mut self, deadline: Instant) -> io::Result<u32> {
        loop {
            if let Some(size) = self.poll()? {
                return Ok(size);
            }
            if Instant::now() >= deadline {
                return Err(io::ErrorKind::TimedOut.into());
            }
            // SAFETY: only this operation's event is waited; short slices preserve the bound.
            unsafe {
                WaitForSingleObject(raw(&self._event), 10);
            }
        }
    }
}
impl Drop for Operation {
    fn drop(&mut self) {
        if self.complete.is_none() {
            let mut transferred = 0;
            // SAFETY: cancellation does not itself complete I/O. Join completion
            // before releasing OVERLAPPED/buffer/event or their owned pipe handle.
            unsafe {
                CancelIoEx(raw(&self.file), &mut *self.overlapped);
                GetOverlappedResult(raw(&self.file), &mut *self.overlapped, &mut transferred, 1);
            }
        }
    }
}

enum State {
    Connecting(Operation),
    Reading(Operation, Instant),
    Writing(Operation, Instant, Peer),
    Closing(Instant, Peer),
}

pub struct Server {
    pipe: Arc<OwnedHandle>,
    state: Option<State>,
    session: ManagerSession,
    images: Vec<PathBuf>,
    manager: PathBuf,
}

impl Server {
    /// Call only after package admission. Image members come from the same
    /// generated layout used to verify the admitted manager package.
    pub fn bind_installed(package: &Path) -> io::Result<Self> {
        let contract: cadrumo_application::installation::DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?;
        let manager = fs::canonicalize(
            contract
                .manager_member()
                .map_err(io::Error::other)?
                .under(package),
        )?;
        if manager != fs::canonicalize(std::env::current_exe()?)? {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let mut images = vec![manager.clone()];
        for image in contract
            .layout
            .application_images
            .iter()
            .filter(|i| i.target == "desktop-host-build")
        {
            if image.placement != "." {
                return Err(io::ErrorKind::InvalidData.into());
            }
            let member = cadrumo_application::value::RelativePath::new(format!(
                "{}{}",
                image.name, contract.layout.entrypoint_suffix
            ))
            .map_err(io::Error::other)?;
            let path = member.under(package);
            if path.is_file() {
                images.push(fs::canonicalize(path)?);
            }
        }
        Self::bind(
            crate::identity::MANAGER_ID,
            ManagerSession::current()?,
            images,
            manager,
        )
    }

    pub(crate) fn bind_cutover(name: &str, successor: &Path) -> io::Result<Self> {
        let image = fs::canonicalize(successor)?;
        Self::bind(name, ManagerSession::current()?, vec![image.clone()], image)
    }

    fn bind(
        manager_id: &str,
        session: ManagerSession,
        images: Vec<PathBuf>,
        manager: PathBuf,
    ) -> io::Result<Self> {
        let name = wide(&endpoint(manager_id, &session)?);
        let sddl = wide(&format!("O:{}D:P(A;;GA;;;{})", session.user, session.user));
        let mut descriptor = ptr::null_mut();
        // SAFETY: SDDL contains only a natively observed, grammar-validated SID.
        checked(unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl.as_ptr(),
                1,
                &mut descriptor,
                ptr::null_mut(),
            )
        })?;
        let descriptor = LocalMemory(descriptor);
        let attributes = Attributes {
            length: mem::size_of::<Attributes>() as u32,
            descriptor: descriptor.0,
            inherit: 0,
        };
        // SAFETY: all inputs outlive creation. First-instance refuses squatting;
        // one message-mode instance rejects remote clients, with owner-only DACL.
        let pipe = Arc::new(owned(unsafe {
            CreateNamedPipeW(
                name.as_ptr(),
                3 | 0x4000_0000 | 0x0008_0000,
                4 | 2 | 8,
                1,
                MAXIMUM_FRAME_BYTES as u32,
                MAXIMUM_FRAME_BYTES as u32,
                0,
                &attributes,
            )
        })?);
        let state = Some(State::Connecting(Operation::start(
            pipe.clone(),
            Kind::Connect,
            &[],
        )?));
        Ok(Self {
            pipe,
            state,
            session,
            images,
            manager,
        })
    }

    fn reconnect(&mut self) -> io::Result<()> {
        self.state = None;
        // SAFETY: pending operation was dropped (cancelled and joined) above.
        unsafe {
            DisconnectNamedPipe(raw(&self.pipe));
        }
        self.state = Some(State::Connecting(Operation::start(
            self.pipe.clone(),
            Kind::Connect,
            &[],
        )?));
        Ok(())
    }

    /// Bounded work on the owning message-loop thread; never waits for a client.
    pub fn poll(&mut self, mut handle: impl FnMut(Request) -> Response) -> io::Result<()> {
        self.poll_authenticated(|_, request| handle(request))
    }
    pub(crate) fn poll_authenticated(
        &mut self,
        mut handle: impl FnMut(u32, Request) -> Response,
    ) -> io::Result<()> {
        for _ in 0..4 {
            let Some(state) = self.state.take() else {
                return Err(io::ErrorKind::BrokenPipe.into());
            };
            match self.advance(state, &mut handle) {
                Ok((state, progress)) => {
                    self.state = Some(state);
                    if !progress {
                        break;
                    }
                }
                Err(_) => {
                    self.reconnect()?;
                    break;
                }
            }
        }
        Ok(())
    }

    fn advance(
        &self,
        state: State,
        handle: &mut impl FnMut(u32, Request) -> Response,
    ) -> io::Result<(State, bool)> {
        match state {
            State::Connecting(mut operation) => {
                if operation.poll()?.is_none() {
                    return Ok((State::Connecting(operation), false));
                }
                Ok((
                    State::Reading(
                        Operation::start(self.pipe.clone(), Kind::Read, &[])?,
                        Instant::now() + TIMEOUT,
                    ),
                    true,
                ))
            }
            State::Reading(mut operation, deadline) => {
                if Instant::now() >= deadline {
                    return Err(io::ErrorKind::TimedOut.into());
                }
                let Some(size) = operation.poll()? else {
                    return Ok((State::Reading(operation, deadline), false));
                };
                let mut pid = 0;
                // SAFETY: native pipe API observes the actual connection, never a request PID.
                checked(unsafe { GetNamedPipeClientProcessId(raw(&self.pipe), &mut pid) })?;
                let peer = inspect_peer(pid, &self.session, &self.images)?;
                let request = decode(&operation.buffer[..size as usize])?;
                if matches!(request, Request::SuccessorReady { .. })
                    && !same_image(&peer.image, &self.manager)
                {
                    return Err(io::ErrorKind::PermissionDenied.into());
                }
                let response =
                    serde_json::to_vec(&handle(pid, request)).map_err(io::Error::other)?;
                Ok((
                    State::Writing(
                        Operation::start(self.pipe.clone(), Kind::Write, &response)?,
                        deadline,
                        peer,
                    ),
                    true,
                ))
            }
            State::Writing(mut operation, deadline, peer) => {
                if Instant::now() >= deadline {
                    return Err(io::ErrorKind::TimedOut.into());
                }
                if operation.poll()?.is_none() {
                    return Ok((State::Writing(operation, deadline, peer), false));
                }
                Ok((State::Closing(deadline, peer), false))
            }
            State::Closing(deadline, peer) => {
                let mut available = 0;
                // SAFETY: peek is nonblocking; keep the response buffered until the
                // client closes. Disconnecting immediately could discard unread bytes.
                checked(unsafe {
                    PeekNamedPipe(
                        raw(&self.pipe),
                        ptr::null_mut(),
                        0,
                        ptr::null_mut(),
                        &mut available,
                        ptr::null_mut(),
                    )
                })?;
                if available != 0 || Instant::now() >= deadline {
                    return Err(io::ErrorKind::TimedOut.into());
                }
                Ok((State::Closing(deadline, peer), false))
            }
        }
    }
}

/// A caller supplies an already-admitted exact manager image. A pipe name alone
/// never authenticates the server. No automatic runtime/manager launch occurs.
pub fn request(manager: &Path, request: &Request) -> io::Result<Response> {
    request_to(crate::identity::MANAGER_ID, manager, request)
}

fn request_to(manager_id: &str, manager: &Path, request: &Request) -> io::Result<Response> {
    request_expected(manager_id, manager, None, request)
}

pub(crate) fn request_expected(
    manager_id: &str,
    manager: &Path,
    expected_pid: Option<u32>,
    request: &Request,
) -> io::Result<Response> {
    let session = ManagerSession::current()?;
    let name = wide(&endpoint(manager_id, &session)?);
    // SAFETY: open an existing pipe, overlapped/noninheritable, identification-only
    // SQOS so a server cannot impersonate this client to perform other effects.
    let deadline = Instant::now() + TIMEOUT;
    let pipe = loop {
        let opened = owned(unsafe {
            CreateFileW(
                name.as_ptr(),
                0xc000_0000,
                0,
                ptr::null(),
                3,
                0x4000_0000 | 0x0010_0000 | 0x0001_0000,
                ptr::null_mut(),
            )
        });
        match opened {
            Ok(pipe) => break Arc::new(pipe),
            Err(error) if error.raw_os_error() == Some(231) && Instant::now() < deadline => {
                let remaining = deadline
                    .saturating_duration_since(Instant::now())
                    .as_millis()
                    .min(u128::from(u32::MAX)) as u32;
                // SAFETY: wait only for this already-existing, terminated pipe name.
                if unsafe { WaitNamedPipeW(name.as_ptr(), remaining.max(1)) } == 0 {
                    return Err(io::Error::last_os_error());
                }
            }
            Err(error) => return Err(error),
        }
    };
    let mut pid = 0;
    // SAFETY: observe the connected server before writing any request.
    checked(unsafe { GetNamedPipeServerProcessId(raw(&pipe), &mut pid) })?;
    if expected_pid.is_some_and(|expected| expected != pid) {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let _peer = inspect_peer(pid, &session, &[fs::canonicalize(manager)?])?;
    let mode = 2;
    // SAFETY: owned client pipe, message-read mode; other properties unchanged.
    checked(unsafe { SetNamedPipeHandleState(raw(&pipe), &mode, ptr::null(), ptr::null()) })?;
    let bytes = serde_json::to_vec(request).map_err(io::Error::other)?;
    decode(&bytes)?;
    let mut writing = Operation::start(pipe.clone(), Kind::Write, &bytes)?;
    if writing.wait(deadline)? as usize != bytes.len() {
        return Err(io::ErrorKind::WriteZero.into());
    }
    let mut reading = Operation::start(pipe, Kind::Read, &[])?;
    let size = reading.wait(deadline)?;
    let response: Response =
        serde_json::from_slice(&reading.buffer[..size as usize]).map_err(io::Error::other)?;
    if response.schema != 1 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok(response)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ipc::{Outcome, respond};
    use std::{
        sync::mpsc,
        thread,
        time::{SystemTime, UNIX_EPOCH},
    };

    fn name() -> String {
        format!(
            "test.cadrumo.ipc.{}.{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        )
    }

    fn server(name: &str, allow: bool) -> Server {
        let image = fs::canonicalize(std::env::current_exe().unwrap()).unwrap();
        Server::bind(
            name,
            ManagerSession::current().unwrap(),
            if allow { vec![image.clone()] } else { vec![] },
            image,
        )
        .unwrap()
    }

    fn exchange(allow: bool, expected_server: PathBuf) -> (io::Result<Response>, usize) {
        let name = name();
        let mut server = server(&name, allow);
        let (send, receive) = mpsc::channel();
        let client = thread::spawn(move || {
            send.send(request_to(
                &name,
                &expected_server,
                &Request::Retry { schema: 1 },
            ))
            .unwrap();
        });
        let deadline = Instant::now() + Duration::from_secs(4);
        let mut retries = 0;
        let result = loop {
            server
                .poll(|request| {
                    respond(request, || {
                        retries += 1;
                        Ok(())
                    })
                })
                .unwrap();
            if let Ok(result) = receive.try_recv() {
                break result;
            }
            assert!(Instant::now() < deadline, "client must be bounded");
            thread::sleep(Duration::from_millis(5));
        };
        client.join().unwrap();
        (result, retries)
    }

    #[test]
    fn native_pipe_verifies_both_images_before_performing_retry() {
        let image = std::env::current_exe().unwrap();
        let (response, retries) = exchange(true, image.clone());
        assert_eq!(response.unwrap().outcome, Outcome::ReEvaluated);
        assert_eq!(retries, 1);
        let (response, retries) = exchange(false, image);
        assert!(response.is_err());
        assert_eq!(retries, 0);
        let (response, retries) = exchange(true, PathBuf::from(r"C:\Windows\System32\notepad.exe"));
        assert!(response.is_err());
        assert_eq!(retries, 0);
    }

    #[test]
    fn endpoint_is_owner_session_and_channel_qualified() {
        let mut session = ManagerSession {
            user: "S-1-5-21-1".into(),
            session: "2".into(),
        };
        let name = endpoint("md.neve.cadrumo.manager", &session).unwrap();
        assert_eq!(
            name,
            r"\\.\pipe\md.neve.cadrumo.manager.S-1-5-21-1.session.2"
        );
        session.session = "3".into();
        assert_ne!(endpoint("md.neve.cadrumo.manager", &session).unwrap(), name);
        session.user = r"S-1\injected".into();
        assert!(endpoint("md.neve.cadrumo.manager", &session).is_err());
    }

    #[test]
    fn native_first_instance_refuses_a_squatted_endpoint() {
        let name = name();
        let _first = server(&name, true);
        let image = fs::canonicalize(std::env::current_exe().unwrap()).unwrap();
        assert!(
            Server::bind(
                &name,
                ManagerSession::current().unwrap(),
                vec![image.clone()],
                image
            )
            .is_err()
        );
    }

    #[test]
    fn peer_identity_rejects_foreign_owner_and_session() {
        let image = fs::canonicalize(std::env::current_exe().unwrap()).unwrap();
        let mut session = ManagerSession::current().unwrap();
        session.user = "S-1-0-0".into();
        assert!(inspect_peer(std::process::id(), &session, std::slice::from_ref(&image)).is_err());
        session = ManagerSession::current().unwrap();
        session.session = "4294967295".into();
        assert!(inspect_peer(std::process::id(), &session, &[image]).is_err());
    }

    fn raw_client(name: &str) -> Arc<OwnedHandle> {
        let path = wide(&endpoint(name, &ManagerSession::current().unwrap()).unwrap());
        // SAFETY: connects only to the isolated test endpoint; noninheritable,
        // overlapped, identification-only client. No installed endpoint is used.
        Arc::new(
            owned(unsafe {
                CreateFileW(
                    path.as_ptr(),
                    0xc000_0000,
                    0,
                    ptr::null(),
                    3,
                    0x4011_0000,
                    ptr::null_mut(),
                )
            })
            .unwrap(),
        )
    }

    #[test]
    fn malformed_and_silent_clients_cannot_hold_the_endpoint() {
        let name = name();
        let mut server = server(&name, true);
        let reject_effect = |_| panic!("invalid requests must have no effect");
        let malformed = raw_client(&name);
        let bytes = br#"{"schema":1,"request":"retry","force":true}"#;
        Operation::start(malformed.clone(), Kind::Write, bytes)
            .unwrap()
            .wait(Instant::now() + TIMEOUT)
            .unwrap();
        server.poll(reject_effect).unwrap();
        let mut available = 0;
        // SAFETY: the owned test client remains open while the server disconnects it.
        assert_eq!(
            unsafe {
                PeekNamedPipe(
                    raw(&malformed),
                    ptr::null_mut(),
                    0,
                    ptr::null_mut(),
                    &mut available,
                    ptr::null_mut(),
                )
            },
            0
        );
        drop(malformed);

        let silent = raw_client(&name);
        server.poll(reject_effect).unwrap();
        let deadline = Instant::now() + TIMEOUT + Duration::from_millis(100);
        while Instant::now() < deadline {
            server.poll(reject_effect).unwrap();
            thread::sleep(Duration::from_millis(10));
        }
        // SAFETY: as above; timeout must disconnect even without a single byte.
        assert_eq!(
            unsafe {
                PeekNamedPipe(
                    raw(&silent),
                    ptr::null_mut(),
                    0,
                    ptr::null_mut(),
                    &mut available,
                    ptr::null_mut(),
                )
            },
            0
        );
        drop(silent);
        // The same first-instance server remains usable after both refusals.
        let image = std::env::current_exe().unwrap();
        let (send, receive) = mpsc::channel();
        let client = thread::spawn(move || {
            send.send(request_to(&name, &image, &Request::Retry { schema: 1 }))
                .unwrap()
        });
        let mut retries = 0;
        let deadline = Instant::now() + TIMEOUT;
        loop {
            server
                .poll(|request| {
                    respond(request, || {
                        retries += 1;
                        Ok(())
                    })
                })
                .unwrap();
            if let Ok(response) = receive.try_recv() {
                assert_eq!(response.unwrap().outcome, Outcome::ReEvaluated);
                assert_eq!(retries, 1);
                break;
            }
            assert!(Instant::now() < deadline);
            thread::sleep(Duration::from_millis(5));
        }
        client.join().unwrap();
    }

    #[test]
    fn image_comparison_handles_native_prefix_and_case_without_opening_paths() {
        assert!(same_image(
            Path::new(r"C:\Installed\Manager.exe"),
            Path::new(r"\\?\C:\installed\manager.exe")
        ));
        assert!(same_image(
            Path::new(r"\\server\share\Manager.exe"),
            Path::new(r"\\?\UNC\server\share\manager.exe")
        ));
        assert!(!same_image(
            Path::new(r"C:\Other\Manager.exe"),
            Path::new(r"\\?\C:\installed\manager.exe")
        ));
    }
}
