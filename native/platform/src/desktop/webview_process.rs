//! Observe WebView2 process failures without retaining COM objects or page data.
use std::panic::{AssertUnwindSafe, catch_unwind};
use webview2_com::{
    Microsoft::Web::WebView2::Win32::{
        COREWEBVIEW2_PROCESS_FAILED_KIND, COREWEBVIEW2_PROCESS_FAILED_REASON,
        ICoreWebView2Controller, ICoreWebView2ProcessFailedEventArgs,
        ICoreWebView2ProcessFailedEventArgs2, ICoreWebView2ProcessFailedEventHandler,
    },
    ProcessFailedEventHandler,
};
use windows_core::{Error, HRESULT, Interface};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct ReadFailures {
    pub arguments_hresult: Option<i32>,
    pub kind_hresult: Option<i32>,
    pub details_hresult: Option<i32>,
    pub reason_hresult: Option<i32>,
    pub exit_code_hresult: Option<i32>,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct ProcessFailure {
    pub kind: Option<i32>,
    pub reason: Option<i32>,
    pub exit_code: Option<i32>,
    pub read_failures: ReadFailures,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MonitorOperation {
    CoreWebview,
    Register,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MonitorFailure {
    pub operation: MonitorOperation,
    pub hresult: i32,
}

/// Register once on the controller's UI thread. WebView2 owns the handler
/// until controller `Close`; Wry calls `Close` when its WebView is dropped.
/// The callback captures only `report`, never a controller or WebView reference.
pub fn monitor(
    controller: &ICoreWebView2Controller,
    report: impl FnMut(ProcessFailure) + 'static,
) -> Result<(), MonitorFailure> {
    // SAFETY: the caller holds a live controller on its UI thread. Both COM
    // calls return owned references or HRESULTs; the registration token is a
    // stack scalar and the WebView retains the owned event-handler reference.
    unsafe {
        let webview = controller.CoreWebView2().map_err(|error| MonitorFailure {
            operation: MonitorOperation::CoreWebview,
            hresult: error.code().0,
        })?;
        let mut token = 0;
        webview
            .add_ProcessFailed(&handler(report), &mut token)
            .map_err(|error| MonitorFailure {
                operation: MonitorOperation::Register,
                hresult: error.code().0,
            })
    }
}

fn handler(
    mut report: impl FnMut(ProcessFailure) + 'static,
) -> ICoreWebView2ProcessFailedEventHandler {
    ProcessFailedEventHandler::create(Box::new(move |_, arguments| {
        // The generated COM helper invokes this closure directly. No panic,
        // including a reporter panic, may unwind across that ABI boundary.
        catch_unwind(AssertUnwindSafe(|| report(read(arguments.as_ref()))))
            .map_err(|_| Error::from_hresult(HRESULT(0x8000_4005_u32 as i32)))
    }))
}

fn read(arguments: Option<&ICoreWebView2ProcessFailedEventArgs>) -> ProcessFailure {
    let mut result = ProcessFailure::default();
    let Some(arguments) = arguments else {
        result.read_failures.arguments_hresult = Some(0x8000_4003_u32 as i32);
        return result;
    };
    let mut kind = COREWEBVIEW2_PROCESS_FAILED_KIND(0);
    // SAFETY: live event arguments are borrowed only during their callback.
    // Each getter writes its one correctly typed stack scalar. No strings,
    // frame information, URLs or module paths are requested.
    match unsafe { arguments.ProcessFailedKind(&mut kind) } {
        Ok(()) => result.kind = Some(kind.0),
        Err(error) => result.read_failures.kind_hresult = Some(error.code().0),
    }
    let details = match arguments.cast::<ICoreWebView2ProcessFailedEventArgs2>() {
        Ok(details) => details,
        Err(error) => {
            result.read_failures.details_hresult = Some(error.code().0);
            return result;
        }
    };
    let mut reason = COREWEBVIEW2_PROCESS_FAILED_REASON(0);
    // SAFETY: as above; failed getters cannot invalidate the other values.
    match unsafe { details.Reason(&mut reason) } {
        Ok(()) => result.reason = Some(reason.0),
        Err(error) => result.read_failures.reason_hresult = Some(error.code().0),
    }
    let mut exit_code = 0;
    // SAFETY: as above; this telemetry value does not imply process settlement.
    match unsafe { details.ExitCode(&mut exit_code) } {
        Ok(()) => result.exit_code = Some(exit_code),
        Err(error) => result.read_failures.exit_code_hresult = Some(error.code().0),
    }
    result
}

#[cfg(test)]
mod tests;
