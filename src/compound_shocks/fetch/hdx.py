"""Humdata (HDX) downloads through the public CKAN API. No account or key is needed."""

import io
import zipfile
from pathlib import Path

from compound_shocks.fetch.core import FetchError, fetch_file, get, save

HDX_API = "https://data.humdata.org/api/3/action/package_show"
WFP_DATASET = "wfp-food-prices-for-somalia"
WFP_RESOURCE = "Somalia - Food Prices"
PRMN_DATASET = "somalia-internally-displaced-persons-idps"
PRMN_RESOURCE = "SOM_UNHCR-PRMN_Displacement-Dataset.csv"
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


def fetch_wfp_prices(out_dir: Path, **kwargs) -> Path:
    return fetch_hdx(WFP_DATASET, WFP_RESOURCE, out_dir, filename="wfp_prices_somalia.csv", **kwargs)


def fetch_prmn(out_dir: Path, **kwargs) -> Path:
    return fetch_hdx(PRMN_DATASET, PRMN_RESOURCE, out_dir, filename="prmn_displacement.csv", **kwargs)


def fetch_codab(out_dir: Path, **kwargs) -> Path:
    """Download the COD-AB GeoJSON zip and keep only its Admin 2 layer; member names are checked, not assumed."""
    out_dir = Path(out_dir)
    archive_path = fetch_hdx(CODAB_DATASET, CODAB_RESOURCE, out_dir, **kwargs)
    with zipfile.ZipFile(io.BytesIO(archive_path.read_bytes())) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".geojson")]
        admin2 = [name for name in members if "admin2" in name.lower()]
        if len(admin2) != 1:
            raise FetchError(f"HDX {CODAB_DATASET}: expected one admin2 GeoJSON in the zip, found {admin2 or members}")
        data = archive.read(admin2[0])
    archive_path.unlink()
    archive_path.with_name(archive_path.name + ".fetch.json").unlink()
    return save(data, f"HDX {CODAB_DATASET} / {CODAB_RESOURCE} / {admin2[0]}", out_dir, Path(admin2[0]).name)
