### Sunrise / Sunset Data Pipeline

This project implements a small, production-style data pipeline that pulls daily
astronomical data from the **Sunrise-Sunset.org** API and loads it into **SQLite**.

All timestamps are converted to **IST (UTC+5:30)** before being emitted, and the
pipeline backfills data from **2020-01-01 through “today”**.

The project is structured as a **Singer tap** inside an existing **Meltano**
project, but you can also run the tap directly from the command line.

---

### 1. Tech Stack

- **Language**: Python
- **Orchestration / ETL framework**: Singer-compatible tap (can be orchestrated by Meltano)
- **Storage**: SQLite
- **Key libraries**:
  - `requests` – HTTP client for Sunrise-Sunset.org API
  - `singer-python` – helper utilities for emitting Singer messages

---

### 2. Data Model

- **Source**: `https://api.sunrise-sunset.org/json`
- **Grain**: 1 record per **day** and **location**
- **Stream**: `sun_events`

Fields (all times already converted to IST):

- `date` – ISO date (e.g. `2020-01-01`)
- `latitude` – numeric
- `longitude` – numeric
- `sunrise_ist` – ISO8601 datetime in IST
- `sunset_ist` – ISO8601 datetime in IST
- `solar_noon_ist` – ISO8601 datetime in IST
- `civil_twilight_begin_ist` – ISO8601 datetime in IST
- `civil_twilight_end_ist` – ISO8601 datetime in IST
- `nautical_twilight_begin_ist` – ISO8601 datetime in IST
- `nautical_twilight_end_ist` – ISO8601 datetime in IST
- `astronomical_twilight_begin_ist` – ISO8601 datetime in IST
- `astronomical_twilight_end_ist` – ISO8601 datetime in IST

---

### 3. Configuration

Create a config file based on `config.example.json`:

```json
{
  "latitude": 28.6139,
  "longitude": 77.2090,
  "start_date": "2020-01-01",
  "end_date": "2026-03-04",
  "database_path": "output/sunrise_sunset.db",
  "table_name": "sun_events"
}
```

- **latitude / longitude**: your desired location (defaults in the example file
  are for New Delhi; change as needed).
- **start_date**: first date to pull (defaults to `2020-01-01` if omitted).
- **end_date**: last date to pull (defaults to “today” if omitted).
- **database_path** (optional): if provided, the tap will look at this SQLite
  database and, when there is no state file yet, will start **after** the
  maximum `date` already present in `table_name`.
- **table_name** (optional): table name in `database_path` (defaults to
  `sun_events`).

The tap is incremental: it keeps a simple `last_synced_date` in state and will
continue from the next day on subsequent runs. If you do not pass a state file
but configure `database_path`, the tap will resume from the last date present
in SQLite, which lets you re-run safely without re-loading old days.

---

### 4. Installation

From the project root:

```bash
python -m venv venv
venv\Scripts\activate  # on Windows

pip install -r requirements.txt
```

---

### 5. Running the Singer Tap

You can run the tap directly and see raw Singer output:

```bash
python -m tap_sunrise_sunset.tap_sunrise_sunset --config config.json
```

To enable incremental sync and resume behavior, pass a state file path:

```bash
python -m tap_sunrise_sunset.tap_sunrise_sunset --config config.json --state output/state.json
```

This will print Singer `SCHEMA`, `RECORD`, and `STATE` messages to `stdout`.

---

### 6. Loading into SQLite

To complete the production-style pipeline and avoid dependency issues with
older third-party targets, this repo includes a **simple custom Singer target**
implemented in `target_sqlite_simple.py`.

Run:

```bash
python -m tap_sunrise_sunset.tap_sunrise_sunset --config config.json \
  | python target_sqlite_simple.py --database output/sunrise_sunset.db
```

This will:

- Read Singer messages from the tap,
- Create a `sun_events` table (if missing),
- And upsert records keyed by `date` into `output/sunrise_sunset.db`.

---

### 7. Optional: Wiring Through Meltano

The repository already contains a `meltano.yml` skeleton. You can add an
extractor and loader entry to let Meltano orchestrate the tap/target pair, e.g.:

```yaml
plugins:
  extractors:
    - name: tap-sunrise-sunset
      namespace: tap_sunrise_sunset
      executable: python -m tap_sunrise_sunset.tap_sunrise_sunset
      pip_url: -r requirements.txt
  loaders:
    - name: target-sqlite
      namespace: target_sqlite
      pip_url: target-sqlite
```

Then:

```bash
meltano install
meltano run tap-sunrise-sunset target-sqlite
```

This is optional but demonstrates how the same Singer tap can be run under a
more fully featured orchestration framework.

---

### 8. Notes and Assumptions

- **Time zone**: All timestamps returned by the API (in UTC) are converted to
  IST by adding a fixed offset of 5 hours 30 minutes. IST does not observe DST,
  so a fixed offset is sufficient.
- **Location**: The example config uses New Delhi coordinates by default. For
  “current location” in a real deployment, you would typically inject latitude
  and longitude via configuration management, environment variables, or secrets
  management instead of hard-coding them.
- **Error handling**: The tap fails fast on API errors and logs the failure via
  Singer’s logger, which is appropriate for a batch-style backfill job.

