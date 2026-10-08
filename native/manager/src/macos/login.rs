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

    pub struct Login {
        library: *mut c_void,
        query: SessionInfo,
    }

    /// Only native peer capture constructs this binding. Session IDs never come from JSON.
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
