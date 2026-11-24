"use client";
import { useState } from "react";
import { CloudRain } from "lucide-react";
import { State, User, request } from "./types";
export default function ExerciseConditions({
  state,
  user,
  refresh,
}: {
  state: State;
  user: User | null;
  refresh: () => Promise<void>;
}) {
  const [selected, setSelected] = useState(state.weather.profile),
    [status, setStatus] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="panel conditions">
      <div className="panel-title">
        <div className="section-title">
          <CloudRain size={18} />
          <h2>Exercise weather</h2>
        </div>
        <span className="chip neutral">Scenario preset</span>
      </div>
      <div className="conditions-body">
        <span>
          <strong>{state.weather.profile}</strong> · {state.weather.wind_kph}{" "}
          km/h wind · {state.weather.gust_kph} km/h gusts ·{" "}
          {state.weather.rain_mm_h} mm/h rain
        </span>
        <span>
          Flight risk · {state.weather.risk}{" "}
          {state.weather.hold ? " / Dispatch held" : ""}
        </span>
        {user?.role === "coordinator" && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await request("weather/" + selected, {});
                await refresh();
                setStatus("Exercise weather updated");
              } catch (err) {
                setStatus((err as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <select
              aria-label="Simulated weather profile"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {["Calm", "Rain", "Storm"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <button
              className="secondary"
              disabled={busy || selected === state.weather.profile}
            >
              Apply profile
            </button>
          </form>
        )}
        {status && <small role="status">{status}</small>}
      </div>
    </section>
  );
}
