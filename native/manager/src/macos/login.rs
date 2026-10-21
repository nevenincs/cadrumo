//! Kernel peer-session provenance; graphical access does not prove an unlocked desktop.

use std::io;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Token([u32; 8]);

impl Token {
    fn decode(bytes: &[u8], owner: u32) -> io::Result<Self> {
        if bytes.len() != 32 || owner == 0 {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let mut words = [0; 8];
        for (word, bytes) in words.iter_mut().zip(bytes.chunks_exact(4)) {
            *word = u32::from_ne_bytes(bytes.try_into().map_err(|_| io::ErrorKind::InvalidData)?);
        }
        if words[0] != owner
            || words[1] != owner
            || words[3] != owner
            || !(1..=i32::MAX as u32).contains(&words[5])
            || !valid_session(words[6])
            || words[7] == 0
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(Self(words))
    }

    fn corroborate(self, pid: u32, version: u32, owner: u32) -> io::Result<()> {
        if self.0[5] != pid || self.0[7] != version || self.0[1] != owner {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }
}

fn valid_session(id: u32) -> bool {
    (1..0xffff_fffe).contains(&id)
}

/// Fresh session facts only. Neither variant supplies lock or unattended eligibility.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Observation {
    Absent,
    Present { graphical: bool },
}

fn observation(
    requested: u32,
    status: i32,
    observed: u32,
    attributes: u32,
) -> io::Result<Observation> {
    if !valid_session(requested) {
        return Err(io::ErrorKind::InvalidInput.into());
    }
    if status == -60500 {
        return Ok(Observation::Absent);
    }
    // SessionGetInfo forwards audit flags, including console/authenticated bits.
    // These known bits do not grant unlocked or unattended eligibility.
    if status != 0 || observed != requested || attributes & !0x7031 != 0 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok(Observation::Present {
        graphical: attributes & 0x10 != 0 && attributes & 0x1001 == 0,
    })
}

#[cfg(target_os = "macos")]
mod native {
    #![allow(unsafe_code)]
    use super::{Observation, Token, observation};
    use crate::macos::process::Process;
    use std::{
        ffi::c_void,
        io,
        os::{fd::AsRawFd, unix::net::UnixStream},
    };

    type SessionInfo = unsafe extern "C" fn(u32, *mut u32, *mut u32) -> i32;

    unsafe extern "C" {
        // mach/task_info.h and mach/mach_init.h: borrowed current-task send right.
        static mach_task_self_: u32;
        fn task_info(task: u32, flavor: u32, output: *mut i32, count: *mut u32) -> i32;
        fn task_name_for_pid(task: u32, pid: i32, port: *mut u32) -> i32;
        fn mach_port_deallocate(task: u32, port: u32) -> i32;
    }

    /// An observation-only send right, never a task-control or debugger right.
    struct TaskName(u32);

    impl TaskName {
        fn open(process: &Process) -> io::Result<Self> {
            let pid = process.identity()?.incarnation.pid;
            let mut port = 0;
            // SAFETY: public mach/mach_traps.h ABI; writable name-port output.
            // The retained process brackets the numeric lookup and the returned
            // kernel token must match its pidversion before it grants authority.
            let status = unsafe { task_name_for_pid(mach_task_self_, pid as i32, &mut port) };
            let owned = (port != 0 && port != u32::MAX).then(|| Self(port));
            if status != 0 {
                // KERN_FAILURE includes policy denial and absence. It is not errno
                // and must never be translated into proof that a process exited.
                return Err(io::Error::other(format!(
                    "task_name_for_pid: Mach status {status}"
                )));
            }
            owned.ok_or_else(|| io::ErrorKind::InvalidData.into())
        }
    }

    impl Drop for TaskName {
        fn drop(&mut self) {
            // SAFETY: this is the uniquely owned send right returned by the kernel;
            // the current-task port itself remains borrowed and is not released.
            unsafe {
                mach_port_deallocate(mach_task_self_, self.0);
            }
        }
    }

    fn current_token(process: &Process) -> io::Result<Token> {
        if process.identity()?.incarnation.pid != std::process::id() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        // SAFETY: the current-task send right is borrowed for this call only.
        task_token(unsafe { mach_task_self_ }, process)
    }

    fn task_token(port: u32, process: &Process) -> io::Result<Token> {
        let identity = process.identity()?;
        let mut words = [0u32; 8];
        let mut count = 8;
        // SAFETY: TASK_AUDIT_TOKEN (15) copies eight natural_t words into the
        // bounded buffer; the caller retains the task-name right throughout.
        let status = unsafe { task_info(port, 15, words.as_mut_ptr().cast(), &mut count) };
        if status != 0 {
            return Err(io::Error::other(format!("task_info: Mach status {status}")));
        }
        if count != 8 {
            return Err(io::ErrorKind::InvalidData.into());
        }
        let bytes: Vec<u8> = words.into_iter().flat_map(u32::to_ne_bytes).collect();
        let token = Token::decode(&bytes, identity.observed.uid)?;
        token.corroborate(
            identity.incarnation.pid,
            identity.incarnation.version,
            identity.observed.uid,
        )?;
        process.identity()?;
        Ok(token)
    }

    pub struct Login {
        library: *mut c_void,
        query: SessionInfo,
    }

    /// Only native kernel-token capture constructs this binding. Session IDs never come from JSON.
    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub struct Session {
        uid: u32,
        id: u32,
    }

    impl Session {
        pub fn uid(&self) -> u32 {
            self.uid
        }
        pub fn id(&self) -> u32 {
            self.id
        }
    }

    impl Drop for Login {
        fn drop(&mut self) {
            // SAFETY: this uniquely held handle came from dlopen.
            unsafe {
                libc::dlclose(self.library);
            }
        }
    }

    fn socket_record<const N: usize>(socket: &UnixStream, option: i32) -> io::Result<[u8; N]> {
        let mut bytes = [0; N];
        let mut size = N as libc::socklen_t;
        // SAFETY: borrowed stream keeps descriptor live; buffer and length are writable.
        let result = unsafe {
            libc::getsockopt(
                socket.as_raw_fd(),
                0,
                option,
                bytes.as_mut_ptr().cast(),
                &mut size,
            )
        };
        if result != 0 {
            return Err(io::Error::last_os_error());
        }
        if size as usize != N {
            return Err(io::ErrorKind::InvalidData.into());
        }
        Ok(bytes)
    }

    fn token(socket: &UnixStream, process: &Process) -> io::Result<Token> {
        let identity = process.identity()?;
        let mut uid = 0;
        let mut gid = 0;
        // SAFETY: borrowed live local socket and writable UID/GID outputs.
        if unsafe { libc::getpeereid(socket.as_raw_fd(), &mut uid, &mut gid) } != 0 {
            return Err(io::Error::last_os_error());
        }
        let token = Token::decode(&socket_record::<32>(socket, 6)?, uid)?;
        let pid = i32::from_ne_bytes(socket_record::<4>(socket, 2)?);
        if pid <= 0 || pid as u32 != token.0[5] {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        token.corroborate(
            identity.incarnation.pid,
            identity.incarnation.version,
            identity.observed.uid,
        )?;
        process.identity()?;
        Ok(token)
    }

    impl Login {
        pub fn open() -> io::Result<Self> {
            // SAFETY: fixed system framework path; returned handle is retained.
            let library = unsafe {
                libc::dlopen(
                    c"/System/Library/Frameworks/Security.framework/Security".as_ptr(),
                    libc::RTLD_NOW | libc::RTLD_LOCAL,
                )
            };
            if library.is_null() {
                return Err(io::ErrorKind::Unsupported.into());
            }
            // SAFETY: terminated symbol name and live handle.
            let symbol = unsafe { libc::dlsym(library, c"SessionGetInfo".as_ptr()) };
            if symbol.is_null() {
                // SAFETY: no function pointer escapes the failed lookup.
                unsafe {
                    libc::dlclose(library);
                }
                return Err(io::ErrorKind::Unsupported.into());
            }
            // SAFETY: exact Security framework SessionGetInfo ABI, handle retained by Self.
            let query = unsafe { std::mem::transmute::<*mut c_void, SessionInfo>(symbol) };
            Ok(Self { library, query })
        }

        pub fn observe(&self, session: &Session) -> io::Result<Observation> {
            let mut id = 0;
            let mut attributes = 0;
            // SAFETY: retained function pointer and two writable u32 outputs.
            let status = unsafe { (self.query)(session.id, &mut id, &mut attributes) };
            observation(session.id, status, id, attributes)
        }

        /// Native current-task identity, with the same admission policy as a socket peer.
        pub fn current(&self, process: &Process) -> io::Result<Session> {
            let before = current_token(process)?;
            let session = Session {
                uid: before.0[1],
                id: before.0[6],
            };
            if self.observe(&session)? != (Observation::Present { graphical: true }) {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            if current_token(process)? != before {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            Ok(session)
        }

        /// Observe an arbitrary held process through its native task-name right.
        /// A boot record or a signal-only audit token cannot supply this identity.
        pub fn process(&self, process: &Process) -> io::Result<Session> {
            let port = TaskName::open(process)?;
            let before = task_token(port.0, process)?;
            let session = Session {
                uid: before.0[1],
                id: before.0[6],
            };
            if self.observe(&session)? != (Observation::Present { graphical: true }) {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            if task_token(port.0, process)? != before {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            Ok(session)
        }

        /// Fresh kernel identity only, for revalidating already-admitted ownership.
        /// This does not grant graphical, unlocked or unattended authority, and
        /// remains usable while the admitted login session is being torn down.
        pub(crate) fn process_identity(process: &Process) -> io::Result<Session> {
            let port = TaskName::open(process)?;
            let before = task_token(port.0, process)?;
            if task_token(port.0, process)? != before {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            Ok(Session {
                uid: before.0[1],
                id: before.0[6],
            })
        }

        /// Open only the kernel's peer PID, then require its current audit incarnation.
        pub fn peer(&self, socket: &UnixStream) -> io::Result<(Process, Session)> {
            let pid = i32::from_ne_bytes(socket_record::<4>(socket, 2)?);
            if pid <= 0 {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            let process = Process::open(pid as u32)?;
            let session = self.capture_peer(socket, &process)?;
            Ok((process, session))
        }

        pub fn capture_peer(&self, socket: &UnixStream, process: &Process) -> io::Result<Session> {
            let before = token(socket, process)?;
            let session = Session {
                uid: before.0[1],
                id: before.0[6],
            };
            if self.observe(&session)? != (Observation::Present { graphical: true }) {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            if token(socket, process)? != before {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            Ok(session)
        }
    }
    #[cfg(test)]
    mod native_tests {
        use super::*;

        #[test]
        fn task_name_token_corroborates_owned_child_and_preserves_session_policy() {
            use std::process::{Child, Command, Stdio};
            struct InputChild(Child);
            impl Drop for InputChild {
                fn drop(&mut self) {
                    drop(self.0.stdin.take());
                    self.0.wait().unwrap();
                }
            }
            let child = InputChild(
                Command::new("/bin/cat")
                    .stdin(Stdio::piped())
                    .stdout(Stdio::null())
                    .spawn()
                    .unwrap(),
            );
            let own = Process::open(std::process::id()).unwrap();
            let held = Process::open(child.0.id()).unwrap();
            let port = TaskName::open(&held).unwrap();
            let before = task_token(port.0, &held).unwrap();
            assert_eq!(before.0[6], current_token(&own).unwrap().0[6]);
            assert_eq!(task_token(port.0, &held).unwrap(), before);
            let login = Login::open().unwrap();
            let session = Session {
                uid: before.0[1],
                id: before.0[6],
            };
            assert_eq!(Login::process_identity(&held).unwrap(), session);
            match login.observe(&session).unwrap() {
                Observation::Present { graphical: true } => {
                    assert_eq!(login.process(&held).unwrap(), session);
                }
                _ => assert_eq!(
                    login.process(&held).unwrap_err().kind(),
                    io::ErrorKind::PermissionDenied
                ),
            }
            drop(child);
            assert!(held.exited().unwrap());
            assert_eq!(
                login.process(&held).unwrap_err().kind(),
                io::ErrorKind::NotFound
            );
        }

        #[test]
        fn current_kernel_token_matches_held_process_and_native_session_policy() {
            let process = Process::open(std::process::id()).unwrap();
            let token = current_token(&process).unwrap();
            let login = Login::open().unwrap();
            let session = Session {
                uid: token.0[1],
                id: token.0[6],
            };
            let observed = login.observe(&session).unwrap();
            match observed {
                Observation::Present { graphical: true } => {
                    assert_eq!(login.current(&process).unwrap(), session);
                    assert_eq!(login.process(&process).unwrap(), session);
                }
                _ => {
                    assert_eq!(
                        login.current(&process).unwrap_err().kind(),
                        io::ErrorKind::PermissionDenied
                    );
                    assert_eq!(
                        login.process(&process).unwrap_err().kind(),
                        io::ErrorKind::PermissionDenied
                    );
                }
            }
        }
    }
}

#[cfg(target_os = "macos")]
pub use native::{Login, Session};

#[cfg(test)]
mod tests {
    use super::*;
    fn bytes(words: [u32; 8]) -> Vec<u8> {
        words.into_iter().flat_map(u32::to_ne_bytes).collect()
    }

    #[test]
    fn token_requires_exact_kernel_owner_and_bounded_coordinates() {
        let words = [501, 501, 20, 501, 20, 77, 42, 3];
        let token = Token::decode(&bytes(words), 501).unwrap();
        token.corroborate(77, 3, 501).unwrap();
        for (pid, version, owner) in [(78, 3, 501), (77, 4, 501), (77, 3, 502)] {
            assert!(token.corroborate(pid, version, owner).is_err());
        }
        for (offset, value) in [
            (0, 502),
            (1, 502),
            (3, 502),
            (5, 0),
            (5, u32::MAX),
            (6, 0),
            (6, 0xffff_fffe),
            (6, u32::MAX),
            (7, 0),
        ] {
            let mut changed = words;
            changed[offset] = value;
            assert!(Token::decode(&bytes(changed), 501).is_err());
        }
        assert!(Token::decode(&bytes(words)[..31], 501).is_err());
        assert!(Token::decode(&bytes([0; 8]), 0).is_err());
    }

    #[test]
    fn session_absence_does_not_hide_query_failure_or_identity_change() {
        assert_eq!(observation(42, -60500, 0, 0).unwrap(), Observation::Absent);
        for (status, id, flags) in [(1, 42, 0x10), (0, 43, 0x10), (0, 42, 0x40)] {
            assert!(observation(42, status, id, flags).is_err());
        }
        for id in [0, 0xffff_fffe, u32::MAX] {
            assert!(observation(id, -60500, 0, 0).is_err());
        }
        assert_eq!(
            observation(42, 0, 42, 0x30).unwrap(),
            Observation::Present { graphical: true }
        );
        for flags in [0x2010, 0x4010, 0x6010] {
            assert_eq!(
                observation(42, 0, 42, flags).unwrap(),
                Observation::Present { graphical: true }
            );
        }
        for flags in [0, 0x20, 0x11, 0x1010, 0x1031, 0x5020, 0x7010, 0x4011] {
            assert_eq!(
                observation(42, 0, 42, flags).unwrap(),
                Observation::Present { graphical: false }
            );
        }
    }
}
