/*
 * Main executable of the macOS application bundle.
 *
 * The package stays one flat, hashed tree nested beneath the bundle's resources,
 * where its data files can be sealed. Its desktop image resolves the package from
 * its own location, so this wrapper replaces itself with that image: the process,
 * its arguments and its environment continue unchanged under the packaged image.
 */
#include <errno.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef CADRUMO_BUNDLE_PAYLOAD
#error "CADRUMO_BUNDLE_PAYLOAD must name the package relative to the executable directory"
#endif
#ifndef CADRUMO_BUNDLE_DESKTOP
#error "CADRUMO_BUNDLE_DESKTOP must name the package's desktop image"
#endif

/* The conventional shell statuses for a command that cannot run or was not found. */
enum { LAUNCH_UNRUNNABLE = 126, LAUNCH_MISSING = 127 };

static int refuse(const char *reason) {
    fprintf(stderr, "{\"bundle_refusal\":\"%s\"}\n", reason);
    return LAUNCH_UNRUNNABLE;
}

int main(int argc, char **argv) {
    char invoked[PATH_MAX];
    uint32_t size = sizeof invoked;
    if (_NSGetExecutablePath(invoked, &size) != 0) {
        return refuse("executable_path_unavailable");
    }
    char executable[PATH_MAX];
    if (realpath(invoked, executable) == NULL) {
        return refuse("executable_path_unresolved");
    }
    char *separator = strrchr(executable, '/');
    if (separator == NULL) {
        return refuse("executable_path_unresolved");
    }
    *separator = '\0';
    char declared[PATH_MAX];
    int written = snprintf(declared, sizeof declared, "%s/%s/%s", executable, CADRUMO_BUNDLE_PAYLOAD,
                           CADRUMO_BUNDLE_DESKTOP);
    if (written < 0 || (size_t)written >= sizeof declared) {
        return refuse("desktop_path_too_long");
    }
    /* The desktop takes its package root from its own path, so hand it the canonical one. */
    char desktop[PATH_MAX];
    if (realpath(declared, desktop) == NULL) {
        int failure = errno;
        fprintf(stderr, "{\"bundle_refusal\":\"desktop_missing\",\"errno\":%d}\n", failure);
        return failure == ENOENT ? LAUNCH_MISSING : LAUNCH_UNRUNNABLE;
    }
    if (argc < 1) {
        return refuse("arguments_missing");
    }
    argv[0] = desktop;
    /* LaunchServices may name the process serial number as the first argument; it
       is no request of the person's, and the desktop reads arguments as a CLI call. */
    if (argc > 1 && strncmp(argv[1], "-psn_", 5) == 0) {
        memmove(&argv[1], &argv[2], (size_t)(argc - 1) * sizeof *argv);
    }
    execv(desktop, argv);
    int failure = errno;
    fprintf(stderr, "{\"bundle_refusal\":\"desktop_exec_failed\",\"errno\":%d}\n", failure);
    return failure == ENOENT ? LAUNCH_MISSING : LAUNCH_UNRUNNABLE;
}
