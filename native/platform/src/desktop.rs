//! Windows desktop admission. Query existing objects; never create or register a session.
use std::{ffi::c_void, mem::size_of, ptr};

#[repr(C)]
struct UserObjectFlags {
    inherit: i32,
    reserved: i32,
    flags: u32,
}

#[link(name = "user32")]
unsafe extern "system" {
    fn GetProcessWindowStation() -> *mut c_void;
    fn GetUserObjectInformationW(
        object: *mut c_void,
        index: i32,
        information: *mut c_void,
        length: u32,
        needed: *mut u32,
    ) -> i32;
    fn OpenInputDesktop(flags: u32, inherit: i32, access: u32) -> *mut c_void;
    fn CloseDesktop(desktop: *mut c_void) -> i32;
}
type ConsoleHandler = unsafe extern "system" fn(u32) -> i32;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn FreeConsole() -> i32;
    fn SetConsoleCtrlHandler(handler: Option<ConsoleHandler>, add: i32) -> i32;
}

pub fn available() -> bool {
    let mut flags = UserObjectFlags {
        inherit: 0,
        reserved: 0,
        flags: 0,
    };
    // SAFETY: the process owns the station; the writable buffer has the API's
    // documented layout and size. Every acquired desktop handle is closed here.
    unsafe {
        let station = GetProcessWindowStation();
        if station.is_null()
            || GetUserObjectInformationW(
                station,
                1,
                ptr::from_mut(&mut flags).cast(),
                size_of::<UserObjectFlags>() as u32,
                ptr::null_mut(),
            ) == 0
            || flags.flags & 1 == 0
        {
            return false;
        }
        let desktop = OpenInputDesktop(0, 0, 1);
        if desktop.is_null() {
            return false;
        }
        CloseDesktop(desktop) != 0
    }
}

/// Sets or clears this process's "ignore Ctrl+C" console attribute.
///
/// Every child created afterwards inherits it, console or not. A process
/// started in a new process group begins with it set, and an interactive
/// child would then ignore Ctrl+C until it cleared the attribute itself;
/// clearing it before starting terminal children restores normal Ctrl+C.
pub fn ignore_console_interrupts(ignore: bool) -> std::io::Result<()> {
    // SAFETY: with a null handler routine the call only changes this process's
    // Ctrl+C attribute; no pointer is passed or retained.
    if unsafe { SetConsoleCtrlHandler(None, i32::from(ignore)) } == 0 {
        return Err(std::io::Error::last_os_error());
    }
    Ok(())
}

pub fn detach_console() {
    // SAFETY: this detaches only the current process, after GUI mode was selected.
    unsafe {
        FreeConsole();
    }
}

/// A WebView2 interface the desktop host requires of the installed runtime.
#[cfg(feature = "webview2")]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WebviewInterface {
    /// `ICoreWebView2_22`: iframe and worker requests reach custom schemes.
    Webview22,
    /// `ICoreWebView2Settings3`: browser accelerator keys can be turned off.
    Settings3,
}

/// The first required WebView2 interface the runtime behind `controller`
/// lacks, or `None` when it has them all. A refused interface cast is the
/// answer, not a failure; failing to reach the webview or its settings is.
#[cfg(feature = "webview2")]
pub fn missing_webview_interface(
    controller: &webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Controller,
) -> std::io::Result<Option<WebviewInterface>> {
    use webview2_com::Microsoft::Web::WebView2::Win32::{ICoreWebView2_22, ICoreWebView2Settings3};
    use windows_core::Interface;
    // SAFETY: `controller` is a live COM reference the caller holds for the
    // duration of the call. Each getter returns an owned reference or an
    // HRESULT and writes through no other pointer.
    let (webview, settings) = unsafe {
        let webview = controller.CoreWebView2().map_err(std::io::Error::other)?;
        let settings = webview.Settings().map_err(std::io::Error::other)?;
        (webview, settings)
    };
    if webview.cast::<ICoreWebView2_22>().is_err() {
        return Ok(Some(WebviewInterface::Webview22));
    }
    if settings.cast::<ICoreWebView2Settings3>().is_err() {
        return Ok(Some(WebviewInterface::Settings3));
    }
    Ok(None)
}

/// Turns off the browser accelerator keys (reload, print, find, zoom,
/// developer tools) and the default context menus of the webview behind
/// `controller`, then reads both settings back.
///
/// A runtime without `ICoreWebView2Settings3` is refused with
/// [`std::io::ErrorKind::Unsupported`] before any setting changes.
#[cfg(feature = "webview2")]
pub fn disable_browser_features(
    controller: &webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Controller,
) -> std::io::Result<()> {
    use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Settings3;
    use windows_core::{BOOL, Interface};
    let failed = std::io::Error::other;
    // SAFETY: `controller` is a live COM reference the caller holds for the
    // duration of the call. The setters take plain values; each getter writes
    // only the `BOOL` it is given, which lives on this stack frame.
    unsafe {
        let settings = controller
            .CoreWebView2()
            .and_then(|webview| webview.Settings())
            .map_err(failed)?;
        let keys = settings
            .cast::<ICoreWebView2Settings3>()
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Unsupported, e))?;
        settings
            .SetAreDefaultContextMenusEnabled(false)
            .map_err(failed)?;
        keys.SetAreBrowserAcceleratorKeysEnabled(false)
            .map_err(failed)?;
        let mut menus_enabled = BOOL(1);
        let mut keys_enabled = BOOL(1);
        settings
            .AreDefaultContextMenusEnabled(&mut menus_enabled)
            .map_err(failed)?;
        keys.AreBrowserAcceleratorKeysEnabled(&mut keys_enabled)
            .map_err(failed)?;
        if menus_enabled.as_bool() || keys_enabled.as_bool() {
            return Err(std::io::Error::other(
                "WebView2 kept a browser feature enabled",
            ));
        }
    }
    Ok(())
}
