//! Windows session admission, job breakaway and the hidden session-end window.
#![allow(unsafe_code)]

use crate::{
    background::Background, lifecycle::ManagerLifecycle, supervision::supervisor::SessionActivity,
};
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
    fn PostMessageW(window: Handle, message: u32, wparam: usize, lparam: isize) -> i32;
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
pub fn escape_job(already_attempted: bool, sign_in: bool) -> io::Result<bool> {
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
        .args(sign_in.then_some("--sign-in"))
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(0x0100_0000 | 0x0800_0000)
        .spawn()?;
    Ok(true)
}

struct WindowState {
    background: Box<dyn ManagerLifecycle>,
    ipc: Option<crate::ipc::windows::Server>,
    failed: bool,
    tray: Option<crate::windows_tray::Tray>,
    revealing: bool,
    upgrades: Option<crate::cutover_coordinator::Coordinator>,
    session: Option<crate::session::instance::SessionLock>,
    ending: bool,
    upgrade_error: bool,
    exit_after_settle: bool,
}
impl WindowState {
    fn cancel_upgrade(&mut self) {
        if let Some(upgrades) = &mut self.upgrades {
            upgrades.cancel();
        }
    }
    fn unsettled(&self) -> bool {
        self.upgrades
            .as_ref()
            .is_some_and(|upgrades| upgrades.unsettled())
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
            // Modal shell APIs pump messages. Detach the tray before entering them:
            // no reference into WindowState survives a reentrant callback.
            if message == 0x8002 && !(*state).revealing {
                if let Some(mut tray) = (*state).tray.take() {
                    (*state).revealing = true;
                    let status = (*state).background.status();
                    let result = tray.reveal(status).and_then(|action| match action {
                        Some(crate::windows_tray::Action::Retry) => (*state).background.retry(),
                        Some(crate::windows_tray::Action::Restart) => {
                            if (*state).unsettled() {
                                Err(io::ErrorKind::WouldBlock.into())
                            } else {
                                (*state).background.restart()
                            }
                        }
                        Some(crate::windows_tray::Action::Quit) => {
                            if let Some(upgrades) = &mut (*state).upgrades {
                                upgrades.cancel();
                            }
                            (*state).background.quit()
                        }
                        None => Ok(()),
                    });
                    if result.is_err() {
                        tray.error();
                    }
                    (*state).tray = Some(tray);
                    (*state).revealing = false;
                }
                return 0;
            }
            let state = &mut *state;
            if let Some(tray) = &mut state.tray
                && tray.taskbar_recreated(message)
            {
                let _ = tray.update(state.background.status());
            }
            if message == crate::windows_tray::CALLBACK
                && crate::windows_tray::Tray::selected(lparam)
            {
                PostMessageW(window, 0x8002, 0, 0);
                return 0;
            }
            match message {
                0x0011 => {
                    state.ending = true;
                    state.cancel_upgrade();
                    state.background.session_end();
                    return 1;
                }
                0x0016 => {
                    if wparam == 0 {
                        state.ending = false;
                        state.exit_after_settle = false;
                        if let Some(upgrades) = &mut state.upgrades {
                            upgrades.resume();
                        } else {
                            state.background.cancel_session_end();
                        }
                    } else {
                        state.exit_after_settle = true;
                        if !state.unsettled() {
                            PostQuitMessage(0);
                        }
                    }
                    return 0;
                }
                0x0113 => {
                    if let Some(ipc) = &mut state.ipc {
                        let result = ipc.poll(|request| {
                            if matches!(request, crate::ipc::Request::Reveal { .. }) {
                                let queued = (state.tray.is_some() || state.revealing)
                                    && PostMessageW(window, 0x8002, 0, 0) != 0;
                                crate::ipc::Response {
                                    schema: 1,
                                    outcome: if queued {
                                        crate::ipc::Outcome::RevealQueued
                                    } else {
                                        crate::ipc::Outcome::SurfaceUnavailable
                                    },
                                }
                            } else {
                                crate::ipc::respond(request, || state.background.retry())
                            }
                        });
                        if result.is_err() {
                            state.failed = true;
                            state.exit_after_settle = true;
                            state.cancel_upgrade();
                        }
                    }
                    if state.background.poll().is_err() {
                        state.failed = true;
                        state.exit_after_settle = true;
                        state.cancel_upgrade();
                    }
                    if let Some(tray) = &mut state.tray {
                        let _ = tray.update(state.background.status());
                    }
                    if let Some(upgrades) = &mut state.upgrades {
                        match upgrades.poll(
                            &mut *state.background,
                            &mut state.session,
                            &mut state.ipc,
                        ) {
                            Ok(true) => PostQuitMessage(0),
                            Ok(false) => {}
                            Err(_) => {
                                // A failed cleanup retains the claim and all process
                                // witnesses. It must not exit and launch a second owner.
                                if !state.upgrade_error
                                    && let Some(tray) = &mut state.tray
                                {
                                    let _ = tray.notice("action_failed");
                                }
                                state.upgrade_error = true;
                            }
                        }
                        if let Some(notice) = upgrades.take_notice()
                            && let Some(tray) = &mut state.tray
                        {
                            let _ = tray.notice(notice);
                        }
                    }
                    if (state.background.quit_completed() || state.exit_after_settle)
                        && !state.unsettled()
                    {
                        PostQuitMessage(0);
                    }
                    return 0;
                }
                0x0010 => {
                    state.ending = true;
                    state.exit_after_settle = true;
                    state.cancel_upgrade();
                    state.background.session_end();
                    if !state.unsettled() {
                        PostQuitMessage(0);
                    }
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

pub fn run(
    background: Background,
    ipc: crate::ipc::windows::Server,
    tray: crate::windows_tray::Configuration,
    selected: cadrumo_application::installation::Selection,
    session: crate::session::instance::SessionLock,
) -> io::Result<()> {
    run_window(
        Box::new(background),
        Some(ipc),
        Some(tray),
        Some((selected, session)),
        |_| {},
    )
}

fn run_window(
    background: Box<dyn ManagerLifecycle>,
    ipc: Option<crate::ipc::windows::Server>,
    tray: Option<crate::windows_tray::Configuration>,
    resources: Option<(
        cadrumo_application::installation::Selection,
        crate::session::instance::SessionLock,
    )>,
    created: impl FnOnce(Handle),
) -> io::Result<()> {
    let name: Vec<u16> = format!("{}.session-window", crate::identity::MANAGER_ID)
        .encode_utf16()
        .chain([0])
        .collect();
    let (upgrades, session) = resources.map_or((None, None), |(selected, session)| {
        (
            Some(crate::cutover_coordinator::Coordinator::new(selected)),
            Some(session),
        )
    });
    let mut state = Box::new(WindowState {
        background,
        ipc,
        failed: false,
        tray: None,
        revealing: false,
        upgrades,
        session,
        ending: false,
        upgrade_error: false,
        exit_after_settle: false,
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
        let installed = tray
            .map(|configuration| crate::windows_tray::Tray::install(window, configuration))
            .transpose();
        let result = if let Err(error) = installed.as_ref() {
            Err(io::Error::other(error.to_string()))
        } else if SetTimer(window, 1, 250, None) == 0 {
            Err(io::Error::last_os_error())
        } else {
            state.tray = installed.unwrap();
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
        state.tray.take();
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
    impl crate::lifecycle::CutoverRuntime for Observed {}
    impl ManagerLifecycle for Observed {
        fn poll(&mut self) -> io::Result<()> {
            self.0.lock().unwrap().push("poll");
            Ok(())
        }
        fn begin_session_end(&mut self) {
            self.session_end();
        }
        fn session_end_settled(&self) -> bool {
            self.0.lock().unwrap().contains(&"end")
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
        run_window(
            Box::new(Observed(observed.clone())),
            None,
            None,
            None,
            |window| {
                for message in [0x0011, 0x0016, 0x0113, 0x0010] {
                    // SAFETY: this is our own live, hidden test window. Only its
                    // queue receives these messages; no real logoff is requested.
                    assert_ne!(unsafe { PostMessageW(window, message, 0, 0) }, 0);
                }
            },
        )
        .unwrap();
        assert_eq!(*observed.lock().unwrap(), ["end", "cancel", "poll", "end"]);
    }
}
