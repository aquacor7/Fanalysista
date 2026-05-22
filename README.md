# Fanalysista

> Data extraction, transformation, and visualization for [Fantacalcio](https://leghe.fantacalcio.it) — turn weekly formation xlsx files into a manager's analytical dashboard.

Fanalysista pulls your league's data straight from `leghe.fantacalcio.it`, normalises it through a Bronze → Silver → Gold medallion pipeline, and renders an interactive Streamlit dashboard answering questions like:

- How efficiently did I use my squad — and how much did I leave on the bench?
- Which players are my top contributors? Who were the high-regret bench warmers?
- Where do my points come from (P / D / C / A breakdown)?
- What was the theoretically optimal lineup each giornata, and how far was I from it?
- Which teams in my league have the most under-used squads vs. the most efficient ones?

The end goal: give a Fantacalcio manager the kind of analytical visibility a real coach would have.

## Quick start

```bash
git clone <this repo>
cd fanalysista

# 1. Set up environment
python3 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Credentials — fantacalcio.it login is needed only for the bronze layer
cp .env.example .env
# edit .env with your FANTA_USERNAME and FANTA_PASSWORD

# 3. Run the four-step pipeline
python src/download_all.py  -l "My League" -c "Serie A"      # → data/bronze/
python src/build_silver.py  -l "My League" -c "Serie A"      # → data/silver/
python src/build_gold.py    -l "My League" -c "Serie A"      # → data/gold/
streamlit run src/dashboard/app.py                            # open the dashboard
```

The dashboard auto-discovers every league + competition you've processed and presents them in the sidebar.

## What's in the box

### Extract (bronze)

- `src/download_one.py` — one giornata
- `src/download_all.py` — every giornata in a competition

Both log in via the reverse-engineered fantacalcio.it API, look up the competition by name, and save the raw xlsx files to `data/bronze/{league_alias}/{competition_slug}/`.

### Transform (silver)

- `src/build_silver.py` — parses every xlsx in a bronze folder; emits two tidy CSVs:
  - `appearances.csv` — one row per player-giornata-team (position, voto, fantavoto, active, on-bench)
  - `matches.csv` — one row per team-giornata (opponent, score, result, totale, module, bonuses)

### Aggregate (gold)

- `src/build_gold.py` — reads silver, produces four CSVs in `data/gold/{league}/{comp}/`:
  - `player_season.csv` — per-player season totals (apps, capture rate, contribution, missed fv, best/worst games, …)
  - `team_season.csv` — the league table (W/D/L, points, goal diff, totale stats, regret summary)
  - `position_rollup.csv` — per-team P/D/C/A breakdowns
  - `regret.csv` — per-(team, giornata) actual vs theoretically-optimal player_fv with module info

### Present

- `src/report_team.py` — generates a wide-format xlsx "season report card" for a chosen team (rows: players, cols: per-giornata voto/fv/active + season totals)
- `src/dashboard/` — interactive Streamlit app, organised as a Football Manager-style drill-in hierarchy (League → Team → Player):
  - **Home (`app.py`)** — competition KPIs, the league table, and the top contributors across the competition. Click any team row to open a team summary modal, or any player row to open a player summary modal.
  - **1. League Table** — table, clickable Points bar chart, dumbbell chart of team vs opp average TOTALE, single-giornata peaks, TOTALE heatmap, cumulative standings race. **Click any team row, bar, or dumbbell dot → team summary modal → Team Detail.**
  - **2. Team Detail** — season KPIs, full schedule (with home/away side), TOTALE-vs-opponent line chart, stacked bar of player contributions (active vs missed), sunburst of position→player with **clickable outer ring**. **Click any player row, bar, or sunburst player slice → player summary modal → Player Detail.**
  - **3. Player Detail** — appearance breakdown pie, voto KPIs with "manager usage" verdict, per-giornata performance bars, fv histogram + box plot, notable games, rank vs team/league peers.
  - **4. Players** — cross-team filterable table + capture-rate scatter + **player-management quadrant** (best- and worst-used players plotted by Δ avg active/missed FV vs active appearances). Click any row or dot → player summary modal → Player Detail.
  - **5. Regret** — per-team giornata-by-giornata actual vs optimal player_fv + league-wide regret comparison.

  Clicking any team or player anywhere (table row, bar, scatter dot, dumbbell point, sunburst leaf) opens a **summary modal** (`@st.dialog`) over the current page. Each modal shows key metrics, one small chart, and a primary button to escalate to the full Detail page. Closing the modal preserves the underlying page state, and the **selected league / competition / team / player persist as you navigate between pages** (via canonical `_canon_*` session-state keys — see [src/dashboard/data.py](src/dashboard/data.py)).

The whole dashboard uses a consistent colour theme defined in `src/dashboard/theme.py`:

| Concept | Colours |
|---|---|
| Player position | P=gold, D=green, C=blue, A=red (Italian football convention) |
| Appearance category | Starter=dark green, Substitute=light green, Benched=orange, No voto=grey |
| Captured vs missed FV | Dark green = counted, orange = missed |
| Real-vs-real comparison (team vs opp, player vs player) | Dark blue (subject) vs **red** (other) |
| Real-vs-hypothetical (actual vs optimal) | Dark blue (actual) vs **light blue** (what-if) |

## CLI reference

All scripts take `-l/--league` (league name, case-insensitive) and `-c/--competition` (competition name, case-insensitive). Login-using scripts also read `.env`.

| Script | Inputs | Outputs | Needs login |
|---|---|---|---|
| `src/download_one.py` | `-l`, `-c`, `-r` (round, default 1), `-t` (team, optional) | `data/bronze/.../Formazioni_*_giornata.xlsx` | yes |
| `src/download_all.py` | `-l`, `-c`, `--min-bytes` | every giornata into `data/bronze/.../` | yes |
| `src/build_silver.py` | `-l`, `-c`, `--bronze`, `--silver` | `data/silver/.../{appearances,matches}.csv` | no |
| `src/build_gold.py` | `-l`, `-c`, `--silver`, `--gold` | `data/gold/.../{player_season,team_season,position_rollup,regret}.csv` | no |
| `src/report_team.py` | `-l`, `-c`, `-t` (required), `--silver`, `--reports` | `reports/.../{team}.xlsx` | no |

## Project structure

```
fanalysista/
├── README.md                  this file — overview + quick start
├── requirements.txt
├── .env.example               credentials template (.env is gitignored)
├── .gitignore
│
├── docs/                      project documentation
│   ├── ARCHITECTURE.md        data flow, endpoints, schemas, Mermaid diagrams
│   └── ROADMAP.md             future ideas and open questions
│
├── src/                       all Python source
│   ├── fanta_client.py        HTTP client (login, list comps, download xlsx)
│   ├── parse_formations.py    xlsx → Match records
│   ├── cli.py                 shared argparse + offline folder resolution
│   │
│   ├── download_one.py        ┐
│   ├── download_all.py        │  Bronze layer scripts
│   ├── build_silver.py        │  Bronze → Silver
│   ├── build_gold.py          │  Silver → Gold
│   ├── report_team.py         │  Presentation (xlsx)
│   │
│   └── dashboard/             │  Presentation (Streamlit)
│       ├── app.py
│       ├── data.py            cached loaders + sidebar selector
│       ├── theme.py           shared colour palette
│       ├── modals.py          @st.dialog team/player summary modals
│       ├── ui.py              shared UI helpers (breadcrumbs)
│       └── pages/
│           ├── 1_League_Table.py
│           ├── 2_Team_Detail.py
│           ├── 3_Player_Detail.py
│           ├── 4_Players.py
│           └── 5_Regret.py
│
├── data/                      ← data layers (gitignored, generated)
│   ├── bronze/{league}/{comp}/Formazioni_*_giornata.xlsx
│   ├── silver/{league}/{comp}/{appearances,matches}.csv
│   └── gold/{league}/{comp}/{player_season,team_season,position_rollup,regret}.csv
│
└── reports/                   ← xlsx exports (gitignored, generated)
    └── {league}/{comp}/{team}.xlsx
```

Reserved for future use (not created yet):

- `sql/` — query templates and migrations once we move to a database backend
- `config/` — YAML/TOML for league-specific rules (modules, scoring, captain logic) if/when we generalise beyond Italian Serie A defaults
- `tests/` — pytest suite once the surface stabilises

## Roadmap (short list)

A handful of high-impact items kept here; the full backlog with categorisation and rationale lives in [docs/ROADMAP.md](docs/ROADMAP.md).

- **Regret decomposition** — split per-giornata regret into "bench order" vs "module choice" components.
- **Counterfactual swap explorer** — drill from any player row into "if you'd subbed in X for Y in giornata G, you'd have gained Z".
- **Auction-draft helper** — historical fv contribution per player, suggesting auction values.
- **Multi-season / multi-competition aggregation** — cross-season summaries once more data is downloaded.
- **Database backend** — move bronze/silver/gold from CSV/xlsx on disk to a SQL store; the `sql/` folder is reserved.
- **Tests + CI** — pytest suite covering the parser, gold builders, and the AppTest smoke tests already running locally.

## Implementation notes

- The site does not expose a public API. Endpoints, auth flow, and the `app_key` constant are reverse-engineered from the bundled JS. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for specifics.
- Login response is base64-encoded JSON; the client mirrors the JS decoding logic exactly.
- The "grey-out" signal for inactive players is the cell font color `#D3D3D3` on the player-name cell — used to determine which 11 (or fewer) of the 25 submitted players actually counted toward TOTALE.
- Player names with a trailing `*` (e.g. `Carboni V. *`) indicate the player has left the player pool; the parser normalises these so both forms refer to the same person.
- The medallion layout is the contract: silver CSVs are the source of truth for analysis, gold tables are business-ready aggregates, and the dashboard reads only from gold (with silver as a supporting source for match-level views). Adding a new analysis is usually a function in `src/build_gold.py` plus a page in `src/dashboard/pages/`.

## Why "Fanalysista"?

A portmanteau that works on several levels:

- **Fan…ta** — first three letters + last two = **Fanta**(calcio)
- **…analysis…** sits in the middle
- **…sista** — tail echoes ***Fantasista***, the Italian football term for a creative, imaginative player (Baggio, Totti, Del Piero — the kind of player who sees a game differently)

The goal is exactly that: not just stats, but the analytical lens a Fantacalcio manager would use to make better auction calls, set better formations, and understand why their team performed the way it did — with the imagination of a fantasista.

## License

Personal / educational use. The data fetched from leghe.fantacalcio.it belongs to its respective owners; this project is unaffiliated with Fantacalcio.it. Use responsibly and respect the site's terms of service.
