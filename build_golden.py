"""Hand-compile the Phoenix 2026 Heat Response Plan into the golden clause set.

This is the reference the automatic compiler is scored against, so it is built
by reading the document, not by running a model over it.

Every ``source_text`` here is checked against the extracted text of the page it
claims to come from. A quote that does not appear verbatim on its stated page
is a hard failure -- provenance is the product, and an unverified citation is
worse than no citation.

    python build_golden.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pdfplumber  # noqa: E402

from schema import Clause, inventory, save_clauses  # noqa: E402

PDF = Path("data/plan/phoenix_2026_heat_response_plan.pdf")
OUT = Path("data/golden/phoenix_2026_clauses.json")

# The plan prints degrees with a special glyph that pdfplumber renders as 
# in places; normalise before comparing quotes.
def norm(s: str) -> str:
    s = s.replace("", "°").replace("", "").replace("’", "'")
    s = s.replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# The 23 actions, transcribed from the table on page 11 with lead departments,
# plus the trigger sentence from each action's narrative page where one exists.
# --------------------------------------------------------------------------

GOLDEN: list[Clause] = [
    # ---- Strategy 1: equip first responders -------------------------------
    Clause(
        clause_id="PHX-2026-A1.1",
        action_id="1.1", strategy_id="1",
        action="Activate summer heat protocols including cold immersion techniques",
        actor=["FIRE"],
        source_page=12,
        source_text=("Protective directives are implemented when temperatures exceed 105°F, "
                     "deploying additional resources and implementing enhanced rehabilitation "
                     "measures."),
        kind="operative_trigger",
        metric="air_temperature",
        operator="above",
        threshold_source=105.0,
        scope="citywide",
        extraction_conf=1.0,
        extraction_note=("Explicit numeric trigger. Scope recorded as citywide: the plan "
                         "attaches no geography to the condition."),
    ),
    Clause(
        clause_id="PHX-2026-A1.2",
        action_id="1.2", strategy_id="1",
        action="Equip Homeless Outreach Teams with Cooling Resources",
        actor=["OHS", "OHRM", "OPH"],
        source_page=12,
        source_text=("During the heat season, outreach teams are equipped with heat relief kits "
                     "to distribute to community members in need, including water, hats, cooling "
                     "towels, and other essential supplies."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Activated for the heat season; no thermal condition stated.",
    ),

    # ---- Strategy 2: cool space and drinking water ------------------------
    Clause(
        clause_id="PHX-2026-A2.1",
        action_id="2.1", strategy_id="2",
        action="Designate City facilities as Heat Relief Network Cooling Centers",
        actor=["LIB", "OHRM"],
        source_page=13,
        source_text=("17 City of Phoenix Library locations served as Cooling Centers throughout "
                     "the 2025 Heat Season and the City will continue this commitment in 2025."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Operates throughout the heat season; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A2.2",
        action_id="2.2", strategy_id="2",
        action="Offer Extended Hours at City of Phoenix Cooling Centers",
        actor=["LIB", "OHS", "OEM", "OHRM", "OPH"],
        source_page=13,
        source_text=("the City of Phoenix will extend the hours of one Cooling Center-Cholla "
                     "Library-to 9pm each day of the week and add capacity from noon to 9pm on "
                     "Sundays throughout the heat season."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason=("Fixed hours for the whole season. Notably, the site was chosen by "
                              "a stated geographic heat-health rationale, but its operation is "
                              "not conditioned on temperature."),
    ),
    Clause(
        clause_id="PHX-2026-A2.3",
        action_id="2.3", strategy_id="2",
        action="Operate a 24/7 Respite and Navigation Center",
        actor=["OHS", "OEM", "OHRM", "OPH"],
        source_page=14,
        source_text=("the City of Phoenix will operate one 24/7 Heat Respite and Navigation "
                     "Center for the entire heat season as well as a second site with afternoon "
                     "and evening hours."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Runs continuously for the season; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A2.4",
        action_id="2.4", strategy_id="2",
        action="Designate City Facilities as Heat Relief Network Hydration Stations",
        actor=["PRD", "HSD", "OHRM"],
        source_page=14,
        source_text=("All City of Phoenix senior centers, community centers, and swimming pools "
                     "served as Hydration Stations during the 2025 Heat Season and the City will "
                     "continue this commitment in 2026."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Season-long designation; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A2.5",
        action_id="2.5", strategy_id="2",
        action="Operate the Safe Outdoor Space",
        actor=["OHS"],
        source_page=14,
        source_text=("The unique property offers both outdoor and cooled indoor spaces."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Continuous operation; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A2.6",
        action_id="2.6", strategy_id="2",
        action="Provide Shade and Cooled Rest areas at The Key Campus",
        actor=["OHS"],
        source_page=15,
        source_text=("These investments include shade structures and evaporative coolers that are "
                     "activated on the Campus during the heat season."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason=("Activated 'during the heat season' -- a calendar condition, not a "
                              "thermal one."),
    ),
    Clause(
        clause_id="PHX-2026-A2.7",
        action_id="2.7", strategy_id="2",
        action="Expand Smart Drinking Water in Public Spaces Initiative",
        actor=["INNOV"],
        source_page=15,
        source_text=("This project expands access to chilled drinking water in high-density areas "
                     "of the city, with locations near public transportation stops and hubs, City "
                     "buildings, and public spaces."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Capital deployment; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A2.8",
        action_id="2.8", strategy_id="2",
        action="Improve Heat Response Educational Resources for City Employees",
        actor=["OHRM", "HR"],
        source_page=15,
        source_text=("A pilot version of the training program will be launched for the 2026 heat "
                     "season, with feedback from the pilot used to enhance the program for "
                     "widespread implementation in 2027."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Training programme; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A2.9",
        action_id="2.9", strategy_id="2",
        action="Provide Heat Relief Grants to Community Partners",
        actor=["OHRM"],
        source_page=16,
        source_text=("In 2026, the heat relief assistance program is being restructured with new "
                     "formal contracts for a heat relief supply provider and distribution manager "
                     "to improve program efficiency."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Grant programme; no thermal condition stated.",
    ),

    # ---- Strategy 3: homes -------------------------------------------------
    Clause(
        clause_id="PHX-2026-A3.1-EVAP",
        action_id="3.1", strategy_id="3",
        action=("Promote and Enforce Cooling Ordinance for Rental Housing Units "
                "(evaporative cooling standard)"),
        actor=["NSD", "HSD", "COMMS"],
        source_page=17,
        source_text=("Each unit must be able to safely cool all livable rooms to 86°F when using "
                     "evaporative cooling and 82°F when using air conditioning."),
        kind="indoor_standard",
        metric="indoor_air_temperature",
        operator="above", threshold_source=86.0, scope="indoor",
        evaluable=False,
        not_evaluable_reason=("Indoor habitability standard. FortyGuard measures 2 m outdoor air, "
                              "so this cannot be evaluated directly without an indoor model."),
        extraction_conf=1.0,
        extraction_note="One sentence carries two thresholds; split into two clauses.",
    ),
    Clause(
        clause_id="PHX-2026-A3.1-AC",
        action_id="3.1", strategy_id="3",
        action=("Promote and Enforce Cooling Ordinance for Rental Housing Units "
                "(air conditioning standard)"),
        actor=["NSD", "HSD", "COMMS"],
        source_page=17,
        source_text=("Each unit must be able to safely cool all livable rooms to 86°F when using "
                     "evaporative cooling and 82°F when using air conditioning."),
        kind="indoor_standard",
        metric="indoor_air_temperature",
        operator="above", threshold_source=82.0, scope="indoor",
        evaluable=False,
        not_evaluable_reason=("Indoor habitability standard; not an outdoor trigger."),
        extraction_conf=1.0,
        extraction_note="Second threshold from the same sentence.",
    ),
    Clause(
        clause_id="PHX-2026-A3.2",
        action_id="3.2", strategy_id="3",
        action="Provide Emergency Utility Assistance",
        actor=["HSD"],
        source_page=17,
        source_text=("The utility assistance program operates year-round and is promoted as a "
                     "heat response strategy during the heat season."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Year-round programme; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A3.3",
        action_id="3.3", strategy_id="3",
        action="Offer Low-Flow Water Service Program",
        actor=["WSD"],
        source_page=18,
        source_text=("This program provides a vital lifeline for customers experiencing difficulty "
                     "paying their water bills, offering essential water services for up to three "
                     "months."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Financial hardship programme; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A3.4",
        action_id="3.4", strategy_id="3",
        action="Deploy Heat Outreach Teams to Mobile Home and Senior Communities",
        actor=["OHRM"],
        source_page=18,
        source_text=("The City will partner with the Red Cross and the Arizona Mobile and "
                     "Manufactured Homeowners Association to coordinate a volunteer-led outreach "
                     "program for residents of mobile and manufactured homes as well as seniors."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason=("Outreach campaign. Targets a heat-vulnerable population but is not "
                              "conditioned on temperature."),
    ),

    # ---- Strategy 4: mobility and recreation -------------------------------
    Clause(
        clause_id="PHX-2026-A4.1",
        action_id="4.1", strategy_id="4",
        action="Deploy Outreach Teams to Select Trailheads",
        actor=["PRD", "OHRM", "FIRE"],
        source_page=19,
        source_text=("Volunteers from the Community Emergency Response Team (CERT) and Park "
                     "Stewards are stationed every Saturday and Sunday from 7-10 a.m. at entrances "
                     "to trails that have higher rates of heat-related illnesses and/or those where "
                     "rescue operations are more technically complex, including trails at Camelback "
                     "Mountain, Piestewa Peak, and South Mountain."),
        kind="scheduled", metric="none", scope="site", evaluable=False,
        not_evaluable_reason=("Fixed weekend schedule, 7-10 a.m., May through September. The "
                              "deployment window is a clock, not a condition."),
    ),
    Clause(
        clause_id="PHX-2026-A4.2",
        action_id="4.2", strategy_id="4",
        action="Close Select Trailheads on Extreme Heat Warning Days",
        actor=["PRD"],
        source_page=19,
        source_text=("The program restricts access to select trails when the National Weather "
                     "Service issues an Extreme Heat Warning."),
        kind="external_trigger",
        metric="daily_high",
        operator="above",
        threshold_source=110.0,
        scope="citywide",
        extraction_conf=0.70,
        extraction_note=(
            "The plan states no temperature for this trigger; the condition is defined by "
            "another agency and issued for a whole forecast zone. A 110 degF proxy is used, "
            "anchored to the plan's own pairing on page 6: 'hit at least 110°F on 37 days and "
            "there were 31 days with National Weather Service Extreme Heat Warnings in effect'. "
            "37 vs 31 days means the mapping is close but not exact, hence reduced confidence. "
            "Treat results for this clause as indicative."),
        evaluable=True,
    ),
    Clause(
        clause_id="PHX-2026-A4.3",
        action_id="4.3", strategy_id="4",
        action="Attend Community Events to Share Heat Safety Resources",
        actor=["OHRM"],
        source_page=19,
        source_text=("The Office of Heat Response and Mitigation will help raise awareness of heat "
                     "response initiatives by supporting requests to participate in community "
                     "gatherings and outreach events throughout the heat season."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Event attendance on request; no thermal condition stated.",
    ),

    # ---- Strategy 5: workers ----------------------------------------------
    Clause(
        clause_id="PHX-2026-A5.1",
        action_id="5.1", strategy_id="5",
        action="Annually Update Heat Safety Plans in City Departments",
        actor=["HR"],
        source_page=20,
        source_text=("The Human Resources Safety & Worker's Compensation Division has developed "
                     "written Heat Injury and Illness Prevention Plans with departments whose "
                     "employees face heat safety dangers during their work duties."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Annual administrative update; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A5.2",
        action_id="5.2", strategy_id="5",
        action="Promote and Enforce Heat Safety Ordinance for City Contractors",
        actor=["FIN", "LAW", "HR", "OHRM"],
        source_page=20,
        source_text=("The ordinance requires these businesses to have compliant heat safety plans "
                     "that ensure appropriate measures to protect employees are in place."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason=("Requires contractors to hold a plan; the ordinance text is not "
                              "reproduced here, so no threshold is available from this document."),
    ),

    # ---- Strategy 6: education and partners --------------------------------
    Clause(
        clause_id="PHX-2026-A6.1",
        action_id="6.1", strategy_id="6",
        action="Operate a Comprehensive Heat Response Public Education Campaign",
        actor=["COMMS"],
        source_page=21,
        source_text=("The City will continue to increase the reach of public messaging related to "
                     "heat response in 2026 through a comprehensive multimedia public education "
                     "campaign."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Campaign runs through the season; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A6.2",
        action_id="6.2", strategy_id="6",
        action="Improve Engagement Strategies for People Who Use Substances",
        actor=["OPH", "OHRM", "OHS", "COMMS"],
        source_page=21,
        source_text=("Efforts in 2026 will include the continuation of heat outreach and expanding "
                     "education on the risks of substance use and heat as well as overdose signs, "
                     "symptoms, and response."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Ongoing engagement programme; no thermal condition stated.",
    ),
    Clause(
        clause_id="PHX-2026-A6.3",
        action_id="6.3", strategy_id="6",
        action="Participate in Cross-Agency Work Groups and Research Initiatives",
        actor=["OHRM", "OEM"],
        source_page=22,
        source_text=("The City will continue to participate in and lead heat response initiatives "
                     "across a wide range of governance scales to ensure that resources are "
                     "deployed as effectively as possible."),
        kind="scheduled", metric="none", evaluable=False,
        not_evaluable_reason="Inter-agency coordination; no thermal condition stated.",
    ),

    # ---- Planning benchmarks the plan sets for itself -----------------------
    # These are not actions. They are the temperatures the document uses to
    # describe severity and to plan the season, and the plan names the single
    # station they are read from.
    Clause(
        clause_id="PHX-2026-BENCH-HIGH110",
        strategy_id=None, action_id=None,
        action="Season-severity benchmark: daily high at or above 110 degF",
        actor=["OHRM"],
        source_page=6,
        source_text=("Temperatures at Phoenix Sky Harbor Airport hit at least 110°F on 37 days and "
                     "there were 31 days with National Weather Service Extreme Heat Warnings in "
                     "effect."),
        kind="planning_benchmark",
        metric="daily_high", operator="above", threshold_source=110.0, scope="citywide",
        extraction_conf=1.0,
        extraction_note=("The plan measures season severity from one station, named in the "
                         "sentence. This is the citywide-sensing assumption, stated explicitly."),
    ),
    Clause(
        clause_id="PHX-2026-BENCH-LOW90",
        strategy_id=None, action_id=None,
        action="Season-severity benchmark: overnight low at or above 90 degF",
        actor=["OHRM"],
        source_page=6,
        source_text=("Nighttime temperatures failed to drop below 90°F at Sky Harbor on 23 days, "
                     "including a seasonal high overnight low of 95°F on July 10."),
        kind="planning_benchmark",
        metric="daily_low", operator="above", threshold_source=90.0, scope="citywide",
        extraction_conf=1.0,
        extraction_note=("Overnight heat is where the urban heat island is strongest, so this "
                         "benchmark is the most spatially variable one in the document."),
    ),
    Clause(
        clause_id="PHX-2026-BENCH-HIGH100",
        strategy_id=None, action_id=None,
        action="Planning benchmark: daily high at or above 100 degF",
        actor=["OHRM"],
        source_page=7,
        source_text=("The table below presents weekly averages, ranges, and probabilities of "
                     "exceedance based on 2016-2025 observations from Phoenix Sky Harbor Airport."),
        kind="planning_benchmark",
        metric="daily_high", operator="above", threshold_source=100.0, scope="citywide",
        extraction_conf=0.80,
        extraction_note=("Threshold read from the column header '100°F or above' of the page 7 "
                         "planning table; the quoted sentence establishes the table's source and "
                         "station. Confidence reduced because the number is tabular, not prose."),
    ),
]


# --------------------------------------------------------------------------
# Claims the plan makes that we can test against measured data. These are not
# rules, so they are not clauses -- but they are the document's own statements
# about spatial variability, and checking them is a result in itself.
# --------------------------------------------------------------------------

CLAIMS = [
    {
        "claim_id": "PHX-2026-CLAIM-10F",
        "source_page": 4,
        "source_text": ("Historical development patterns and varying topography across Phoenix "
                        "lead to neighborhood-to-neighborhood air temperature differences of 10°F "
                        "or more on summer days."),
        "testable": True,
        "test": ("Measure the spread of daily mean 2 m temperature across the 15 urban villages "
                 "on each day of the study window and compare with 10 degF."),
    },
    {
        "claim_id": "PHX-2026-CLAIM-63PCT",
        "source_page": 9,
        "source_text": ("In 2025, 37% of heat-related deaths in Maricopa County occurred on days "
                        "with the HeatRisk was designated by the National Weather Service as Major "
                        "or Extreme, and 63% of deaths occurred on days when the HeatRisk was "
                        "designated as Moderate, Minor, or None."),
        "testable": False,
        "test": ("Not testable with temperature data alone. Recorded because it is the plan's own "
                 "statement that most heat deaths fall outside warning conditions."),
    },
]


def main() -> int:
    with pdfplumber.open(PDF) as pdf:
        pages = {i: norm(p.extract_text() or "") for i, p in enumerate(pdf.pages, 1)}

    print(f"Verifying {len(GOLDEN)} clause quotes against {PDF.name} ({len(pages)} pages)\n")
    failures = []
    for c in GOLDEN:
        c.validate()
        page_text = pages.get(c.source_page, "")
        if norm(c.source_text) in page_text:
            print(f"  OK    {c.clause_id:<26s} p{c.source_page:<3d} {c.kind}")
        else:
            failures.append(c)
            print(f"  FAIL  {c.clause_id:<26s} p{c.source_page:<3d} quote not found verbatim")

    for cl in CLAIMS:
        if norm(cl["source_text"]) in pages.get(cl["source_page"], ""):
            print(f"  OK    {cl['claim_id']:<26s} p{cl['source_page']:<3d} claim")
        else:
            failures.append(cl)
            print(f"  FAIL  {cl['claim_id']:<26s} p{cl['source_page']:<3d} quote not found verbatim")

    if failures:
        print(f"\n{len(failures)} quote(s) could not be verified. Not writing the golden set.")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    save_clauses(GOLDEN, OUT, meta={
        "source_document": "City of Phoenix 2026 Heat Response Plan DRAFT (2.13.2026)",
        "source_url": ("https://www.phoenix.gov/content/dam/phoenix/heatsite/documents/"
                       "2026%20Heat%20Response%20Plan.pdf"),
        "source_pages": len(pages),
        "compiled_by": "hand (golden reference set)",
        "quote_verification": "every source_text verified verbatim against its stated page",
        "claims": CLAIMS,
    })

    inv = inventory(GOLDEN)
    print("\n" + "=" * 70)
    print("PLAN INVENTORY")
    print("=" * 70)
    print(f"  clauses compiled            {inv['total']}")
    for k, v in sorted(inv["by_kind"].items(), key=lambda kv: -kv[1]):
        print(f"    {k:<22s}    {v}")
    print(f"  conditional on temperature  {inv['conditional']}")
    print(f"  calendar-activated          {inv['scheduled']}")
    print(f"  of the conditional, citywide-scoped: {inv['citywide_scope']}")
    print(f"\n  written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
