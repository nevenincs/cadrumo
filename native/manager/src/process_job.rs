//! A kill-on-close Job Object for one supervised child and everything it starts.
//!
//! The owner creates the child suspended, hands it here before any of its code
//! runs, and keeps the job for the child's whole life. Closing the job's last
//! handle, which happens however the owner ends, terminates every process still
//! in it. Breakaway is not granted, so the child cannot start a process outside.
#![allow(unsafe_code)]

use std::{
    io,
    os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle},
    process::Child,
    ptr,
};
use windows_sys::Win32::{
    Foundation::{HANDLE, INVALID_HANDLE_VALUE},
    System::{
        Diagnostics::ToolHelp::{
            CreateToolhelp32Snapshot, TH32CS_SNAPTHREAD, THREADENTRY32, Thread32First, Thread32Next,
        },
        JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
            JOBOBJECT_BASIC_ACCOUNTING_INFORMATION, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            JobObjectBasicAccountingInformation, JobObjectExtendedLimitInformation,
            QueryInformationJobObject, SetInformationJobObject, TerminateJobObject,
        },
        Threading::{OpenThread, ResumeThread, THREAD_SUSPEND_RESUME},
    },
};

/// The creation flag the owner passes so the child runs nothing before it is
/// contained.
pub const CREATE_SUSPENDED: u32 = 0x0000_0004;

fn checked(value: i32) -> io::Result<()> {
    if value == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

fn owned(handle: HANDLE) -> io::Result<OwnedHandle> {
    if handle.is_null() || handle == INVALID_HANDLE_VALUE {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: a handle a successful kernel call just returned has no other owner.
    Ok(unsafe { OwnedHandle::from_raw_handle(handle) })
}

/// One unnamed, non-inheritable job whose close terminates its processes.
pub struct ProcessJob {
    job: OwnedHandle,
}

impl ProcessJob {
    /// Creates the job and confirms the kill-on-close limit is the one it holds.
    pub fn new() -> io::Result<Self> {
        // SAFETY: null attributes give a non-inheritable handle; a null name
        // gives a job no other process can open by name.
        let job = owned(unsafe { CreateJobObjectW(ptr::null(), ptr::null()) })?;
        // SAFETY: zero is a valid bit pattern for this plain C structure.
        let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        // SAFETY: the new job holds no process yet; the pointer and size name
        // one live structure of the class given.
        checked(unsafe {
            SetInformationJobObject(
                job.as_raw_handle(),
                JobObjectExtendedLimitInformation,
                (&limits as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast(),
                size_of_val(&limits) as u32,
            )
        })?;
        // SAFETY: as above; the structure is written, not read.
        let mut actual: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
        // SAFETY: the job handle has query access; the output names one live
        // structure of the class given.
        checked(unsafe {
            QueryInformationJobObject(
                job.as_raw_handle(),
                JobObjectExtendedLimitInformation,
                (&mut actual as *mut JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast(),
                size_of_val(&actual) as u32,
                ptr::null_mut(),
            )
        })?;
        if actual.BasicLimitInformation.LimitFlags != JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE {
            return Err(io::ErrorKind::Unsupported.into());
        }
        Ok(Self { job })
    }

    /// Places a child created with [`CREATE_SUSPENDED`] in the job, then lets
    /// it run. On failure the child has executed nothing; the caller kills it.
    pub fn adopt_suspended(&self, child: &Child) -> io::Result<()> {
        // SAFETY: the child's process handle stays open while `child` lives,
        // and the job handle is owned by `self`.
        checked(unsafe {
            AssignProcessToJobObject(self.job.as_raw_handle(), child.as_raw_handle())
        })?;
        resume_threads(child.id())
    }

    /// How many processes the job still holds.
    pub fn active_processes(&self) -> io::Result<u32> {
        // SAFETY: zero is a valid bit pattern for this plain C structure.
        let mut accounting: JOBOBJECT_BASIC_ACCOUNTING_INFORMATION = unsafe { std::mem::zeroed() };
        // SAFETY: the job handle has query access; the output names one live
        // structure of the class given.
        checked(unsafe {
            QueryInformationJobObject(
                self.job.as_raw_handle(),
                JobObjectBasicAccountingInformation,
                (&mut accounting as *mut JOBOBJECT_BASIC_ACCOUNTING_INFORMATION).cast(),
                size_of_val(&accounting) as u32,
                ptr::null_mut(),
            )
        })?;
        Ok(accounting.ActiveProcesses)
    }

    /// Ends every process in the job now.
    pub fn terminate(&self) -> io::Result<()> {
        // SAFETY: only the processes this job holds are terminated.
        checked(unsafe { TerminateJobObject(self.job.as_raw_handle(), 1) })
    }
}

/// Resumes the threads of a suspended process. A process created suspended
/// has exactly its initial thread, and its id cannot be reused while the
/// caller holds the process handle.
fn resume_threads(process: u32) -> io::Result<()> {
    // SAFETY: a thread snapshot takes no process argument it would dereference.
    let snapshot = owned(unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) })?;
    // SAFETY: zero is a valid bit pattern for this plain C structure.
    let mut entry: THREADENTRY32 = unsafe { std::mem::zeroed() };
    entry.dwSize = size_of::<THREADENTRY32>() as u32;
    let mut resumed = 0;
    // SAFETY: the snapshot is open and `entry` is one live structure whose
    // size field is set, as the enumeration requires.
    let mut found = unsafe { Thread32First(snapshot.as_raw_handle(), &mut entry) };
    while found != 0 {
        if entry.th32OwnerProcessID == process {
            // SAFETY: the thread id came from the snapshot of a process the
            // caller holds open; the returned handle gets one owner.
            let thread =
                owned(unsafe { OpenThread(THREAD_SUSPEND_RESUME, 0, entry.th32ThreadID) })?;
            // SAFETY: the handle has suspend-resume access.
            if unsafe { ResumeThread(thread.as_raw_handle()) } == u32::MAX {
                return Err(io::Error::last_os_error());
            }
            resumed += 1;
        }
        // SAFETY: as for the first entry.
        found = unsafe { Thread32Next(snapshot.as_raw_handle(), &mut entry) };
    }
    if resumed == 0 {
        return Err(io::ErrorKind::NotFound.into());
    }
    Ok(())
}
