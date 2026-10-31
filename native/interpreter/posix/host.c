#define _POSIX_C_SOURCE 200809L
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cadrumo_platform.h"
#include "contract.h"
#include "build_metadata.h"
#include "launch_guard.h"

#ifndef CADRUMO_DEVELOPMENT
#define CADRUMO_DEVELOPMENT 0
#endif
#include "launch_profile.h"

typedef int (*bridge_main)(int, char **, const char **, int);
extern char **environ;

/* What this process runs: the declared launch image whose profile defines its environment,
 * and for a console entrypoint its script and optional fixed module. A standalone host has
 * it compiled in; the Cadrumo binary selects it by role at run time. */
typedef struct {
    const char *image;
    const char *entrypoint;
    const char *fixed_module;
    int bundled;
} host_role;

static char *path(cadrumo_context *ctx, uint32_t key) {
    cadrumo_buffer value = {0};
    if (cadrumo_platform_path(ctx, key, &value)) return NULL;
    char *result = value.len < SIZE_MAX ? malloc((size_t)value.len + 1) : NULL;
    if (result) {
        memcpy(result, value.data, (size_t)value.len);
        result[value.len] = '\0';
    }
    cadrumo_platform_release(&value);
    return result;
}

static char *join(const char *directory, const char *name) {
    size_t a = strlen(directory), b = strlen(name);
    /* A directory that already ends in a separator takes no second one. */
    const char *separator = a > 0 && directory[a - 1] == '/' ? "" : "/";
    size_t s = strlen(separator);
    if (a > SIZE_MAX - b - s - 1) return NULL;
    char *value = malloc(a + s + b + 1);
    if (value) snprintf(value, a + s + b + 1, "%s%s%s", directory, separator, name);
    return value;
}

static void *load(const char *directory, const char *name, int flags) {
    char *filename = join(directory, name);
    if (!filename) return NULL;
    void *handle = dlopen(filename, RTLD_NOW | flags);
    if (!handle) fprintf(stderr, "CADRUMO: cannot load bundled %s: %s\n", name, dlerror());
    free(filename);
    return handle;
}

/* A console entrypoint runs one declared console script through the package
 * interpreter, and the Cadrumo binary's interpreter role runs that interpreter itself.
 * sys.executable remains the package interpreter. Hosted by the Cadrumo binary, Python
 * also receives the -X option ROLE_IMAGE_OPTION naming that binary, so the runtime
 * workers and the supervised KDF child it starts re-enter the binary's interpreter role
 * and stay in its process tree. */
#define ROLE_IMAGE_OPTION "cadrumo_role_image"

#define FIXED_FORMAT "import %s as fixed; raise SystemExit(fixed.main())"
#define SCRIPT_FORMAT "import _cadrumo_bootstrap; _cadrumo_bootstrap.run_entrypoint('%s')"

static int format_command(char *command, size_t size, const host_role *role) {
    if (role->fixed_module) return snprintf(command, size, FIXED_FORMAT, role->fixed_module);
    return snprintf(command, size, SCRIPT_FORMAT, role->entrypoint);
}

static int run_python(bridge_main run, const host_role *role, int argc, char **argv, char **paths) {
    const char *subject = role->fixed_module ? role->fixed_module : role->entrypoint;
    size_t command_size = subject ? sizeof(SCRIPT_FORMAT) + sizeof(FIXED_FORMAT) + strlen(subject) : 1;
#ifdef CADRUMO_LINKED_HOST
    size_t marker_size = strlen(ROLE_IMAGE_OPTION) + strlen(argv[0]) + 2;
#else
    size_t marker_size = 1;
#endif
    char *command = calloc(command_size, 1);
    char *interpreter = join(paths[0], CADRUMO_EXECUTABLE);
    char *marker = calloc(marker_size, 1);
    char **forwarded = calloc((size_t)argc + 5, sizeof(char *));
    int result = 123;
    if (command && interpreter && marker && forwarded
        && (!subject || format_command(command, command_size, role) >= 0)
#ifdef CADRUMO_LINKED_HOST
        && snprintf(marker, marker_size, "%s=%s", ROLE_IMAGE_OPTION, argv[0]) >= 0
#endif
    ) {
        free(paths[2]);
        paths[2] = interpreter;
        interpreter = NULL;
        int count = 0;
        forwarded[count++] = paths[2];
#ifdef CADRUMO_LINKED_HOST
        forwarded[count++] = "-X";
        forwarded[count++] = marker;
#endif
        if (subject) {
            forwarded[count++] = "-c";
            forwarded[count++] = command;
        }
        for (int i = 1; i < argc; ++i) forwarded[count++] = argv[i];
        result = run(count, forwarded, (const char **)paths, CADRUMO_DEVELOPMENT);
    } else {
        fprintf(stderr, "CADRUMO: cannot prepare the %s interpreter\n", role->image);
    }
    free(command);
    free(interpreter);
    free(marker);
    free(forwarded);
    return result;
}

static int host_main(const host_role *role, int argc, char **argv) {
    /* Refusal cannot undo loader injection that happened before main. */
    for (char **item = environ; *item; ++item) {
        if (!strncmp(*item, "LD_", 3) || !strncmp(*item, "DYLD_", 5)) {
            fprintf(stderr, "CADRUMO: inherited dynamic-loader controls are not permitted\n");
            return 120;
        }
    }
    cadrumo_context *ctx = NULL;
    cadrumo_launch_guard *version_guard = NULL;
    cadrumo_buffer error = {0};
    char *paths[CADRUMO_PATH_KEYS] = {0};
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
    if (interpreter && argc == 2 && (!strcmp(argv[1], "--version") || !strcmp(argv[1], "-V"))) {
        printf("CADRUMO %s build %s (%s), Python %s [%s]\n", CADRUMO_DISPLAY_VERSION,
            CADRUMO_BUILD_NUMBER, CADRUMO_BUILD_DATE, CADRUMO_PYTHON_VERSION,
            CADRUMO_DEVELOPMENT ? "development" : "production");
        result = 0;
        goto done;
    }
    /* libpython must export symbols to subsequently loaded extension modules. */
    if (!load(paths[5], CADRUMO_RUNTIME, RTLD_GLOBAL)) goto done;
    void *bridge = load(paths[5], CADRUMO_BRIDGE, RTLD_LOCAL);
    if (!bridge) goto done;
    bridge_main run = (bridge_main)dlsym(bridge, "cadrumo_python_main");
    if (!run) goto failure;
    /* The launch profile defines the environment before Python starts. */
    int defined = define_launch(ctx, role->image, argc, argv, &error);
    if (defined < 0) goto failure;
    if (defined > 0) {
        result = defined;
        goto done;
    }
    if (role->entrypoint) {
        result = run_python(run, role, argc, argv, paths);
    } else if (role->bundled) {
        /* The image stays sys.executable, so a child it starts with sys.executable re-enters
         * this image and its launch profiles; sys.frozen is never set. */
        result = run(argc, argv, (const char **)paths, CADRUMO_DEVELOPMENT);
    } else if (argc == 2 && !strcmp(argv[1], "--check-package")) {
        char *check[] = {argv[0], "-c", "import _cadrumo_bootstrap; _cadrumo_bootstrap.verify(full=True); print('CADRUMO package verified')", NULL};
        result = run(3, check, (const char **)paths, CADRUMO_DEVELOPMENT);
    } else {
#ifdef CADRUMO_LINKED_HOST
        result = run_python(run, role, argc, argv, paths);
#else
        result = run(argc, argv, (const char **)paths, CADRUMO_DEVELOPMENT);
#endif
    }
    goto done;
failure:
    if (error.data) fprintf(stderr, "CADRUMO: %.*s\n", (int)error.len, error.data);
    else fprintf(stderr, "CADRUMO: native bootstrap failed\n");
done:
    /* Keep the single version guard alive through loader destructors and exit.
     * The kernel closes its lease descriptor when this process finishes. */
    cadrumo_platform_release(&error);
    cadrumo_platform_destroy(ctx);
    for (int i = 0; i < CADRUMO_PATH_KEYS; ++i) free(paths[i]);
    return result;
}

#ifdef CADRUMO_LINKED_HOST
/* The Cadrumo binary's entry into a role hosted by the interpreter: a console entrypoint,
 * or the interpreter itself when entrypoint is NULL. argv[0] is the binary and the
 * remaining arguments are the script's or the interpreter's; the role argument has already
 * been removed. */
int cadrumo_host_entrypoint(const char *image, const char *entrypoint, int argc, char **argv) {
    if (!image || argc < 1 || !argv || !argv[0]) return 2;
    host_role role = {image, entrypoint, NULL, 0};
    return host_main(&role, argc, argv);
}
#else
int main(int argc, char **argv) {
#if defined(CADRUMO_ENTRYPOINT) && defined(CADRUMO_FIXED_MODULE)
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, CADRUMO_ENTRYPOINT, CADRUMO_FIXED_MODULE, 0};
#elif defined(CADRUMO_ENTRYPOINT)
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, CADRUMO_ENTRYPOINT, NULL, 0};
#elif defined(CADRUMO_BUNDLED_IMAGE)
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, NULL, NULL, 1};
#else
    static const host_role role = {CADRUMO_LAUNCH_IMAGE, NULL, NULL, 0};
#endif
    return host_main(&role, argc, argv);
}
#endif
