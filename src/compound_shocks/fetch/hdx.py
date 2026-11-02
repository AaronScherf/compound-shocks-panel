"""Humdata (HDX) downloads through the public CKAN API. No account or key is needed."""

import io
import zipfile
from pathlib import Path

from compound_shocks.fetch.core import FetchError, fetch_file, get, save

HDX_API = "https://data.humdata.org/api/3/action/package_show"
WFP_DATASET = "wfp-food-prices-for-somalia"
WFP_RESOURCE = "Somalia - Food Prices"
PRMN_DATASET = "somalia-internally-displaced-persons-idps"
# The dataset also has a 3 KB CSV ("som_prmn_map_data.csv") that is only a per-district total as at 2022-11-30.
# The XLSX is the district-level displacement record (departure and arrival, reason), January 2016 to August 2023.
PRMN_RESOURCE = "SOM_UNHCR-PRMN-Displacement-Dataset-August-2023"
CODAB_DATASET = "cod-ab-som"
CODAB_RESOURCE = "som_admin_boundaries.geojson.zip"


def fetch_hdx(
    dataset_id: str,
    resource_name: str,
    out_dir: Path,
    filename: str | None = None,
    expected_sha256: str | None = None,
    refresh: bool = False,
) -> Path:
    package = get(HDX_API, f"HDX {dataset_id}", params={"id": dataset_id}).json()["result"]
    by_name = {resource["name"]: resource for resource in package["resources"]}
    if resource_name not in by_name:
        raise FetchError(f"HDX {dataset_id}: no resource named {resource_name!r}; available: {', '.join(by_name)}")
    return fetch_file(by_name[resource_name]["url"], Path(out_dir), expected_sha256, refresh,
                      source=f"HDX {dataset_id}", name=filename or resource_name)


# Sudan: the WFP file has 22,698 rows (2001 to 2026). IOM DTM publishes stocks of IDPs per locality, not flows;
# the API-derived CSV is one tidy file for admin levels 0 to 2 (the per-round XLSX resources have differing layouts).
SUDAN_WFP = ("wfp-food-prices-for-sudan", "Sudan - Food Prices")
SUDAN_DTM = ("sdn-iom-dtm-from-api", "Sudan IOM DTM data for admin levels 0-2")
SUDAN_CODAB = ("cod-ab-sdn", "sdn_admin_boundaries.geojson.zip")

# instance name -> role -> (provider, dataset, resource, saved filename); the CLI reads this to fetch an instance
SOURCES: dict[str, dict[str, tuple[str, str, str, str]]] = {
    "somalia": {
        "prices": ("WFP", WFP_DATASET, WFP_RESOURCE, "wfp_prices_somalia.csv"),
        "displacement": ("UNHCR/NRC PRMN", PRMN_DATASET, PRMN_RESOURCE, "prmn_displacement.xlsx"),
        "admin_boundaries": ("OCHA COD-AB", CODAB_DATASET, CODAB_RESOURCE, ""),
    },
    "sudan": {
        "prices": ("WFP", *SUDAN_WFP, "wfp_prices_sudan.csv"),
        "displacement": ("IOM DTM", *SUDAN_DTM, "iom_dtm_admin0-2.csv"),
        "admin_boundaries": ("OCHA COD-AB", *SUDAN_CODAB, ""),
    },
}


def fetch_wfp_prices(out_dir: Path, geography: str = "somalia", **kwargs) -> Path:
    _, dataset, resource, name = SOURCES[geography]["prices"]
    return fetch_hdx(dataset, resource, out_dir, filename=name, **kwargs)


def fetch_displacement(out_dir: Path, geography: str, **kwargs) -> Path:
    _, dataset, resource, name = SOURCES[geography]["displacement"]
    return fetch_hdx(dataset, resource, out_dir, filename=name, **kwargs)


def fetch_prmn(out_dir: Path, **kwargs) -> Path:
    return fetch_displacement(out_dir, "somalia", **kwargs)


def fetch_dtm(out_dir: Path, **kwargs) -> Path:
    return fetch_displacement(out_dir, "sudan", **kwargs)


def fetch_codab(out_dir: Path, geography: str = "somalia", **kwargs) -> Path:
    """Download the COD-AB GeoJSON zip and keep only its Admin 2 layer; member names are checked, not assumed."""
    out_dir = Path(out_dir)
    _, dataset, resource, _ = SOURCES[geography]["admin_boundaries"]
    archive_path = fetch_hdx(dataset, resource, out_dir, **kwargs)
    with zipfile.ZipFile(io.BytesIO(archive_path.read_bytes())) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".geojson")]
        admin2 = [name for name in members if "admin2" in name.lower()]
        if len(admin2) > 1:  # OCHA ships a standard layer and an edge-matched (_em) copy; use the standard one
            admin2 = [name for name in admin2 if not name.lower().endswith("_em.geojson")]
        if len(admin2) != 1:
            raise FetchError(f"HDX {dataset}: expected one admin2 GeoJSON in the zip, found {admin2 or members}")
        data = archive.read(admin2[0])
    archive_path.unlink()
    archive_path.with_name(archive_path.name + ".fetch.json").unlink()
    return save(data, f"HDX {dataset} / {resource} / {admin2[0]}", out_dir, Path(admin2[0]).name)
