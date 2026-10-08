//! An inspection-only adopted process must remain owned after stop failure.
#![cfg(all(windows, feature = "fixture-test-mode"))]

use cadrumo_manager::{
    session::ManagerSession,
    supervision::{
        adoption::{InstalledVersion, InstalledVersions},
        launch::LaunchTarget,
        process::RuntimeProcess,
        stop::{StopSignal, StopSignalError},
        supervisor::{
            Collaborators, EVENT_QUEUE, Effects, Event, Outcome, Request, SessionActivity,
            Supervisor, SupervisorConfig, VersionProbe,
        },
    },
};
use std::{
    fs,
    io::{BufRead, BufReader, ErrorKind},
    os::windows::{io::AsRawHandle, process::CommandExt},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::mpsc,
    thread,
    time::Duration,
};

const FIXTURE: &str = env!("CARGO_BIN_EXE_cadrumo-manager-fixture");

struct Fixture {
    child: Child,
    root: PathBuf,
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = fs::remove_dir_all(&self.root);
    }
}
struct Active;
impl SessionActivity for Active {
    fn is_active(&self) -> bool {
        true
    }
}
struct Probe;
impl VersionProbe for Probe {
    fn reprobe(&mut self) -> Option<String> {
        None
    }
}
struct Catalogue(PathBuf);
impl InstalledVersions for Catalogue {
    fn containing(&self, image: &Path) -> Option<InstalledVersion> {
        (fs::canonicalize(image).ok()? == fs::canonicalize(&self.0).ok()?).then(|| {
            InstalledVersion {
                version: "0.5.1".into(),
                package_root: self.0.parent().unwrap().into(),
                runtime_image: self.0.clone(),
            }
        })
    }
    fn failed(&self, _: &str) -> bool {
        false
    }
}
struct Undeliverable;
impl StopSignal for Undeliverable {
    fn deliver(&self, _: &mut RuntimeProcess) -> Result<(), StopSignalError> {
        Err(StopSignalError::NoConsole)
    }
}

#[test]
fn denied_termination_and_expired_confirmation_retain_the_live_runtime() {
    let root = std::env::temp_dir().join(format!("manager-termination-{}", std::process::id()));
    fs::create_dir(&root).unwrap();
    fs::write(root.join("fixture-plan"), "serve hang=hard\n").unwrap();
    let image = PathBuf::from(FIXTURE);
    let target =
        LaunchTarget::fixture(image.clone(), root.clone(), "ab".repeat(32), "0.5.1".into())
            .unwrap();
    let child = Command::new(&image)
        .args(target.arguments())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .creation_flags(0x08000000)
        .spawn()
        .unwrap();
    let mut fixture = Fixture { child, root };
    let mut reader = BufReader::new(fixture.child.stdout.take().unwrap());
    let mut ready = String::new();
    reader.read_line(&mut ready).unwrap();
    assert!(ready.contains("ready"));
    let sid = ManagerSession::current().unwrap().user;
    let _restricted = process_security::restrict(fixture.child.as_raw_handle(), &sid);
    let (events, observed) = mpsc::sync_channel(EVENT_QUEUE);
    let supervisor = Supervisor::new(
        SupervisorConfig {
            drain_bound: Duration::from_millis(20),
            termination_bound: Duration::from_millis(100),
            poll_interval: Duration::from_millis(10),
            ..SupervisorConfig::default()
        },
        target,
        Collaborators {
            session: Box::new(Active),
            probe: Box::new(Probe),
            versions: Box::new(Catalogue(image)),
            stop_signal: Box::new(Undeliverable),
        },
        events,
    );
    let handle = supervisor.handle();
    assert!(handle.request(Request::Stop));
    let running = thread::spawn(move || supervisor.run_adopting());
    let mut seen = Vec::new();
    loop {
        let event = observed.recv_timeout(Duration::from_secs(20)).unwrap();
        let unconfirmed = matches!(event, Event::TerminationUnconfirmed { .. });
        assert!(!matches!(
            event,
            Event::Terminated { .. } | Event::Exited { .. } | Event::RestartScheduled { .. }
        ));
        seen.push(event);
        if unconfirmed {
            break;
        }
    }
    assert!(seen.iter().any(|event| matches!(
        event,
        Event::TerminationFailed {
            kind: ErrorKind::PermissionDenied,
            os_code: Some(5),
            ..
        }
    )));
    assert!(fixture.child.try_wait().unwrap().is_none());
    assert!(!running.is_finished());
    assert!(handle.request(Request::SessionEnd));
    // The original CreateProcess handle retains its granted rights for independent cleanup.
    fixture.child.kill().unwrap();
    fixture.child.wait().unwrap();
    while let Ok(event) = observed.recv_timeout(Duration::from_secs(20)) {
        seen.push(event);
    }
    assert_eq!(
        running.join().unwrap(),
        Outcome::Stopped {
            effects: Effects::Unknown
        }
    );
    assert_eq!(
        seen.iter()
            .filter(|event| matches!(event, Event::Exited { .. }))
            .count(),
        1
    );
    assert!(!seen.iter().any(|event| matches!(
        event,
        Event::Terminated { .. } | Event::RestartScheduled { .. }
    )));
}

#[allow(unsafe_code)]
mod process_security {
    use std::{
        ffi::c_void,
        os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle, RawHandle},
    };
    #[repr(C)]
    #[derive(Default)]
    struct Luid {
        low: u32,
        high: i32,
    }
    #[repr(C)]
    #[derive(Default)]
    struct Privileges {
        count: u32,
        luid: Luid,
        attributes: u32,
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetCurrentProcess() -> *mut c_void;
        fn LocalFree(memory: *mut c_void) -> *mut c_void;
    }
    #[link(name = "advapi32")]
    unsafe extern "system" {
        fn OpenProcessToken(process: *mut c_void, access: u32, token: *mut *mut c_void) -> i32;
        fn LookupPrivilegeValueW(system: *const u16, name: *const u16, luid: *mut Luid) -> i32;
        fn AdjustTokenPrivileges(
            token: *mut c_void,
            disable_all: i32,
            state: *const Privileges,
            size: u32,
            previous: *mut Privileges,
            returned: *mut u32,
        ) -> i32;
        fn ConvertStringSecurityDescriptorToSecurityDescriptorW(
            text: *const u16,
            revision: u32,
            result: *mut *mut c_void,
            size: *mut u32,
        ) -> i32;
        fn GetSecurityDescriptorDacl(
            descriptor: *mut c_void,
            present: *mut i32,
            dacl: *mut *mut c_void,
            defaulted: *mut i32,
        ) -> i32;
        fn SetSecurityInfo(
            handle: *mut c_void,
            kind: u32,
            information: u32,
            owner: *mut c_void,
            group: *mut c_void,
            dacl: *mut c_void,
            sacl: *mut c_void,
        ) -> u32;
    }
    pub struct Restricted {
        token: OwnedHandle,
        previous: Privileges,
    }
    impl Drop for Restricted {
        fn drop(&mut self) {
            // SAFETY: retained token has adjustment rights; previous is the OS-returned state.
            unsafe {
                AdjustTokenPrivileges(
                    self.token.as_raw_handle().cast(),
                    0,
                    &self.previous,
                    0,
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                );
            }
        }
    }
    pub fn restrict(process: RawHandle, sid: &str) -> Restricted {
        let sddl: Vec<u16> = format!("D:P(D;;0x1;;;{sid})(A;;GA;;;{sid})")
            .encode_utf16()
            .chain([0])
            .collect();
        let mut descriptor = std::ptr::null_mut();
        // SAFETY: terminated SDDL and local out-pointers outlive all synchronous calls;
        // the retained child handle grants WRITE_DAC, and LocalFree owns this descriptor.
        unsafe {
            assert_ne!(
                ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    sddl.as_ptr(),
                    1,
                    &mut descriptor,
                    std::ptr::null_mut()
                ),
                0
            );
            let (mut present, mut defaulted, mut dacl) = (0, 0, std::ptr::null_mut());
            assert_ne!(
                GetSecurityDescriptorDacl(descriptor, &mut present, &mut dacl, &mut defaulted),
                0
            );
            assert_eq!(
                SetSecurityInfo(
                    process.cast(),
                    6,
                    4 | 0x80000000,
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                    dacl,
                    std::ptr::null_mut()
                ),
                0
            );
            LocalFree(descriptor);
        }
        let mut raw = std::ptr::null_mut();
        // SAFETY: pseudo-handle names this test process; raw receives one owned token.
        assert_ne!(
            unsafe { OpenProcessToken(GetCurrentProcess(), 0x20 | 0x8, &mut raw) },
            0
        );
        // SAFETY: OpenProcessToken succeeded and no other owner closes raw.
        let token = unsafe { OwnedHandle::from_raw_handle(raw.cast()) };
        let name: Vec<u16> = "SeDebugPrivilege".encode_utf16().chain([0]).collect();
        let mut state = Privileges {
            count: 1,
            ..Privileges::default()
        };
        let mut previous = Privileges::default();
        let mut returned = 0;
        // SAFETY: valid token/terminated privilege name and correctly sized repr(C) buffers.
        // Only this isolated test executable's privilege is changed, then restored on drop.
        unsafe {
            assert_ne!(
                LookupPrivilegeValueW(std::ptr::null(), name.as_ptr(), &mut state.luid),
                0
            );
            assert_ne!(
                AdjustTokenPrivileges(
                    token.as_raw_handle().cast(),
                    0,
                    &state,
                    std::mem::size_of::<Privileges>() as u32,
                    &mut previous,
                    &mut returned
                ),
                0
            );
        }
        Restricted { token, previous }
    }
}
