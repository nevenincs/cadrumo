//! Windows session admission, job breakaway and the hidden session-end window.
#![allow(unsafe_code)]

use crate::{background::Background, supervision::supervisor::SessionActivity};
use std::{
    ffi::c_void,
    io, mem,
    os::windows::process::CommandExt,
    process::{Command, Stdio},
    ptr,
};

type Handle = *mut c_void;
type WindowProc = unsafe extern "system" fn(Handle, u32, usize, isize) -> isize;
#[repr(C)]
struct WindowClass {
    style: u32,
    procedure: Option<WindowProc>,
    class_extra: i32,
    window_extra: i32,
    instance: Handle,
    icon: Handle,
    cursor: Handle,
    background: Handle,
    menu: *const u16,
    name: *const u16,
}
#[repr(C)]
#[derive(Default)]
struct Point {
    x: i32,
    y: i32,
}
#[repr(C)]
#[derive(Default)]
struct Message {
    window: Handle,
    message: u32,
    wparam: usize,
    lparam: isize,
    time: u32,
    point: Point,
    private: u32,
}

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetCurrentProcess() -> Handle;
    fn IsProcessInJob(process: Handle, job: Handle, result: *mut i32) -> i32;
    fn GetModuleHandleW(name: *const u16) -> Handle;
}
#[link(name = "user32")]
unsafe extern "system" {
    fn RegisterClassW(class: *const WindowClass) -> u16;
    fn UnregisterClassW(name: *const u16, instance: Handle) -> i32;
    fn CreateWindowExW(
        ex: u32,
        class: *const u16,
        title: *const u16,
        style: u32,
        x: i32,
        y: i32,
        width: i32,
        height: i32,
        parent: Handle,
        menu: Handle,
        instance: Handle,
        parameter: *mut c_void,
    ) -> Handle;
    fn DestroyWindow(window: Handle) -> i32;
    fn DefWindowProcW(window: Handle, message: u32, wparam: usize, lparam: isize) -> isize;
    fn GetMessageW(message: *mut Message, window: Handle, first: u32, last: u32) -> i32;
    fn TranslateMessage(message: *const Message) -> i32;
    fn DispatchMessageW(message: *const Message) -> isize;
    fn SetWindowLongPtrW(window: Handle, index: i32, value: isize) -> isize;
    fn GetWindowLongPtrW(window: Handle, index: i32) -> isize;
    fn SetTimer(
        window: Handle,
        id: usize,
        interval: u32,
        callback: Option<unsafe extern "system" fn(Handle, u32, usize, u32)>,
    ) -> usize;
    fn KillTimer(window: Handle, id: usize) -> i32;
    fn PostQuitMessage(code: i32);
    fn MessageBoxW(owner: Handle, text: *const u16, caption: *const u16, flags: u32) -> i32;
}
#[link(name = "wtsapi32")]
unsafe extern "system" {
    fn WTSQuerySessionInformationW(
        server: Handle,
        session: u32,
        class: i32,
        buffer: *mut *mut u16,
        size: *mut u32,
    ) -> i32;
    fn WTSFreeMemory(memory: *mut c_void);
}

pub struct WindowsSession;
impl SessionActivity for WindowsSession {
    fn is_active(&self) -> bool {
        let mut buffer = ptr::null_mut();
        let mut size = 0;
        // SAFETY: WTS allocates the output buffer; read only the declared DWORD
        // after checking its size, then free it with the matching API.
        unsafe {
            if WTSQuerySessionInformationW(ptr::null_mut(), u32::MAX, 8, &mut buffer, &mut size)
                == 0
            {
                return false;
            }
            let active = !buffer.is_null()
                && size as usize >= mem::size_of::<i32>()
                && *buffer.cast::<i32>() == 0;
            WTSFreeMemory(buffer.cast());
            active
        }
    }
}
pub fn activity() -> Box<dyn SessionActivity> {
    Box::new(WindowsSession)
}

/// Call only after interactive, unelevated native admission. Shell launches
/// have no stderr, so their failure must also remain visible on that desktop.
pub fn show_startup_failure() {
    let title: Vec<u16> = crate::identity::MANAGER_NAME
        .encode_utf16()
        .chain([0])
        .collect();
    let code: Vec<u16> = "manager_startup_failed".encode_utf16().chain([0]).collect();
    // SAFETY: both terminated strings remain alive throughout this modal call;
    // no foreign window is borrowed and no native error/user data is displayed.
    unsafe {
        MessageBoxW(ptr::null_mut(), code.as_ptr(), title.as_ptr(), 0x10);
    }
}

/// Escape once, or refuse. The successor repeats native admission; the private
/// argument records an attempt, never grants elevation or desktop admission.
pub fn escape_job(already_attempted: bool) -> io::Result<bool> {
    let mut in_job = 0;
    // SAFETY: current-process pseudo handle is borrowed, and output is writable.
    if unsafe { IsProcessInJob(GetCurrentProcess(), ptr::null_mut(), &mut in_job) } == 0 {
        return Err(io::Error::last_os_error());
    }
    if in_job == 0 {
        return Ok(false);
    }
    if already_attempted {
        return Err(io::Error::other("manager_job_escape_refused"));
    }
    Command::new(std::env::current_exe()?)
        .arg("--breakaway-attempt")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(0x0100_0000 | 0x0800_0000)
        .spawn()?;
    Ok(true)
}

struct WindowState {
    background: Box<dyn Lifecycle>,
    failed: bool,
}

trait Lifecycle {
    fn poll(&mut self) -> io::Result<()>;
    fn session_end(&mut self);
    fn cancel_session_end(&mut self);
}
impl Lifecycle for Background {
    fn poll(&mut self) -> io::Result<()> {
        Background::poll(self)
    }
    fn session_end(&mut self) {
        Background::session_end(self);
    }
    fn cancel_session_end(&mut self) {
        Background::cancel_session_end(self);
    }
}
unsafe extern "system" fn procedure(
    window: Handle,
    message: u32,
    wparam: usize,
    lparam: isize,
) -> isize {
    // SAFETY: WM_NCCREATE supplies a CREATESTRUCT whose first member is the
    // lpParam pointer passed to CreateWindowExW. The Box remains alive until
    // DestroyWindow returns, and all callbacks run on this owning thread.
    unsafe {
        if message == 0x0081 {
            let state = *(lparam as *const *mut c_void);
            SetWindowLongPtrW(window, -21, state as isize);
        }
        let state = GetWindowLongPtrW(window, -21) as *mut WindowState;
        if !state.is_null() {
            let state = &mut *state;
            match message {
                0x0011 => {
                    state.background.session_end();
                    return 1;
                }
                0x0016 => {
                    if wparam == 0 {
                        state.background.cancel_session_end();
                    } else {
                        PostQuitMessage(0);
                    }
                    return 0;
                }
                0x0113 => {
                    if state.background.poll().is_err() {
                        state.failed = true;
                        PostQuitMessage(1);
                    }
                    return 0;
                }
                0x0010 => {
                    state.background.session_end();
                    PostQuitMessage(0);
                    return 0;
                }
                0x0082 => {
                    SetWindowLongPtrW(window, -21, 0);
                }
                _ => {}
            }
        }
        DefWindowProcW(window, message, wparam, lparam)
    }
}

pub fn run(background: Background) -> io::Result<()> {
    run_window(Box::new(background), |_| {})
}

fn run_window(background: Box<dyn Lifecycle>, created: impl FnOnce(Handle)) -> io::Result<()> {
    let name: Vec<u16> = format!("{}.session-window", crate::identity::MANAGER_ID)
        .encode_utf16()
        .chain([0])
        .collect();
    let mut state = Box::new(WindowState {
        background,
        failed: false,
    });
    // SAFETY: the class, UTF-16 name and boxed state outlive this window and its
    // message loop. It is an invisible top-level window (not HWND_MESSAGE), so
    // Windows delivers end-session broadcasts. No pointer escapes destruction.
    unsafe {
        let instance = GetModuleHandleW(ptr::null());
        let class = WindowClass {
            style: 0,
            procedure: Some(procedure),
            class_extra: 0,
            window_extra: 0,
            instance,
            icon: ptr::null_mut(),
            cursor: ptr::null_mut(),
            background: ptr::null_mut(),
            menu: ptr::null(),
            name: name.as_ptr(),
        };
        if RegisterClassW(&class) == 0 {
            return Err(io::Error::last_os_error());
        }
        let window = CreateWindowExW(
            0,
            name.as_ptr(),
            name.as_ptr(),
            0,
            0,
            0,
            0,
            0,
            ptr::null_mut(),
            ptr::null_mut(),
            instance,
            (&mut *state as *mut WindowState).cast(),
        );
        if window.is_null() {
            UnregisterClassW(name.as_ptr(), instance);
            return Err(io::Error::last_os_error());
        }
        let result = if SetTimer(window, 1, 250, None) == 0 {
            Err(io::Error::last_os_error())
        } else {
            created(window);
            let mut message = Message::default();
            loop {
                let result = GetMessageW(&mut message, ptr::null_mut(), 0, 0);
                if result == 0 {
                    break Ok(());
                }
                if result < 0 {
                    break Err(io::Error::last_os_error());
                }
                TranslateMessage(&message);
                DispatchMessageW(&message);
            }
        };
        KillTimer(window, 1);
        DestroyWindow(window);
        UnregisterClassW(name.as_ptr(), instance);
        result?;
    }
    if state.failed {
        Err(io::Error::other("manager_runtime_unavailable"))
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    #[link(name = "user32")]
    unsafe extern "system" {
        fn PostMessageW(window: Handle, message: u32, wparam: usize, lparam: isize) -> i32;
    }
    struct Observed(Arc<Mutex<Vec<&'static str>>>);
    impl Lifecycle for Observed {
        fn poll(&mut self) -> io::Result<()> {
            self.0.lock().unwrap().push("poll");
            Ok(())
        }
        fn session_end(&mut self) {
            self.0.lock().unwrap().push("end");
        }
        fn cancel_session_end(&mut self) {
            self.0.lock().unwrap().push("cancel");
        }
    }

    #[test]
    fn native_window_delivers_session_end_cancellation_and_close() {
        let observed = Arc::new(Mutex::new(Vec::new()));
        run_window(Box::new(Observed(observed.clone())), |window| {
            for message in [0x0011, 0x0016, 0x0113, 0x0010] {
                // SAFETY: this is our own live, hidden test window. Only its
                // queue receives these messages; no real logoff is requested.
                assert_ne!(unsafe { PostMessageW(window, message, 0, 0) }, 0);
            }
        })
        .unwrap();
        assert_eq!(*observed.lock().unwrap(), ["end", "cancel", "poll", "end"]);
    }
}
