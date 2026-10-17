//! The interpreter host linked into the Cadrumo binary.
//!
//! A role that runs Python enters the same C host the standalone images use, selected at
//! run time instead of by compile-time definitions. The host keeps its restricted DLL
//! search, the bundled CPython DLL and bridge, the package launch guard and the launch
//! profile of the declared image. It returns only when Python has finished.

#[cfg(windows)]
mod windows {
    // The C host calls into both libraries; naming them keeps them in the link.
    use cadrumo_launch_guard as _;
    use cadrumo_platform as _;
    use std::ffi::{CString, OsStr, OsString, c_char, c_int};
    use std::os::windows::ffi::OsStrExt;

    unsafe extern "C" {
        fn cadrumo_host_entrypoint(
            image: *const c_char,
            entrypoint: *const u16,
            argc: c_int,
            argv: *mut *mut u16,
        ) -> c_int;
    }

    fn wide(value: &OsStr) -> Option<Vec<u16>> {
        let mut units: Vec<u16> = value.encode_wide().collect();
        if units.contains(&0) {
            return None;
        }
        units.push(0);
        Some(units)
    }

    /// Run the console script `entrypoint` under the launch profile of `image`, as the
    /// process `executable` with `arguments` after it. `None` when a value holds NUL.
    pub fn run_entrypoint(
        image: &str,
        entrypoint: &str,
        executable: &OsStr,
        arguments: &[OsString],
    ) -> Option<i32> {
        let image = CString::new(image).ok()?;
        let entrypoint = wide(OsStr::new(entrypoint))?;
        let mut owned = vec![wide(executable)?];
        for argument in arguments {
            owned.push(wide(argument)?);
        }
        let argc = c_int::try_from(owned.len()).ok()?;
        let mut argv: Vec<*mut u16> = owned.iter_mut().map(|unit| unit.as_mut_ptr()).collect();
        argv.push(std::ptr::null_mut());
        // SAFETY: every pointer is a NUL-terminated buffer owned above that outlives the
        // call, argv holds argc of them plus a terminating null, and the host neither
        // retains nor frees them.
        Some(unsafe {
            cadrumo_host_entrypoint(image.as_ptr(), entrypoint.as_ptr(), argc, argv.as_mut_ptr())
        })
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn values_holding_nul_are_refused_before_the_host_runs() {
            let executable = OsStr::new("C:\\cadrumo.exe");
            assert_eq!(
                run_entrypoint("cadrumo-runtime\0", "x", executable, &[]),
                None
            );
            assert_eq!(
                run_entrypoint("cadrumo-runtime", "x\0", executable, &[]),
                None
            );
            assert_eq!(
                run_entrypoint("cadrumo-runtime", "x", OsStr::new("a\0b"), &[]),
                None
            );
            assert_eq!(
                run_entrypoint("cadrumo-runtime", "x", executable, &["\0".into()]),
                None
            );
        }
    }
}

#[cfg(windows)]
pub use windows::run_entrypoint;
