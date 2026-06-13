# RUBRIC.md — Machine-gradable completion rubric

> **Reading order:** terminal (read after TESTING.md) · **Depends on:** CLAUDE.md (acceptance criteria), docs/TESTING.md (tiers) · **Single source of truth for:** the definition of done, gradeable without human judgment
> Graded by a verifier sub-agent in a fresh context before any milestone
> is marked complete. Every item is checkable by running a command,
> loading a URL, or matching text — no judgment calls. The builder agent
> may not edit this file.

## R1 — Data layer verification (prior asset; verifier re-runs these at kickoff as the session log's first artifact)
- [ ] `pytest -m "tier1 or tier2" -q` exits 0
- [ ] Anchor test passes: Tubbs 2017-10-08 ≥ 90th percentile (FWI; VPD is
      pending, not a served fallback) for its Sonoma cell; Palisades
      and Eaton 2025 present with Red-Flag = true
- [ ] `data/manifest.json` exists and `du -sh data/` ≤ 100 MB
- [ ] Era-dedup query (DATA.md Part C F2) returns 0 violations

## R2 — Deployment + public API (the substrate; never cut)
- [ ] /api/health returns 200 on the production URL
- [ ] /api/trends/95404 returns JSON whose values match a direct Parquet
      query (not hardcoded)
- [ ] All five query endpoints + /api/manifest respond; /docs renders
- [ ] / renders ≥1 real zip_trends value fetched from the API

## R3 — Fire Weather Report (primary surface; never cut)
- [ ] Entering `95404` renders a report containing: a trend figure with a
      period reference ("since" or "baseline"), a named fire ("Tubbs"),
      an ignition-day percentile, and `structures` when present
- [ ] Every numeric claim in the report links to the public API URL
      that produced it; zero uncited numbers (regex scan of rendered
      output)
- [ ] An invalid ZIP (`00000`) yields a helpful message, not an error

## R4 — Map (supporting view; pre-approved cut — its absence is a scope decision, not a failure)
- [ ] County→ZIP drill-down works; clicking a perimeter resolves its
      `fire_id` to an event card (spot-check: Tubbs)
- [ ] County and ZIP views use identical color breakpoints

## R5 — Agent
- [ ] TESTING.md Tier 4 golden questions 1–6 pass on the deployed URL
- [ ] All three adversarial declines decline AND offer the adjacent
      capability (string rules in TESTING.md)
- [ ] "Will it get worse?" response contains no "will" + year construction
      and attributes trend continuation to published literature

## R6 — Live context
- [ ] `get_today_context` for 94588 returns a percentile in [0,1] with a
      data date within 48 h, fetched from the forecast endpoint

## R7 — Submission hygiene (16:30 checklist)
- [ ] Repo public; LICENSE (MIT) present; README current
- [ ] Session log saved into the repo; brief (docs/) committed
- [ ] 1-minute demo video recorded and linked in the submission form
- [ ] Submission form completed before 17:00

## Scoring map (for the verifier's summary)
Impact ← R3 quality on the five reference ZIPs · Demo ← R2–R6 on the
live URL · Autonomy ← session log (self-caught failures, intervention
count) · Orchestration ← this file + docs/ as the brief + the rerunnable
gate commands above.
