#ifndef POKEHEARTGOLD_GLOBAL_H
#define POKEHEARTGOLD_GLOBAL_H

#ifndef PM_ASM
#include <nitro.h>
#pragma thumb on
#include <nnsys.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#ifdef SDK_PORT
#include "port/sdk_compat.h"
#endif
#endif

#include "constants/global.h"

#include "assert.h"
#include "config.h" // MUST COME BEFORE ANY OTHER GAMEFREAK HEADERS
#include "pm_version.h"

#define NELEMS(a) (sizeof(a) / sizeof(*(a)))

typedef struct {
    int x;
    int y;
    int z;
} Vec32;

#ifdef SDK_PORT
// The struct copy below cannot target arrays of const elements under GCC or Clang.
#define ARRAY_ASSIGN_EX(dest, src, as_type, count) memcpy((void *)&(dest), &(src), sizeof(as_type) * (count))
#else
#define ARRAY_ASSIGN_EX(dest, src, as_type, count)            \
    {                                                         \
        struct tmp {                                          \
            as_type _[count];                                 \
        };                                                    \
        *(struct tmp *)&(dest) = *(const struct tmp *)&(src); \
    }
#endif

#define ARRAY_ASSIGN(dest, src) ARRAY_ASSIGN_EX(dest, src, typeof(*(dest)), NELEMS(dest))

#endif // POKEHEARTGOLD_GLOBAL_H
