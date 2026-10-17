#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "cadrumo_platform.h"
#include "contract.h"
#include "build_metadata.h"
#include "launch_guard.h"
#include "launch_profile.h"
#ifndef CADRUMO_DEVELOPMENT
#define CADRUMO_DEVELOPMENT 0
#endif
#define WIDE_LITERAL_(value) L##value
#define WIDE_LITERAL(value) WIDE_LITERAL_(value)

typedef int (__cdecl *bridge_main)(int, wchar_t **, const wchar_t **, int);

/* What this process runs: the declared launch image whose profile defines its environment,
 * and for a console entrypoint its script and optional fixed module. A standalone host has
 * it compiled in; the Cadrumo binary selects it by role at run time. */
typedef struct {
    const char *image;
    const wchar_t *entrypoint;
    const wchar_t *fixed_module;
    int bundled;
} host_role;

static wchar_t *path(cadrumo_context *ctx, uint32_t key) {
    cadrumo_buffer value = {0};
    if (cadrumo_platform_path(ctx, key, &value)) return NULL;
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
        (char *)value.data, (int)value.len, NULL, 0);
    wchar_t *result = count ? calloc((size_t)count + 1, sizeof(wchar_t)) : NULL;
    if (result) MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
        (char *)value.data, (int)value.len, result, count);
    cadrumo_platform_release(&value);
    return result;
}

/* A console entrypoint runs one declared console script through the package
 * interpreter. sys.executable remains that interpreter: runtime workers and the
 * supervised KDF child relaunch sys.executable with interpreter arguments. */
static int run_entrypoint(bridge_main run, const host_role *role, int argc, wchar_t **argv, wchar_t **paths) {
    static const wchar_t fixed_format[] = L"import %ls as fixed; raise SystemExit(fixed.main())";
    static const wchar_t script_format[] =
        L"import _cadrumo_bootstrap; _cadrumo_bootstrap.run_entrypoint('%ls')";
    const wchar_t *format = role->fixed_module ? fixed_format : script_format;
    const wchar_t *subject = role->fixed_module ? role->fixed_module : role->entrypoint;
    size_t command_size = wcslen(format) + wcslen(subject) + 1;
    size_t size = wcslen(paths[0]) + wcslen(WIDE_LITERAL(CADRUMO_EXECUTABLE)) + 2;
    wchar_t *command = calloc(command_size, sizeof(wchar_t));
    wchar_t *interpreter = calloc(size, sizeof(wchar_t));
    wchar_t **forwarded = calloc((size_t)argc + 2, sizeof(wchar_t *));
    int result = 123;
    if (command && interpreter && forwarded
        && swprintf_s(command, command_size, format, subject) >= 0
        && swprintf_s(interpreter, size, L"%ls\\%ls", paths[0], WIDE_LITERAL(CADRUMO_EXECUTABLE)) >= 0) {
        free(paths[2]);
        paths[2] = interpreter;
        interpreter = NULL;
        forwarded[0] = paths[2];
        forwarded[1] = L"-c";
        forwarded[2] = command;
        for (int i = 1; i < argc; ++i) forwarded[i + 2] = argv[i];
        result = run(argc + 2, forwarded, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    } else {
        fprintf(stderr, "CADRUMO: cannot prepare the %s entrypoint\n", role->image);
    }
    free(command);
    free(interpreter);
    free(forwarded);
    return result;
}

static int host_main(const host_role *role, int argc, wchar_t **argv) {
    cadrumo_context *ctx = NULL;
    cadrumo_launch_guard *version_guard = NULL;
    cadrumo_buffer error = {0};
    wchar_t *paths[CADRUMO_PATH_KEYS] = {0};
    wchar_t library[32768];
    int interpreter = !role->entrypoint && !role->bundled;
    int result = 120;
    if (cadrumo_platform_abi() != CADRUMO_PLATFORM_ABI ||
        cadrumo_platform_create(CADRUMO_PLATFORM_ABI, &ctx, &error)) goto failure;
    for (uint32_t i = 0; i < CADRUMO_PATH_KEYS; ++i) {
        paths[i] = path(ctx, i);
        if (!paths[i]) goto failure;
    }
    if (!acquire_launch_guard(ctx, &version_guard)) {
        fprintf(stderr, "CADRUMO: installed package is unavailable for launch\n");
        goto done;
    }
    if (interpreter && argc == 2 && (!wcscmp(argv[1], L"--version") || !wcscmp(argv[1], L"-V"))) {
        printf("CADRUMO %s build %s (%s), Python %s [%s]\n", CADRUMO_VERSION,
            CADRUMO_BUILD_NUMBER, CADRUMO_BUILD_DATE, CADRUMO_PYTHON_VERSION,
            CADRUMO_DEVELOPMENT ? "development" : "production");
        result = 0;
        goto done;
    }
    if (!SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32 | LOAD_LIBRARY_SEARCH_USER_DIRS) ||
        !AddDllDirectory(paths[5])) goto failure;
    if (swprintf_s(library, 32768, L"%ls\\%ls", paths[5], WIDE_LITERAL(CADRUMO_RUNTIME)) < 0) goto failure;
    if (!LoadLibraryExW(library, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32)) {
        fprintf(stderr, "CADRUMO: missing or incompatible bundled CPython DLL (Windows error %lu)\n", GetLastError());
        goto done;
    }
    if (swprintf_s(library, 32768, L"%ls\\%ls", paths[5], WIDE_LITERAL(CADRUMO_BRIDGE)) < 0) goto failure;
    HMODULE bridge = LoadLibraryExW(library, NULL,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!bridge) goto failure;
    bridge_main run = (bridge_main)(void *)GetProcAddress(bridge, "cadrumo_python_main");
    if (!run) goto failure;
    /* The launch profile defines the environment before Python starts. A declared
     * invocation may select its own profile; context paths, isolated Python and
     * package verification are identical for every profile. */
    int defined = define_launch(ctx, role->image, argc, (cadrumo_native_char **)argv, &error);
    if (defined < 0) goto failure;
    if (defined > 0) {
        result = defined;
        goto done;
    }
    if (role->entrypoint) {
        result = run_entrypoint(run, role, argc, argv, paths);
    } else if (role->bundled) {
        /* The image stays sys.executable, so a child it starts with sys.executable re-enters
         * this image and its launch profiles; sys.frozen is never set. */
        result = run(argc, argv, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    } else if (argc == 2 && !wcscmp(argv[1], L"--check-package")) {
        wchar_t *check[] = {argv[0], L"-c", L"import _cadrumo_bootstrap; _cadrumo_bootstrap.verify(full=True); print('CADRUMO package verified')"};
        result = run(3, check, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    } else {
        result = run(argc, argv, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    }
    goto done;
failure:
    if (error.data) fprintf(stderr, "CADRUMO: %.*s\n", (int)error.len, error.data);
    else fprintf(stderr, "CADRUMO: native bootstrap failed (Windows error %lu)\n", GetLastError());
done:
    /* Keep the single version guard alive through DLL detach and process exit.
     * The OS closes its lease handle after all package exit code has finished. */
    cadrumo_platform_release(&error);
    cadrumo_platform_destroy(ctx);
    for (int i = 0; i < CADRUMO_PATH_KEYS; ++i) free(paths[i]);
    return result;
}

#ifdef CADRUMO_LINKED_HOST
/* The Cadrumo binary's entry into a console entrypoint role. argv[0] is the binary and the
 * remaining arguments are the script's; the role argument has already been removed. */
int cadrumo_host_entrypoint(const char *image, const wchar_t *entrypoint, int argc, wchar_t **argv) {
    if (!image || !entrypoint || argc < 1 || !argv) return 2;
    host_role role = {image, entrypoint, NULL, 0};
    return host_main(&role, argc, argv);
}
#else
int wmain(int argc, wchar_t **argv) {
#if defined(CADRUMO_ENTRYPOINT) && defined(CADRUMO_FIXED_MODULE)
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, WIDE_LITERAL(CADRUMO_ENTRYPOINT),
        WIDE_LITERAL(CADRUMO_FIXED_MODULE), 0};
#elif defined(CADRUMO_ENTRYPOINT)
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, WIDE_LITERAL(CADRUMO_ENTRYPOINT), NULL, 0};
#elif defined(CADRUMO_BUNDLED_IMAGE)
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, NULL, NULL, 1};
#else
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, NULL, NULL, 0};
#endif
    return host_main(&role, argc, argv);
}
#endif
