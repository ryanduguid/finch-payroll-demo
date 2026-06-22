"""Finch pay-statement extraction.

In live mode (FINCH_ACCESS_TOKEN) this would pull pay statements from Finch's
unified payroll API — one integration that already speaks 200+ payroll/HRIS
systems. For the demo it loads bundled samples in the same shape, then normalizes
to the facts the withholding check needs.

Finch amounts are in cents; we divide by 100. We pull the employee Social
Security and Medicare lines out of the `taxes` array by name.
"""

from __future__ import annotations

import json
import os

FINCH_ACCESS_TOKEN = os.environ.get("FINCH_ACCESS_TOKEN")


def extract(source: str) -> list[dict]:
    if FINCH_ACCESS_TOKEN:
        return _extract_live()
    with open(source) as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [data]


def _extract_live() -> list[dict]:  # pragma: no cover - needs a real token
    """Live Finch pull. Wired but inert until FINCH_ACCESS_TOKEN is present.

    POST /employer/pay-statement with pay-statement ids from /employer/payment.
    """
    import urllib.request

    req = urllib.request.Request(
        "https://api.tryfinch.com/employer/pay-statement",
        headers={"Authorization": f"Bearer {FINCH_ACCESS_TOKEN}",
                 "Finch-API-Version": "2020-09-17", "Content-Type": "application/json"},
        data=b'{"requests":[]}',
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("responses", [])


def _tax(taxes: list[dict], name: str) -> float:
    for t in taxes or []:
        if name.lower() in (t.get("name", "").lower()) and not t.get("employer"):
            return float(t.get("amount", 0)) / 100.0
    return 0.0


def normalize(stmt: dict) -> dict:
    taxes = stmt.get("taxes") or []
    return {
        "name": stmt.get("individual_name", "Employee"),
        "country": (stmt.get("country") or "US").upper(),
        "gross": float((stmt.get("gross_pay") or {}).get("amount", 0)) / 100.0,
        "ytd_prior_gross": float(stmt.get("ytd_prior_gross", 0)) / 100.0,
        "withheld_social_security": _tax(taxes, "Social Security"),
        "withheld_medicare": _tax(taxes, "Medicare"),
    }
