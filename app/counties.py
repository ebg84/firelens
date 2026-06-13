"""CA county FIPS <-> name lookup (the 58 counties), server side. Mirrors the
CA_COUNTY map in static/app.js. Used only as a NAVIGATION aid (resolve a county
name to its real ZIPs) — never to synthesize a county-level metric.
"""
from __future__ import annotations

# 3-digit county code (the suffix of the 5-char "06xxx" FIPS) -> county name
CA_COUNTY = {
    "001": "Alameda", "003": "Alpine", "005": "Amador", "007": "Butte",
    "009": "Calaveras", "011": "Colusa", "013": "Contra Costa", "015": "Del Norte",
    "017": "El Dorado", "019": "Fresno", "021": "Glenn", "023": "Humboldt",
    "025": "Imperial", "027": "Inyo", "029": "Kern", "031": "Kings", "033": "Lake",
    "035": "Lassen", "037": "Los Angeles", "039": "Madera", "041": "Marin",
    "043": "Mariposa", "045": "Mendocino", "047": "Merced", "049": "Modoc",
    "051": "Mono", "053": "Monterey", "055": "Napa", "057": "Nevada", "059": "Orange",
    "061": "Placer", "063": "Plumas", "065": "Riverside", "067": "Sacramento",
    "069": "San Benito", "071": "San Bernardino", "073": "San Diego",
    "075": "San Francisco", "077": "San Joaquin", "079": "San Luis Obispo",
    "081": "San Mateo", "083": "Santa Barbara", "085": "Santa Clara",
    "087": "Santa Cruz", "089": "Shasta", "091": "Sierra", "093": "Siskiyou",
    "095": "Solano", "097": "Sonoma", "099": "Stanislaus", "101": "Sutter",
    "103": "Tehama", "105": "Trinity", "107": "Tulare", "109": "Tuolumne",
    "111": "Ventura", "113": "Yolo", "115": "Yuba",
}


def county_name(county_fips: str | None) -> str | None:
    if not county_fips:
        return None
    return CA_COUNTY.get(str(county_fips)[-3:])


def _normalize(q: str) -> str:
    return q.strip().lower().removesuffix(" county").strip()


# normalized name -> full 5-char FIPS ("06xxx")
_NAME_TO_FIPS = {name.lower(): "06" + code for code, name in CA_COUNTY.items()}


def resolve_county(q: str) -> tuple[str, str] | None:
    """Exact (normalized) county-name match -> (name, '06xxx'), else None."""
    norm = _normalize(q)
    fips = _NAME_TO_FIPS.get(norm)
    if fips:
        return CA_COUNTY[fips[-3:]], fips
    return None


def county_candidates(q: str) -> list[str]:
    """Substring matches on county names (for ambiguous free-text), e.g. 'san' -> many."""
    norm = _normalize(q)
    if len(norm) < 2:
        return []
    return sorted(name for name in CA_COUNTY.values() if norm in name.lower())
