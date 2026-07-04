# Sentinel by SourceBox — Home Assistant integration

Connect [Sentinel](https://sentinel-command.com) to Home Assistant with
a single key. Every camera across every Camera Node in your organization shows
up at once — live video, snapshots, recording control, and motion triggers —
and the entity list re-syncs automatically as nodes and cameras come and go.

Available on **every Sentinel plan**. Live video is pulled **directly from
each camera node over your local network**, so it never round-trips the cloud
or counts against your viewer-hour cap.

## What you get

| Entity | Per | From |
|--------|-----|------|
| Camera (live stream + snapshot) | camera | LAN-direct HLS + snapshot API |
| Switch — Recording | camera | toggles continuous recording |
| Binary sensor — Motion | camera | real-time motion feed (SSE) |
| Binary sensor — Connectivity | camera | online/offline |
| Sensor — Storage used / Version | Camera Node | node diagnostics |

## Install

**Via HACS (recommended)**

1. HACS → ⋮ → *Custom repositories* → add this repo's URL, category *Integration*.
2. Install **Sentinel by SourceBox**, then restart Home Assistant.

**Manual**

Copy `custom_components/sourcebox_sentry/` into your HA `config/custom_components/`
directory and restart.

## Set up

1. In your **Sentinel Command Center**, open **Integrations** and generate an
   integration key (it starts with `osi_` and is shown once — copy it).
2. In Home Assistant: **Settings → Devices & Services → Add Integration →
   Sentinel by SourceBox**.
3. Enter your **Command Center URL** (e.g. `https://sentinel-command.com`,
   or your self-hosted address) and paste the key.

That's it — all cameras across all nodes appear as devices. If you later add a
node or camera in the Command Center, it shows up in Home Assistant on the next
refresh without any reconfiguration.

## How it works

- A `DataUpdateCoordinator` polls `GET /api/integration/cameras` and
  `GET /api/integration/status` every 30s for entity state.
- A background task subscribes to `GET /api/integration/motion/stream` (Server-
  Sent Events) and fires the per-camera motion binary sensors in real time.
- Camera live view uses each camera's LAN-direct HLS URL (`stream_source`);
  Home Assistant plays it via its bundled stream/go2rtc. Stills come from the
  snapshot endpoint.

## Notes

- Requires Home Assistant 2024.1 or newer.
- Live video requires Home Assistant to be on the **same LAN** as the camera
  nodes (the common home setup). An off-LAN proxy path is planned in the
  Command Center.
- If the integration key is revoked or rotated, Home Assistant prompts you to
  re-enter a new one (Settings → Devices & Services → Reconfigure).

## License

[Apache License 2.0](LICENSE) © 2026 SourceBox LLC.
