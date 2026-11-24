"use client";
import { useEffect, useRef, useState } from "react";
import {
  Crosshair,
  Layers3,
  Plus,
  Minus,
  Maximize2,
  Minimize2,
  MapPin,
  ChevronDown,
} from "lucide-react";
import type { State } from "./types";
declare global {
  interface Window {
    L: any;
  }
}
let leaflet: Promise<any> | undefined;
function loadLeaflet() {
  if (!leaflet)
    leaflet = new Promise((resolve, reject) => {
      if (window.L) {
        resolve(window.L);
        return;
      }
      const tag = document.createElement("script");
      tag.src = "/vendor/leaflet/leaflet.js";
      tag.onload = () => resolve(window.L);
      tag.onerror = () => {
        leaflet = undefined;
        reject(new Error("Map library unavailable"));
      };
      document.head.appendChild(tag);
    });
  return leaflet;
}
const droneGlyph =
  '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7"><path d="m6 6 12 12M6 18 18 6"/><circle cx="6" cy="6" r="3.3"/><circle cx="18" cy="6" r="3.3"/><circle cx="6" cy="18" r="3.3"/><circle cx="18" cy="18" r="3.3"/><rect x="9" y="9" width="6" height="6" rx="2"/></svg>';
export default function RescueMap({
  state,
  onPick,
}: {
  state: State;
  onPick: (type: string, key: string) => void;
}) {
  const host = useRef<HTMLDivElement>(null),
    map = useRef<any>(null),
    overlays = useRef<any>(null),
    pick = useRef(onPick);
  pick.current = onPick;
  const [ready, setReady] = useState(false),
    [full, setFull] = useState(false),
    [menu, setMenu] = useState(false),
    [flags, setFlags] = useState({ routes: true, areas: true, signals: true }),
    [failed, setFailed] = useState(false);
  const reset = () => {
    if (map.current && host.current) {
      map.current.fitBounds(
        [
          [34.06, 74.812],
          [34.091, 74.868],
        ],
        { animate: false, padding: [2, 2] },
      );
    }
  };
  useEffect(() => {
    let alive = true;
    let observer: ResizeObserver | undefined;
    loadLeaflet()
      .then((L) => {
        if (!alive || !host.current) return;
        const m = L.map(host.current, {
          zoomControl: false,
          attributionControl: false,
          zoomSnap: 0.05,
          zoomDelta: 0.5,
          scrollWheelZoom: false,
          minZoom: 11,
          maxZoom: 17,
          maxBounds: [
            [34.047, 74.79],
            [34.103, 74.89],
          ],
        });
        map.current = m;
        L.imageOverlay(
          "/scene/map.png",
          [
            [34.055, 74.805],
            [34.095, 74.875],
          ],
          { className: "map-raster" },
        ).addTo(m);
        overlays.current = L.layerGroup().addTo(m);
        reset();
        observer = new ResizeObserver(() => {
          m.invalidateSize();
          reset();
        });
        observer.observe(host.current);
        setReady(true);
      })
      .catch(() => setFailed(true));
    return () => {
      alive = false;
      observer?.disconnect();
      map.current?.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (!full) return;
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFull(false);
    };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [full]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const L = window.L,
      g = overlays.current;
    g.clearLayers();
    const label = (p: any, name: string) =>
      L.marker(p, {
        interactive: false,
        icon: L.divIcon({
          className: "map-label",
          html: name,
          iconSize: [130, 16],
          iconAnchor: [65, 8],
        }),
      }).addTo(g);
    label([34.089, 74.826], "NORTH BANK");
    label([34.064, 74.853], "EAST EMBANKMENT");
    label([34.06, 74.826], "SOUTH APPROACH");
    if (flags.areas)
      state.blocks.forEach((z) => {
        const [s, w, n, e] = z.bounds;
        L.rectangle(
          [
            [s, w],
            [n, e],
          ],
          {
            color: "#f37568",
            weight: 1.2,
            dashArray: "5 4",
            fillColor: "#e86a61",
            fillOpacity: 0.2,
          },
        )
          .bindTooltip(z.name)
          .addTo(g);
      });
    if (flags.routes)
      state.missions
        .filter((m) =>
          ["Active", "Returning", "Proposed", "Awaiting receipt"].includes(
            m.status,
          ),
        )
        .forEach((m) =>
          L.polyline(m.route, {
            color: m.status === "Proposed" ? "#96a5ae" : "#b8eb84",
            weight: 2.3,
            dashArray: "6 6",
            opacity: 0.95,
          })
            .bindTooltip(m.id)
            .addTo(g),
        );
    Object.entries(state.zones).forEach(([name, p]) =>
      L.circleMarker(p, {
        radius: 4,
        color: "#d5f3c4",
        fillColor: "#172c20",
        weight: 2,
        fillOpacity: 1,
      })
        .bindTooltip(name)
        .addTo(g),
    );
    L.marker(state.base, {
      icon: L.divIcon({
        className: "base-pin",
        html: "H",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      }),
    })
      .bindTooltip("Exercise base")
      .addTo(g);
    if (flags.signals)
      state.detections
        .filter((d) => d.status !== "Dismissed")
        .forEach((d) => {
          L.circleMarker([d.lat, d.lon], {
            radius: 9,
            color: d.status === "Pending" ? "#ffc17a" : "#a8d9fe",
            weight: 1.5,
            fillOpacity: 0.35,
          })
            .bindTooltip(d.id)
            .on("click", () => pick.current("detection", d.id))
            .addTo(g);
          L.circleMarker([d.lat, d.lon], {
            radius: 2.7,
            stroke: false,
            fillColor: "#fff0cc",
            fillOpacity: 1,
            interactive: false,
          }).addTo(g);
        });
    state.drones
      .filter((d) => d.status !== "Ready")
      .forEach((d) => {
        const marker = L.marker([d.lat, d.lon], {
          title: d.id,
          icon: L.divIcon({
            className: "aircraft-pin",
            html: droneGlyph,
            iconSize: [33, 33],
            iconAnchor: [16, 16],
          }),
        }).addTo(g);
        marker.bindTooltip(d.id, {
          permanent: true,
          direction: "right",
          offset: [11, 0],
          className: "drone-label",
        });
        marker.on("click", () => pick.current("drone", d.id));
      });
  }, [state, ready, flags]);
  return (
    <section className={"panel map-panel " + (full ? "map-expanded" : "")}>
      <div className="panel-title">
        <div>
          <span className="kicker">Geospatial overview</span>
          <h2>Operations map</h2>
        </div>
        <div className="actions">
          <div className="layer-wrap">
            <button
              className="small-btn"
              onClick={() => setMenu(!menu)}
              aria-expanded={menu}
            >
              <Layers3 size={15} /> Layers <ChevronDown size={13} />
            </button>
            {menu && (
              <div className="layers">
                {(["routes", "areas", "signals"] as const).map((k, i) => (
                  <label key={k}>
                    <input
                      type="checkbox"
                      checked={flags[k]}
                      onChange={() => setFlags({ ...flags, [k]: !flags[k] })}
                    />
                    {
                      [
                        "Mission routes",
                        "Restricted areas",
                        "Survivor signals",
                      ][i]
                    }
                  </label>
                ))}
              </div>
            )}
          </div>
          <button
            className="icon-btn"
            aria-label={full ? "Close expanded map" : "Expand map"}
            onClick={() => setFull(!full)}
          >
            {full ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </div>
      <div className="map-stage">
        <div ref={host} className="leaflet-host" />
        {failed && <p>Map could not load. Reload the dashboard.</p>}
        <div className="map-location">
          <MapPin size={13} /> Srinagar sector
        </div>
        <div className="north">
          <span>▴</span>N
        </div>
        <div className="map-controls">
          <button aria-label="Zoom in" onClick={() => map.current?.zoomIn()}>
            <Plus size={17} />
          </button>
          <button aria-label="Zoom out" onClick={() => map.current?.zoomOut()}>
            <Minus size={17} />
          </button>
          <button aria-label="Fit exercise area" onClick={reset}>
            <Crosshair size={16} />
          </button>
        </div>
        <span className="map-credit">Illustrative geography · WGS 84</span>
      </div>
      <div className="map-legend">
        <span>
          <i className="legend-drone" />
          Aircraft
        </span>
        <span>
          <i className="legend-signal" />
          Detection
        </span>
        <span>
          <i className="legend-route" />
          Flight route
        </span>
        <span>
          <i className="legend-zone" />
          Restricted
        </span>
      </div>
    </section>
  );
}
