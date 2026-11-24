"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  Boxes,
  ChevronRight,
  ChevronDown,
  Clock3,
  Download,
  Drone as Aircraft,
  FileText,
  LayoutDashboard,
  ListFilter,
  MapPin,
  Menu,
  Package,
  Plus,
  Radio,
  RadioTower,
  Route,
  ScanLine,
  ShieldCheck,
  Siren,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import RescueMap from "./RescueMap";
import Camera from "./Camera";
import ExerciseConditions from "./ExerciseConditions";
import Dialogs, { Chip, Dialog } from "./Dialogs";
import { clock, request, shortDate, State, User, View } from "./types";
const nav: [View, LucideIcon, string][] = [
  ["Overview", LayoutDashboard, "Overview"],
  ["Missions", Route, "Missions"],
  ["Detections", ScanLine, "Survivor detections"],
  ["Supplies", Boxes, "Supply inventory"],
  ["Fleet", Aircraft, "Drone fleet"],
  ["Reports", FileText, "Mission reports"],
];
const headings: Record<View, string> = {
  Overview: "Operations overview",
  Missions: "Mission control",
  Detections: "Survivor detections",
  Supplies: "Supply inventory",
  Fleet: "Drone fleet",
  Reports: "Mission reports",
};
function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon shrink-0">
        <svg viewBox="0 0 36 36" fill="none" aria-hidden="true">
          <path d="M3 26 18 5l15 21-15-8-15 8Z" fill="currentColor" />
          <path d="m11 27 7-4 7 4-7 4-7-4Z" fill="currentColor" />
        </svg>
      </span>
      <div>
        <b>AERIS</b>
        <small>RESCUE SYSTEMS</small>
      </div>
    </div>
  );
}
function Metric({
  label,
  value,
  detail,
  tone,
  Icon,
}: {
  label: string;
  value: number;
  detail: string;
  tone: string;
  Icon: LucideIcon;
}) {
  return (
    <div className={"metric " + tone}>
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon size={18} />
        </span>
      </div>
      <strong>{String(value).padStart(2, "0")}</strong>
      <div className="metric-foot">
        <i />
        {detail}
      </div>
    </div>
  );
}
function PanelTitle({
  kicker,
  title,
  action,
  onClick,
}: {
  kicker?: string;
  title: string;
  action?: string;
  onClick?: () => void;
}) {
  return (
    <div className="panel-title">
      <div>
        {kicker && <span className="kicker">{kicker}</span>}
        <h2>{title}</h2>
      </div>
      {action && (
        <button className="text-button" onClick={onClick}>
          {action}
          <ChevronRight size={15} />
        </button>
      )}
    </div>
  );
}
export default function Console() {
  const [view, setView] = useState<View>("Overview"),
    [state, setState] = useState<State | null>(null),
    [user, setUser] = useState<User | null>(null),
    [demo, setDemo] = useState(true),
    [conn, setConn] = useState("Connecting"),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [dialog, setDialog] = useState<Dialog | null>(null),
    [mobile, setMobile] = useState(false),
    [filter, setFilter] = useState("All"),
    [search, setSearch] = useState(""),
    [assessment, setAssessment] = useState<any>(null);
  const generation = useRef(0);
  const apply = useCallback((s: State) => {
    setState((old) => (old && old.time > s.time ? old : s));
    setError("");
    setDemo(s.demo);
    try {
      if (s.demo)
        localStorage.setItem("aeris-exercise-cache", JSON.stringify(s));
      else localStorage.removeItem("aeris-exercise-cache");
    } catch {}
  }, []);
  const refresh = useCallback(async () => {
    const n = ++generation.current;
    try {
      const p = await request<{ user: User | null; demo: boolean }>("session");
      if (n !== generation.current) return;
      setUser(p.user);
      setDemo(p.demo);
      if (!p.demo && !p.user) {
        try {
          localStorage.removeItem("aeris-exercise-cache");
        } catch {}
        setState(null);
        setDialog({ kind: "login" });
        return;
      }
      const s = await request<State>("state");
      if (n === generation.current) apply(s);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [apply]);
  useEffect(() => {
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/worker.js").catch(() => {});
    try {
      const s = JSON.parse(
        localStorage.getItem("aeris-exercise-cache") || "null",
      );
      if (s?.mode === "Simulation" && s.demo) {
        setState(s);
        setConn("Cached");
      }
    } catch {}
    refresh();
  }, [refresh]);
  useEffect(() => {
    if (!state) return;
    let stopped = false,
      timer: ReturnType<typeof setTimeout>,
      ws: WebSocket;
    const connect = () => {
      ws = new WebSocket(
        (location.protocol === "https:" ? "wss://" : "ws://") +
          location.host +
          "/api/stream",
      );
      ws.onopen = () => {
        if (!stopped) setConn("Connected");
      };
      ws.onmessage = (e) => {
        if (!stopped) apply(JSON.parse(e.data));
      };
      ws.onerror = () => ws.close();
      ws.onclose = (event) => {
        if (stopped) return;
        if (event.code === 1008) {
          setUser(null);
          setState(null);
          setDialog({ kind: "login" });
          setConn("Signed out");
          return;
        }
        setConn("Reconnecting");
        timer = setTimeout(connect, 2500);
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ws.close();
    };
  }, [Boolean(state), user?.username, apply]);
  useEffect(() => {
    if (!message) return;
    const id = setTimeout(() => setMessage(""), 4000);
    return () => clearTimeout(id);
  }, [message]);
  useEffect(() => {
    if (view === "Reports")
      request("assessment")
        .then(setAssessment)
        .catch((e) => setError(e.message));
  }, [view]);
  function go(v: View) {
    setView(v);
    setMobile(false);
    setSearch("");
    setFilter("All");
    window.scrollTo({ top: 0 });
  }
  const pending = state?.detections.filter((d) => d.status === "Pending") || [],
    active =
      state?.missions.filter((m) =>
        ["Active", "Returning", "Awaiting receipt"].includes(m.status),
      ) || [],
    alerts = state?.alerts.filter((a) => !a.acknowledged_by) || [];
  const open = (kind: Dialog["kind"], id?: string) => setDialog({ kind, id });
  const filteredMissions = (state?.missions || []).filter(
    (m) =>
      (filter === "All" || m.status === filter) &&
      (m.id + " " + m.name + " " + m.zone)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const toolbar = (options: string[], name: string) => (
    <div className="table-tools">
      <input
        aria-label={"Search " + name}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder={"Search " + name + "…"}
      />
      <div>
        <ListFilter size={15} />
        <select
          aria-label="Status filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {["All", ...options].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </div>
    </div>
  );
  const missionTable = (overview = false) => (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Mission</th>
            <th>Aircraft</th>
            <th>Relief zone</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {(overview ? active.slice(0, 4) : filteredMissions).map((m) => (
            <tr key={m.id}>
              <td>
                <button
                  className="row-link"
                  onClick={() => open("mission", m.id)}
                >
                  {m.name}
                </button>
                <small>
                  {m.id} · {m.kind}
                </small>
              </td>
              <td className="mono tabular-nums">{m.drone}</td>
              <td>{m.zone}</td>
              <td>
                <Chip value={m.status} />
              </td>
              <td>
                <button
                  className="plain-icon"
                  aria-label={"Open mission " + m.id}
                  onClick={() => open("mission", m.id)}
                >
                  <ChevronRight size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!(overview ? active : filteredMissions).length && (
        <div className="empty">No missions match this view.</div>
      )}
    </div>
  );
  const queue = (overview = false) => {
    const ds = (overview ? pending : state?.detections || []).filter(
      (d) =>
        overview ||
        ((filter === "All" || d.status === filter) &&
          (d.id + " " + d.sector).toLowerCase().includes(search.toLowerCase())),
    );
    return (
      <div className="queue">
        {ds.map((d) => (
          <button
            className="queue-row"
            key={d.id}
            onClick={() => open("detection", d.id)}
          >
            <span
              className={
                "queue-icon " + (d.priority === "High" ? "orange" : "blue")
              }
            >
              <ScanLine size={19} />
            </span>
            <span className="grow min-w-0">
              <b>{d.sector}</b>
              <small>
                {d.id} <span>·</span>{" "}
                {overview ? d.priority + " priority" : d.source}
              </small>
            </span>
            {!overview && <Chip value={d.status} />}
            <ChevronRight size={14} />
          </button>
        ))}
        {!ds.length && (
          <div className="empty">No detections match this view.</div>
        )}
      </div>
    );
  };
  return (
    <div className="shell">
      {mobile && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={mobile ? "sidebar open" : "sidebar"}>
        <Brand />
        <div className="sidebar-main">
          <div className="nav-group-label">Workspace</div>
          <nav>
            {nav.map(([key, Icon, title], i) => (
              <div key={key}>
                {i === 4 && (
                  <div className="nav-group-label secondary-group">
                    Resources
                  </div>
                )}
                <button
                  className={"nav-item " + (view === key ? "active" : "")}
                  onClick={() => go(key)}
                >
                  <Icon size={18} />
                  <span>{title}</span>
                  {key === "Detections" && pending.length > 0 && (
                    <small>{pending.length}</small>
                  )}
                </button>
              </div>
            ))}
          </nav>
        </div>
        <div className="side-bottom">
          <div className="exercise-status">
            <div className="indicator" />
            <div>
              <b>Simulation mode</b>
              <small>Local exercise environment</small>
            </div>
          </div>
          <button
            className="account"
            onClick={() => {
              setMobile(false);
              open("login");
            }}
          >
            <span className="avatar">
              {user ? user.username.slice(0, 2).toUpperCase() : "OB"}
            </span>
            <span>
              <b>
                {user
                  ? user.role[0].toUpperCase() + user.role.slice(1)
                  : "Observer"}
              </b>
              <small>{user ? "Exercise account" : "Sign in to operate"}</small>
            </span>
            <ChevronDown size={14} />
          </button>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <button
              className="plain-icon mobile-toggle"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={19} />
            </button>
            <span className="crumb">Command center</span>
            <ChevronRight size={12} />
            <b>{view}</b>
          </div>
          <div>
            <span
              className={
                "system-status " + (conn === "Connected" ? "" : "disconnected")
              }
            >
              <i />
              {conn === "Connected" ? "Telemetry online" : conn}
            </span>
            <span className="divider" />
            <button
              className="bell"
              aria-label={"Alerts, " + alerts.length + " unacknowledged"}
              onClick={() => open("alerts")}
            >
              <Bell size={18} />
              {!!alerts.length && <i />}
            </button>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <i /> Incident command
              </div>
              <h1>{headings[view]}</h1>
              <p>
                <MapPin size={14} /> Srinagar, Kashmir Valley{" "}
                <span className="subtitle-dot">/</span> Flood response exercise
              </p>
            </div>
            <button
              className="primary"
              onClick={() => open("new")}
              disabled={!state}
            >
              <Plus size={17} /> New mission
            </button>
          </div>
          {error && (
            <div className="notice" role="alert">
              {error} <button onClick={refresh}>Retry connection</button>
            </div>
          )}
          {!state ? (
            <div className="panel loading">
              <Radio size={24} /> Connecting to the exercise server…{" "}
              <button className="secondary" onClick={() => open("login")}>
                Operator sign in
              </button>
            </div>
          ) : (
            <>
              {view === "Overview" && (
                <>
                  <section className="metrics">
                    <Metric
                      label="Active missions"
                      value={active.length}
                      detail={
                        state.missions.filter((m) => m.status === "Proposed")
                          .length + " awaiting approval"
                      }
                      tone="lime"
                      Icon={Route}
                    />
                    <Metric
                      label="Airborne units"
                      value={state.drones.filter((d) => d.altitude > 0).length}
                      detail={"Of " + state.drones.length + " fleet aircraft"}
                      tone="blue"
                      Icon={Aircraft}
                    />
                    <Metric
                      label="Survivor signals"
                      value={
                        state.detections.filter((d) => d.status !== "Dismissed")
                          .length
                      }
                      detail={pending.length + " awaiting review"}
                      tone="orange"
                      Icon={ScanLine}
                    />
                    <Metric
                      label="Supply stock"
                      value={state.inventory.reduce(
                        (n, i) => n + i.available,
                        0,
                      )}
                      detail={state.inventory.length + " supply categories"}
                      tone="purple"
                      Icon={Package}
                    />
                  </section>
                  <div className="overview-grid">
                    <div className="map-col">
                      <RescueMap
                        state={state}
                        onPick={(k, id) => open(k as Dialog["kind"], id)}
                      />
                      <section className="panel">
                        <PanelTitle
                          title="Active missions"
                          action="View all"
                          onClick={() => go("Missions")}
                        />
                        {missionTable(true)}
                      </section>
                    </div>
                    <div className="feed-col">
                      <Camera />
                      <section className="panel">
                        <div className="panel-title compact">
                          <div className="section-title">
                            <ScanLine size={17} />
                            <h2>Detection queue</h2>
                          </div>
                          <span className="count">{pending.length}</span>
                        </div>
                        {queue(true)}
                        <button
                          className="panel-foot-link"
                          onClick={() => go("Detections")}
                        >
                          Review detections
                          <ChevronRight size={14} />
                        </button>
                      </section>
                      <section
                        className={
                          "alert-strip " + (!alerts.length ? "resolved" : "")
                        }
                      >
                        <Siren size={18} />
                        <div>
                          <b>{alerts[0]?.message || "Alerts acknowledged"}</b>
                          <small>
                            {alerts.length
                              ? alerts.length +
                                " unacknowledged alert" +
                                (alerts.length === 1 ? "" : "s")
                              : "Exercise alert log"}
                          </small>
                        </div>
                        <button
                          aria-label="View emergency alerts"
                          onClick={() => open("alerts")}
                        >
                          <ChevronRight size={16} />
                        </button>
                      </section>
                    </div>
                  </div>
                </>
              )}
              {view === "Missions" && (
                <section className="panel">
                  <PanelTitle kicker="Dispatch desk" title="Mission register" />
                  {toolbar(
                    [
                      "Proposed",
                      "Active",
                      "Awaiting receipt",
                      "Returning",
                      "Completed",
                      "Recalled",
                      "Landed",
                      "Cancelled",
                    ],
                    "missions",
                  )}
                  {missionTable()}
                </section>
              )}
              {view === "Detections" && (
                <section className="panel">
                  <PanelTitle
                    kicker="Intelligence"
                    title="Observation register"
                    action="Import vision report"
                    onClick={() => open("import")}
                  />
                  {toolbar(["Pending", "Verified", "Dismissed"], "detections")}
                  {queue()}
                </section>
              )}
              {view === "Supplies" && (
                <section className="panel">
                  <PanelTitle
                    kicker="Logistics"
                    title="Supply manifest"
                    action="Plan delivery"
                    onClick={() => {
                      setDialog({ kind: "new", id: "delivery" });
                    }}
                  />
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Supply</th>
                          <th>Unit weight</th>
                          <th>Available</th>
                          <th>Reserved</th>
                          <th>Issued</th>
                        </tr>
                      </thead>
                      <tbody>
                        {state.inventory.map((i) => (
                          <tr key={i.id}>
                            <td>
                              <strong>{i.name}</strong>
                            </td>
                            <td>{i.mass.toFixed(2)} kg</td>
                            <td className="mono tabular-nums">{i.available}</td>
                            <td>
                              {state.missions
                                .filter((m) => m.item === i.id && m.reserved)
                                .reduce((n, m) => n + m.qty, 0)}
                            </td>
                            <td>
                              {state.missions
                                .filter(
                                  (m) =>
                                    m.item === i.id &&
                                    m.approved_by &&
                                    m.return_reason === "Delivered",
                                )
                                .reduce((n, m) => n + m.qty, 0)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
              {view === "Fleet" && (
                <>
                  <ExerciseConditions
                    state={state}
                    user={user}
                    refresh={refresh}
                  />
                  <div className="fleet-grid">
                    {state.drones.map((d) => (
                      <button
                        key={d.id}
                        className="panel fleet-card"
                        onClick={() => open("drone", d.id)}
                      >
                        <div>
                          <span className="fleet-icon">
                            <Aircraft size={26} />
                          </span>
                          <Chip value={d.status} />
                        </div>
                        <h2>{d.id}</h2>
                        <p>{d.model}</p>
                        <div>
                          <span>Battery</span>
                          <b>{Math.round(d.battery)}%</b>
                        </div>
                        <div className="battery">
                          <i style={{ width: d.battery + "%" }} />
                        </div>
                        <div>
                          <span>{d.capacity} kg payload</span>
                          <span>{d.link ? "Connected" : "Link lost"}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {view === "Reports" && (
                <>
                  <div className="report-grid">
                    <section className="panel">
                      <PanelTitle
                        kicker="Synthetic assessment"
                        title="Sector impact"
                      />
                      {assessment ? (
                        <dl className="report-dl">
                          <dt>Estimated severity</dt>
                          <dd>
                            <Chip
                              value={
                                assessment.severity === "high"
                                  ? "High"
                                  : assessment.severity
                              }
                            />
                          </dd>
                          <dt>Flooded exercise area</dt>
                          <dd>
                            {(assessment.flooded_area_fraction * 100).toFixed(
                              1,
                            )}
                            %
                          </dd>
                          <dt>Blocked road coverage</dt>
                          <dd>
                            {(assessment.blocked_road_fraction * 100).toFixed(
                              1,
                            )}
                            %
                          </dd>
                          <dt>Damaged buildings</dt>
                          <dd>
                            {assessment.damaged_buildings} of{" "}
                            {assessment.reference_buildings}
                          </dd>
                          <dt>Candidate relief site</dt>
                          <dd>
                            {assessment.candidate_sites_for_review.join(", ")}
                          </dd>
                          <dt>Visible distress sign</dt>
                          <dd>
                            {assessment.sos?.detected
                              ? "SOS · pending review"
                              : "No template match"}
                          </dd>
                        </dl>
                      ) : (
                        <p className="pad">Loading assessment…</p>
                      )}
                    </section>
                    <section className="panel">
                      <PanelTitle
                        kicker="Exercise analytics"
                        title="Response summary"
                      />
                      <dl className="report-dl">
                        <dt>Verified requests</dt>
                        <dd>
                          {
                            state.detections.filter(
                              (d) => d.status === "Verified",
                            ).length
                          }
                        </dd>
                        <dt>Completed missions</dt>
                        <dd>
                          {
                            state.missions.filter(
                              (m) => m.status === "Completed",
                            ).length
                          }
                        </dd>
                        <dt>Confirmed deliveries</dt>
                        <dd>
                          {
                            state.missions.filter(
                              (m) => m.return_reason === "Delivered",
                            ).length
                          }
                        </dd>
                        <dt>Pending reviews</dt>
                        <dd>{pending.length}</dd>
                        <dt>Exercise demand estimate</dt>
                        <dd>
                          {state.demand.food_units} food +{" "}
                          {state.demand.water_units} water units
                        </dd>
                      </dl>
                      <p className="pad forecast-note">{state.demand.basis}</p>
                      <div className="pad">
                        {user ? (
                          <a className="secondary" href="/api/report" download>
                            <Download size={15} /> Export exercise report
                          </a>
                        ) : (
                          <button
                            className="secondary"
                            onClick={() => open("login")}
                          >
                            Sign in to export report
                          </button>
                        )}
                      </div>
                    </section>
                  </div>
                  <section className="panel">
                    <PanelTitle title="Mission history" />
                    <div className="history">
                      {state.events.map((e) => (
                        <div key={e.id}>
                          <Clock3 size={15} />
                          <span className="mono tabular-nums">
                            {clock(e.time)}
                          </span>
                          <strong>{e.message}</strong>
                          <small>{e.actor}</small>
                        </div>
                      ))}
                    </div>
                  </section>
                </>
              )}
              <footer className="footer">
                <span>
                  <RadioTower size={13} /> Simulated operations
                </span>
                <span>
                  {shortDate(state.time)} <span>·</span> {clock(state.time)} UTC
                </span>
              </footer>
            </>
          )}
        </div>
      </main>
      {dialog && (
        <Dialogs
          key={dialog.kind + (dialog.id || "")}
          dialog={dialog}
          state={state}
          user={user}
          demo={demo}
          close={() => setDialog(null)}
          refresh={refresh}
          onUser={setUser}
          notify={setMessage}
        />
      )}{" "}
      {message && (
        <div className="toast" role="status">
          <ShieldCheck size={17} />
          {message}
        </div>
      )}
    </div>
  );
}
