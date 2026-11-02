"""Analysis-unit decisions that change which polygons the panel is built on, kept out of the adapters."""

import geopandas as gpd
import pandas as pd
import shapely

REQUIRED = ("id", "name", "members")


def merge_units(boundaries: gpd.GeoDataFrame, merges: list[dict]) -> tuple[gpd.GeoDataFrame, list[str]]:
    """Dissolve each merge's member districts into one unit; return the new boundaries and a note per merge.

    Each merge is {"id", "name", "members": [admin2_id, ...]} and comes from the instance config, so the decision
    is recorded in the run manifest. Every member must exist and belong to one merge only.
    """
    if not merges:
        return boundaries, []
    known = set(boundaries["admin2_id"])
    claimed: dict[str, str] = {}
    for merge in merges:
        missing = [key for key in REQUIRED if key not in merge]
        if missing:
            raise ValueError(f"merge_districts entry {merge} is missing: {', '.join(missing)}")
        unknown = [member for member in merge["members"] if member not in known]
        if unknown:
            raise ValueError(f"merge_districts {merge['id']}: unknown member(s) {', '.join(unknown)}")
        for member in merge["members"]:
            if member in claimed:
                raise ValueError(f"district {member} is a member of both {claimed[member]} and {merge['id']}")
            claimed[member] = merge["id"]
    survivors = known - set(claimed)
    for merge in merges:
        if merge["id"] in survivors:
            raise ValueError(f"merged id {merge['id']} collides with an existing district {merge['id']}")
    rows, notes = [], []
    for merge in merges:
        members = boundaries[boundaries["admin2_id"].isin(merge["members"])]
        rows.append({"admin2_id": merge["id"], "name": merge["name"], "geometry": shapely.union_all(members.geometry.to_numpy())})
        notes.append(f"merged {len(members)} districts ({', '.join(merge['members'])}) into {merge['id']} ({merge['name']})")
    kept = boundaries[~boundaries["admin2_id"].isin(claimed)][["admin2_id", "name", "geometry"]]
    combined = pd.concat([kept, gpd.GeoDataFrame(rows, geometry="geometry", crs=boundaries.crs)], ignore_index=True)
    result = gpd.GeoDataFrame(combined.sort_values("admin2_id").reset_index(drop=True), geometry="geometry", crs=boundaries.crs)
    result.attrs.update(boundaries.attrs)
    return result, notes
