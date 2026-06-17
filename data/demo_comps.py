"""
demo_comps.py -- Location-aware *illustrative* comparables for any address.

Sample/sandbox feeds aren't tied to real addresses, so without a licensed MLS
feed we can't return real comps for an arbitrary property. This generator instead
produces a plausible, deterministic set of nearby comps derived from the entered
address + subject details, so the whole app visibly responds to any address
(price, comps, map, trends all change).

These are clearly labeled as demo data in the UI/report. Connect a live MLS source
(Admin -> data source) for real comparables.
"""
from __future__ import annotations

import hashlib
import random
import urllib.parse
from datetime import date, timedelta


def _seed(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16) % (2 ** 32)


def _num(v, default):
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


def generate_demo_comps(address: str, lat, lng, subject: dict, n: int = 7,
                        today: date = None) -> list:
    """Deterministic illustrative comps near (lat, lng) for the given subject."""
    today = today or date.today()
    address = (address or "Subject Property").strip()
    lat = lat if lat is not None else _num(subject.get("Latitude"), 30.2672)
    lng = lng if lng is not None else _num(subject.get("Longitude"), -97.7431)

    rng = random.Random(_seed(f"{address}|{round(float(lat), 3)}|{round(float(lng), 3)}"))

    # Location-derived market rate so different areas show different price levels.
    base_ppsf = 150 + rng.random() * 450  # ~$150–$600 / sqft

    subj_sqft = _num(subject.get("LivingArea"), 2000)
    subj_beds = int(_num(subject.get("BedroomsTotal"), 3))
    subj_baths = int(_num(subject.get("BathroomsTotalInteger"), 2))
    street = address.split(",")[0].strip() if "," in address else address
    # strip a leading house number so generated comps share the street name
    parts = street.split(" ", 1)
    street_name = parts[1] if len(parts) == 2 and parts[0].isdigit() else street

    offices = ["Keller Williams Realty", "RE/MAX Premier", "Coldwell Banker",
               "Compass", "Local Realty Group", "Century 21"]

    comps = []
    for i in range(n):
        active = i >= n - 2  # last two are active listings
        sqft = max(800, int(subj_sqft * (0.85 + rng.random() * 0.30)))
        ppsf = base_ppsf * (0.92 + rng.random() * 0.16)
        price = max(50000, round(ppsf * sqft / 1000) * 1000)
        close = None if active else (today - timedelta(days=rng.randint(20, 175))).isoformat()
        house_no = rng.randint(100, 9899)
        comps.append({
            "ListingId": f"D-{1000 + i}",
            "ListingUrl": "https://www.google.com/search?q=" +
                          urllib.parse.quote(f"{house_no} {street_name}"),
            "ListOfficeName": rng.choice(offices),
            "StandardStatus": "Active" if active else "Closed",
            "ClosePrice": None if active else price,
            "ListPrice": round(price * (1.0 + rng.random() * 0.04) / 1000) * 1000,
            "CloseDate": close,
            "UnparsedAddress": f"{house_no} {street_name}",
            "LivingArea": sqft,
            "BedroomsTotal": max(1, subj_beds + rng.choice([-1, 0, 0, 1])),
            "BathroomsTotalInteger": max(1, subj_baths + rng.choice([-1, 0, 1])),
            "GarageSpaces": rng.choice([1, 2, 2, 3]),
            "PoolPrivateYN": rng.random() < 0.25,
            "YearBuilt": rng.randint(1985, 2020),
            "Latitude": float(lat) + (rng.random() - 0.5) * 0.02,
            "Longitude": float(lng) + (rng.random() - 0.5) * 0.02,
        })

    # Make one closed comp a clear outlier so outlier handling is visible.
    out = comps[0]
    out["ClosePrice"] = round(out["ClosePrice"] * 1.9 / 1000) * 1000 if out["ClosePrice"] else None
    out["Latitude"] = float(lat) + 0.05
    out["Longitude"] = float(lng) + 0.05
    return comps
