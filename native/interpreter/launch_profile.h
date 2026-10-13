#ifndef CADRUMO_INTERPRETER_LAUNCH_PROFILE_H
#define CADRUMO_INTERPRETER_LAUNCH_PROFILE_H
#include <stdint.h>
#include <stdio.h>
#include "cadrumo_platform.h"
#include "contract.h"

/* An image's identity is compiled in: an entrypoint is its console script, the
 * interpreter is the generic Python image. No environment value selects it. */
#ifdef CADRUMO_ENTRYPOINT
#define CADRUMO_LAUNCH_IMAGE CADRUMO_ENTRYPOINT
#else
#define CADRUMO_LAUNCH_IMAGE CADRUMO_LAUNCH_IMAGE_PYTHON
#endif

/* The refusal line is the last standard-error line before the host exits; it
 * names a closed code and a declared subject, never a value. */
static void write_launch_refusal(const cadrumo_buffer *line) {
    fflush(stdout);
    fprintf(stderr, "%.*s\n", (int)line->len, (const char *)line->data);
    fflush(stderr);
}

/* Define this process's environment from the profile the image's invocation selects.
 * Returns 0 when defined, CADRUMO_LAUNCH_PROFILE_REFUSED_EXIT after reporting a
 * refusal, or -1 with the platform's message in error. Python has not started. */
static int define_launch(cadrumo_context *ctx, int argc, cadrumo_native_char **argv, cadrumo_buffer *error) {
    uint32_t count = argc > 1 ? (uint32_t)(argc - 1) : 0;
    uint32_t status = cadrumo_platform_define(ctx, CADRUMO_LAUNCH_IMAGE, count,
        (const cadrumo_native_char *const *)(argv + 1), error);
    if (status == 0) return 0;
    if (status == 4) {
        write_launch_refusal(error);
        cadrumo_platform_release(error);
        return CADRUMO_LAUNCH_PROFILE_REFUSED_EXIT;
    }
    return -1;
}
#endif
