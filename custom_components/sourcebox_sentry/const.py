"""Constants for the Sentinel by SourceBox integration."""

DOMAIN = "sourcebox_sentry"

CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"

# Default Command Center URL (operators on a self-hosted CC override this).
DEFAULT_BASE_URL = "https://opensentry-command.fly.dev"

# How often the coordinator polls /cameras + /status for entity state.
# Motion is real-time over SSE; this poll only covers camera/node state,
# recording flags, and diagnostics, so 30s is plenty.
DEFAULT_SCAN_INTERVAL = 30

# How long a motion binary_sensor stays "on" after an SSE motion event.
# The feed is event-only (not stateful), so the entity self-resets.
MOTION_RESET_SECONDS = 30

MANUFACTURER = "SourceBox"


def motion_signal(camera_id: str) -> str:
    """Dispatcher signal a camera's motion binary_sensor listens on."""
    return f"{DOMAIN}_motion_{camera_id}"
