//! Machine boot broker. Only genuine user-token workers host taxpayer runtimes.
#![allow(unsafe_code)]

use cadrumo_application::installation::{DiscoveryContract, maintenance::NativeContext};
use std::{
    collections::{BTreeMap, BTreeSet},
    ffi::c_void,
    io,
    os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle},
    path::Path,
    ptr,
    sync::{
        Mutex, OnceLock,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};
use windows_sys::Win32::{
    Foundation::*,
    Security::{Authorization::*, *},
    System::{Environment::*, JobObjects::*, RemoteDesktop::*, Services::*, Threading::*},
};

const STOP_BOUND: Duration = Duration::from_secs(10);
const RECONCILE: Duration = Duration::from_secs(5);
const JOB_QUERY: u32 = 4;
const SESSION_LOGON: u32 = 5;
static STOP: AtomicBool = AtomicBool::new(false);
static LOGONS: Mutex<BTreeSet<u32>> = Mutex::new(BTreeSet::new());
static WORKER_STOP: OnceLock<OwnedHandle> = OnceLock::new();

fn checked(value: i32) -> io::Result<()> {
    if value == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}
fn owned(handle: HANDLE) -> io::Result<OwnedHandle> {
    if handle.is_null() {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: a newly returned kernel handle is transferred to its sole owner.
    Ok(unsafe { OwnedHandle::from_raw_handle(handle) })
}
fn raw(handle: &OwnedHandle) -> HANDLE {
    handle.as_raw_handle()
}
fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain([0]).collect()
}

struct Local(*mut c_void);
impl Drop for Local {
    fn drop(&mut self) {
        // SAFETY: Windows security conversion APIs return LocalAlloc storage.
        unsafe {
            LocalFree(self.0);
        }
    }
}
fn sid_text(sid: PSID) -> io::Result<String> {
    let mut text = ptr::null_mut();
    // SAFETY: SID belongs to a successful token/security descriptor query.
    checked(unsafe { ConvertSidToStringSidW(sid, &mut text) })?;
    let _memory = Local(text.cast());
    let mut length = 0;
    // SAFETY: ConvertSidToStringSid returns a terminated SID of at most 184 units.
    while length < 184 && unsafe { *text.add(length) } != 0 {
        length += 1;
    }
    if length == 184 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    // SAFETY: preceding scan bounds this native allocation.
    String::from_utf16(unsafe { std::slice::from_raw_parts(text, length) })
        .map_err(io::Error::other)
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
struct User {
    sid: String,
    logon: u64,
}
fn user(token: &OwnedHandle) -> io::Result<User> {
    let mut bytes = 0;
    // SAFETY: size-only query; no writable output is supplied.
    unsafe {
        GetTokenInformation(raw(token), TokenUser, ptr::null_mut(), 0, &mut bytes);
    }
    if bytes == 0 || bytes > 65536 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let mut storage = vec![0_usize; (bytes as usize).div_ceil(size_of::<usize>())];
    // SAFETY: pointer-aligned buffer has the exact native-reported capacity.
    checked(unsafe {
        GetTokenInformation(
            raw(token),
            TokenUser,
            storage.as_mut_ptr().cast(),
            bytes,
            &mut bytes,
        )
    })?;
    // SAFETY: successful TokenUser query begins with TOKEN_USER.
    let sid = sid_text(unsafe { (*storage.as_ptr().cast::<TOKEN_USER>()).User.Sid })?;
    let mut statistics: TOKEN_STATISTICS = unsafe { std::mem::zeroed() };
    // SAFETY: exact native structure output, token has query access.
    checked(unsafe {
        GetTokenInformation(
            raw(token),
            TokenStatistics,
            (&mut statistics as *mut TOKEN_STATISTICS).cast(),
            size_of::<TOKEN_STATISTICS>() as u32,
            &mut bytes,
        )
    })?;
    Ok(User {
        sid,
        logon: ((statistics.AuthenticationId.HighPart as u64) << 32)
            | u64::from(statistics.AuthenticationId.LowPart),
    })
}
fn current_token() -> io::Result<OwnedHandle> {
    let mut token = ptr::null_mut();
    // SAFETY: current process pseudo handle is borrowed; query-only token is owned.
    checked(unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) })?;
    owned(token)
}
fn name(user: &User, kind: &str) -> String {
    format!(
        "Global\\{}.service.{}.{:016x}.{kind}",
        crate::identity::MANAGER_ID,
        user.sid,
        user.logon
    )
}
fn require_system_owner(handle: &OwnedHandle) -> io::Result<()> {
    let mut owner = ptr::null_mut();
    let mut descriptor = ptr::null_mut();
    // SAFETY: retained kernel object handle has READ_CONTROL; native allocation is owned.
    let result = unsafe {
        GetSecurityInfo(
            raw(handle),
            SE_KERNEL_OBJECT,
            OWNER_SECURITY_INFORMATION,
            &mut owner,
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            &mut descriptor,
        )
    };
    if result != 0 {
        return Err(io::Error::from_raw_os_error(result as i32));
    }
    let _memory = Local(descriptor);
    if sid_text(owner)? != "S-1-5-18" {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(())
}

/// Inherited service containment is accepted only through a SYSTEM-owned named job.
pub fn in_service_job() -> bool {
    (|| -> io::Result<bool> {
        let user = user(&current_token()?)?;
        // SAFETY: terminated canonical name; handle receives query/read-control only.
        let job = owned(unsafe {
            OpenJobObjectW(
                JOB_QUERY | SYNCHRONIZATION_READ_CONTROL,
                0,
                wide(&name(&user, "job")).as_ptr(),
            )
        })?;
        require_system_owner(&job)?;
        let mut present = 0;
        // SAFETY: both process and job handles are valid through this native query.
        checked(unsafe { IsProcessInJob(GetCurrentProcess(), raw(&job), &mut present) })?;
        Ok(present != 0)
    })()
    .unwrap_or(false)
}

/// This flag grants no profile authority: the worker keeps its actual user token.
pub fn admit_worker() -> io::Result<()> {
    if !in_service_job() {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let user = user(&current_token()?)?;
    // SAFETY: terminated canonical event name; worker cannot modify the broker's event.
    let event = owned(unsafe {
        OpenEventW(
            SYNCHRONIZATION_SYNCHRONIZE | SYNCHRONIZATION_READ_CONTROL,
            0,
            wide(&name(&user, "stop")).as_ptr(),
        )
    })?;
    require_system_owner(&event)?;
    let _ = WORKER_STOP.set(event);
    Ok(())
}
/// Cutover successors inherit the same job and acquire the same stop channel.
pub fn worker_stop_requested() -> bool {
    if WORKER_STOP.get().is_none() && in_service_job() {
        let _ = admit_worker();
    }
    WORKER_STOP.get().is_some_and(|event| {
        // SAFETY: event is retained for this worker's entire lifetime; nonblocking query.
        unsafe { WaitForSingleObject(raw(event), 0) == WAIT_OBJECT_0 }
    })
}

struct Worker {
    _process: OwnedHandle,
    event: OwnedHandle,
    job: OwnedHandle,
}
impl Worker {
    fn active(&self) -> io::Result<bool> {
        let mut accounting: JOBOBJECT_BASIC_ACCOUNTING_INFORMATION = unsafe { std::mem::zeroed() };
        // SAFETY: retained queryable job; exact structure output.
        checked(unsafe {
            QueryInformationJobObject(
                raw(&self.job),
                JobObjectBasicAccountingInformation,
                (&mut accounting as *mut JOBOBJECT_BASIC_ACCOUNTING_INFORMATION).cast(),
                size_of_val(&accounting) as u32,
                ptr::null_mut(),
            )
        })?;
        Ok(accounting.ActiveProcesses != 0)
    }
    fn request_stop(&self) -> io::Result<()> {
        // SAFETY: broker retains modify-state access to its own event.
        checked(unsafe { SetEvent(raw(&self.event)) })
    }
    fn force_stop(&self) -> io::Result<()> {
        // SAFETY: only this broker's retained worker cohort is terminated.
        checked(unsafe { TerminateJobObject(raw(&self.job), 1) })
    }
}
fn launch(token: &OwnedHandle, user: &User, manager: &Path, sign_in: bool) -> io::Result<Worker> {
    let descriptor_text = wide(&format!("O:SYG:SYD:P(A;;GA;;;SY)(A;;GR;;;{})", user.sid));
    let mut descriptor = ptr::null_mut();
    // SAFETY: canonical SID text from native token, output allocation retained below.
    checked(unsafe {
        ConvertStringSecurityDescriptorToSecurityDescriptorW(
            descriptor_text.as_ptr(),
            1,
            &mut descriptor,
            ptr::null_mut(),
        )
    })?;
    let _memory = Local(descriptor);
    let attributes = SECURITY_ATTRIBUTES {
        nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
        lpSecurityDescriptor: descriptor,
        bInheritHandle: 0,
    };
    // SAFETY: names and attributes remain alive; no handles are inherited.
    let event =
        owned(unsafe { CreateEventW(&attributes, 1, 0, wide(&name(user, "stop")).as_ptr()) })?;
    if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
        return Err(io::ErrorKind::AlreadyExists.into());
    }
    let job = owned(unsafe { CreateJobObjectW(&attributes, wide(&name(user, "job")).as_ptr()) })?;
    if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
        return Err(io::ErrorKind::AlreadyExists.into());
    }
    let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    // SAFETY: this newly created job has no processes, no breakaway is granted.
    checked(unsafe {
        SetInformationJobObject(
            raw(&job),
            JobObjectExtendedLimitInformation,
            (&limits as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast(),
            size_of_val(&limits) as u32,
        )
    })?;
    let mut environment = ptr::null_mut();
    // SAFETY: genuine WTS primary token; SYSTEM environment is explicitly not inherited.
    checked(unsafe { CreateEnvironmentBlock(&mut environment, raw(token), 0) })?;
    struct Environment(*mut c_void);
    impl Drop for Environment {
        fn drop(&mut self) {
            unsafe {
                DestroyEnvironmentBlock(self.0);
            }
        }
    }
    let _environment = Environment(environment);
    let image = wide(manager.to_str().ok_or(io::ErrorKind::InvalidData)?);
    let argument = if sign_in {
        "--service-sign-in"
    } else {
        "--service-worker"
    };
    let mut command = wide(&format!("\"{}\" {argument}", manager.display()));
    // Empty requests Windows' native connection policy for this genuine logon.
    // NULL would inherit the broker's station; no desktop/session name is fabricated.
    let mut desktop = wide("");
    let mut startup: STARTUPINFOW = unsafe { std::mem::zeroed() };
    startup.cb = size_of::<STARTUPINFOW>() as u32;
    startup.lpDesktop = desktop.as_mut_ptr();
    let mut process: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
    // SAFETY: explicit verified image and user primary token; process starts suspended,
    // preventing execution before it is assigned to the broker's retained containment.
    checked(unsafe {
        CreateProcessAsUserW(
            raw(token),
            image.as_ptr(),
            command.as_mut_ptr(),
            ptr::null(),
            ptr::null(),
            0,
            CREATE_UNICODE_ENVIRONMENT | CREATE_SUSPENDED | CREATE_NO_WINDOW,
            environment,
            ptr::null(),
            &startup,
            &mut process,
        )
    })?;
    let process_handle = owned(process.hProcess)?;
    let thread = owned(process.hThread)?;
    let assigned = unsafe { AssignProcessToJobObject(raw(&job), raw(&process_handle)) };
    if assigned == 0 {
        let error = io::Error::last_os_error();
        // SAFETY: exact newly created suspended process; no user code has executed.
        unsafe {
            TerminateProcess(raw(&process_handle), 1);
        }
        return Err(error);
    }
    // SAFETY: retained initial thread of the assigned suspended worker.
    if unsafe { ResumeThread(raw(&thread)) } == u32::MAX {
        return Err(io::Error::last_os_error());
    }
    Ok(Worker {
        _process: process_handle,
        event,
        job,
    })
}

fn sessions() -> io::Result<Vec<(u32, OwnedHandle, User)>> {
    let mut sessions = ptr::null_mut();
    let mut count = 0;
    // SAFETY: native array allocation returned by successful local enumeration.
    checked(unsafe {
        WTSEnumerateSessionsW(WTS_CURRENT_SERVER_HANDLE, 0, 1, &mut sessions, &mut count)
    })?;
    struct Sessions(*mut WTS_SESSION_INFOW);
    impl Drop for Sessions {
        fn drop(&mut self) {
            unsafe {
                WTSFreeMemory(self.0.cast());
            }
        }
    }
    let _memory = Sessions(sessions);
    if count > 1024 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let mut found = Vec::new();
    for index in 0..count as usize {
        // SAFETY: index is bounded by native-reported array length.
        let session = unsafe { &*sessions.add(index) };
        let mut token = ptr::null_mut();
        // SAFETY: dynamically discovered session; unavailable/no-user sessions are skipped.
        if unsafe { WTSQueryUserToken(session.SessionId, &mut token) } == 0 {
            let error = unsafe { GetLastError() };
            if matches!(error, ERROR_NO_TOKEN | ERROR_CTX_WINSTATION_NOT_FOUND) {
                continue;
            }
            return Err(io::Error::from_raw_os_error(error as i32));
        }
        let token = owned(token)?;
        let identity = user(&token)?;
        if identity.sid == "S-1-5-18" {
            continue;
        }
        found.push((session.SessionId, token, identity));
    }
    Ok(found)
}

fn manager_target() -> io::Result<cadrumo_application::installation::Selection> {
    let contract: DiscoveryContract =
        serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).map_err(io::Error::other)?;
    let executable = std::env::current_exe()?;
    let prefix = contract
        .local_prefix(&executable)
        .ok_or(io::ErrorKind::PermissionDenied)?;
    let publication = contract
        .layout
        .installation
        .publication
        .as_ref()
        .ok_or(io::ErrorKind::PermissionDenied)?
        .under(&prefix);
    // SYSTEM never consumes HKCU hints or trusts a user-owned portable prefix.
    let _custody = cadrumo_installer::publication::admit_existing(
        &prefix,
        &publication,
        &NativeContext::Machine,
    )
    .map_err(|_| io::Error::other("service_machine_namespace_refused"))?;
    let selection = contract.inspect(&prefix).map_err(io::Error::other)?;
    if selection
        .registration
        .as_ref()
        .is_none_or(|owner| owner.context() != &NativeContext::Machine)
    {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(selection)
}

unsafe extern "system" fn control(code: u32, event: u32, data: *mut c_void, _: *mut c_void) -> u32 {
    match code {
        SERVICE_CONTROL_STOP | SERVICE_CONTROL_SHUTDOWN => {
            STOP.store(true, Ordering::Release);
        }
        SERVICE_CONTROL_SESSIONCHANGE if event == SESSION_LOGON && !data.is_null() => {
            // SAFETY: SCM supplies WTSSESSION_NOTIFICATION for SESSIONCHANGE controls.
            let session = unsafe { (*data.cast::<WTSSESSION_NOTIFICATION>()).dwSessionId };
            if let Ok(mut pending) = LOGONS.lock() {
                pending.insert(session);
            }
        }
        _ => {}
    }
    0
}
fn status(
    handle: SERVICE_STATUS_HANDLE,
    state: u32,
    error: u32,
    checkpoint: u32,
) -> io::Result<()> {
    let value = SERVICE_STATUS {
        dwServiceType: SERVICE_WIN32_OWN_PROCESS,
        dwCurrentState: state,
        dwControlsAccepted: if state == SERVICE_RUNNING {
            SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN | SERVICE_ACCEPT_SESSIONCHANGE
        } else {
            0
        },
        dwWin32ExitCode: error,
        dwServiceSpecificExitCode: 0,
        dwCheckPoint: checkpoint,
        dwWaitHint: if state == SERVICE_STOP_PENDING {
            STOP_BOUND.as_millis() as u32
        } else {
            0
        },
    };
    // SAFETY: SCM returned this status handle; exact SERVICE_STATUS structure.
    checked(unsafe { SetServiceStatus(handle, &value) })
}
fn broker(handle: SERVICE_STATUS_HANDLE) -> io::Result<()> {
    if user(&current_token()?)?.sid != "S-1-5-18" {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let mut workers = BTreeMap::<User, Worker>::new();
    let mut retry = BTreeMap::<User, Instant>::new();
    status(handle, SERVICE_RUNNING, 0, 0)?;
    let mut next = Instant::now();
    let outcome = (|| -> io::Result<()> {
        while !STOP.load(Ordering::Acquire) {
            if Instant::now() < next {
                std::thread::sleep(Duration::from_millis(100));
                continue;
            }
            next = Instant::now() + RECONCILE;
            let present = sessions()?;
            let identities: BTreeSet<_> = present.iter().map(|(_, _, user)| user.clone()).collect();
            let ending: Vec<_> = workers
                .keys()
                .filter(|user| !identities.contains(*user))
                .cloned()
                .collect();
            for user in ending {
                if let Some(worker) = workers.remove(&user) {
                    stop_workers(handle, vec![worker])?;
                }
            }
            retry.retain(|user, _| identities.contains(user));
            for (session, token, user) in present {
                if workers
                    .get(&user)
                    .is_some_and(|worker| worker.active().unwrap_or(true))
                {
                    continue;
                }
                workers.remove(&user);
                if retry.get(&user).is_some_and(|at| Instant::now() < *at) {
                    continue;
                }
                retry.insert(user.clone(), Instant::now() + Duration::from_secs(30));
                let sign_in = LOGONS
                    .lock()
                    .map_err(|_| io::Error::other("service_logon_state_failed"))?
                    .contains(&session);
                // MSI publication may still be settling at service start. Never launch
                // unverified bytes: retry after publication becomes complete.
                let Ok(target) = manager_target() else {
                    continue;
                };
                let Ok(worker) = launch(&token, &user, &target.manager, sign_in) else {
                    continue;
                };
                if sign_in {
                    LOGONS
                        .lock()
                        .map_err(|_| io::Error::other("service_logon_state_failed"))?
                        .remove(&session);
                }
                workers.insert(user, worker);
            }
        }
        Ok(())
    })();
    let cleanup = stop_workers(handle, workers.into_values().collect());
    outcome.and(cleanup)
}
fn stop_workers(handle: SERVICE_STATUS_HANDLE, workers: Vec<Worker>) -> io::Result<()> {
    for worker in &workers {
        worker.request_stop()?;
    }
    let deadline = Instant::now() + STOP_BOUND;
    let mut checkpoint = 0;
    while Instant::now() < deadline && workers.iter().any(|worker| worker.active().unwrap_or(true))
    {
        if STOP.load(Ordering::Acquire) {
            checkpoint += 1;
            status(handle, SERVICE_STOP_PENDING, 0, checkpoint)?;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    for worker in &workers {
        if worker.active()? {
            worker.force_stop()?;
        }
    }
    let force_deadline = Instant::now() + Duration::from_secs(3);
    while Instant::now() < force_deadline
        && workers.iter().any(|worker| worker.active().unwrap_or(true))
    {
        std::thread::sleep(Duration::from_millis(100));
    }
    if workers.iter().any(|worker| worker.active().unwrap_or(true)) {
        return Err(io::ErrorKind::TimedOut.into());
    }
    Ok(())
}
unsafe extern "system" fn service_main(_: u32, _: *mut *mut u16) {
    STOP.store(false, Ordering::Release);
    let service = wide(crate::identity::MANAGER_ID);
    // SAFETY: callback and fixed service name live for the dispatcher lifetime.
    let handle =
        unsafe { RegisterServiceCtrlHandlerExW(service.as_ptr(), Some(control), ptr::null_mut()) };
    if handle.is_null() {
        return;
    }
    let outcome = broker(handle);
    let error = outcome
        .err()
        .map_or(0, |error| error.raw_os_error().unwrap_or(1) as u32);
    let _ = status(handle, SERVICE_STOPPED, error, 0);
}
/// Service mode never enters the ordinary manager/runtime startup path as SYSTEM.
pub fn run() -> io::Result<()> {
    let mut service = wide(crate::identity::MANAGER_ID);
    let table = [
        SERVICE_TABLE_ENTRYW {
            lpServiceName: service.as_mut_ptr(),
            lpServiceProc: Some(service_main),
        },
        SERVICE_TABLE_ENTRYW {
            lpServiceName: ptr::null_mut(),
            lpServiceProc: None,
        },
    ];
    // SAFETY: terminated service table and callbacks remain live until SCM shutdown.
    checked(unsafe { StartServiceCtrlDispatcherW(table.as_ptr()) })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ordinary_process_has_no_service_worker_authority() {
        assert!(!in_service_job());
        assert!(admit_worker().is_err());
        assert!(!worker_stop_requested());
    }
    #[test]
    fn channel_and_native_logon_define_worker_custody_names() {
        let first = User {
            sid: "S-1-5-21-1".into(),
            logon: 17,
        };
        let second = User {
            logon: 18,
            ..first.clone()
        };
        assert_ne!(name(&first, "stop"), name(&second, "stop"));
        assert_ne!(name(&first, "job"), name(&first, "stop"));
        assert!(name(&first, "stop").contains(crate::identity::MANAGER_ID));
    }
}
