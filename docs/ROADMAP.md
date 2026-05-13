# Roadmap

A living list of analyses, visualizations, data improvements, and engineering work that would extend Fanalysista. Items are grouped by category, not strict priority — pick whatever serves the next session best.

Items marked **✓** have shipped; everything else is open.

## Analytics

### Done

- ✓ Per-player season totals (apps, capture rate, contribution, missed fv, best/worst games)
- ✓ Per-team league table (W/D/L, points, goal diff, totale stats)
- ✓ Position rollup (P/D/C/A breakdown per team)
- ✓ Regret / optimal-lineup analysis (best-11 from the 25-player squad with any valid module)
- ✓ "Manager usage" verdict on Player Detail page (avg active fv vs avg missed fv)

### Open

- **Regret decomposition** — split the existing `regret` metric into two components:
  - `bench_regret` = best 11 *inside the actual module chosen* minus actual
  - `module_regret` = optimal across all modules minus best-with-actual-module

  Tells the manager whether their bench order was the issue, the module choice, or both. One change to `build_regret()`, one new column on the Regret page.

- **Counterfactual swap explorer** — interactive: pick a player on your team, see "if you'd swapped them in for X each time both were available, you'd have gained Y". Per-giornata diff + season total. Drill-in target from the Players page and the Regret page.

- **Consistency / boom-or-bust leaderboard** — stddev of active fv per player. Histogram + box plot are already on the Player Detail page; this surfaces the same insight at scale: which players are reliable (low stddev) vs. volatile (high stddev)? Useful for choosing captains and trade targets.

- **Auction-draft helper** — once we ingest auction prices, compute fv-per-credit ratios and surface "best value" and "biggest flop" rankings. Requires either a CSV of auction prices (manual import) or a new fantacalcio.it endpoint (TBD).

- **Schedule strength rating** — for any team, the avg `opp_totale` of upcoming opponents. Helps with "should I trade for next week's matchup or hold for two weeks out".

- **Best XI of the giornata** — across the whole league, the 11 players with the highest fv satisfying a valid module. Fun cross-team showcase; could also be aggregated season-long ("which player made it most often").

- **Captain analysis** — if a captain rule is enabled, identify the best captain candidates per giornata (high-floor or high-ceiling depending on preference). Currently no captain data is parsed because Husky/Serie C doesn't use one.

- **Manager comparison** — head-to-head view between any two teams: their match-ups, comparative TOTALE, where each team's points came from, etc.

- **Goalkeeper rotation analysis** — for teams that rotate keepers, did they pick the right one each giornata?

- **Streak tracking** — longest win/draw streak, longest unbeaten run, longest active streak per player. Some of this is already on the Player Detail page (longest active streak); team-level analogues are missing.

## Visualization

### Done

- ✓ Stacked vertical bar of total_fv = active + missed per player (now on Team Detail)
- ✓ Sunburst (pie-of-pie): position → player share of active fv
- ✓ Donut: single-ring player share of team total
- ✓ TOTALE heatmap (teams × giornate, RdYlGn scale)
- ✓ Cumulative standings race (points and TOTALE tabs)
- ✓ Appearance breakdown pie (starter/sub/benched/no-voto)
- ✓ Per-player performance bars over time, with avg line
- ✓ Histogram + box plot for fv distribution
- ✓ Capture-rate vs total-active-fv scatter
- ✓ Dumbbell chart for team vs opp average TOTALE
- ✓ Centralised colour theme in `src/dashboard/theme.py` (position, category, subject/opponent/what-if)
- ✓ Click-to-navigate row selection on league table, players, top contributors, and the team's player table

### Open

- **Rolling form sparkline** — per-player rolling 5-giornata average, small chart embedded in the Players table and on Player Detail.

- **Per-opponent breakdown for a player** — small bar chart showing avg fv against each opponent. Reveals "this player always scores against X".

- **Home vs away splits** — split player and team stats by whether the team had Fattore campo. Possibly noise at single-season scale but interesting at multi-season.

- **Animated standings race** — bar-chart-race style animation (Plotly supports `animation_frame`). Visually striking for sharing a season recap with leaguemates.

- **Player profile radar** — multi-axis radar chart for a single player: capture rate, avg active fv, best fv, apps rate, vs-position-average. Quick visual identity comparison between two players side-by-side.

- **Trade timeline annotations** — when a player has a `*` rename mid-season, mark the cutoff giornata on the performance chart. Useful when reviewing why a player's contribution stopped.

- **TOTALE distribution density per team** — small multiples of TOTALE distributions, one panel per team. Quickly compares consistency vs volatility across the league.

- **Clickable points inside charts** (extends current row-click pattern). `st.plotly_chart(fig, on_select="rerun", selection_mode="points")` returns a selection event. If each trace is built with `customdata=[..., (team, player), ...]`, the click handler reads the customdata and calls `st.switch_page()`. Feasible; would let users click a dot in the capture-rate scatter, a slice in a sunburst, or a bar in a stacked chart and land on the relevant Team / Player Detail page.

- **Modal detail dialogs (`@st.dialog`)** instead of redirects. Streamlit 1.31+ supports modal overlays via the `@st.dialog` decorator. Click → modal opens over the current page with a condensed Team / Player summary → close button → the underlying page is untouched (no browser-back needed). Much better UX than the current redirect pattern. Trade-off: modal width is constrained (`small` / `large`); the modal would likely show a digest with an "Open full page →" link for the deep view. Feasible and high-impact.

- **League Trends page** (deferred / low priority). A single page bundling all cross-team comparisons: P/D/C/A contribution stacked bar (currently displaced when Position Rollup was removed), regret distribution density, capture-rate spread per position, etc. At single-season scale these aren't especially engaging; they get interesting if/when multi-season data exists. Rebuild then.

## Data

### Done

- ✓ Bronze → Silver → Gold medallion structure
- ✓ Offline transforms (no creds needed past download)
- ✓ Multi-league / multi-competition auto-discovery in the dashboard

### Open

- **Multi-season aggregation** — once more than one season is downloaded, cross-season summaries: career fv per player, longitudinal manager performance, year-over-year auction price tracking. Path naming already supports it (`bronze/{league}/{comp}/...`) but no gold table currently aggregates across seasons.

- **Multi-competition aggregation within a league** — overall team performance combined across Serie A / B / C / Champions / etc. inside one fantacalcio league. Need to decide whether to weight equally or by giornate played.

- **Database backend** — move bronze/silver/gold from CSV/xlsx on disk to a SQL store (likely DuckDB for portability, optionally Postgres for shared access). The `sql/` folder is reserved for migrations, queries, and views. Streamlit data loaders would switch from `pd.read_csv` to `pd.read_sql_query`.

- **Auction price ingestion** — accept a CSV of league auction prices (player → credits paid) and join into gold/player_season to enable cost-effectiveness analysis.

- **Real-time refresh during the season** — once weekly cron / GitHub Action that pulls the latest giornata as it becomes available. Currently you re-run the whole pipeline manually.

- **Mantra / Classic mode flag** — the parser assumes Classic mode (fixed positions). If your league uses Mantra (per-giornata flexible positions), we'd need to capture position per appearance and adjust the regret optimizer to allow position swaps.

## Engineering

### Done

- ✓ `src/` layout for source code, `docs/` for documentation
- ✓ `data/` folder consolidates bronze / silver / gold
- ✓ Streamlit `AppTest`-based smoke-testing of every page
- ✓ Generic `.env.example`; real credentials gitignored
- ✓ Dashboard pages reorganised as a FM-style drill-in hierarchy (League → Team → Player)

### Open

- **Tests** — `tests/` folder is reserved. Priorities, in order:
  1. `parse_formations` against a checked-in tiny xlsx fixture (catches xlsx-format regressions)
  2. `build_silver` and `build_gold` against a known small silver dataset (catches aggregation regressions)
  3. Dashboard pages via `AppTest` (catches page-loading regressions)

- **CI** — GitHub Actions workflow running `pytest` and the `AppTest` suite on every PR.

- **Per-league config files** — `config/{league}.yaml` describing valid modules, scoring rules, captain enabled/disabled. Loaded by `build_gold.py` instead of the hardcoded `VALID_MODULES` constant.

- **Type checking** — `mypy` (or `pyright`) over `src/`. Most of the codebase already has type hints; this would tighten them.

- **Package layout** — currently `src/` is a flat module directory; for a more "professional" Python package layout we'd move to `src/fanalysista/__init__.py` and expose console-script entry points via `pyproject.toml` (`fanalysista-download`, `fanalysista-build`, etc.).

- **Static dashboard export** — Streamlit's `nbconvert`-style export isn't great. A workaround: render each page's plotly figures to standalone HTML via `fig.write_html()`, then assemble into a single page. Useful for sharing a season recap with leaguemates who don't want to install Python.

- **Logging** — current scripts use `print()`. Switch to `logging` with a configurable level (`-v/--verbose`).

- **`pyproject.toml`** — replace `requirements.txt` with a proper `pyproject.toml` once the project stabilises. Lockfile via `pip-tools` or `uv`.

## Deployment & infrastructure direction

The current dashboard is local-only — `streamlit run` on the user's machine, reading CSVs from disk. The medium-term goal is to host it so leaguemates (and eventually a broader audience) can use it as a web app. This section captures the thinking on how that evolution looks.

### Database migration (probably the first non-trivial step)

The trigger for a DB is *not* concurrent users yet — it's the friction of:
- Cross-season / cross-league queries via SQL becoming natural.
- A single index file that the dashboard can read instead of multiple CSV directories.
- The path to a hosted version: web apps want a DB, not a folder full of CSVs.

**Likely route**:
1. **DuckDB** as the transitional backend. File-based (single `.duckdb` file), no server, very fast OLAP, drop-in for the analytical queries the dashboard makes. Loaders switch from `pd.read_csv` to `pd.read_sql_query` against a DuckDB connection. Bronze stays as xlsx files; silver and gold migrate into DuckDB tables. The `sql/` folder holds the schema and views.
2. **Postgres** later, if/when multi-user concurrency or write paths matter (e.g., a hosted version where users upload their own league data).

### Hosting options, matched to scale

| Scale | Option | Notes |
|---|---|---|
| Single user (you on your laptop) | current state | nothing changes |
| Small private group (≤10 concurrent) | **Streamlit Community Cloud** (free), **fly.io** / **Render** / **Railway**, or a $5/month VPS | low-friction, Streamlit-native |
| Larger / public | reconsider framework first (below) | Streamlit's per-session memory model gets expensive at scale |

### Is Streamlit the right framework long-term?

**Where Streamlit is strong** — and where we are now:
- Fast iteration, low boilerplate
- Built-in caching, dataframe widgets, multi-page support
- Sufficient for this analytical use case at small user counts

**Where Streamlit gets uncomfortable**:
- Every interaction re-runs the script top-to-bottom — fine for tabular slicing, painful for complex interactivity
- Per-session memory is high (the full script state per user)
- Multi-page navigation is awkward (we're already pushing it with `st.switch_page` + shared session state)
- No native auth/permissions (third-party `streamlit-authenticator` exists but isn't first-class)
- Deep linking / URL state was limited until v1.30; still not great for shareable links

**Crossover signals** — when to seriously evaluate alternatives:
- Concurrent users start hitting memory limits on the host
- Interactions need to feel "instant" (sub-100ms) rather than "scripty"
- Real auth / per-user data isolation becomes a hard requirement
- The dashboard becomes a product, not a tool

**Streamlit alternatives**, sorted by how disruptive a switch would be:

1. **Dash (Plotly)** — production-grade, callback-based, faster, more verbose. Closest like-for-like swap if Streamlit becomes constraining without rewriting the data layer.
2. **Panel (HoloViz)** — similar tradeoffs to Streamlit, more layout flexibility. Reasonable alternative.
3. **Marimo** — reactive notebook framework, newer and interesting. Bleeding edge; watch but don't bet on yet.
4. **FastAPI + a frontend (React / Svelte / Vue)** — full control, real web app, way more work. The right answer once this is a product rather than an analytical tool. Allows native modals, deep linking, real auth, shareable URLs.

### Recommendation for now

- **Stay on Streamlit** for the analytical phase.
- **Migrate to DuckDB** when convenient — the win/effort ratio is good and it doesn't require any other architectural change.
- **Try `st.dialog` modals** (see Visualization → Open) before reaching for a framework change; they may solve the navigation friction you're feeling.
- **Revisit framework choice** only when concrete pain shows up. Avoid premature rewriting.

When (and only when) Streamlit becomes the bottleneck, the natural path is **Dash → FastAPI+frontend**. The Bronze/Silver/Gold split makes a framework swap relatively cheap: the data layer is portable, the dashboard layer is the part that gets rewritten.

## Open questions (worth thinking about before designing)

These shape future architecture decisions; no code change is implied.

1. **Database choice when we migrate**: DuckDB is the easiest (file-based, no server, fast for OLAP, perfect for analyst-style queries). Postgres if multi-user access or web hosting comes into play. SQLite is fine for personal use but limits the SQL window-function ergonomics we'd want.

2. **Hosting the dashboard**: Streamlit Cloud is free for small projects but requires the data to be either committed (no — it's per-user) or fetched on demand (means embedding credentials). Self-hosting via Tailscale or a cheap VPS works. Probably stays local-only for the foreseeable future.

3. **Granularity of "season"**: Currently the path is `{league}/{competition}`. A season identifier would normally sit between league and competition: `{league}/{season}/{competition}`. Worth adding before we accumulate multi-season data, to avoid a painful migration.

4. **How to encode league rules**: a config file per league (see "Per-league config files" above) is the obvious answer, but the format matters. YAML is readable but loose; JSON Schema validation is strict but verbose. Pydantic models would give us both. Decide before the first non-Serie-A-default league.

5. **Captain modeling**: when we eventually add it, is "captain" a column on `appearances.csv` (per-player-giornata bonus multiplier) or a separate `captain_picks.csv` (per-team-giornata pointing at the chosen captain)? The latter is more normalized; the former is faster to query.

## How to use this document

When you start a session and want to know what to work on, pick from "Open" items above. Add new ideas as bullets under the matching category. When something ships, move it to "Done" with a `✓` and keep the description so the rationale survives.

If an idea grows beyond a bullet (becomes a multi-paragraph spec), promote it to its own file under `docs/proposals/` and link from here.
