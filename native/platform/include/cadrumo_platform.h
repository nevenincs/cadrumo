#ifndef CADRUMO_PLATFORM_H
#define CADRUMO_PLATFORM_H
#include <stdint.h>

/* ABI 1: UTF-8 bytes, no terminator in len. Provider owns every returned buffer.
 * A zeroed buffer is valid to release. Never copy ownership or free with a CRT.
 * Calls require valid pointers; contexts are process-local and not thread-safe.
 * 0 success, 1 incompatible ABI, 2 invalid argument, 3 platform/policy failure.
 * No unwinding crosses this boundary. Create/define error text is provider
 * owned. Path conversion/key failures clear out.
 */
typedef struct cadrumo_context cadrumo_context;
typedef struct { uint8_t *data; uint64_t len; } cadrumo_buffer;
uint32_t cadrumo_platform_abi(void);
uint32_t cadrumo_platform_create(uint32_t abi, cadrumo_context **out, cadrumo_buffer *error);
uint32_t cadrumo_platform_path(cadrumo_context *ctx, uint32_t key, cadrumo_buffer *out);
/* Define the process environment from the launch profile `image` selects for the
 * arguments after the image's own path. 4 is a launch-profile refusal: error holds
 * the one refusal line to write last on stderr before exiting with
 * CADRUMO_LAUNCH_PROFILE_REFUSED_EXIT; the environment is unchanged. */
#ifdef _WIN32
typedef uint16_t cadrumo_native_char;
#else
typedef char cadrumo_native_char;
#endif
uint32_t cadrumo_platform_define(cadrumo_context *ctx, const char *image, uint32_t argc,
    const cadrumo_native_char *const *argv, cadrumo_buffer *error);
void cadrumo_platform_release(cadrumo_buffer *buffer);
void cadrumo_platform_destroy(cadrumo_context *ctx);
/* Path keys: 0 package, 1 user root, 2 executable, 3 stdlib, 4 site-packages,
 * 5 native libraries, 6 authority, 7 secure storage, 8 temp. */
#define CADRUMO_PATH_KEYS 9
#endif
