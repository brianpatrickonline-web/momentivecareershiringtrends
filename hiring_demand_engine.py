#!/usr/bin/env python3
"""
Hiring-Demand Engine — Stage 1 (data engine only, no visuals)
=============================================================
Pulls Indeed Hiring Lab occupation-sector data, maps sales verticals onto a
single PRIMARY Indeed sector each, and emits a plain table for sanity-checking
BEFORE any dashboard is built.

Data: Indeed Hiring Lab job_postings_tracker (CC-BY — cite Hiring Lab).
Index: 100 = Feb 1 2020 baseline. variable = "total postings". Daily, US.

This same script is the weekly-refresh tool: run `python3 hiring_demand_engine.py`
with no args and it fetches fresh data and rewrites vertical_table.csv.
"""

import sys
import pandas as pd

SECTOR_URL = ("https://raw.githubusercontent.com/hiring-lab/"
              "job_postings_tracker/master/US/job_postings_by_sector_US.csv")

# ---------------------------------------------------------------------------
# VERTICAL -> PRIMARY INDEED SECTOR   (37 verticals)
# tier:    "clean" = strong match | "proxy" = directional only
# primary: the single sector the vertical's index is taken from
# alts:    other sectors originally considered — kept for audit only, NOT used
#          in the math (switch to averaging later by combining primary+alts)
# ---------------------------------------------------------------------------
MAPPING = {
    # ---- clean / strong matches (25) ----
    "Accounting & Finance":     ("clean", "Accounting",                              ["Banking & Finance"]),
    "Actuarial & Insurance":    ("clean", "Insurance",                              []),
    "Administration":           ("clean", "Administrative Assistance",              []),
    "Arts & Entertainment":     ("clean", "Arts & Entertainment",                   []),
    "Banking":                  ("clean", "Banking & Finance",                      []),
    "Construction":             ("clean", "Construction",                           []),
    "Education":                ("clean", "Education & Instruction",                []),
    "Engineering":              ("clean", "Mechanical Engineering",                 ["Civil Engineering", "Electrical Engineering", "Industrial Engineering", "Architecture"]),
    "Facilities Management":    ("clean", "Installation & Maintenance",             ["Cleaning & Sanitation"]),
    "Healthcare":               ("clean", "Nursing",                               ["Medical Technician", "Medical Information", "Physicians & Surgeons", "Pharmacy", "Dental", "Therapy"]),
    "Hospitality & Tourism":    ("clean", "Hospitality & Tourism",                  ["Food Preparation & Service"]),
    "Human Resources":          ("clean", "Human Resources",                        []),
    "Law Enforcement":          ("clean", "Security & Public Safety",               []),
    "Legal":                    ("clean", "Legal",                                 []),
    "Life Sciences":            ("clean", "Scientific Research & Development",       []),
    "Manufacturing":            ("clean", "Production & Manufacturing",             []),
    "Marketing/Comms/PR":       ("clean", "Marketing",                             ["Media & Communications"]),
    "Mental Health":            ("clean", "Therapy",                               ["Community & Social Service"]),
    "Project Management":       ("clean", "Project Management",                     []),
    "Retail":                   ("clean", "Retail",                               []),
    "Sales":                    ("clean", "Sales",                                []),
    "Sciences":                 ("clean", "Scientific Research & Development",       ["Social Science"]),
    "Supply Chain & Logistics": ("clean", "Logistic Support",                       ["Loading & Stocking", "Driving"]),
    "Technology":               ("clean", "Software Development",                   ["IT Infrastructure, Operations & Support", "IT Systems & Solutions", "Data & Analytics"]),
    "Transportation":           ("clean", "Driving",                               []),

    # ---- proxy / directional only (12) ----
    "Aeronautics & Defense":    ("proxy", "Aviation",                              ["Mechanical Engineering", "Electrical Engineering"]),
    "Aging Services":           ("proxy", "Personal Care & Home Health",            ["Nursing"]),
    "Automotive":               ("proxy", "Installation & Maintenance",             ["Production & Manufacturing"]),
    "Design":                   ("proxy", "Arts & Entertainment",                   []),
    "End of Life Services":     ("proxy", "Personal Care & Home Health",            ["Community & Social Service"]),
    "Energy":                   ("proxy", "Installation & Maintenance",             ["Electrical Engineering"]),
    "Fundraising":              ("proxy", "Community & Social Service",             ["Marketing"]),
    "Higher Education":         ("proxy", "Education & Instruction",                []),
    "Journalism":               ("proxy", "Media & Communications",                []),
    "Nonprofit":                ("proxy", "Community & Social Service",             []),
    "Telecom":                  ("proxy", "IT Infrastructure, Operations & Support", ["Installation & Maintenance"]),
    "Water & Public Utilities": ("proxy", "Installation & Maintenance",             ["Civil Engineering"]),
}


def load_total_postings(source):
    df = pd.read_csv(source)
    df = df[(df["variable"] == "total postings") & (df["jobcountry"] == "US")].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def build_wide(df):
    """date x sector matrix of the index, daily, gaps time-filled for rolling math."""
    wide = df.pivot_table(index="date", columns="display_name",
                          values="indeed_job_postings_index", aggfunc="mean")
    full = pd.date_range(wide.index.min(), wide.index.max(), freq="D")
    return wide.reindex(full).ffill()


def slice_deltas(series7):
    """Non-overlapping, stacking deltas on the 7-day-smoothed series.
    this week (0-7d) + prior 3 weeks (7-28d) + prior 2 months (28-88d)
    are additive -> sum = net ~3-month change. NOT nested cumulative windows."""
    t0 = series7.index.max()
    def at(days):
        return series7.asof(t0 - pd.Timedelta(days=days))
    now, d7, d28, d88 = at(0), at(7), at(28), at(88)
    return {
        "net_3mo": round(now - d88, 1),          # headline momentum: net ~3-month change
        "delta_this_week": round(now - d7, 1),   # the three slices below stack to net_3mo
        "delta_prior_3wk": round(d7 - d28, 1),
        "delta_prior_2mo": round(d28 - d88, 1),
    }


# A vertical is called rising/falling on its NET 3-MONTH move, not the noisy
# week. TREND_PTS is the index-point threshold for "meaningful" — tune after
# watching a couple weeks of output.
TREND_PTS = 2.5

def tag(level, net_3mo):
    base = "below baseline" if level < 99 else "above baseline" if level > 101 else "at baseline"
    trend = ("rising" if net_3mo > TREND_PTS
             else "falling" if net_3mo < -TREND_PTS else "flat")
    return f"{base}, {trend} (3-mo)"


def main(source):
    df = load_total_postings(source)
    real = set(df["display_name"].unique())

    # Fail loud on ANY typo — primary and alternates must all exist.
    referenced = {p for _, p, _ in MAPPING.values()} | {a for _, _, alts in MAPPING.values() for a in alts}
    bad = referenced - real
    if bad:
        sys.exit(f"ABORT — sector name(s) not in data (typo?): {sorted(bad)}")

    wide = build_wide(df)

    # shared weekly x-axis (last point pinned to latest date)
    weekly = pd.date_range(wide.index.min(), wide.index.max(), freq="7D")
    weekly = weekly.append(pd.DatetimeIndex([wide.index.max()])).unique().sort_values()

    # Compute stats+series once for EVERY referenced Indeed sector (deduped pool).
    # These are the drill-down "categories" that sit under each vertical.
    sector_pool = {}
    for name in sorted(referenced):
        s7 = wide[name].rolling("7D").mean()
        d = slice_deltas(s7)
        sector_pool[name] = {"level": round(s7.iloc[-1], 1), "net_3mo": d["net_3mo"],
                             "d_week": d["delta_this_week"], "d_3wk": d["delta_prior_3wk"],
                             "d_2mo": d["delta_prior_2mo"],
                             "series": s7.reindex(weekly).round(1).tolist()}

    rows = []
    for vert, (tier, primary, alts) in MAPPING.items():
        s7 = wide[primary].rolling("7D").mean()
        level = round(s7.iloc[-1], 1)
        d = slice_deltas(s7)
        # categories = primary first, then alternates (deduped); only >1 is a real drill-down
        cats, seen = [], set()
        for s in [primary] + alts:
            if s not in seen:
                cats.append(s); seen.add(s)
        rows.append({"vertical": vert, "tier": tier, "primary_sector": primary,
                     "current_index": level, "raw_latest": round(wide[primary].iloc[-1], 1),
                     "tag": tag(level, d["net_3mo"]), **d, "categories": cats})

    table = pd.DataFrame(rows)
    order = {"clean": 0, "proxy": 1}
    table = table.sort_values(
        ["tier", "net_3mo"],
        key=lambda c: c.map(order) if c.name == "tier" else c,
        ascending=[True, False]).reset_index(drop=True)
    table.drop(columns=["categories"]).to_csv("vertical_table.csv", index=False)

    write_dashboard(table, sector_pool, weekly, wide.index.max())
    return table, wide.index.max()


def write_dashboard(table, sector_pool, weekly, latest):
    """Inject data into dashboard_template.html -> self-contained index.html."""
    import json, pathlib
    payload = {
        "meta": {"data_through": str(latest.date()),
                 "baseline": "Feb 1, 2020 = 100",
                 "source": "Indeed Hiring Lab"},
        "dates": [d.strftime("%Y-%m-%d") for d in weekly],
        "sectors": sector_pool,                       # shared pool: series + stats per Indeed sector
        "verticals": table.to_dict("records"),        # each references its primary + categories by name
    }
    tpl = pathlib.Path("dashboard_template.html").read_text()
    html = tpl.replace("/*__DATA__*/", "const DATA = " + json.dumps(payload, separators=(",", ":")) + ";")
    pathlib.Path("index.html").write_text(html)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else SECTOR_URL
    table, latest = main(src)
    print(f"Data through {latest.date()} | {len(table)} verticals "
          f"({(table.tier=='clean').sum()} clean, {(table.tier=='proxy').sum()} proxy)\n")
    with pd.option_context("display.max_rows", None, "display.width", 170):
        print(table[["vertical", "tier", "primary_sector", "current_index", "net_3mo", "tag",
                     "delta_this_week", "delta_prior_3wk", "delta_prior_2mo"]].to_string(index=False))
    # Momentum (what's trending up) is a different question than level (what's hot now).
    print("\nFastest-RISING (net 3-mo):", ", ".join(table.nlargest(5, "net_3mo")["vertical"]))
    print("Fastest-FALLING (net 3-mo):", ", ".join(table.nsmallest(5, "net_3mo")["vertical"]))
    print("Highest LEVEL right now:   ", ", ".join(table.nlargest(5, "current_index")["vertical"]))
    print("\nWrote: vertical_table.csv, index.html")
