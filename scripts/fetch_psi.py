"""
Step 1: Download NASA PSI combustion metadata + experimental tables.

Run from the project root:   python scripts/fetch_psi.py
Output:
  data/investigations.json      metadata for every combustion investigation
  data/tables/<PSI-ID>__<name>.csv   every experimental table (raw, as NASA publishes it)

Raw images/videos are NOT downloaded (they are GBs to TBs).
"""
import json
import re
import time
from pathlib import Path

import requests

BASE = "https://psi.nasa.gov/geode-py/ws"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TABLES = DATA / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

SEARCH_TERMS = ["combustion", "flame", "fire", "flammability", "droplet",
                "soot", "smoke", "ACME", "burning"]

session = requests.Session()
session.headers["User-Agent"] = "FlameWatch-SpaceApps2026"


def get(url, **kw):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=60, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"   retry {attempt + 1} for {url[:90]}... ({e})")
            time.sleep(2)
    raise RuntimeError(f"failed: {url}")


def find_combustion_ids():
    ids = {}
    for term in SEARCH_TERMS:
        r = get(f"{BASE}/repo/search", params={
            "term": term, "source": "psi", "type": "investigation", "size": 200})
        for hit in r.json()["hits"]["hits"]:
            s = hit["_source"]
            if "combustion" in json.dumps(s.get("Research Area", "")).lower():
                ids[s["Accession"]] = s
    return ids


def table_names(meta_json):
    text = json.dumps(meta_json)
    return sorted(set(re.findall(r"PSI-\d+_Experimental table_[^\"/\\]*?\.csv", text)))


def download_table(psi_id, fname):
    r = get(f"{BASE}/studies/{psi_id}/download",
            params={"file": fname, "version": 1, "redirect": "false"})
    signed_url = r.text.strip().strip('"')
    csv = get(signed_url).content
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", fname.split("_Experimental table_")[-1])
    out = TABLES / f"{psi_id}__{safe}"
    out.write_bytes(csv)
    return out


def main():
    print("Searching PSI for combustion investigations...")
    found = find_combustion_ids()
    print(f"Found {len(found)} investigations\n")

    investigations = []
    for psi_id in sorted(found, key=lambda x: int(x.split("-")[1])):
        summary = found[psi_id]
        print(f"{psi_id}  {summary.get('Acronym') or summary.get('Title', '')[:60]}")
        full = get(f"{BASE}/repo/investigations/{psi_id}").json()

        tables = []
        for fname in table_names(full):
            try:
                path = download_table(psi_id, fname)
                rows = max(0, len(path.read_text(errors="replace").splitlines()) - 1)
                tables.append({"file": path.name, "rows": rows})
                print(f"   table: {path.name} ({rows} rows)")
            except Exception as e:
                print(f"   table FAILED: {fname} ({e})")

        investigations.append({
            "id": psi_id,
            "acronym": full.get("investigationAcronym") or summary.get("Acronym") or "",
            "title": full.get("title") or summary.get("Title", ""),
            "doi": full.get("doi", ""),
            "project_type": full.get("projectType") or summary.get("Project Type", ""),
            "sub_area": full.get("subResearchArea", ""),
            "platform": summary.get("Flight Platform", ""),
            "hardware": summary.get("Experiment Hardware", {}),
            "objectives": full.get("objective", ""),
            "approach": full.get("approach", ""),
            "hypothesis": full.get("hypothesis", ""),
            "impacts": full.get("researchImpacts", ""),
            "keywords": summary.get("Keywords", ""),
            "related": summary.get("Related Investigations", ""),
            "start": full.get("investigationStartDate", ""),
            "end": full.get("investigationEndDate", ""),
            "total_bytes": full.get("totalFileSize"),
            "url": f"https://psi.nasa.gov/physci/repo/data/investigations/{psi_id}",
            "tables": tables,
        })

    (DATA / "investigations.json").write_text(json.dumps(investigations, indent=2))
    print(f"\nSaved {len(investigations)} investigations -> data/investigations.json")
    print(f"Tables in {TABLES}")


if __name__ == "__main__":
    main()
