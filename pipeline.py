#!/usr/bin/env python3
"""Finch -> OpenAccountants payroll-withholding pipeline.

    python pipeline.py                       # bundled sample pay statements (mock mode)
    python pipeline.py samples/pay_statements.json

The flow:
    Finch pay statements -> OA MCP (start -> get_skill) -> recompute FICA -> verdict

Finch is a unified payroll API, so one integration validates withholding across
200+ payroll/HRIS systems. Live: set OA_MCP_TOKEN (+ FINCH_ACCESS_TOKEN).
"""

from __future__ import annotations

import os
import sys

import finch_client
import withholding_check
from oa_client import OAClient

STATUS = {"ok": "✅", "warn": "⚠️ "}


def run(source: str, oa: OAClient) -> None:
    for stmt in finch_client.extract(source):
        f = finch_client.normalize(stmt)
        print(f"\n🧾  {f['name']} · {f['country']} · gross ${f['gross']:,.2f} (YTD prior ${f['ytd_prior_gross']:,.0f})")

        plan = oa.start("Validate payroll withholding", f["country"])
        slug = (plan.get("skills_to_load") or [None])[0]
        skill = oa.get_skill(slug) if slug else {}

        v = withholding_check.check(f, skill)
        trust = f"tier {v.get('tier')}" + (f", signed off by {v['verifier']}" if v.get("verifier") else "")
        print(f"    OpenAccountants → {v.get('oa_skill_name') or 'payroll rules'}  ({trust})")
        for c in v["checks"]:
            mark = STATUS.get(c["status"], "")
            money = f"  (${c['withheld']:,.2f} withheld vs ${c['expected']:,.2f} due)" if c["status"] == "warn" else ""
            print(f"    {mark} {c['tax']} — {c['note']}{money}")


def main(argv: list[str]) -> int:
    oa = OAClient()
    mode = "LIVE" if oa.live else "MOCK (set OA_MCP_TOKEN + FINCH_ACCESS_TOKEN to go live)"
    print(f"Finch → OpenAccountants · payroll-withholding demo  [{mode}]")
    here = os.path.dirname(os.path.abspath(__file__))
    source = argv[1] if len(argv) > 1 else os.path.join(here, "samples", "pay_statements.json")
    run(source, oa)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
