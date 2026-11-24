CREATE EXTENSION IF NOT EXISTS postgis;
CREATE OR REPLACE VIEW exercise_drone_locations AS
 SELECT id, status, ST_SetSRID(ST_MakePoint(lon,lat),4326) AS geom FROM drones;
CREATE OR REPLACE VIEW exercise_observations AS
 SELECT id, status, source, ST_SetSRID(ST_MakePoint(lon,lat),4326) AS geom FROM detections;
CREATE INDEX IF NOT EXISTS observations_geom ON detections USING GIST (ST_SetSRID(ST_MakePoint(lon,lat),4326));
