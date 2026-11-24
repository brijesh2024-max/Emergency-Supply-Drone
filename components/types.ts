export type Point = [number, number];
export type Drone = {
  id: string;
  model: string;
  capacity: number;
  battery: number;
  lat: number;
  lon: number;
  altitude: number;
  link: number;
  status: string;
};
export type Mission = {
  id: string;
  name: string;
  kind: string;
  drone: string;
  zone: string;
  route: Point[];
  progress: number;
  status: string;
  qty: number;
  item: string | null;
  candidate: string | null;
  created: string;
  created_by: string;
  approved_by: string | null;
  reserved: number;
  return_reason: string | null;
};
export type Detection = {
  id: string;
  sector: string;
  lat: number;
  lon: number;
  source: string;
  confidence: number | null;
  status: string;
  priority: string;
  observed: string;
  reviewed_by: string | null;
  hint: { priority: string; reason: string };
  evidence: {
    frame_index?: number;
    time_s?: number;
    bbox?: number[];
    name?: string;
  };
};
export type Stock = {
  id: string;
  name: string;
  mass: number;
  available: number;
};
export type RescueEvent = {
  id: string;
  time: string;
  kind: string;
  message: string;
  actor: string;
};
export type Alert = {
  id: string;
  message: string;
  detail: string;
  severity: string;
  acknowledged_by: string | null;
};
export type State = {
  mode: string;
  demo: boolean;
  plans: Record<string, Point[]>;
  weather: {
    profile: string;
    wind_kph: number;
    gust_kph: number;
    rain_mm_h: number;
    risk: string;
    hold: boolean;
  };
  demand: {
    open_requests: number;
    food_units: number;
    water_units: number;
    basis: string;
  };
  time: string;
  drones: Drone[];
  missions: Mission[];
  detections: Detection[];
  inventory: Stock[];
  events: RescueEvent[];
  alerts: Alert[];
  zones: Record<string, Point>;
  base: Point;
  bounds: [number, number, number, number];
  blocks: { name: string; bounds: [number, number, number, number] }[];
};
export type User = { username: string; role: string };
export type View =
  | "Overview"
  | "Missions"
  | "Detections"
  | "Supplies"
  | "Fleet"
  | "Reports";
export async function request<T = any>(
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(
    "/api/" + path,
    body === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.[0]?.msg || "Request failed",
    );
  return data;
}
export const clock = (date: string) =>
  new Date(date).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour12: false,
  });
export const shortDate = (date: string) =>
  new Date(date).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
export function statusClass(s: string) {
  return [
    "Verified",
    "Ready",
    "Completed",
    "Connected",
    "Surveying",
    "Active",
    "Delivering",
  ].includes(s)
    ? "green"
    : ["High", "Grounded", "Landed", "Disconnected"].includes(s)
      ? "red"
      : [
            "Pending",
            "Proposed",
            "Awaiting receipt",
            "Returning",
            "Medium",
          ].includes(s)
        ? "amber"
        : "neutral";
}
