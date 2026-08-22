# Solar Dashboard

Monitoring and control for a three-inverter Knox hybrid solar system: a FastAPI
backend that talks to the inverters over RS232 and the battery BMS over RS485,
and a React/Vite dashboard on top of it.

- **Backend** — `backend/`, FastAPI on port 8000
- **Frontend** — `src/`, Vite dev server on port 5173
- **Storage** — SQLite at `backend/solar.db`

```bash
docker compose up -d --build
```

## Where the numbers come from

Every daily energy figure has two possible sources, and the distinction matters:

1. **Inverter lifetime registers** (`QET`, `QLT`, `QGT`, `QFT`, `QCT`, `QDT`),
   differenced against a start-of-day baseline. This is authoritative — the same
   counter the inverter display and DESSMonitor report. Stored in `daily_totals`.
2. **Integration of the 1-minute power samples** in `telemetry_history`. A
   fallback only: it misses any period the backend was down and inherits every
   sensor error.

`db.get_combined_daily_total()` prefers (1) and falls back to (2). It never takes
the maximum of the two — that biases every figure upward.

### Two rules that are easy to break

**Never assume a fixed sample interval.** Energy is integrated against the real
spacing between consecutive samples (`db._sample_durations`). Live samples are one
minute apart; DESS-backfilled days are ten. Dividing every row by 60 makes a
backfilled day read 10× low, and makes a day with a duplicate writer read ~2× high.

**Only one process may write telemetry.** `db.claim_writer_lock()` enforces this.
A second backend instance sharing `solar.db` will serve the API read-only and
refuse to poll hardware. `telemetry_history` also carries
`UNIQUE(timestamp, inverter_id)` with minute-truncated timestamps, and all read
paths `GROUP BY` the minute, so duplicates cannot inflate a total even if some
appear.

Sanity ceilings (`MAX_DAILY_KWH_PER_INVERTER`, `MAX_DAILY_KWH_ALL` in `db.py`)
exist purely to reject corrupt register frames. They must stay far above any
achievable daily total — a ceiling set near the real maximum silently discards
good hardware readings on the best days of the year.

## Configuration

All backend settings are environment variables, wired through `docker-compose.yml`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SOLAR_API_TOKEN` | *(unset)* | Shared secret required by every write endpoint. **Strongly recommended** — see below. |
| `SOLAR_ALLOWED_ORIGINS` | `*` | Comma-separated browser origins allowed to call the API. |
| `SOLAR_TELEMETRY_RETENTION_DAYS` | `0` | Days of 1-minute telemetry to keep. `0` keeps everything; daily totals are never purged. |
| `DESS_USER` / `DESS_PASS` | *(unset)* | DESSMonitor login for historical backfill. Falls back to `backend/dess_credentials.json` (gitignored). |

### Securing the write endpoints

The backend reconfigures real inverter hardware and is reachable from the public
internet. Without `SOLAR_API_TOKEN`, any page the browser visits can POST to it.

```bash
# .env next to docker-compose.yml
SOLAR_API_TOKEN=$(openssl rand -hex 24)
```

Then, once, in the dashboard's browser console:

```js
localStorage.setItem('solar_api_token', '<the same token>');
```

Read-only endpoints ignore the token. Writes without it return 401.

Commands sent to `/api/inverter_settings/update` are checked against an
allow-list in `server.py` (`ALLOWED_COMMANDS`, `ALLOWED_VOLTAGE_COMMANDS`), and
voltage setpoints must fall inside ranges that are safe for a 48 V LiFePO4 bank.
Extend those tables to expose a new setting — never bypass them.

## API

Read-only: `GET /api/telemetry`, `/api/history`, `/api/cumulative`,
`/api/dess_totals`, `/api/battery`, `/api/bms_totals`, `/api/devices`,
`/api/automations`, `/api/inverter_settings`.

Authenticated writes (POST/PUT/DELETE only — none of these are reachable by GET):
`/api/inverter_settings/update`, `/api/automations…`, `/api/backfill`,
`/api/reset_db`, `/api/restart_container`.

## Hardware notes

- Inverters are matched to `/dev/ttyUSB*` by serial number (`QID`, falling back to
  `QPGS0`), so port order does not matter. 2400 baud.
- Replies are CRC-checked. QPIGS degrades to an unverified frame after three
  failed attempts rather than going dark; lifetime registers require either a
  valid CRC or the same value twice, because six commands share one open port and
  a late reply would otherwise be read as the answer to the next command.
- Battery SOC and voltage always come from the Knox BMS over RS485, never from
  the inverter's own reading.
- The Knox BMS reports a register count where Modbus expects a byte count, so
  replies are validated by header and length plus value-range checks.

## Development

```bash
npm install
npm run dev                     # frontend with HMR
python backend/server.py        # backend (needs the serial hardware)
```

The first backend start after upgrading collapses any duplicate telemetry rows
to one per minute and adds the unique index. It writes `solar.db.bak-<timestamp>`
next to the database first, and is a no-op on every subsequent start.

`backend/` also contains ~130 one-off `test_*` / `scan_*` / `probe_*` scripts kept
for hardware debugging. They are excluded from the Docker image by
`backend/.dockerignore` and are not part of the application.
