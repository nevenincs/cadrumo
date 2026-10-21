//! Native waits over kernel objects and the nearest owned deadline.
#![allow(unsafe_code)]

use super::Notify;
use std::{
    ffi::c_void,
    io,
    os::windows::io::{AsHandle, AsRawHandle, BorrowedHandle, FromRawHandle, OwnedHandle},
    ptr,
    sync::Arc,
    thread::JoinHandle,
    time::{Duration, Instant},
};
use windows_sys::Win32::System::Threading::{CreateEventW, SetEvent};

type Handle = *mut c_void;
const INFINITE: u32 = u32::MAX;
const WAIT_TIMEOUT: u32 = 258;
const WAIT_FAILED: u32 = u32::MAX;
const WAIT_ABANDONED: u32 = 0x80;
const QS_ALLINPUT: u32 = 0x04ff;
const MWMO_INPUTAVAILABLE: u32 = 0x0004;
const MAXIMUM_WAIT_OBJECTS: usize = 64;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn WaitForSingleObject(handle: Handle, timeout: u32) -> u32;
    fn WaitForMultipleObjects(count: u32, handles: *const Handle, all: i32, timeout: u32) -> u32;
}
#[link(name = "user32")]
unsafe extern "system" {
    fn MsgWaitForMultipleObjectsEx(
        count: u32,
        handles: *const Handle,
        timeout: u32,
        mask: u32,
        flags: u32,
    ) -> u32;
}

/// A private auto-reset event: each signal releases one wait, so a consumer
/// that has drained its producers never observes a stale signal twice.
pub struct Event(OwnedHandle);

impl Event {
    pub fn new() -> io::Result<Arc<Self>> {
        // SAFETY: creates a private, noninheritable, unnamed auto-reset event.
        let handle = unsafe { CreateEventW(ptr::null(), 0, 0, ptr::null()) };
        if handle.is_null() {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: successful creation transferred this distinct owned handle.
        Ok(Arc::new(Self(unsafe {
            OwnedHandle::from_raw_handle(handle)
        })))
    }

    pub fn set(&self) {
        // SAFETY: the owned event remains open for this call.
        unsafe {
            SetEvent(self.0.as_raw_handle());
        }
    }

    pub fn notifier(self: &Arc<Self>) -> Notify {
        let event = Arc::clone(self);
        Arc::new(move || event.set())
    }
}

impl AsHandle for Event {
    fn as_handle(&self) -> BorrowedHandle<'_> {
        self.0.as_handle()
    }
}

/// What ended a wait.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Woken {
    Signaled,
    Input,
    Elapsed,
}

/// The kernel objects and the nearest deadline a host loop waits on. Borrowing
/// keeps every handle open until the wait returns.
#[derive(Default)]
pub struct Readiness<'a> {
    handles: Vec<BorrowedHandle<'a>>,
    deadline: Option<Instant>,
}

impl<'a> Readiness<'a> {
    pub fn handle(&mut self, handle: BorrowedHandle<'a>) {
        self.handles.push(handle);
    }

    pub fn at(&mut self, deadline: Instant) {
        self.deadline = Some(
            self.deadline
                .map_or(deadline, |current| current.min(deadline)),
        );
    }

    pub fn after(&mut self, delay: Duration) {
        self.at(Instant::now() + delay);
    }

    pub fn now(&mut self) {
        self.at(Instant::now());
    }

    fn timeout(&self) -> u32 {
        self.deadline.map_or(INFINITE, timeout_until)
    }

    fn raw(&self, limit: usize) -> io::Result<Vec<Handle>> {
        if self.handles.len() > limit {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        Ok(self
            .handles
            .iter()
            .map(AsRawHandle::as_raw_handle)
            .collect())
    }

    /// Block until a handle is signaled or the nearest deadline passes.
    pub fn wait(&self) -> io::Result<Woken> {
        let handles = self.raw(MAXIMUM_WAIT_OBJECTS)?;
        let timeout = self.timeout();
        if handles.is_empty() {
            if timeout == INFINITE {
                return Err(io::ErrorKind::InvalidInput.into());
            }
            std::thread::sleep(Duration::from_millis(u64::from(timeout)));
            return Ok(Woken::Elapsed);
        }
        // SAFETY: every handle is borrowed from an object that outlives `self`.
        let result =
            unsafe { WaitForMultipleObjects(handles.len() as u32, handles.as_ptr(), 0, timeout) };
        woken(result, handles.len() as u32, false)
    }

    /// As [`Readiness::wait`], also returning when window-thread input is queued,
    /// including input already queued before the call.
    pub fn wait_with_messages(&self) -> io::Result<Woken> {
        let handles = self.raw(MAXIMUM_WAIT_OBJECTS - 1)?;
        // SAFETY: every handle is borrowed from an object that outlives `self`;
        // an empty array is permitted and then only input or the timeout end it.
        let result = unsafe {
            MsgWaitForMultipleObjectsEx(
                handles.len() as u32,
                if handles.is_empty() {
                    ptr::null()
                } else {
                    handles.as_ptr()
                },
                self.timeout(),
                QS_ALLINPUT,
                MWMO_INPUTAVAILABLE,
            )
        };
        woken(result, handles.len() as u32, true)
    }
}

fn woken(result: u32, count: u32, input: bool) -> io::Result<Woken> {
    match result {
        WAIT_FAILED => Err(io::Error::last_os_error()),
        WAIT_TIMEOUT => Ok(Woken::Elapsed),
        index if index < count => Ok(Woken::Signaled),
        index if input && index == count => Ok(Woken::Input),
        index if (WAIT_ABANDONED..WAIT_ABANDONED + count).contains(&index) => Ok(Woken::Signaled),
        _ => Err(io::ErrorKind::InvalidData.into()),
    }
}

/// Milliseconds until `deadline`, rounded up so a wait never ends before it.
fn timeout_until(deadline: Instant) -> u32 {
    let remaining = deadline.saturating_duration_since(Instant::now());
    let millis = remaining.as_nanos().div_ceil(1_000_000);
    millis.min(u128::from(INFINITE - 1)) as u32
}

/// Wait for a thread to return. The thread handle is signaled only after the
/// thread has finished, so a true result means joining it will not block.
pub fn wait_thread<T>(worker: &JoinHandle<T>, bound: Duration) -> io::Result<bool> {
    let timeout = timeout_until(Instant::now() + bound);
    // SAFETY: the join handle owns the thread handle and outlives this wait.
    match unsafe { WaitForSingleObject(worker.as_raw_handle(), timeout) } {
        WAIT_FAILED => Err(io::Error::last_os_error()),
        WAIT_TIMEOUT => Ok(false),
        _ => Ok(true),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_idle_set_waits_for_its_deadline_and_a_signal_ends_the_wait_once() {
        let event = Event::new().unwrap();
        let mut readiness = Readiness::default();
        readiness.handle(event.as_handle());
        readiness.after(Duration::from_millis(60));
        let started = Instant::now();
        assert_eq!(readiness.wait().unwrap(), Woken::Elapsed);
        assert!(started.elapsed() >= Duration::from_millis(60));

        let signal = Arc::clone(&event);
        let signaller = std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(20));
            signal.set();
        });
        let mut readiness = Readiness::default();
        readiness.handle(event.as_handle());
        readiness.after(Duration::from_secs(5));
        let started = Instant::now();
        assert_eq!(readiness.wait().unwrap(), Woken::Signaled);
        assert!(started.elapsed() < Duration::from_secs(2));
        signaller.join().unwrap();
        // Auto-reset: the consumed signal does not end a second wait.
        let mut readiness = Readiness::default();
        readiness.handle(event.as_handle());
        readiness.after(Duration::from_millis(20));
        assert_eq!(readiness.wait().unwrap(), Woken::Elapsed);
    }

    #[test]
    fn a_thread_wait_returns_when_the_thread_does_and_otherwise_at_its_bound() {
        let (release, gate) = std::sync::mpsc::channel::<()>();
        let worker = std::thread::spawn(move || {
            let _ = gate.recv();
        });
        assert!(!wait_thread(&worker, Duration::from_millis(20)).unwrap());
        assert!(!worker.is_finished());
        drop(release);
        assert!(wait_thread(&worker, Duration::from_secs(5)).unwrap());
        assert!(worker.is_finished());
        worker.join().unwrap();
    }
}
