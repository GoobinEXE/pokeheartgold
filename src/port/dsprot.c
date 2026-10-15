#include "dsprot.h"

#include <stddef.h>

// Answers the way the protection library does on a retail cartridge in a retail DS:
// only the "Not" checks succeed, and only they run their callback.

static u32 RunCallback(void *callback) {
    if (callback != NULL) {
        ((void (*)(void))callback)();
    }
    return 1;
}

u32 DSProt_DetectFlashcart(void *callback) {
    return 0;
}

u32 DSProt_DetectNotFlashcart(void *callback) {
    return RunCallback(callback);
}

u32 DSProt_DetectEmulator(void *callback) {
    return 0;
}

u32 DSProt_DetectNotEmulator(void *callback) {
    return RunCallback(callback);
}

u32 DSProt_DetectDummy(void *callback) {
    return 0;
}

u32 DSProt_DetectNotDummy(void *callback) {
    return RunCallback(callback);
}
