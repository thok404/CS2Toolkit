"""Shared bounds for the persisted flash recovery duration."""

DEFAULT_FLASH_FADE_MS = 1000
MAX_FLASH_FADE_MS = 2000
FLASH_FADE_STEP_MS = 100


def normalize_flash_fade_duration(value):
    # Configuration imports are a trust boundary. A missing/invalid optional
    # value retains the established default; valid values use slider increments.
    if not isinstance(value, int) or isinstance(value, bool):
        return DEFAULT_FLASH_FADE_MS
    bounded = max(0, min(MAX_FLASH_FADE_MS, value))
    return ((bounded + FLASH_FADE_STEP_MS // 2) // FLASH_FADE_STEP_MS) * FLASH_FADE_STEP_MS
