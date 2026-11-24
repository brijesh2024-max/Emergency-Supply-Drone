"use client";
import { useEffect, useRef, useState } from "react";
import { X, ShieldCheck, LockKeyhole, Route, Box, MapPin } from "lucide-react";
import { State, User, request, statusClass, clock } from "./types";
import Camera from "./Camera";
export type Dialog = {
  kind:
    | "login"
    | "new"
    | "detection"
    | "mission"
    | "drone"
    | "alerts"
    | "import";
  id?: string;
};
export function Chip({ value }: { value: string }) {
  return <span className={"chip " + statusClass(value)}>{value}</span>;
}
type Props = {
  dialog: Dialog;
  state: State | null;
  user: User | null;
  demo: boolean;
  close: () => void;
  refresh: () => Promise<void>;
  onUser: (u: User | null) => void;
  notify: (s: string) => void;
};
export default function Dialogs({
  dialog,
  state,
  user,
  demo,
  close,
  refresh,
  onUser,
  notify,
}: Props) {
  const box = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [role, setRole] = useState("coordinator"),
    [password, setPassword] = useState("");
  const [kind, setKind] = useState(
      dialog.id === "delivery" ? "Delivery" : "Survey",
    ),
    [name, setName] = useState(""),
    [zone, setZone] = useState(Object.keys(state?.zones || {})[0] || ""),
    [aircraft, setAircraft] = useState(
      state?.drones.find((d) => d.status === "Ready" && d.link)?.id || "",
    ),
    [item, setItem] = useState("medical"),
    [qty, setQty] = useState(1),
    [candidate, setCandidate] = useState(
      state?.detections.find((d) => d.status === "Verified")?.id || "",
    ),
    [priority, setPriority] = useState(
      state?.detections.find((d) => d.id === dialog.id)?.priority || "Medium",
    ),
    [confirm, setConfirm] = useState(""),
    [needLogin, setNeedLogin] = useState(false);
  const [report, setReport] = useState<any>(null),
    [frameIndex, setFrameIndex] = useState(0);
  useEffect(() => {
    box.current?.showModal();
    const element = box.current;
    return () => element?.close();
  }, []);
  const d = state?.detections.find((x) => x.id === dialog.id),
    m = state?.missions.find((x) => x.id === dialog.id),
    dr = state?.drones.find((x) => x.id === dialog.id),
    stock = state?.inventory.find((x) => x.id === item),
    vehicle = state?.drones.find((x) => x.id === aircraft);
  const load = kind === "Delivery" ? qty * (stock?.mass || 0) : 0;
  const write = user && user.role !== "observer",
    coord = user?.role === "coordinator";
  const loginView = dialog.kind === "login" || needLogin;
  async function submit(
    fn: () => Promise<unknown>,
    message: string,
    finish = true,
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
      notify(message);
      if (finish) close();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function access(coordinator = false) {
    if (coordinator ? coord : write) return null;
    return (
      <div className="access-note">
        <LockKeyhole size={16} />
        <span>
          {coordinator
            ? "Coordinator approval required"
            : "Operator or coordinator access required"}
        </span>
        <button
          type="button"
          onClick={() => {
            setNeedLogin(true);
            setError("");
          }}
        >
          Sign in
        </button>
      </div>
    );
  }
  const route = state?.plans?.[zone] || [];
  const sessionForm = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit(
          async () => {
            const u = await request<User>("login", {
              username: role,
              password: password || (demo ? "exercise-" + role : ""),
            });
            onUser(u);
            if (needLogin) setNeedLogin(false);
          },
          "Signed in as " + role,
          !needLogin,
        );
      }}
    >
      <p className="muted">
        {demo
          ? "Choose an exercise account to work in the simulated incident."
          : "Sign in with your assigned exercise credentials."}
      </p>
      <label>
        Account
        <select
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setPassword("");
          }}
        >
          <option value="coordinator">Coordinator</option>
          <option value="operator">Rescue operator</option>
          <option value="observer">Observer</option>
        </select>
      </label>
      <div className="info-line">
        <ShieldCheck size={17} />
        {role === "coordinator"
          ? "Approve deployments, review signals and manage the fleet."
          : role === "operator"
            ? "Propose missions, verify signals and confirm delivery receipts."
            : "Read exercise telemetry, history and reports."}
      </div>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required={!demo}
          placeholder={
            demo ? "Demo password supplied automatically" : "Account password"
          }
        />
      </label>
      <button className="primary" disabled={busy}>
        Sign in{demo ? " to exercise" : ""}
      </button>
    </form>
  );
  const names: Record<Dialog["kind"], string> = {
    login: "Operator session",
    new: "Create mission",
    detection: "Review detection",
    mission: "Mission details",
    drone: "Aircraft telemetry",
    alerts: "Emergency alerts",
    import: "Import vision observations",
  };
  return (
    <dialog
      ref={box}
      className="dialog"
      onCancel={close}
      onClick={(e) => {
        if (e.target === box.current) close();
      }}
    >
      <article>
        <header>
          <div>
            <span className="kicker">Aeris / simulation</span>
            <h2>{needLogin ? "Operator session" : names[dialog.kind]}</h2>
          </div>
          <button
            aria-label="Close dialog"
            className="icon-btn"
            onClick={close}
          >
            <X size={18} />
          </button>
        </header>
        {loginView ? (
          user && !needLogin && dialog.kind === "login" ? (
            <>
              <p>
                Signed in as <strong>{user.username}</strong>.
              </p>
              <div className="dialog-actions">
                <button
                  className="secondary"
                  onClick={() =>
                    submit(async () => {
                      await request("logout", {});
                      onUser(null);
                    }, "Signed out")
                  }
                >
                  Sign out
                </button>
                <button className="primary" onClick={() => setNeedLogin(true)}>
                  Switch account
                </button>
              </div>
            </>
          ) : (
            sessionForm
          )
        ) : (
          <>
            {dialog.kind === "new" && state && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  submit(
                    () =>
                      request("missions", {
                        name,
                        kind,
                        zone,
                        drone: aircraft,
                        item,
                        qty,
                        candidate,
                      }),
                    "Mission submitted for coordinator approval",
                  );
                }}
              >
                <div className="segmented">
                  {["Survey", "Delivery"].map((k) => (
                    <button
                      type="button"
                      key={k}
                      className={kind === k ? "chosen" : ""}
                      onClick={() => setKind(k)}
                    >
                      {k === "Survey" ? <Route size={16} /> : <Box size={16} />}{" "}
                      {k}
                    </button>
                  ))}
                </div>
                <label>
                  Mission name
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    minLength={3}
                    maxLength={70}
                    placeholder="e.g. North bank relief run"
                  />
                </label>
                <div className="form-row">
                  <label>
                    Relief zone
                    <select
                      value={zone}
                      onChange={(e) => setZone(e.target.value)}
                    >
                      {Object.keys(state.zones).map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Available aircraft
                    <select
                      required
                      value={aircraft}
                      onChange={(e) => setAircraft(e.target.value)}
                    >
                      {state.drones
                        .filter((x) => x.status === "Ready" && x.link)
                        .map((x) => (
                          <option key={x.id}>{x.id}</option>
                        ))}
                    </select>
                  </label>
                </div>
                {kind === "Delivery" && (
                  <>
                    <label>
                      Verified assistance request
                      <select
                        required
                        value={candidate}
                        onChange={(e) => setCandidate(e.target.value)}
                      >
                        <option value="">Select a verified request</option>
                        {state.detections
                          .filter((x) => x.status === "Verified")
                          .map((x) => (
                            <option value={x.id} key={x.id}>
                              {x.id} · {x.sector}
                            </option>
                          ))}
                      </select>
                    </label>
                    <div className="form-row">
                      <label>
                        Supply
                        <select
                          value={item}
                          onChange={(e) => setItem(e.target.value)}
                        >
                          {state.inventory.map((x) => (
                            <option key={x.id} value={x.id}>
                              {x.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Units
                        <input
                          type="number"
                          value={qty}
                          min={1}
                          max={stock?.available}
                          onChange={(e) => setQty(Number(e.target.value))}
                        />
                      </label>
                    </div>
                    <p
                      className={
                        load > (vehicle?.capacity || 0) ? "error" : "muted"
                      }
                    >
                      Payload {load.toFixed(2)} / {vehicle?.capacity || 0} kg ·{" "}
                      {stock?.available} units in stock
                    </p>
                  </>
                )}
                <div className="info-line">
                  <Route size={18} />
                  <span>
                    Base to {zone} · {route.length} waypoints
                    <br />
                    <small>
                      Exercise geofence and exclusions checked before dispatch.
                    </small>
                  </span>
                </div>
                {access()}
                <button
                  className="primary"
                  disabled={
                    busy ||
                    !write ||
                    !aircraft ||
                    load > (vehicle?.capacity || 0)
                  }
                >
                  Submit for approval
                </button>
              </form>
            )}
            {dialog.kind === "detection" && d && (
              <>
                <div className="record-head">
                  <span className="mono">{d.id}</span>
                  <Chip value={d.status} />
                </div>
                <h3>{d.sector}</h3>
                <p className="muted">
                  <MapPin size={15} /> {d.lat.toFixed(5)}° N ·{" "}
                  {d.lon.toFixed(5)}° E · exercise location
                </p>
                {d.id === "DET-001" && <Camera wide />}
                {d.source === "Synthetic SOS placard" && (
                  <div className="sos-evidence">
                    <img
                      src="/scene/sos.png"
                      alt="Synthetic SOS placard for exercise review"
                    />
                    <span>
                      <strong>Visible SOS sign</strong>Pixel-template match,
                      pending operator interpretation.
                    </span>
                  </div>
                )}
                <dl>
                  <dt>Evidence</dt>
                  <dd>{d.source}</dd>
                  <dt>Confidence</dt>
                  <dd>
                    {d.confidence === null
                      ? "Fixture annotation"
                      : (100 * d.confidence).toFixed(1) + "%"}
                  </dd>
                  <dt>Observed</dt>
                  <dd>{clock(d.observed)} UTC</dd>
                  {d.evidence.time_s !== undefined && (
                    <>
                      <dt>Recording position</dt>
                      <dd>
                        {d.evidence.time_s.toFixed(2)} s · frame{" "}
                        {d.evidence.frame_index}
                      </dd>
                    </>
                  )}
                  {d.reviewed_by && (
                    <>
                      <dt>Reviewed by</dt>
                      <dd>{d.reviewed_by}</dd>
                    </>
                  )}
                </dl>
                {d.status === "Pending" ? (
                  <>
                    <div className="info-line">
                      <ShieldCheck size={16} />
                      <span>
                        Suggested review priority · {d.hint.priority}
                        <br />
                        <small>{d.hint.reason}</small>
                      </span>
                    </div>
                    <label>
                      Response priority
                      <select
                        value={priority}
                        onChange={(e) => setPriority(e.target.value)}
                      >
                        {["High", "Medium", "Low"].map((x) => (
                          <option key={x}>{x}</option>
                        ))}
                      </select>
                    </label>
                    {access()}
                    <div className="dialog-actions">
                      {["Dismissed", "Verified"].map((s) => (
                        <button
                          key={s}
                          disabled={!write || busy}
                          className={s === "Verified" ? "primary" : "secondary"}
                          onClick={() =>
                            submit(
                              () =>
                                request("detections/" + d.id + "/review", {
                                  status: s,
                                  priority,
                                }),
                              "Detection " + s.toLowerCase(),
                            )
                          }
                        >
                          {s === "Verified" ? "Verify request" : "Dismiss"}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <p>Response priority · {d.priority}</p>
                )}
              </>
            )}
            {dialog.kind === "mission" && m && (
              <>
                <div className="record-head">
                  <span className="mono">{m.id}</span>
                  <Chip value={m.status} />
                </div>
                <h3>{m.name}</h3>
                <dl>
                  <dt>Aircraft</dt>
                  <dd>{m.drone}</dd>
                  <dt>Destination</dt>
                  <dd>{m.zone}</dd>
                  <dt>Route</dt>
                  <dd>{m.route.length} exercise waypoints</dd>
                  <dt>Submitted by</dt>
                  <dd>{m.created_by}</dd>
                  <dt>Approved by</dt>
                  <dd>{m.approved_by || "Awaiting authorization"}</dd>
                  {m.kind === "Delivery" && (
                    <>
                      <dt>Manifest</dt>
                      <dd>
                        {m.qty} ×{" "}
                        {state?.inventory.find((i) => i.id === m.item)?.name}
                      </dd>
                      <dt>Assistance request</dt>
                      <dd>{m.candidate}</dd>
                    </>
                  )}
                </dl>
                {access(["Active", "Returning", "Proposed"].includes(m.status))}
                <div className="dialog-actions">
                  {(m.status === "Proposed"
                    ? ["cancel", "approve"]
                    : m.status === "Awaiting receipt"
                      ? ["return", "confirm", "land"]
                      : m.status === "Active"
                        ? ["return", "land"]
                        : m.status === "Returning"
                          ? ["land"]
                          : []
                  ).map((a) => (
                    <button
                      key={a}
                      disabled={
                        busy ||
                        (!["confirm", "cancel"].includes(a) ? !coord : !write)
                      }
                      className={
                        a === "approve" || a === "confirm"
                          ? "primary"
                          : "secondary"
                      }
                      onClick={() => {
                        setConfirm(a);
                        setError("");
                      }}
                    >
                      {
                        (
                          {
                            cancel: "Cancel proposal",
                            approve: "Approve dispatch",
                            return: "Return to base",
                            confirm: "Verify delivery",
                            land: "Emergency landing",
                          } as Record<string, string>
                        )[a]
                      }
                    </button>
                  ))}
                </div>
                {confirm && (
                  <div className="confirm-box">
                    <p>
                      Confirm{" "}
                      {confirm === "confirm"
                        ? "receipt of these supplies at the approved relief zone"
                        : confirm + " for " + m.id}{" "}
                      in this simulation?
                    </p>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() =>
                        submit(
                          () => request("missions/" + m.id + "/" + confirm, {}),
                          "Mission updated",
                        )
                      }
                    >
                      Confirm action
                    </button>
                  </div>
                )}
              </>
            )}
            {dialog.kind === "drone" && dr && (
              <>
                <div className="record-head">
                  <h3>{dr.id}</h3>
                  <Chip value={dr.status} />
                </div>
                <p>{dr.model}</p>
                <dl>
                  <dt>Battery</dt>
                  <dd>{Math.round(dr.battery)}%</dd>
                  <dt>Altitude</dt>
                  <dd>{dr.altitude} m</dd>
                  <dt>Payload capacity</dt>
                  <dd>{dr.capacity} kg</dd>
                  <dt>Link</dt>
                  <dd>{dr.link ? "Connected" : "Disconnected"}</dd>
                  <dt>Position</dt>
                  <dd>
                    {dr.lat.toFixed(5)}, {dr.lon.toFixed(5)}
                  </dd>
                </dl>
                {access(true)}
                <div className="dialog-actions">
                  {[
                    dr.link ? "link-loss" : "restore-link",
                    ...(dr.status === "Grounded" ? ["recover"] : []),
                  ].map((a) => (
                    <button
                      key={a}
                      disabled={!coord || busy}
                      className="secondary"
                      onClick={() => setConfirm(a)}
                    >
                      {a === "link-loss"
                        ? "Simulate link loss"
                        : a === "recover"
                          ? "Recover at base"
                          : "Restore link"}
                    </button>
                  ))}
                </div>
                {confirm && (
                  <button
                    className="primary"
                    disabled={!coord || busy}
                    onClick={() =>
                      submit(
                        () => request("fleet/" + dr.id + "/" + confirm, {}),
                        "Fleet updated",
                      )
                    }
                  >
                    Confirm {confirm.replace("-", " ")}
                  </button>
                )}
              </>
            )}
            {dialog.kind === "alerts" && state && (
              <>
                {state.alerts.map((a) => (
                  <div className="alert-card" key={a.id}>
                    <Chip value={a.severity} />
                    <h3>{a.message}</h3>
                    <p>{a.detail}</p>
                    {a.acknowledged_by ? (
                      <small>Acknowledged by {a.acknowledged_by}</small>
                    ) : (
                      <button
                        className="secondary"
                        disabled={!write || busy}
                        onClick={() =>
                          submit(
                            () =>
                              request("alerts/" + a.id + "/acknowledge", {}),
                            "Alert acknowledged",
                            false,
                          )
                        }
                      >
                        Acknowledge alert
                      </button>
                    )}
                  </div>
                ))}
                {access()}
              </>
            )}
            {dialog.kind === "import" && state && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = report?.frames?.[frameIndex];
                  submit(
                    () =>
                      request("vision/import", {
                        zone,
                        source: report.source.name,
                        frame_index: f.frame_index,
                        time_s: f.time_s,
                        candidates: f.candidates.map((c: any) => ({
                          bbox: c.bbox,
                          confidence: c.confidence,
                          provenance: c.provenance,
                        })),
                      }),
                    "Frame observations added to review queue",
                  );
                }}
              >
                <p className="muted">
                  Select a report produced by the offline vision pipeline.
                  Choose one frame and assign its observations to an exercise
                  sector.
                </p>
                <label>
                  Vision report
                  <input
                    type="file"
                    accept=".json,application/json"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      try {
                        if (file.size > 12e6)
                          throw Error("Report exceeds 12 MB");
                        const data = JSON.parse(await file.text());
                        if (
                          data.schema_version !== 1 ||
                          data.mode !== "simulation" ||
                          !Array.isArray(data.frames) ||
                          !data.source?.name
                        )
                          throw Error(
                            "Select a version 1 simulation vision report",
                          );
                        data.frames = data.frames.filter(
                          (f: any) =>
                            Array.isArray(f.candidates) && f.candidates.length,
                        );
                        if (!data.frames.length)
                          throw Error(
                            "No candidate observations in this report",
                          );
                        setReport(data);
                        setFrameIndex(0);
                        setError("");
                      } catch (err) {
                        setReport(null);
                        setError((err as Error).message);
                      }
                    }}
                  />
                </label>
                {report && (
                  <label>
                    Frame
                    <select
                      value={frameIndex}
                      onChange={(e) => setFrameIndex(Number(e.target.value))}
                    >
                      {report.frames.map((f: any, i: number) => (
                        <option key={i} value={i}>
                          Frame {f.frame_index} · {f.time_s}s ·{" "}
                          {f.candidates.length} observations
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label>
                  Exercise sector
                  <select
                    value={zone}
                    onChange={(e) => setZone(e.target.value)}
                  >
                    {Object.keys(state.zones).map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                {access()}
                <button
                  className="primary"
                  disabled={!write || !report || busy}
                >
                  Import selected frame
                </button>
              </form>
            )}
          </>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </article>
    </dialog>
  );
}
