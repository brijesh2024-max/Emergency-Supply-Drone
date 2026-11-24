"""Assess an explicitly synthetic, co-registered overhead exercise raster."""

from math import hypot


def assess_exercise_raster(width=96, height=56):
    """Compare synthetic flood/debris/damage masks with known exercise assets."""
    flooded_cells = road_cells = unusable_road_cells = 0
    buildings = [(25, 15, 33, 23), (45, 26, 56, 33), (68, 37, 78, 47)]
    damaged = set()
    clear_sites = {"west assembly ground": True, "east field": True}
    for y in range(height):
        for x in range(width):
            # All layers use the same artificial scene coordinates.
            u, v = x * 96 / width, y * 56 / height
            flooded = abs(u - (29 + 0.47 * v)) < 8
            road = abs(v - (10 + u * 0.40)) < 1.5
            debris = 63 <= u < 72 and 32 <= v < 40
            damage = 47 <= u < 53 and 27 <= v < 31
            flooded_cells += int(flooded)
            road_cells += int(road)
            unusable_road_cells += int(road and (flooded or debris))
            for i, (left, top, right, bottom) in enumerate(buildings):
                if left <= u < right and top <= v < bottom and damage:
                    damaged.add(i)
            for site, sx, sy in (("west assembly ground", 16, 40), ("east field", 46, 33)):
                if hypot(u - sx, v - sy) <= 4 and (flooded or debris or damage):
                    clear_sites[site] = False
    water_fraction = round(flooded_cells / (width * height), 3)
    road_fraction = round(unusable_road_cells / max(1, road_cells), 3)
    affected_fraction = len(damaged) / len(buildings)
    score = max(water_fraction, road_fraction, affected_fraction)
    return {
        "provenance": "synthetic_scenario_masks",
        "scope": "exercise sector, independent of camera framing",
        "flooded_area_fraction": water_fraction,
        "blocked_road_fraction": road_fraction,
        "damaged_buildings": len(damaged),
        "reference_buildings": len(buildings),
        "severity": "high" if score >= 0.30 else "moderate" if score >= 0.10 else "low",
        "candidate_sites_for_review": [site for site, clear in clear_sites.items() if clear],
        "review_status": "pending",
    }
