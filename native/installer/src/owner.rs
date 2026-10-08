//! Authenticated, bounded rendezvous between the native transaction owner and MSI.
#![allow(unsafe_code)]
use crate::{
    admission::{MAX_DATA_BYTES, Refusal, Scope},
    custody,
};
use cadrumo_application::{
    installation::maintenance::{Identity, NativeContext},
    value::{RelativePath, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    ffi::OsString,
    io::{Read, Write},
    os::windows::{
        ffi::OsStringExt,
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
    },
    path::PathBuf,
    ptr,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};
use windows_sys::Win32::{
    Foundation::*,
    Security::{Authorization::*, Cryptography::*, *},
    Storage::FileSystem::*,
    System::{IO::*, Pipes::*, SystemInformation::GetSystemDirectoryW, Threading::*},
};

const ENDPOINT_PREFIX: &str = r"\\.\pipe\CADRUMO.MsiOwner.";
const REQUEST_TIMEOUT: Duration = Duration::from_secs(3);

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Operation {
    Install,
    Remove,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Version,
    Registration,
}
impl Role {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Version => "version",
            Self::Registration => "registration",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Claim {
    pub product_code: String,
    pub scope: Scope,
    pub prefix: PathBuf,
    pub operation: Operation,
    pub role: Role,
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Callback {
    pub schema: u32,
    pub identity: Identity,
    pub publication: RelativePath,
    pub claim: Claim,
}

impl Callback {
    pub fn parse(bytes: &[u8]) -> Result<Self, Refusal> {
        if bytes.len() > MAX_DATA_BYTES {
            return Err(Refusal::InvalidRequest);
        }
        let value: Self = serde_json::from_slice(bytes).map_err(|_| Refusal::InvalidRequest)?;
        if value.schema != 2
            || value.identity.application_id.is_empty()
            || value.identity.channel.is_empty()
            || value.identity.platform != "windows-x64"
            || !value.claim.prefix.is_absolute()
            || value
                .claim
                .prefix
                .components()
                .any(|part| matches!(part, std::path::Component::ParentDir))
            || crate::admission::canonical_guid(&value.claim.product_code)?
                != value.claim.product_code
        {
            return Err(Refusal::InvalidRequest);
        }
        Ok(value)
    }
}

/// This file is authoritative only under independently admitted native ACL and
/// namespace custody, with a matching live NPFS peer. It never proves settlement.
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Record {
    schema: u32,
    identity: Identity,
    context: NativeContext,
    prefix: PathBuf,
    transaction: String,
    endpoint: String,
    pid: u32,
    created: u64,
    image: PathBuf,
    image_sha256: Sha256Digest,
    claims: Vec<Claim>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    schema: u32,
    transaction: String,
    claim: Claim,
}

fn nonce() -> Result<String, Refusal> {
    let mut bytes = [0; 32];
    // SAFETY: system random generator writes the exact supplied buffer.
    if unsafe {
        BCryptGenRandom(
            ptr::null_mut(),
            bytes.as_mut_ptr(),
            bytes.len() as u32,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        )
    } != 0
    {
        return Err(Refusal::NativeFailure);
    }
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

fn creation(process: &OwnedHandle) -> Result<u64, Refusal> {
    let mut created = FILETIME::default();
    let mut exited = FILETIME::default();
    let mut kernel = FILETIME::default();
    let mut user = FILETIME::default();
    // SAFETY: process is query-only and owned, all four outputs are writable.
    checked(unsafe {
        GetProcessTimes(
            process.as_raw_handle(),
            &mut created,
            &mut exited,
            &mut kernel,
            &mut user,
        )
    })?;
    Ok((u64::from(created.dwHighDateTime) << 32) | u64::from(created.dwLowDateTime))
}

fn digest(file: &mut std::fs::File) -> Result<Sha256Digest, Refusal> {
    if file.metadata().map_err(|_| Refusal::NativeFailure)?.len() > 128 * 1024 * 1024 {
        return Err(Refusal::NativeFailure);
    }
    let mut digest = Sha256::new();
    let mut buffer = [0; 65536];
    loop {
        let size = file.read(&mut buffer).map_err(|_| Refusal::NativeFailure)?;
        if size == 0 {
            break;
        }
        digest.update(&buffer[..size]);
    }
    Sha256Digest::new(format!("{:x}", digest.finalize())).map_err(|_| Refusal::NativeFailure)
}

fn verified_peer(
    record: &Record,
    pid: u32,
    context: &NativeContext,
) -> Result<(OwnedHandle, custody::FileCustody), Refusal> {
    let (process, image, token) = process(pid)?;
    if pid != record.pid || creation(&process)? != record.created || image != record.image {
        return Err(Refusal::NativeFailure);
    }
    token_matches(&token, context)?;
    let mut image = custody::file(&image)?;
    if digest(&mut image.file)? != record.image_sha256 {
        return Err(Refusal::NativeFailure);
    }
    Ok((process, image))
}

fn checked(value: i32) -> Result<(), Refusal> {
    if value != 0 {
        Ok(())
    } else {
        Err(Refusal::NativeFailure)
    }
}
fn handle(raw: HANDLE) -> Result<OwnedHandle, Refusal> {
    if raw.is_null() || raw == INVALID_HANDLE_VALUE {
        return Err(Refusal::NativeFailure);
    }
    // SAFETY: callers supply only newly owned kernel handles, never borrowed ones.
    Ok(unsafe { OwnedHandle::from_raw_handle(raw) })
}
fn wide(value: &str) -> Result<Vec<u16>, Refusal> {
    if value.contains('\0') {
        return Err(Refusal::InvalidRequest);
    }
    Ok(value.encode_utf16().chain([0]).collect())
}
struct Local(*mut std::ffi::c_void);
impl Drop for Local {
    fn drop(&mut self) {
        // SAFETY: allocated by the security descriptor/SID conversion API.
        unsafe {
            LocalFree(self.0);
        }
    }
}

fn token_sid(token: &OwnedHandle) -> Result<String, Refusal> {
    let mut storage = [0_usize; 32];
    let mut size = 0;
    // SAFETY: aligned bounded TOKEN_USER storage; token is query-only and live.
    checked(unsafe {
        GetTokenInformation(
            token.as_raw_handle(),
            TokenUser,
            storage.as_mut_ptr().cast(),
            size_of_val(&storage) as u32,
            &mut size,
        )
    })?;
    let mut text = ptr::null_mut();
    // SAFETY: successful TOKEN_USER includes a valid SID in the live storage.
    checked(unsafe {
        ConvertSidToStringSidW(
            (*(storage.as_ptr().cast::<TOKEN_USER>())).User.Sid,
            &mut text,
        )
    })?;
    let _allocation = Local(text.cast());
    let mut count = 0;
    // SAFETY: native SID conversion returns a terminated allocation, bounded by SID limits.
    while count < 184 && unsafe { *text.add(count) } != 0 {
        count += 1;
    }
    if count == 184 {
        return Err(Refusal::NativeFailure);
    }
    // SAFETY: the preceding terminated scan establishes the readable string extent.
    String::from_utf16(unsafe { std::slice::from_raw_parts(text, count) })
        .map_err(|_| Refusal::NativeFailure)
}

fn token_matches(token: &OwnedHandle, context: &NativeContext) -> Result<(), Refusal> {
    match context {
        NativeContext::User { sid } if token_sid(token)? == *sid => Ok(()),
        NativeContext::Machine => {
            let mut elevation = TOKEN_ELEVATION::default();
            let mut size = 0;
            // SAFETY: exact TOKEN_ELEVATION output and owned query token.
            checked(unsafe {
                GetTokenInformation(
                    token.as_raw_handle(),
                    TokenElevation,
                    ptr::from_mut(&mut elevation).cast(),
                    size_of::<TOKEN_ELEVATION>() as u32,
                    &mut size,
                )
            })?;
            if elevation.TokenIsElevated != 0 {
                Ok(())
            } else {
                Err(Refusal::NativeFailure)
            }
        }
        _ => Err(Refusal::NativeFailure),
    }
}

fn effective_context(scope: Scope) -> Result<NativeContext, Refusal> {
    let mut token = ptr::null_mut();
    // SAFETY: MSI deferred actions may impersonate; the thread identity is authoritative.
    let opened = unsafe { OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, 1, &mut token) };
    if opened == 0 {
        // SAFETY: inspect the failed thread-token query before any other native call.
        if unsafe { GetLastError() } != ERROR_NO_TOKEN {
            return Err(Refusal::NativeFailure);
        }
        // SAFETY: only a genuinely unimpersonated thread uses its process token.
        checked(unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) })?;
    }
    let token = handle(token)?;
    let context = match scope {
        Scope::Machine => NativeContext::Machine,
        Scope::User => NativeContext::User {
            sid: token_sid(&token)?,
        },
    };
    token_matches(&token, &context)?;
    Ok(context)
}

fn installer_image() -> Result<PathBuf, Refusal> {
    let mut directory = [0; 32768];
    // SAFETY: fixed writable buffer; native system directory ignores environment overrides.
    let length =
        unsafe { GetSystemDirectoryW(directory.as_mut_ptr(), directory.len() as u32) } as usize;
    if length == 0 || length >= directory.len() {
        return Err(Refusal::NativeFailure);
    }
    Ok(PathBuf::from(OsString::from_wide(&directory[..length])).join("msiexec.exe"))
}

fn process(pid: u32) -> Result<(OwnedHandle, PathBuf, OwnedHandle), Refusal> {
    // SAFETY: opens only query/synchronize rights on the peer PID supplied by NPFS.
    let process =
        handle(unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, 0, pid) })?;
    let mut name = vec![0; 32768];
    let mut length = name.len() as u32;
    let mut token = ptr::null_mut();
    // SAFETY: writable bounded name and token outputs, live process handle.
    checked(unsafe {
        QueryFullProcessImageNameW(process.as_raw_handle(), 0, name.as_mut_ptr(), &mut length)
    })?;
    checked(unsafe { OpenProcessToken(process.as_raw_handle(), TOKEN_QUERY, &mut token) })?;
    let token = handle(token)?;
    // SAFETY: zero-timeout observation only, no process mutation.
    if unsafe { WaitForSingleObject(process.as_raw_handle(), 0) } != WAIT_TIMEOUT {
        return Err(Refusal::NativeFailure);
    }
    Ok((
        process,
        PathBuf::from(OsString::from_wide(&name[..length as usize])),
        token,
    ))
}

enum Io {
    Connect,
    Read,
    Write,
}
fn exchange(
    pipe: &OwnedHandle,
    operation: Io,
    data: &mut [u8],
    timeout: Duration,
) -> Result<usize, Refusal> {
    // SAFETY: unnamed noninheritable private completion event.
    let event = handle(unsafe { CreateEventW(ptr::null(), 1, 0, ptr::null()) })?;
    let mut overlapped = OVERLAPPED {
        hEvent: event.as_raw_handle(),
        ..Default::default()
    };
    let mut transferred = 0;
    // SAFETY: pipe/event/data/overlapped all remain live until completion or cancelled join below.
    let status = unsafe {
        match operation {
            Io::Connect => ConnectNamedPipe(pipe.as_raw_handle(), &mut overlapped),
            Io::Read => ReadFile(
                pipe.as_raw_handle(),
                data.as_mut_ptr(),
                data.len() as u32,
                &mut transferred,
                &mut overlapped,
            ),
            Io::Write => WriteFile(
                pipe.as_raw_handle(),
                data.as_ptr(),
                data.len() as u32,
                &mut transferred,
                &mut overlapped,
            ),
        }
    };
    if status != 0 {
        return Ok(transferred as usize);
    }
    // SAFETY: inspect only the immediately preceding Win32 result.
    let error = unsafe { GetLastError() };
    if matches!(operation, Io::Connect) && error == ERROR_PIPE_CONNECTED {
        return Ok(0);
    }
    if error != ERROR_IO_PENDING {
        return Err(Refusal::NativeFailure);
    }
    // SAFETY: event belongs to the pending operation; wait is explicitly bounded.
    let wait = unsafe {
        WaitForSingleObject(
            event.as_raw_handle(),
            timeout.as_millis().min(u128::from(u32::MAX)) as u32,
        )
    };
    if wait != WAIT_OBJECT_0 {
        // SAFETY: cancel exactly our stack OVERLAPPED, then join before releasing its storage.
        unsafe {
            CancelIoEx(pipe.as_raw_handle(), &overlapped);
            GetOverlappedResult(pipe.as_raw_handle(), &overlapped, &mut transferred, 1);
        }
        return Err(Refusal::NativeFailure);
    }
    // SAFETY: signaled event means completion; buffer remains live and output writable.
    checked(unsafe {
        GetOverlappedResult(pipe.as_raw_handle(), &overlapped, &mut transferred, 0)
    })?;
    Ok(transferred as usize)
}

/// Keeps the process/pipe and active exact native operation under one owner.
pub struct Broker {
    endpoint: String,
    active: Arc<Mutex<Vec<Claim>>>,
    stop: Arc<AtomicBool>,
    worker: Option<JoinHandle<()>>,
    ownership: crate::ownership::Ownership,
    record: Record,
    record_path: PathBuf,
    _namespace: crate::publication::PublicationCustody,
}
impl Broker {
    pub fn bind(
        context: NativeContext,
        ownership: crate::ownership::Ownership,
        identity: Identity,
        prefix: PathBuf,
        publication: RelativePath,
    ) -> Result<Self, Refusal> {
        ownership.current()?;
        let state = publication.under(&prefix);
        let namespace = crate::publication::admit_existing(&prefix, &state, &context)?;
        let mut token = ptr::null_mut();
        // SAFETY: current process pseudo handle is borrowed, output is newly owned.
        checked(unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) })?;
        let sid = token_sid(&handle(token)?)?;
        let endpoint = format!("{ENDPOINT_PREFIX}{}", nonce()?);
        // SAFETY: current process ID is read-only, never a bearer credential.
        let pid = unsafe { GetCurrentProcessId() };
        let (process, image, _) = process(pid)?;
        let mut source = custody::file(&image)?;
        let record = Record {
            schema: 1,
            identity,
            context: context.clone(),
            prefix,
            transaction: nonce()?,
            endpoint: endpoint.clone(),
            pid,
            created: creation(&process)?,
            image,
            image_sha256: digest(&mut source.file)?,
            claims: Vec::new(),
        };
        let name = wide(&endpoint)?;
        let sddl = wide(&format!("O:{sid}D:P(A;;GA;;;{sid})(A;;GA;;;SY)"))?;
        let mut descriptor = ptr::null_mut();
        // SAFETY: SID is native-derived, SDDL terminated, descriptor output writable.
        checked(unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl.as_ptr(),
                1,
                &mut descriptor,
                ptr::null_mut(),
            )
        })?;
        let _descriptor = Local(descriptor);
        let attributes = SECURITY_ATTRIBUTES {
            nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: descriptor,
            bInheritHandle: 0,
        };
        // SAFETY: first-instance, overlapped, one local message-mode pipe with protected DACL.
        let pipe = handle(unsafe {
            CreateNamedPipeW(
                name.as_ptr(),
                PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_REJECT_REMOTE_CLIENTS,
                1,
                MAX_DATA_BYTES as u32,
                MAX_DATA_BYTES as u32,
                0,
                &attributes,
            )
        })?;
        let active = Arc::new(Mutex::new(Vec::new()));
        let stop = Arc::new(AtomicBool::new(false));
        let shared = active.clone();
        let stopping = stop.clone();
        let observer = ownership.clone();
        let transaction = record.transaction.clone();
        let worker =
            thread::spawn(move || serve(pipe, context, shared, stopping, observer, transaction));
        Ok(Self {
            endpoint,
            active,
            stop,
            worker: Some(worker),
            ownership,
            record,
            record_path: state.join("owner.json"),
            _namespace: namespace,
        })
    }
    pub fn endpoint(&self) -> &str {
        &self.endpoint
    }
    pub fn activate(&self, claim: Claim) -> Result<Active<'_>, Refusal> {
        self.activate_claims(vec![claim])
    }
    pub fn activate_claims(&self, claims: Vec<Claim>) -> Result<Active<'_>, Refusal> {
        self.ownership.current()?;
        let mut active = self.active.lock().map_err(|_| Refusal::NativeFailure)?;
        if !active.is_empty() || claims.is_empty() || claims.len() > 2 {
            return Err(Refusal::NativeFailure);
        }
        for (index, claim) in claims.iter().enumerate() {
            if claim.prefix != self.record.prefix
                || matches!(
                    (&self.record.context, claim.scope),
                    (NativeContext::Machine, Scope::User)
                        | (NativeContext::User { .. }, Scope::Machine)
                )
                || crate::admission::canonical_guid(&claim.product_code)? != claim.product_code
                || claims[..index].contains(claim)
            {
                return Err(Refusal::InvalidRequest);
            }
        }
        let mut record = self.record.clone();
        record.claims = claims.clone();
        let bytes = serde_json::to_vec(&record).map_err(|_| Refusal::InvalidRequest)?;
        if bytes.len() > MAX_DATA_BYTES {
            return Err(Refusal::InvalidRequest);
        }
        let temporary = self.record_path.with_extension(format!("{}.tmp", nonce()?));
        let result = (|| {
            let mut file = std::fs::File::options()
                .write(true)
                .create_new(true)
                .open(&temporary)?;
            file.write_all(&bytes)?;
            file.sync_all()?;
            drop(file);
            std::fs::rename(&temporary, &self.record_path)
        })();
        if result.is_err() {
            let _ = std::fs::remove_file(&temporary);
            return Err(Refusal::NativeFailure);
        }
        self.ownership.current()?;
        *active = claims;
        Ok(Active(self))
    }
}
pub struct Active<'a>(&'a Broker);
impl Drop for Active<'_> {
    fn drop(&mut self) {
        if let Ok(mut active) = self.0.active.lock() {
            active.clear();
        }
        let _ = std::fs::remove_file(&self.0.record_path);
    }
}
impl Drop for Broker {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
        let _ = std::fs::remove_file(&self.record_path);
    }
}

fn serve(
    pipe: OwnedHandle,
    context: NativeContext,
    active: Arc<Mutex<Vec<Claim>>>,
    stop: Arc<AtomicBool>,
    ownership: crate::ownership::Ownership,
    transaction: String,
) {
    while !stop.load(Ordering::Acquire) && ownership.current().is_ok() {
        if exchange(&pipe, Io::Connect, &mut [], Duration::from_millis(100)).is_err() {
            continue;
        }
        let mut bytes = [0; MAX_DATA_BYTES];
        let accepted = (|| -> Result<(), Refusal> {
            let count = exchange(&pipe, Io::Read, &mut bytes, REQUEST_TIMEOUT)?;
            let request: Request =
                serde_json::from_slice(&bytes[..count]).map_err(|_| Refusal::InvalidRequest)?;
            if request.schema != 1 || request.transaction != transaction {
                return Err(Refusal::InvalidRequest);
            }
            let mut pid = 0;
            // SAFETY: connected pipe and writable native peer PID output.
            checked(unsafe { GetNamedPipeClientProcessId(pipe.as_raw_handle(), &mut pid) })?;
            let (_process, image, _token) = process(pid)?;
            let expected = installer_image()?;
            let _image = custody::file(&image)?;
            let _expected = custody::file(&expected)?;
            if std::fs::canonicalize(image).map_err(|_| Refusal::NativeFailure)?
                != std::fs::canonicalize(expected).map_err(|_| Refusal::NativeFailure)?
            {
                return Err(Refusal::NativeFailure);
            }
            // SAFETY: impersonate only the context of the request just read. The
            // client grants identification only, sufficient to inspect its token.
            checked(unsafe { ImpersonateNamedPipeClient(pipe.as_raw_handle()) })?;
            let mut token = ptr::null_mut();
            // SAFETY: query effective client identity, not the MSI server's process token.
            let opened = unsafe { OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, 1, &mut token) };
            // SAFETY: always revert before returning or inspecting request contents.
            if unsafe { RevertToSelf() } == 0 {
                std::process::abort();
            }
            checked(opened)?;
            token_matches(&handle(token)?, &context)?;
            if !active
                .lock()
                .map_err(|_| Refusal::NativeFailure)?
                .contains(&request.claim)
            {
                return Err(Refusal::InvalidRequest);
            }
            Ok(())
        })()
        .is_ok();
        let mut response = [u8::from(accepted && ownership.current().is_ok())];
        if exchange(&pipe, Io::Write, &mut response, REQUEST_TIMEOUT).is_ok() {
            // An acknowledgement ensures DisconnectNamedPipe cannot discard an
            // unread admission result. Silent clients are still bounded.
            let _ = exchange(&pipe, Io::Read, &mut response, REQUEST_TIMEOUT);
        }
        // SAFETY: all per-client I/O completed or was cancelled and joined.
        unsafe {
            DisconnectNamedPipe(pipe.as_raw_handle());
        }
    }
}

pub fn authenticate(callback: &Callback) -> Result<(), Refusal> {
    let context = effective_context(callback.claim.scope)?;
    let state = callback.publication.under(&callback.claim.prefix);
    let _namespace = crate::publication::admit_existing(&callback.claim.prefix, &state, &context)?;
    let mut source = custody::file(&state.join("owner.json"))?;
    let mut bytes = Vec::new();
    std::io::Read::by_ref(&mut source.file)
        .take((MAX_DATA_BYTES + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|_| Refusal::NativeFailure)?;
    if bytes.len() > MAX_DATA_BYTES {
        return Err(Refusal::InvalidRequest);
    }
    let record: Record = serde_json::from_slice(&bytes).map_err(|_| Refusal::InvalidRequest)?;
    let endpoint_nonce = record
        .endpoint
        .strip_prefix(ENDPOINT_PREFIX)
        .ok_or(Refusal::InvalidRequest)?;
    if record.schema != 1
        || record.identity != callback.identity
        || record.context != context
        || record.prefix != callback.claim.prefix
        || !record.claims.contains(&callback.claim)
        || record.claims.is_empty()
        || record.claims.len() > 2
        || record.pid == 0
        || record.created == 0
        || !record.image.is_absolute()
        || ![endpoint_nonce, &record.transaction]
            .iter()
            .all(|value| value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit()))
    {
        return Err(Refusal::InvalidRequest);
    }
    let name = wide(&record.endpoint)?;
    let deadline = Instant::now() + REQUEST_TIMEOUT;
    // SAFETY: existing local pipe, overlapped and identification-only SQOS, no inheritance.
    let pipe = handle(unsafe {
        CreateFileW(
            name.as_ptr(),
            GENERIC_READ | GENERIC_WRITE,
            0,
            ptr::null(),
            OPEN_EXISTING,
            FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION,
            ptr::null_mut(),
        )
    })?;
    let mut pid = 0;
    // SAFETY: query connected server before writing any claim.
    checked(unsafe { GetNamedPipeServerProcessId(pipe.as_raw_handle(), &mut pid) })?;
    let (_process, _image) = verified_peer(&record, pid, &context)?;
    let mode = PIPE_READMODE_MESSAGE;
    // SAFETY: client owns pipe; set only message read mode.
    checked(unsafe {
        SetNamedPipeHandleState(pipe.as_raw_handle(), &mode, ptr::null(), ptr::null())
    })?;
    let mut claim = serde_json::to_vec(&Request {
        schema: 1,
        transaction: record.transaction,
        claim: callback.claim.clone(),
    })
    .map_err(|_| Refusal::InvalidRequest)?;
    if claim.len() > MAX_DATA_BYTES
        || exchange(
            &pipe,
            Io::Write,
            &mut claim,
            deadline.saturating_duration_since(Instant::now()),
        )? != claim.len()
    {
        return Err(Refusal::NativeFailure);
    }
    let mut response = [0];
    let count = exchange(
        &pipe,
        Io::Read,
        &mut response,
        deadline.saturating_duration_since(Instant::now()),
    )?;
    let accepted = count == 1 && response[0] == 1;
    exchange(
        &pipe,
        Io::Write,
        &mut response,
        deadline.saturating_duration_since(Instant::now()),
    )?;
    if accepted {
        Ok(())
    } else {
        Err(Refusal::NativeFailure)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn claim() -> Claim {
        Claim {
            product_code: "12345678-1234-1234-1234-123456789ABC".into(),
            scope: Scope::User,
            prefix: std::env::temp_dir(),
            operation: Operation::Install,
            role: Role::Version,
        }
    }

    fn identity() -> Identity {
        Identity {
            application_id: "test.cadrumo".into(),
            channel: "test".into(),
            platform: "windows-x64".into(),
        }
    }

    #[test]
    fn callback_admission_refuses_unsafe_state_oversize_and_unknown_fields() {
        let mut value = serde_json::json!({
            "schema": 2,
            "identity": identity(),
            "publication": "data/installation-state",
            "claim": claim(),
        });
        assert!(Callback::parse(&serde_json::to_vec(&value).unwrap()).is_ok());
        value["publication"] = serde_json::json!("../outside");
        assert!(Callback::parse(&serde_json::to_vec(&value).unwrap()).is_err());
        value["publication"] = serde_json::json!("data/installation-state");
        value["override"] = serde_json::json!(true);
        assert!(Callback::parse(&serde_json::to_vec(&value).unwrap()).is_err());
        assert!(Callback::parse(&vec![b' '; MAX_DATA_BYTES + 1]).is_err());
    }

    #[test]
    fn real_owner_pipe_rejects_a_same_user_non_installer_process() {
        let context = effective_context(Scope::User).unwrap();
        let root = tempfile::tempdir_in(std::env::var_os("LOCALAPPDATA").unwrap()).unwrap();
        let prefix = root.path().join("installed");
        let publication = RelativePath::new("data/installation-state").unwrap();
        let _namespace =
            crate::publication::prepare(&prefix, &publication.under(&prefix), &context).unwrap();
        let mut claim = claim();
        claim.prefix = prefix.clone();
        let broker = Broker::bind(
            context,
            crate::ownership::tests::unsignaled(),
            identity(),
            prefix,
            publication.clone(),
        )
        .unwrap();
        let _active = broker.activate(claim.clone()).unwrap();
        assert!(broker.activate(claim.clone()).is_err());
        let callback = Callback {
            schema: 2,
            identity: identity(),
            publication,
            claim,
        };
        // Server image and account are genuine and the claim matches, but the
        // caller is this test image rather than the native Windows Installer.
        assert_eq!(authenticate(&callback), Err(Refusal::NativeFailure));
        let record: Record =
            serde_json::from_slice(&std::fs::read(&broker.record_path).unwrap()).unwrap();
        assert!(verified_peer(&record, record.pid, &record.context).is_ok());
        for alteration in 0..4 {
            let mut altered = record.clone();
            match alteration {
                0 => altered.pid += 1,
                1 => altered.created += 1,
                2 => altered.image = altered.image.with_extension("other.exe"),
                _ => altered.image_sha256 = Sha256Digest::new("a".repeat(64)).unwrap(),
            }
            assert!(verified_peer(&altered, record.pid, &record.context).is_err());
        }
        drop(_active);
        assert!(!broker.record_path.exists());
        assert!(authenticate(&callback).is_err());
    }
}
