# Elkron MP500 (IT500WEB) for Home Assistant

🇮🇹 [Italiano](README.md) · 🇬🇧 English

A **local** (no cloud) custom integration for **Elkron MP500** alarm panels with the **IT500WEB** network module. It shows the panel inputs as sensors, shows the system state, and lets you **arm and disarm the whole system** from Home Assistant.

Independent project: **not affiliated with or endorsed by Elkron/Urmet**. The IT500WEB protocol is not public; this integration is based on analysing the network traffic of Hi-Connect and of the module's Web Server. Use it at your own risk and test the commands with the system under your eyes before relying on them.

> Entity names and attributes are in Italian (`Ingresso N`, `Sistema`, `settori`, `sessioni_aperte`, `stato_grezzo`). The configuration screens are translated.

## What it does

- **Input sensors.** One binary sensor for every input the panel reports. The number is not fixed: it is read from the panel (4, 8, 16... inputs, wired and wireless), so it adapts to your installation.
- **Names.** If you give the Web Server user and password once, the integration reads the input and sector names from the panel. If an input has no name in the panel, or you give no credentials, it is simply called **Ingresso 1, Ingresso 2, ...** ("Input 1, 2..."), and you can rename it by hand in the options.
- **Sectors.** Each sensor has a `settori` attribute listing the sectors it belongs to (when read from the panel).
- **`Sistema` entity** (alarm control panel): `disarmed` / `armed_away` and the **arm** and **disarm** commands. In this version the **whole system** is always armed or disarmed.
- **Local.** No account or cloud. The module must be reachable on the network from Home Assistant.

## Disarm code (optional)

In **Settings → Devices & services → Elkron MP500 → Configure** you can set a 6-digit numeric code of your choice. It is not the panel's user or technician code: it only exists in Home Assistant. When set, Home Assistant asks for it before disarming (dashboard, scripts, voice assistants); arming stays code-free. Only a salted hash is stored. After 5 consecutive wrong codes, disarming is locked for 5 minutes. Tick "Remove the disarm code" to remove it.

This is a software gate: it does not protect against disarming from the app, the web UI or the panel keypad.

## Dashboard card (optional)

[`examples/dashboard_card.yaml`](examples/dashboard_card.yaml) is a ready-made card: a status display, ARM and DISARM buttons and a tile for every input with name, state and last change (tap a tile for its history). It needs these HACS frontend add-ons: *button-card*, *stack-in-card*, *card-mod* and *Browser Mod*. To use it: Dashboard → Edit → Add card → **Manual** → paste the file content. If your panel has fewer inputs, delete the extra tiles.

DISARM opens a **numeric keypad** (services `elkron_mp500.keypad_press` and `keypad_submit`): the digits only live in the integration's memory and are dropped after 30 seconds. If you set a disarm code it is checked, otherwise disarming goes through anyway.

## What it does NOT do (yet)

- **Partial** or per-sector arming, scenarios and outputs.
- The panel's event history.
- No user code is asked for or used to arm/disarm (see "Security").

## Example card with keypad

`examples/card_elkron_mp500.yaml` is a complete Lovelace card: display, LED, ARM, DISARM with a numeric keypad, and the input tiles with history. It needs **button-card** and **Browser Mod** (HACS). Adapt the input names and `entity_id`s to yours. The keypad uses the `elkron_mp500.keypad_press` and `elkron_mp500.keypad_submit` services: the digits stay only in the integration's memory, never in a state or the history, and are dropped after 30 seconds. Nothing is needed in `configuration.yaml`.

## Requirements

- An Elkron MP500 panel with an IT500WEB module on your network, preferably with a **fixed IP** (DHCP reservation on your router).
- A recent Home Assistant (tested on 2026.10; automatic tests on 2026.2).
- The module's TCP service on port `5555` (default).

## Installation

### With HACS (recommended)
1. HACS → three-dot menu → **Custom repositories**.
2. Paste this address in the "Repository" field:
   ```
   https://github.com/stefanodr/ha-elkron-mp500
   ```
   Category **Integration** → **Add**.
3. Search for **Elkron MP500**, download it and **restart Home Assistant**.

### Manual
1. Copy the `custom_components/elkron_mp500` folder into `/config/custom_components/` (replacing any older version).
2. **Restart Home Assistant.**

## Setup, step by step

1. **Settings → Devices & services → Add integration → Elkron MP500.**
2. Fill in:

| Field | What to enter |
|---|---|
| IT500WEB IP address | The module's IP (the one you open in the browser for the Web Server). |
| TCP port | `5555` (leave it unless you changed it). |
| Polling interval | How often to read the state, in seconds. 10 s is fine; use 1–2 s for motion sensors. Min 1, max 300. |
| Web Server user / password | **Optional.** The same user and password you use on the module's web page. Used **once** to read the names; **not stored**. Leave empty to get "Ingresso N". |
| Plant code | **Optional.** 8 digits. Keep the factory value `55555555` if you did not change it. |
| Technical code | **Optional.** Keep the factory value `000000` if you did not change it. |

3. Confirm. If the panel does not accept the codes you will see "The panel did not accept the plant code or technical code."

### Changing names, types, interval (options)
**Settings → Devices & services → Elkron MP500 → Configure:**
- **Input N name**: the name you prefer (it wins over the panel's name).
- **Input N type**: *Opening* (generic), *Door*, *Window* or *Motion*. It decides how the state reads (Open/Closed or Detected/Clear) and the icon.
- **Re-read names from the panel**: tick it and enter the Web Server user and password. Hand-typed names are replaced by the panel's.

### If you changed the factory codes
The *plant code* and *technical code* are those set on the panel (Hi-Connect uses them too). If setup rejects them, check you typed them correctly. To change them later, delete the entry and add it again.

## Living with the app, the Web Server and Hi-Connect

The panel accepts **one web login at a time**. So the integration:
- reads the state over the module's TCP channel and **does not keep a web session open**: the app, the web page and Hi-Connect stay usable while Home Assistant runs;
- makes a web login only to read the names; it lasts less than a second and is closed immediately;
- if the Web Server is busy while you read the names, you will see "The Web Server is busy": try again shortly.

Every session opening is written in the panel's event history (user TECNICO). The `Sistema` entity has a **`sessioni_aperte`** attribute (sessions opened since start): it should stay close to 1. If it keeps growing, the connection keeps dropping: open an issue with the log.

## Inputs: wired, wireless and sensors

The panel thinks in **inputs**, not in individual doors or windows. An MP500/8 has **8 wired inputs**, and several contacts can be wired in series on each (for example several doors and windows on one input). **Wireless** sensors (such as a wireless PIR) are added as further inputs. Home Assistant therefore sees **one sensor per input**, not one per physical door or window: if an input groups three windows, it tells you that "something" on that input is open.

## Entities
Entity ids are fixed and do not change if you rename the inputs: `alarm_control_panel.elkron_mp500_sistema` and `binary_sensor.elkron_mp500_ingresso_1`, `..._2`, ... Use them in dashboards and automations.


- `binary_sensor.*ingresso_N*`: on (open/detected) = value `02`, off = `00`. Attributes: `raw_state` (raw value), `settori`.
- `alarm_control_panel.*sistema*`: `disarmed`, `armed_away`; with any other value (for example only some sectors armed from the app) it shows **armed_custom_bypass** and the `stato_grezzo` attribute. Also the `sessioni_aperte` attribute.

## Arming and disarming

It uses the panel's total arm/disarm TCP command. **Total arming and disarming are verified on a real MP500/8** (version 1.4.5). After each command the integration re-reads the state for about 10 seconds: if it does not change, it raises an error instead of pretending it worked. The panel does not always send a confirmation reply to the command, so the proof that it worked is the state read right afterwards. The network command does not carry a user code: to avoid unwanted disarming set the Home Assistant **disarm code** (section below) and **protect the `Sistema` entity** (Home Assistant users, automations, dashboards) as you would protect the keypad.

## Known limitations

- Tested only on an **MP500/8 with IT500WEB** (firmware `it500web 2.0.170615`): reading inputs, state, and total arm and disarm are verified on this installation. Other models, firmwares or installations are unverified.
- **Plant code other than `55555555`:** the plant code is also sent in the TCP session-opening frame. With the factory value the frame is identical to the captured one; with other values it follows the same layout but is **unverified** on a real panel. If it does not work, open an issue.
- **Total arming** = frame verified with all sectors (mask `ff 00`). Installations with more than 8 sectors may behave differently.
- Input values other than `00` and `02` (for example excluded, tamper, alarm) are unknown: look at `raw_state` and report them.
- In my tests two inputs (a double door and a wireless PIR) did not change in the bytes read: the mapping of some wireless sensors to inputs may not be direct.
- The protocol is undocumented: a module firmware update may change it.

## Security

- The Web Server user and password are **not stored**.
- Plant code and technical code are stored in the Home Assistant configuration (needed at every reconnection). The factory codes are well known: change them on the panel if you can.
- Never paste passwords or codes into issues, logs or public network captures.

## Troubleshooting

| Symptom | What to check |
|---|---|
| "Connection refused" | IP and port; the module's TCP service; retry in a few seconds. |
| "Cannot communicate" | Network, IP, firewall; Web Server busy with another client. |
| "The panel did not accept the plant code or technical code" | Typed correctly? Did you change them on the panel? |
| "Invalid Web Server user or password" | Same credentials as the module's web page. |
| Sensors always "unavailable" | Home Assistant log (`custom_components.elkron_mp500`); `sessioni_aperte`. |
| Arming: "State after the command not confirmed" | The panel did not change state (e.g. open inputs blocking arming): check on the panel. |

For a detailed log add to `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.elkron_mp500: debug
```

## Reporting a problem or contributing

Open an issue with: model and firmware version (the `cmodel` and `backend` fields of the module's `/sys/info.cgi` page), Home Assistant version, and the log (without passwords or codes). Network captures (Wireshark) are very useful but **contain credentials**: redact them before sharing.

## Development and tests

The tests use a simulated panel and need no hardware:
```
python -I tests/test_fake_panel.py      # protocol (uses ports 80 and 5555 on localhost)
python - < tests/test_ha_parts.py       # Home Assistant side (needs the homeassistant package)
```
See `CHANGELOG.md` for the version history. MIT licence.
