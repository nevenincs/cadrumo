//! Caller-scoped Quartz console activity, corroborated by retained audit identity.
//!
//! Console activity does not prove unlocked or unattended eligibility. Switching
//! away is inactivity, never evidence that the native login session has ended.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Observation {
    Active,
    Inactive,
    Unavailable,
}

#[derive(Clone, Copy, Debug)]
struct Console {
    uid: u32,
    on_console: bool,
    login_done: bool,
}

fn classify(owner: u32, console: Option<Console>, identity_matches: bool) -> Observation {
    let Some(console) = console else {
        return Observation::Unavailable;
    };
    if owner == 0 || console.uid != owner || !identity_matches {
        Observation::Unavailable
    } else if console.on_console && console.login_done {
        Observation::Active
    } else {
        Observation::Inactive
    }
}

#[cfg(target_os = "macos")]
mod native {
    #![allow(unsafe_code)]

    use super::{Console, Observation, classify};
    use crate::macos::{
        login::{Login, Session},
        process::Process,
    };
    use std::{ffi::c_void, io, ptr};

    type Ref = *const c_void;

    #[link(name = "CoreGraphics", kind = "framework")]
    unsafe extern "C" {
        // CGSession.h: public since macOS 10.3, scoped to the caller's Quartz session.
        fn CGSessionCopyCurrentDictionary() -> Ref;
    }

    #[link(name = "CoreFoundation", kind = "framework")]
    unsafe extern "C" {
        fn CFRelease(value: Ref);
        fn CFGetTypeID(value: Ref) -> usize;
        fn CFDictionaryGetTypeID() -> usize;
        fn CFDictionaryGetValue(dictionary: Ref, key: Ref) -> Ref;
        fn CFStringCreateWithBytes(
            allocator: Ref,
            bytes: *const u8,
            count: isize,
            encoding: u32,
            external: u8,
        ) -> Ref;
        fn CFNumberGetTypeID() -> usize;
        fn CFNumberIsFloatType(number: Ref) -> u8;
        fn CFNumberGetValue(number: Ref, kind: isize, output: *mut c_void) -> u8;
        fn CFBooleanGetTypeID() -> usize;
        fn CFBooleanGetValue(boolean: Ref) -> u8;
    }

    /// One owned Create/Copy reference. Borrowed dictionary members never enter it.
    struct Owned(Ref);
    impl Owned {
        fn key(bytes: &[u8]) -> Option<Self> {
            // SAFETY: bounded static ASCII key bytes, valid UTF-8 encoding constant,
            // default allocator, and exact readable buffer length.
            let value = unsafe {
                CFStringCreateWithBytes(
                    ptr::null(),
                    bytes.as_ptr(),
                    bytes.len() as isize,
                    0x0800_0100,
                    0,
                )
            };
            (!value.is_null()).then(|| Self(value))
        }
    }
    impl Drop for Owned {
        fn drop(&mut self) {
            // SAFETY: nonnull uniquely owned Create/Copy reference released once.
            unsafe { CFRelease(self.0) }
        }
    }

    fn uid(value: Ref) -> Option<u32> {
        // SAFETY: caller passes a live borrowed CF object or null. Check runtime
        // type before the number-only API; reject float coercion and lossy reads.
        if value.is_null()
            || unsafe {
                CFGetTypeID(value) != CFNumberGetTypeID() || CFNumberIsFloatType(value) != 0
            }
        {
            return None;
        }
        let mut value64 = 0i64;
        // SAFETY: kCFNumberSInt64Type=4 and an exact writable i64 output buffer.
        if unsafe { CFNumberGetValue(value, 4, (&mut value64 as *mut i64).cast()) } == 0 {
            return None;
        }
        u32::try_from(value64).ok()
    }

    fn boolean(value: Ref) -> Option<bool> {
        // SAFETY: as above; numeric 0/1 and strings are not CFBoolean authority.
        if value.is_null() || unsafe { CFGetTypeID(value) != CFBooleanGetTypeID() } {
            return None;
        }
        // SAFETY: the runtime type check established a live CFBoolean object.
        Some(unsafe { CFBooleanGetValue(value) } != 0)
    }

    fn console() -> Option<Console> {
        // SAFETY: public no-argument query; null is a documented unavailable result.
        let value = unsafe { CGSessionCopyCurrentDictionary() };
        if value.is_null() {
            return None;
        }
        let dictionary = Owned(value);
        // SAFETY: Copy returned an owned CF object; verify before dictionary access.
        if unsafe { CFGetTypeID(dictionary.0) != CFDictionaryGetTypeID() } {
            return None;
        }
        let owner_key = Owned::key(b"kCGSSessionUserIDKey")?;
        let console_key = Owned::key(b"kCGSSessionOnConsoleKey")?;
        let login_key = Owned::key(b"kCGSessionLoginDoneKey")?;
        // SAFETY: all keys and dictionary are retained; returned member objects are
        // borrowed only until dictionary drops, after these typed reads finish.
        let (owner, on_console, login_done) = unsafe {
            (
                CFDictionaryGetValue(dictionary.0, owner_key.0),
                CFDictionaryGetValue(dictionary.0, console_key.0),
                CFDictionaryGetValue(dictionary.0, login_key.0),
            )
        };
        Some(Console {
            uid: uid(owner)?,
            on_console: boolean(on_console)?,
            login_done: boolean(login_done)?,
        })
    }

    /// Activity for this fully admitted graphical manager incarnation only.
    #[derive(Debug)]
    pub struct Activity {
        process: Process,
        session: Session,
    }

    impl Activity {
        pub fn current() -> io::Result<Self> {
            let process = Process::open(std::process::id())?;
            let session = Login::open()?.current(&process)?;
            Ok(Self { process, session })
        }

        pub fn observe(&self) -> Observation {
            if Login::process_identity(&self.process).ok() != Some(self.session) {
                return Observation::Unavailable;
            }
            let observed = console();
            // UID is not an ASID. The caller-scoped Quartz observation is bracketed
            // by the retained native audit identity, never by a dictionary session ID.
            let unchanged = Login::process_identity(&self.process).ok() == Some(self.session);
            classify(self.session.uid(), observed, unchanged)
        }
    }

    impl crate::supervision::supervisor::SessionActivity for Activity {
        fn is_active(&self) -> bool {
            self.observe() == Observation::Active
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        unsafe extern "C" {
            fn CFNumberCreate(allocator: Ref, kind: isize, value: *const c_void) -> Ref;
            static kCFBooleanTrue: Ref;
            static kCFBooleanFalse: Ref;
        }

        #[test]
        fn native_public_values_require_exact_types_and_uid_range() {
            assert_eq!(uid(ptr::null()), None);
            assert_eq!(boolean(ptr::null()), None);
            let text = Owned::key(b"501").unwrap();
            assert_eq!(uid(text.0), None);
            assert_eq!(boolean(text.0), None);
            for number in [-1i64, 0, 501, u32::MAX as i64, u32::MAX as i64 + 1] {
                // SAFETY: exact SInt64 value buffer; own the newly created reference.
                let raw = unsafe { CFNumberCreate(ptr::null(), 4, (&number as *const i64).cast()) };
                assert!(!raw.is_null());
                let value = Owned(raw);
                assert_eq!(uid(value.0), u32::try_from(number).ok());
                assert_eq!(boolean(value.0), None);
            }
            let number = 501f64;
            // SAFETY: kCFNumberFloat64Type=6 and exact readable f64 buffer.
            let raw = unsafe { CFNumberCreate(ptr::null(), 6, (&number as *const f64).cast()) };
            assert!(!raw.is_null());
            let float = Owned(raw);
            assert_eq!(uid(float.0), None);
            // SAFETY: borrowed immortal public CFBoolean constants, never released.
            unsafe {
                assert_eq!(boolean(kCFBooleanTrue), Some(true));
                assert_eq!(boolean(kCFBooleanFalse), Some(false));
                assert_eq!(uid(kCFBooleanTrue), None);
            }
        }

        #[test]
        fn native_query_does_not_bypass_graphical_admission() {
            // Read only: no application event loop, switch, login or session mutation.
            let queried = console();
            eprintln!(
                "caller Quartz dictionary available with public typed fields: {}",
                queried.is_some()
            );
            let process = Process::open(std::process::id()).unwrap();
            match Login::open().unwrap().current(&process) {
                Ok(session) => {
                    let activity = Activity::current().unwrap();
                    assert_eq!(activity.session, session);
                    let _observation = activity.observe();
                }
                Err(_) => assert!(Activity::current().is_err()),
            }
        }
    }
}

#[cfg(target_os = "macos")]
pub use native::Activity;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_corroborated_completed_console_login_is_active() {
        let active = Console {
            uid: 501,
            on_console: true,
            login_done: true,
        };
        assert_eq!(classify(501, Some(active), true), Observation::Active);
        assert_eq!(classify(501, None, true), Observation::Unavailable);
        assert_eq!(classify(501, Some(active), false), Observation::Unavailable);
        assert_eq!(classify(502, Some(active), true), Observation::Unavailable);
        assert_eq!(
            classify(0, Some(Console { uid: 0, ..active }), true),
            Observation::Unavailable
        );
        for (on_console, login_done) in [(false, false), (false, true), (true, false)] {
            assert_eq!(
                classify(
                    501,
                    Some(Console {
                        on_console,
                        login_done,
                        ..active
                    }),
                    true
                ),
                Observation::Inactive
            );
        }
    }
}
