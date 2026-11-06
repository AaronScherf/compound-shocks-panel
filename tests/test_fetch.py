import gzip
import hashlib
import io
import json
import logging
import os
import zipfile

import pytest
import requests

from compound_shocks.cli import main
from compound_shocks.fetch import (
    FetchError,
    ProviderRevisedData,
    fetch_acled,
    fetch_chirps,
    fetch_codab,
    fetch_file,
    fetch_hdx,
    fetch_prmn,
    fetch_wfp_prices,
)

SECRET = "hunter2-very-secret"


class FakeResponse:
    def __init__(self, content=b"", status=200, payload=None):
        self.content = content
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeWeb:
    """Maps URL substrings to responses; any unmapped URL is a 404. Records every call."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def _answer(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        for fragment, response in self.routes.items():
            if fragment in url:
                return response(kwargs) if callable(response) else response
        return FakeResponse(status=404)

    def get(self, url, **kwargs):
        return self._answer("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._answer("POST", url, kwargs)


@pytest.fixture
def web(monkeypatch):
    def install(routes):
        fake = FakeWeb(routes)
        monkeypatch.setattr(requests, "get", fake.get)
        monkeypatch.setattr(requests, "post", fake.post)
        return fake

    return install


def hdx_package(*resources):
    return FakeResponse(payload={"success": True, "result": {"resources": [
        {"name": name, "format": fmt, "url": f"https://files.example/{name}"} for name, fmt in resources]}})


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_fetch_file_writes_file_and_a_record_with_hash_and_access_date(tmp_path, web):
    web({"files.example/a.csv": FakeResponse(b"x,y\n1,2\n")})
    path = fetch_file("https://files.example/a.csv", tmp_path, source="Example")
    assert path.read_bytes() == b"x,y\n1,2\n"
    record = json.loads((tmp_path / "a.csv.fetch.json").read_text(encoding="utf-8"))
    assert record["sha256"] == sha(b"x,y\n1,2\n") and record["url"] == "https://files.example/a.csv"
    assert len(record["accessed"]) == 10


def test_hash_mismatch_raises_provider_revised_data_unless_refresh(tmp_path, web):
    web({"files.example/a.csv": FakeResponse(b"new")})
    with pytest.raises(ProviderRevisedData) as caught:
        fetch_file("https://files.example/a.csv", tmp_path, expected_sha256=sha(b"old"))
    assert sha(b"old") in str(caught.value) and sha(b"new") in str(caught.value)
    assert not (tmp_path / "a.csv").exists()
    assert fetch_file("https://files.example/a.csv", tmp_path, expected_sha256=sha(b"old"), refresh=True).read_bytes() == b"new"


def test_matching_hash_passes(tmp_path, web):
    web({"files.example/a.csv": FakeResponse(b"same")})
    assert fetch_file("https://files.example/a.csv", tmp_path, expected_sha256=sha(b"same")).exists()


def test_404_names_the_source_and_url(tmp_path, web):
    web({})
    with pytest.raises(FetchError, match=r"Example.*https://files.example/gone.csv.*404"):
        fetch_file("https://files.example/gone.csv", tmp_path, source="Example")


def test_fetch_hdx_downloads_the_named_resource(tmp_path, web):
    fake = web({"package_show": hdx_package(("Other", "CSV"), ("Somalia - Food Prices", "CSV")),
                "files.example/Somalia - Food Prices": FakeResponse(b"date\n")})
    path = fetch_hdx("wfp-food-prices-for-somalia", "Somalia - Food Prices", tmp_path, filename="prices.csv")
    assert path == tmp_path / "prices.csv" and path.read_bytes() == b"date\n"
    assert fake.calls[0][2]["params"] == {"id": "wfp-food-prices-for-somalia"}


def test_fetch_hdx_unknown_resource_lists_available_names(tmp_path, web):
    web({"package_show": hdx_package(("Alpha", "CSV"), ("Beta", "CSV"))})
    with pytest.raises(FetchError, match="Alpha.*Beta"):
        fetch_hdx("some-dataset", "Missing", tmp_path)


def test_fetch_writes_into_role_directory(tmp_path, web):
    web({"package_show": hdx_package(("Somalia - Food Prices", "CSV")),
         "files.example": FakeResponse(b"date\n")})
    path = fetch_wfp_prices(tmp_path / "prices")
    assert path.parent == tmp_path / "prices" and path.suffix == ".csv"


def test_fetch_prmn_uses_the_pinned_dataset(tmp_path, web):
    fake = web({"package_show": hdx_package(("SOM_UNHCR-PRMN-Displacement-Dataset-August-2023", "XLSX")),
                "files.example": FakeResponse(b"month\n")})
    fetch_prmn(tmp_path)
    assert fake.calls[0][2]["params"] == {"id": "somalia-internally-displaced-persons-idps"}


def zipped(**members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def test_fetch_codab_extracts_only_admin2_geojson(tmp_path, web):
    archive = zipped(**{"som_admin0.geojson": "{}", "som_admin2.geojson": '{"type":"FeatureCollection","features":[]}'})
    web({"package_show": hdx_package(("som_admin_boundaries.geojson.zip", "GeoJSON")), "files.example": FakeResponse(archive)})
    path = fetch_codab(tmp_path)
    assert [p.name for p in tmp_path.glob("*.geojson")] == ["som_admin2.geojson"] and path.name == "som_admin2.geojson"


def test_fetch_codab_prefers_the_standard_layer_over_the_edge_matched_copy(tmp_path, web):
    archive = zipped(**{"som_admin2_em.geojson": '{"em": true}', "som_admin2.geojson": '{"em": false}'})
    web({"package_show": hdx_package(("som_admin_boundaries.geojson.zip", "GeoJSON")), "files.example": FakeResponse(archive)})
    path = fetch_codab(tmp_path)
    assert path.name == "som_admin2.geojson" and '"em": false' in path.read_text(encoding="utf-8")


def test_fetch_codab_with_two_unrelated_admin2_files_lists_them(tmp_path, web):
    archive = zipped(**{"a_admin2.geojson": "{}", "b_admin2.geojson": "{}"})
    web({"package_show": hdx_package(("som_admin_boundaries.geojson.zip", "GeoJSON")), "files.example": FakeResponse(archive)})
    with pytest.raises(FetchError, match="a_admin2.geojson.*b_admin2.geojson"):
        fetch_codab(tmp_path)


def test_fetch_codab_without_admin2_member_lists_members(tmp_path, web):
    web({"package_show": hdx_package(("som_admin_boundaries.geojson.zip", "GeoJSON")),
         "files.example": FakeResponse(zipped(**{"som_admin0.geojson": "{}"}))})
    with pytest.raises(FetchError, match="som_admin0.geojson"):
        fetch_codab(tmp_path)


def test_fetch_chirps_builds_v2_urls_gunzips_and_names_months(tmp_path, web):
    tif = b"II*\x00fake-tif"
    fake = web({"chirps-v2.0.2021.01.tif.gz": FakeResponse(gzip.compress(tif)),
                "chirps-v2.0.2021.02.tif.gz": FakeResponse(gzip.compress(tif + b"2"))})
    paths = fetch_chirps(["2021-01", "2021-02"], tmp_path)
    assert [p.name for p in paths] == ["chirps-v2.0.2021.01.tif", "chirps-v2.0.2021.02.tif"]
    assert paths[0].read_bytes() == tif
    assert fake.calls[0][1] == "https://data.chc.ucsb.edu/products/CHIRPS/v2.0/africa_monthly/tifs/chirps-v2.0.2021.01.tif.gz"
    assert not list(tmp_path.glob("*.gz"))


def test_fetch_chirps_404_names_source_and_url(tmp_path, web):
    web({})
    with pytest.raises(FetchError, match=r"CHIRPS v2.0.*chirps-v2.0.2021.01.tif.gz.*404"):
        fetch_chirps(["2021-01"], tmp_path)


def test_acled_missing_credentials_explains_how_to_register(tmp_path, monkeypatch):
    monkeypatch.delenv("ACLED_EMAIL", raising=False)
    monkeypatch.delenv("ACLED_PASSWORD", raising=False)
    with pytest.raises(FetchError) as caught:
        fetch_acled({"country": "Somalia"}, tmp_path, root=tmp_path)
    assert str(caught.value) == (
        'ACLED: missing ACLED_EMAIL. Put it in .env at the project root; '
        'see README.md "Accounts and keys". Register at https://acleddata.com, '
        'or download the file by hand as described in Getting the data.'
    )


def test_acled_reads_temp_project_env_and_names_missing_password(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    (tmp_path / ".env").write_text("ACLED_EMAIL='test@example.org'\n", encoding="utf-8")
    monkeypatch.delenv("ACLED_EMAIL", raising=False)
    monkeypatch.delenv("ACLED_PASSWORD", raising=False)
    with pytest.raises(FetchError) as caught:
        fetch_acled({"country": "Somalia"}, tmp_path, root=tmp_path)
    assert str(caught.value) == (
        'ACLED: missing ACLED_PASSWORD. Put it in .env at the project root; '
        'see README.md "Accounts and keys". Register at https://acleddata.com, '
        'or download the file by hand as described in Getting the data.'
    )
    assert "test@example.org" not in str(caught.value)


def acled_routes():
    def token(kwargs):
        assert kwargs["data"]["password"] == SECRET
        return FakeResponse(payload={"access_token": "tok"})

    def data(kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        return FakeResponse(payload={"status": 200, "data": [{"event_id_cnty": "A1", "fatalities": "0"}]})

    return {"oauth/token": token, "api/acled/read": data}


def test_acled_fetch_writes_csv_into_role_directory(tmp_path, monkeypatch, web):
    monkeypatch.setenv("ACLED_EMAIL", "me@example.org")
    monkeypatch.setenv("ACLED_PASSWORD", SECRET)
    web(acled_routes())
    path = fetch_acled({"country": "Somalia"}, tmp_path)
    assert path.parent == tmp_path and "event_id_cnty" in path.read_text(encoding="utf-8")


def test_acled_fetch_uses_temp_project_env(tmp_path, monkeypatch, web, capsys, caplog):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv("ACLED_EMAIL", raising=False)
    monkeypatch.delenv("ACLED_PASSWORD", raising=False)
    (tmp_path / ".env").write_text(
        f"ACLED_EMAIL='me@example.org'\nACLED_PASSWORD=\"{SECRET}\"\n", encoding="utf-8"
    )
    web(acled_routes())
    with caplog.at_level(logging.DEBUG):
        fetch_acled({"country": "Somalia"}, tmp_path / "raw", root=tmp_path)
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err + caplog.text
    assert "me@example.org" not in output.out + output.err + caplog.text


def test_credentials_never_appear_in_logs_or_exceptions(tmp_path, monkeypatch, web, caplog):
    monkeypatch.setenv("ACLED_EMAIL", "me@example.org")
    monkeypatch.setenv("ACLED_PASSWORD", SECRET)
    web({"oauth/token": FakeResponse(status=401)})
    with caplog.at_level(logging.DEBUG), pytest.raises(FetchError) as caught:
        fetch_acled({"country": "Somalia"}, tmp_path)
    assert SECRET not in str(caught.value) and SECRET not in caplog.text
    assert "me@example.org" not in str(caught.value) and "me@example.org" not in caplog.text


def test_acled_data_non_200_contains_no_response_body(tmp_path, monkeypatch, web):
    monkeypatch.setenv("ACLED_EMAIL", "me@example.org")
    monkeypatch.setenv("ACLED_PASSWORD", SECRET)
    fake = web(acled_routes() | {"api/acled/read": FakeResponse(b"PRIVATE_SYNTHETIC_ROW", status=503)})
    with pytest.raises(FetchError) as caught:
        fetch_acled({"country": "Somalia"}, tmp_path)
    assert "503" in str(caught.value) and "PRIVATE_SYNTHETIC_ROW" not in str(caught.value)
    assert len(fake.calls) == 2


def test_cli_acled_save_parameters_and_no_row_output(root, monkeypatch, web, capsys):
    monkeypatch.setenv("ACLED_EMAIL", "me@example.org")
    monkeypatch.setenv("ACLED_PASSWORD", SECRET)
    marker = "PRIVATE_SYNTHETIC_ROW"
    config = root / "instances/somalia/config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("Synthland", "Somalia")
                      .replace("2021-03-31", "2025-10-31"), encoding="utf-8")
    folder = root / "instances/somalia/data/raw/conflict_events"
    for path in folder.glob("*.csv"):
        path.unlink()
    routes = acled_routes()

    def data(kwargs):
        assert kwargs["params"] == {"country": "Somalia", "event_date": "2021-01-01|2025-10-31",
                                    "event_date_where": "BETWEEN", "_format": "json", "limit": 0}
        return FakeResponse(payload={"data": [{"event_id_cnty": "A1", "notes": marker}]})

    routes["api/acled/read"] = data
    fake = web(routes)
    assert main(["fetch", "--instance", "somalia", "--root", str(root), "--role", "conflict_events"]) == 0
    output = capsys.readouterr()
    assert marker not in output.out + output.err
    assert "1 rows" in output.out and "sha256" in output.out
    assert len(list(folder.glob("*.csv"))) == 1
    assert len(list(folder.glob("*.fetch.json"))) == 1
    assert main(["fetch", "--instance", "somalia", "--root", str(root), "--role", "conflict_events"]) == 0
    assert len(fake.calls) == 2
    assert "move or remove" in capsys.readouterr().out


def test_cli_fetch_dry_run_lists_urls_and_downloads_nothing(root, web, capsys):
    fake = web({})
    assert main(["fetch", "--instance", "somalia", "--root", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "chirps-v2.0.2021.01.tif.gz" in out and "wfp-food-prices-for-somalia" in out
    assert "ACLED API, Synthland, 2021-01-01 to 2021-03-31" in out
    assert fake.calls == []


def test_cli_fetch_role_filter_downloads_only_that_role(root, web, capsys):
    fake = web({"package_show": hdx_package(("Somalia - Food Prices", "CSV")), "files.example": FakeResponse(b"date")})
    assert main(["fetch", "--instance", "somalia", "--root", str(root), "--role", "prices"]) == 0
    assert "chirps" not in capsys.readouterr().out
    assert all("chirps" not in call[1] for call in fake.calls)


def test_cli_fetch_unknown_role_stops_with_exit_1(root, web, capsys):
    web({})
    assert main(["fetch", "--instance", "somalia", "--root", str(root), "--role", "nonsense"]) == 1
    assert "nonsense" in capsys.readouterr().out


def test_cli_fetch_unpinned_provider_stops_with_exit_1(root, web, capsys):
    config = root / "instances/somalia/config.yaml"
    config.write_text(config.read_text().replace("provider: WFP", "provider: FSNAU"), encoding="utf-8")
    web({})
    assert main(["fetch", "--instance", "somalia", "--root", str(root)]) == 1
    assert "FSNAU" in capsys.readouterr().out


def test_cli_fetch_sudan_lists_the_sudan_datasets(root, capsys):
    from conftest import make_instance

    make_instance(root, "sudan")
    config = root / "instances/sudan/config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("UNHCR/NRC PRMN", "IOM DTM"), encoding="utf-8")
    assert main(["fetch", "--instance", "sudan", "--root", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "wfp-food-prices-for-sudan" in out and "sdn-iom-dtm-from-api" in out and "cod-ab-sdn" in out
    assert "ACLED API, Synthland" in out
    assert "somalia" not in out.lower()
