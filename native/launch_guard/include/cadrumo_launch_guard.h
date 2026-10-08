#ifndef CADRUMO_LAUNCH_GUARD_H
#define CADRUMO_LAUNCH_GUARD_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct cadrumo_launch_guard cadrumo_launch_guard;
/* UTF-8 absolute package root, without a terminating NUL. Acquire before loading
 * package Python. Success is zero; a null guard means explicitly unmanaged.
 * Failure leaves *out null. Hold each process's own guard until process exit.
 * This grants removal exclusion only, not package integrity or runtime authority. */
uint32_t cadrumo_launch_guard_acquire(const uint8_t *package, size_t length, cadrumo_launch_guard **out);
/* Null is allowed. Release each non-null guard exactly once, after all package use. */
void cadrumo_launch_guard_release(cadrumo_launch_guard *guard);
#ifdef __cplusplus
}
#endif
#endif
