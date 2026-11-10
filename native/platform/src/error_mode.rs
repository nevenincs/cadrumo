//! Windows error-mode control, so that an unusable program image fails the process
//! creation call instead of raising a dialog.
//!
//! With the default error mode, creating a process from a file that is not a valid
//! program image for this machine raises a modal system message box and does not return
//! until someone answers it. A service, a background manager or a test host has nobody to
//! answer, so the creating thread waits forever, and with it every caller that needs the
//! creation step that thread holds. With the modes below the same call returns an error
//! at once (`ERROR_BAD_EXE_FORMAT`, `ERROR_EXE_MACHINE_TYPE_MISMATCH`).

use std::io;

// Fail on a critical error instead of asking, show no crash dialog, and show no
// open-file dialog.
const SEM_FAILCRITICALERRORS: u32 = 0x0001;
const SEM_NOGPFAULTERRORBOX: u32 = 0x0002;
const SEM_NOOPENFILEERRORBOX: u32 = 0x8000;
const HEADLESS_MODE: u32 = SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn SetErrorMode(mode: u32) -> u32;
    fn SetThreadErrorMode(new_mode: u32, old_mode: *mut u32) -> i32;
    #[cfg(test)]
    fn GetThreadErrorMode() -> u32;
}

/// Makes every later critical or program-image error of this process fail its call
/// rather than raise a dialog. Call once, early in a process that creates children.
///
/// The mode is inherited by every child this process creates, which is intended: a
/// headless server must not raise a dialog nobody can answer either.
pub fn suppress_dialogs_for_process() {
    // SAFETY: this sets a flag word of the calling process and takes no pointers.
    unsafe { SetErrorMode(HEADLESS_MODE) };
}

/// The calling thread's error mode, set to fail instead of raising a dialog until this
/// guard is dropped. Children created meanwhile do not inherit a thread's mode.
///
/// The guard belongs to the thread that made it: it restores that thread's earlier mode,
/// so it is neither `Send` nor `Sync`.
#[derive(Debug)]
#[must_use = "the mode is restored as soon as the guard is dropped"]
pub struct ThreadDialogSuppression {
    previous: u32,
    thread_bound: std::marker::PhantomData<*const ()>,
}

impl ThreadDialogSuppression {
    /// Sets the calling thread's error mode to the headless one.
    pub fn enter() -> io::Result<Self> {
        let mut previous = 0_u32;
        // SAFETY: `previous` is a live, writable word for the length of the call.
        if unsafe { SetThreadErrorMode(HEADLESS_MODE, &mut previous) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Self {
            previous,
            thread_bound: std::marker::PhantomData,
        })
    }
}

impl Drop for ThreadDialogSuppression {
    fn drop(&mut self) {
        // SAFETY: the old mode is not asked for, so a null pointer is permitted.
        unsafe { SetThreadErrorMode(self.previous, std::ptr::null_mut()) };
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_guard_sets_the_headless_mode_and_restores_the_earlier_one() {
        // A thread of its own, so the harness thread's mode is never touched.
        std::thread::spawn(|| {
            // SAFETY: a read of this thread's mode, taking no pointers.
            let before = unsafe { GetThreadErrorMode() };
            {
                let _guard = ThreadDialogSuppression::enter().unwrap();
                // SAFETY: as above.
                let during = unsafe { GetThreadErrorMode() };
                assert_eq!(during & HEADLESS_MODE, HEADLESS_MODE);
                {
                    let _nested = ThreadDialogSuppression::enter().unwrap();
                }
                // SAFETY: as above.
                assert_eq!(unsafe { GetThreadErrorMode() }, during);
            }
            // SAFETY: as above.
            assert_eq!(unsafe { GetThreadErrorMode() }, before);
        })
        .join()
        .unwrap();
    }
}
