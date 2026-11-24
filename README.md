# Aeris · Emergency Rescue and Supply Drone System

Aeris is a working rescue coordination exercise for a fictionalized flood in Srinagar. A dispatcher can review a rooftop observation, propose an assistance mission, approve a payload, watch the simulated flight, and record the delivery receipt. The dashboard shares one database across operators and updates over WebSocket every two seconds. All geography, telemetry, flight actions, and onboard camera scenes in the default exercise are simulated.

## Start the exercise

Extract the entire archive. On Windows, double-click **Start-Aeris.cmd**, or run the following from the project directory on Windows, macOS, or Linux.

```sh
python tools/start.py
```

Open **http://127.0.0.1:8765** when Uvicorn reports application startup complete. Keep the terminal running. Ctrl+C stops the service. The archive contains the compiled frontend. Python 3.11+ is required. The bundled Windows x64 wheels support CPython 3.14 offline. Other Python versions and platforms need internet access for the first dependency installation. A clean source-only checkout also needs Node.js 22.12+ and npm to build the frontend.

The initial dashboard opens with observer access. Select **Observer → Sign in to exercise**. Local demo mode supplies the password for the selected role. The simulated aircraft are ready to use immediately.

| Exercise account | Demo password | Authority |
| --- | --- | --- |
| observer | exercise-observer | View the console, telemetry, and reports |
| operator | exercise-operator | Review observations, propose missions, acknowledge alerts, confirm supply receipts |
| coordinator | exercise-coordinator | All operator functions, dispatch approval, return, landing, recovery, and weather controls |

## Five-minute demonstration

1. Sign in as **coordinator**. In **Detection queue**, open *Riverside rooftops*. Inspect the camera overlay and the simulated observation location. Set a priority and select **Verify request**.
2. Select **New mission → Delivery**. Enter a name, choose an available cargo aircraft, a relief zone and the verified request. Choose *Drinking water* and two units. The form shows the load and aircraft capacity.
3. In **Missions**, open the proposed mission. Select **Approve dispatch → Confirm action**. Approval reserves stock and assigns the aircraft in the same transaction. The map shows its proposed and approved route.
4. After a few simulation ticks, the aircraft lands at the exercise relief zone. Open the mission in **Awaiting receipt** and select **Verify delivery → Confirm action**. Watch the return to base and **Completed** status. The **Supplies** screen shows the issued units.
5. Open **Mission reports**, inspect the timestamped history, and export the JSON report. A survey mission produces a new pending scenario observation when it reaches its survey zone.

The exercise begins with two preapproved survey patrols, two ready cargo aircraft, five supplies, and a small observation queue. Leaflet serves an offline raster. Operators can toggle restrictions, tracks and signals, inspect aircraft, pan, zoom, or expand the map. In the camera panel, **Stream** switches to a six-frame-per-second MJPEG replay. **Overlays** toggles frame-matched candidate boxes. The still-frame download captures the selected replay frame or the reference poster in streaming mode.

## Architecture

| Component | Implementation |
| --- | --- |
| Dashboard | Next.js static export, React, TypeScript, Tailwind utilities and custom CSS, locally bundled Leaflet and Geist |
| Application service | FastAPI REST endpoints, WebSocket state stream, same-origin static hosting |
| Flight simulation | Single timed worker, synthetic GPS, obstacle-checked waypoint graph, fuel reserve represented as battery, return and landing state transitions |
| Persistence | SQLite for local use. PostgreSQL/PostGIS through Docker Compose. DDL in `backend/schema.sql` and `backend/postgis.sql` |
| Vision | OpenCV + local Ultralytics YOLO/PyTorch for recorded RGB or compatible thermal clips. Bundled annotated synthetic footage works offline without model weights |
| Incident evidence | Reviewable candidate boxes, timestamp, provenance, optional model confidence, exercise location, reviewer and priority |
| Operator access | Password hashes using scrypt, opaque expiring HttpOnly session cookies, role checks and same-origin mutation checks |

The service rechecks available aircraft, link, battery reserve, mass, stock, safe exercise zone and request state at approval. A shortest-path search filters edges against the exercise boundary, restricted rectangle and bridge obstacle. Only named exercise sites can be selected. A recall returns unissued cargo to stock on reaching base. Emergency landing keeps cargo reserved until a coordinator records ground recovery. Concurrent approvals cannot allocate the same aircraft or inventory twice.

The first version runs entirely on the software simulator. It has no hardware command interface. PX4/ArduPilot, MAVLink/MAVSDK, Gazebo, physical delivery mechanisms, and real camera-to-ground geolocation remain integration work. A hardware phase would require engineering tests, site and airspace review, and operator authorization.

## Additional exercise controls

- **Fleet** shows simulated position, altitude, battery, connectivity, and payload capacity. Coordinators can simulate link loss or restore connectivity. Low battery or lost link triggers an onboard simulated return along previous approved segments.
- The **exercise weather** controls provide calm, rain and storm presets. Storm pauses dispatch and recalls active missions. The values and thresholds are training assumptions.
- **Mission reports** shows flood-mask coverage, blocked-road coverage, damaged structures, an exercise assembly-site candidate, response history, and a demand estimate. The demand estimate assumes one food unit and one water unit per unassigned verified request.
- A rule-based review suggestion highlights a scripted isolation or distress cue. The operator sets the actual priority. The fixture does not perform medical triage.
- The east embankment observation includes a separate synthetic SOS placard. The detector reads its pixels and compares the exercise lettering with a fixed template. Its review screen shows the original sign.
- After a successful visit and service-worker installation, the browser caches the exercise dashboard, map, footage and latest demo snapshot. During disconnection it displays the last snapshot and reconnects automatically. State-changing operations require the server. A private deployment does not persist operational snapshots in browser storage.

## Vision pipeline

Generate a report from the included footage annotations.

```sh
python -m vision.pipeline fixture --output exercise-report.json
```

For inference, install `vision/requirements.txt` in a Python environment supported by your PyTorch build. Supply a trusted local checkpoint with a person class.

```sh
python -m vision.pipeline analyze --video public/scene/camera.avi --weights models/person.pt --sample-seconds 0.5 --output detections.json
```

Open **Survivor detections → Import vision report**. Select a report, frame and exercise sector. Each box becomes a pending observation. Importing the same frame at the same sector again is idempotent. Recorded clips retain image coordinates and model confidence. Map pins use the operator-selected exercise sector. Recurring observations of the same person in different frames require operator reconciliation. Synthetic annotations have no model confidence.

See `vision/README.md` for thermal input, optional disaster-class weights, the report schema, and evaluation limits. Backend fixture assessment measures overlap against known synthetic masks. Field detection accuracy has not been measured.

## Deployment with PostgreSQL and PostGIS

Install Docker Engine with Compose. In the project root, create a local `.env` and set four unique passwords. Use a URL-safe database password because Compose inserts it into the database connection URL.

```dotenv
AERIS_DB_PASSWORD=replace_with_random_urlsafe_database_password
AERIS_COORDINATOR_PASSWORD=replace_with_coordinator_password
AERIS_OPERATOR_PASSWORD=replace_with_operator_password
AERIS_OBSERVER_PASSWORD=replace_with_observer_password
```

```sh
docker compose up --build
```

Open the same loopback URL. Compose disables demo access, persists PostgreSQL in a named volume, and starts one simulator worker. The service creates spatial views for aircraft and observation locations and a spatial index. A reverse proxy for a team deployment must forward WebSocket upgrades and preserve the Host header. Use HTTPS there and set `AERIS_SECURE_COOKIE=1`. Keep one simulator process per exercise database.

The local database defaults to `data/exercise.sqlite3`. To start an independent exercise without changing previous records, set `AERIS_DB` to a new path before starting the service. For a direct PostGIS deployment install `backend/requirements-postgres.txt`, set `DATABASE_URL`, and grant permission to create the extension or preinstall it. All three explicit role passwords are required when `AERIS_DEMO=0`.

## API and development

Interactive OpenAPI documentation is at **/docs**. REST paths below are relative to **/api**.

| Method and path | Function |
| --- | --- |
| GET /health, /session | Health, simulation mode, session identity |
| POST /login, /logout | Create or revoke a session |
| GET /state | Fleet, missions, inventory, geofence, observations, events and alerts |
| WS /stream | Full exercise snapshot every two seconds |
| GET /camera/stream?overlays=true | Synthetic MJPEG replay, with optional annotations |
| POST /missions | Validate payload and propose a survey or delivery |
| POST /missions/{id}/{action} | approve, cancel, return, land, confirm |
| POST /detections/{id}/review | Record operator verification or dismissal and priority |
| POST /vision/import | Import a normalized frame of candidate observations |
| POST /fleet/{id}/{action} | link-loss, restore-link, recover |
| POST /alerts/{id}/acknowledge | Record acknowledgement |
| POST /weather/{profile} | Set exercise weather to Calm, Rain or Storm |
| GET /assessment, /report | Synthetic sector assessment and exercise history export |

To rebuild after frontend edits, run `npm install` and `npm run build`, then restart the FastAPI service. Run `npm run typecheck` to verify TypeScript. To run the integration tests, install backend requirements and `httpx` in your active environment, build the frontend (or use the included export), and run:

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s vision -t . -v
```

Tests use temporary databases. They cover authorization, dispatch races, verification, payload limits, geofence rejection, disaster weather, return and recovery, delivery receipt accounting, frame import, WebSocket updates, and static asset serving.

The procedural assets are original. Leaflet and Geist license files are included under `public/vendor/leaflet` and `public/fonts`. The offline Python wheel distributions retain their package metadata and licenses.
#   E m e r g e n c y - S u p p l y - D r o n e  
 