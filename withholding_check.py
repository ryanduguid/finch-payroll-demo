"""Validate a Finch pay statement's FICA withholding against the loaded OA rates.

Recomputes employee Social Security and Medicare from the period gross + YTD, and
compares to what the payroll system actually withheld. Catches the classic
errors: SS over-withheld past the annual wage base, and the Additional Medicare
Tax missed above $200k.

DELIBERATE SCOPE: employee-side FICA only (not federal/state income-tax tables,
SUTA, garnishments, etc.). Production leans on the full OA skill + an agent step;
the named-CPA sign-off makes the verdict relianceable.
"""

from __future__ import annotations


def _round(x: float) -> float:
    return round(x + 1e-9, 2)


def check(facts: dict, oa_skill: dict) -> dict:
    rules = oa_skill.get("rules", {})
    ss = rules.get("social_security", {})
    mc = rules.get("medicare", {})
    base = {"oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
            "tier": oa_skill.get("tier"), "verifier": oa_skill.get("verifier")}

    gross = facts["gross"]
    ytd = facts["ytd_prior_gross"]
    checks = []

    # --- Social Security ---
    if ss:
        ss_base = max(0.0, min(gross, ss["wage_base"] - ytd))
        exp = _round(ss["rate"] * ss_base)
        got = facts["withheld_social_security"]
        if abs(got - exp) < 0.01:
            checks.append({"tax": "Social Security", "status": "ok", "expected": exp, "withheld": got,
                           "note": f"{ss['rate']:.1%} on ${ss_base:,.0f}"})
        else:
            if ytd >= ss["wage_base"]:
                why = f"YTD ${ytd:,.0f} already exceeds the ${ss['wage_base']:,.0f} wage base — no further SS due"
            elif ss_base < gross:
                why = f"only ${ss_base:,.0f} of this pay is under the ${ss['wage_base']:,.0f} wage base"
            else:
                why = f"expected {ss['rate']:.1%} of ${ss_base:,.0f}"
            verb = "over-withheld" if got > exp else "under-withheld"
            checks.append({"tax": "Social Security", "status": "warn", "expected": exp, "withheld": got,
                           "note": f"{verb} ${abs(got - exp):,.2f} — {why}"})

    # --- Medicare (+ Additional Medicare Tax over threshold) ---
    if mc:
        regular = mc["rate"] * gross
        over = max(0.0, (ytd + gross) - mc["additional_threshold"])
        add_base = min(gross, over)
        additional = mc["additional_rate"] * add_base
        exp = _round(regular + additional)
        got = facts["withheld_medicare"]
        if abs(got - exp) < 0.01:
            note = f"{mc['rate']:.2%} on ${gross:,.0f}" + (f" + {mc['additional_rate']:.1%} on ${add_base:,.0f} over ${mc['additional_threshold']:,.0f}" if add_base > 0 else "")
            checks.append({"tax": "Medicare", "status": "ok", "expected": exp, "withheld": got, "note": note})
        else:
            if add_base > 0 and abs(got - _round(regular)) < 0.01:
                why = f"Additional Medicare Tax ({mc['additional_rate']:.1%}) on ${add_base:,.0f} over ${mc['additional_threshold']:,.0f} not withheld"
            else:
                why = f"expected {mc['rate']:.2%} of ${gross:,.0f}" + (" + 0.9% surtax" if add_base > 0 else "")
            verb = "over-withheld" if got > exp else "under-withheld"
            checks.append({"tax": "Medicare", "status": "warn", "expected": exp, "withheld": got,
                           "note": f"{verb} ${abs(got - exp):,.2f} — {why}"})

    status = "warn" if any(c["status"] == "warn" for c in checks) else "ok"
    return {**base, "status": status, "checks": checks}
