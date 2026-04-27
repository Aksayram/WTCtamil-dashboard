"""
IPL 2026 Pitch & Bowling Analyzer (Live)
=========================================
Single-season live dashboard for IPL 2026.

Pick a ground (or 'Overall' for league-wide view) and a metric (Economy or
Bowling Effectiveness) from the sidebar. The page shows the metric game-by-game
through the season, then breaks it down by phase (PP / Middle / Death) and by
bowler type (Pace / Spin).

Sections:
  1. KPI strip
  2. Metric per match (one line, per-match values across the season)
  3. Phase split: Powerplay (1–6) / Middle (7–16) / Death (17–20)
  4. Pace vs Spin

Data updates daily — use the 🔄 Refresh data button in the sidebar to clear
the cache and reload the latest Excel file from disk.

Run:
    pip install streamlit pandas numpy plotly openpyxl
    streamlit run pitch_economy_dashboard_2026.py
"""

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# ---------------- PASSWORD ----------------
def check_password():
    def password_entered():
        if st.session_state["password"] == "wtc123":
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("Wrong Password")
        return False
    return True

if not check_password():
    st.stop()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="IPL 2026 Live Pitch Analyzer",
    page_icon="🏏",
    layout="wide",
)

DEFAULT_FILE = "IPL_2026_hg.xlsx"

PHASE_DEFS = {
    "Powerplay (1–6)": (1, 6),
    "Middle (7–16)": (7, 16),
    "Death (17–20)": (17, 20),
}
PHASE_COLORS = {
    "Powerplay (1–6)": "#1f77b4",
    "Middle (7–16)": "#ff7f0e",
    "Death (17–20)": "#d62728",
}

YEAR_COLOR = "#636EFA"  # single-year so one stable colour

# Dismissal types NOT credited to the bowler (excluded from bowling average wickets)
NON_BOWLER_DISMISSALS = {"run out", "retired not out (hurt)", "retired out"}

# Columns the dashboard reads. Note `dismissal` and `daynight` are new vs the
# 2023–25 dashboard.
REQUIRED_COLUMNS = [
    "p_match", "inns", "team_bat", "team_bowl", "ball", "score", "over",
    "noball", "wide", "out", "dismissal", "date", "year", "ground",
    "bowl_kind", "daynight", "winner",
]


# ---------------------------------------------------------------------------
# Loading & enrichment
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading 2026 ball-by-ball data...")
def load_data(path_or_buffer):
    df = pd.read_excel(path_or_buffer, usecols=REQUIRED_COLUMNS)
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"Input file is missing required column(s): {sorted(missing)}"
        )
    df["date"] = pd.to_datetime(df["date"])
    df["total_runs"] = df["score"] + df["wide"] + df["noball"]
    df["legal_ball"] = ((df["wide"] == 0) & (df["noball"] == 0)).astype(int)
    # Bowler-credited wicket: a dismissal that isn't a run-out / retirement
    df["bowler_wicket"] = (
        df["out"].fillna(False).astype(bool)
        & ~df["dismissal"].fillna("").isin(NON_BOWLER_DISMISSALS)
    ).astype(int)
    # Normalise daynight values.
    # The source uses values like "night match" (pure evening game under lights)
    # and "day/night match" (afternoon game that starts in daylight, finishes
    # under lights). For the filter, "day/night match" -> Day, "night match" -> Night.
    raw = df["daynight"].astype(str).str.strip().str.lower()
    df["session"] = np.where(
        raw.str.startswith("day"), "Day",
        np.where(raw.str.startswith("night"), "Night", "Night"),
    )
    return df


def filter_innings(df: pd.DataFrame, innings_filter: str) -> pd.DataFrame:
    if innings_filter == "1st innings only":
        return df[df["inns"] == 1]
    if innings_filter == "2nd innings only":
        return df[df["inns"] == 2]
    return df


def filter_session(df: pd.DataFrame, session_filter: str) -> pd.DataFrame:
    if session_filter == "Both":
        return df
    label = session_filter.replace(" only", "")
    return df[df["session"] == label]


def compute_bowling_stats(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    """
    Compute economy AND bowling average for arbitrary grouping.

      economy = runs / overs
      avg     = runs / wickets (NaN if 0 wickets)
    """
    g = (
        df.groupby(group_cols, as_index=False)
        .agg(
            total_runs=("total_runs", "sum"),
            legal_balls=("legal_ball", "sum"),
            wickets=("bowler_wicket", "sum"),
        )
    )
    g["overs"] = g["legal_balls"] / 6.0
    g["economy"] = np.where(g["overs"] > 0, g["total_runs"] / g["overs"], np.nan)
    g["bowling_avg"] = np.where(
        g["wickets"] > 0, g["total_runs"] / g["wickets"], np.nan
    )
    return g


def assign_match_seq(match_df: pd.DataFrame) -> pd.DataFrame:
    """Chronological match sequence number; resets at 1."""
    out = match_df.sort_values(["date", "p_match"]).reset_index(drop=True)
    out["match_num"] = range(1, len(out) + 1)
    return out


@st.cache_data
def match_meta(df: pd.DataFrame) -> pd.DataFrame:
    """Per-match metadata for hover tooltips: matchup, runs, ground, winner."""
    # Build matchup from union of team_bat and team_bowl per match — covers
    # rain-shortened games where only one innings was played.
    teams_long = pd.concat([
        df[["p_match", "team_bat"]].rename(columns={"team_bat": "team"}),
        df[["p_match", "team_bowl"]].rename(columns={"team_bowl": "team"}),
    ]).drop_duplicates()
    matchup = (
        teams_long.dropna(subset=["team"])
        .groupby("p_match")["team"]
        .apply(lambda s: " vs ".join(sorted(s.unique())))
        .reset_index(name="matchup")
    )
    runs = df.groupby("p_match")["total_runs"].sum().reset_index(name="match_runs")
    grounds = df[["p_match", "ground"]].drop_duplicates()
    winners = df[["p_match", "winner"]].drop_duplicates()
    return (
        matchup.merge(runs, on="p_match")
        .merge(grounds, on="p_match")
        .merge(winners, on="p_match")
    )


# ---------------------------------------------------------------------------
# Verdict helpers — same idea as 2023-25 dashboard but adapted for:
#   - single season (no cross-year comparisons)
#   - either economy OR bowling_avg as the metric
# ---------------------------------------------------------------------------
def _trend_word(delta: float, threshold: float = 0.3) -> str:
    if delta <= -threshold:
        return "dropped"
    if delta >= threshold:
        return "rose"
    return "held flat"


def _trisect_means(series: pd.Series) -> tuple:
    """Return (early, mid, late) means by splitting the series into thirds."""
    s = series.dropna()
    n = len(s)
    if n < 3:
        m = s.mean() if n else float("nan")
        return (m, m, m)
    third = n // 3
    return (
        s.iloc[:third].mean(),
        s.iloc[third:2 * third].mean(),
        s.iloc[2 * third:].mean(),
    )


def _direction_label(metric: str, delta: float) -> tuple:
    """
    Map a numeric delta to (direction_word, is_good_for_bowlers).

    For ECONOMY:   lower = better for bowlers.   "dropped" => bowler-friendly.
    For BOWLING AVG: lower = better for bowlers. "dropped" => bowler-friendly.
    Both metrics share the same directionality, so this is symmetric — but I'm
    keeping the function in case we add more metrics later.
    """
    word = _trend_word(delta)
    is_bowler_friendly = (word == "dropped")
    return word, is_bowler_friendly


def verdict_overall(match_df: pd.DataFrame, metric: str, metric_label: str) -> str:
    """Verdict for the per-match line chart."""
    sub = match_df.dropna(subset=[metric]).sort_values("match_num")
    if len(sub) < 3:
        return "_Not enough games yet to summarise._"

    early, _, late = _trisect_means(sub[metric])
    delta = late - early
    word, bowler_friendly = _direction_label(metric, delta)
    avg = sub[metric].mean()

    median_val = sub[metric].median()
    sub_dev = sub.assign(dev=sub[metric] - median_val)
    big_dip = sub_dev.loc[sub_dev["dev"].idxmin()]
    big_spike = sub_dev.loc[sub_dev["dev"].idxmax()]

    lines = []

    # Line 1: trend
    if word == "held flat":
        lines.append(f"**{metric_label}** held flat at ~{avg:.2f} across the season so far.")
    else:
        lines.append(
            f"**{metric_label}** {word} from {early:.2f} → {late:.2f} "
            f"({delta:+.2f}) between the early and late portion of games played."
        )

    # Line 2: highlight games
    if metric == "economy":
        lines.append(
            f"Slowest game (lowest economy): game #{int(big_dip['match_num'])} "
            f"({big_dip[metric]:.2f} rpo, {big_dip.get('matchup','—')}). "
            f"Highest scoring: game #{int(big_spike['match_num'])} "
            f"({big_spike[metric]:.2f} rpo)."
        )
    else:
        # For bowling avg, a dip is good for bowlers (low avg = effective)
        lines.append(
            f"Most bowler-effective game: game #{int(big_dip['match_num'])} "
            f"({big_dip[metric]:.2f} runs/wkt, {big_dip.get('matchup','—')}). "
            f"Worst for bowlers: game #{int(big_spike['match_num'])} "
            f"({big_spike[metric]:.2f} runs/wkt)."
        )

    # Line 3: verdict
    if word == "held flat":
        lines.append(
            f"⚖️ **Stable so far** — {metric_label.lower()} hasn't shifted "
            "meaningfully as the season has progressed."
        )
    elif bowler_friendly:
        lines.append(
            f"🔻 **Bowler-friendly drift** — {metric_label.lower()} is moving "
            "in bowlers' favour as more games are played."
        )
    else:
        lines.append(
            f"🔺 **Batter-friendly drift** — {metric_label.lower()} is rising, "
            "suggesting surfaces are flattening or batters are adapting."
        )
    return "\n\n".join(lines)


def verdict_phase(phase_df: pd.DataFrame, metric: str, metric_label: str) -> str:
    """Verdict for the phase split chart."""
    sub = phase_df.dropna(subset=[metric])
    if sub.empty:
        return "_No phase data yet._"

    phase_trends = {}
    for phase_name, ph in sub.groupby("phase"):
        ph = ph.sort_values("match_num")
        if len(ph) < 3:
            continue
        early, _, late = _trisect_means(ph[metric])
        phase_trends[phase_name] = {
            "early": early, "late": late,
            "delta": late - early,
            "avg": ph[metric].mean(),
            "word": _trend_word(late - early),
        }

    if not phase_trends:
        return "_Not enough games per phase yet._"

    bits = []
    for phase_name, t in phase_trends.items():
        short = phase_name.split(" ")[0]
        if t["word"] == "held flat":
            bits.append(f"**{short}** flat (~{t['avg']:.2f})")
        else:
            bits.append(f"**{short}** {t['word']} {t['delta']:+.2f}")
    lines = [" · ".join(bits)]

    avgs = sorted(
        ((name, t["avg"]) for name, t in phase_trends.items()),
        key=lambda x: x[1], reverse=(metric == "economy"),
    )
    # For economy: highest = most expensive. For avg: highest = worst for bowlers.
    if len(avgs) >= 2:
        if metric == "economy":
            lines.append(
                f"Most expensive phase: **{avgs[0][0].split(' ')[0]}** "
                f"({avgs[0][1]:.2f} rpo). Cheapest: **{avgs[-1][0].split(' ')[0]}** "
                f"({avgs[-1][1]:.2f} rpo)."
            )
        else:
            lines.append(
                f"Worst phase for bowlers: **{avgs[0][0].split(' ')[0]}** "
                f"({avgs[0][1]:.2f} runs/wkt). Most effective: "
                f"**{avgs[-1][0].split(' ')[0]}** ({avgs[-1][1]:.2f} runs/wkt)."
            )

    pp = phase_trends.get("Powerplay (1–6)")
    mid = phase_trends.get("Middle (7–16)")
    death = phase_trends.get("Death (17–20)")

    if pp and mid and death:
        if mid["word"] == "dropped" and pp["word"] != "dropped":
            lines.append(
                f"🎯 **Spinner-grip signal:** middle-overs {metric_label.lower()} "
                "got better for bowlers while powerplay held — surfaces gripping "
                "more for spin as the season progresses."
            )
        elif death["word"] == "dropped" and mid["word"] != "dropped":
            lines.append(
                f"🎯 **Death-overs squeeze:** late-innings {metric_label.lower()} "
                "improved for bowlers while middle held — finishers struggling "
                "to hit through slower surfaces."
            )
        elif all(t["word"] == "dropped" for t in (pp, mid, death)):
            lines.append(
                f"🎯 **Across-the-board bowler shift:** every phase tightened. "
                "Surfaces favouring bowlers more as more games are played."
            )
        elif all(t["word"] == "rose" for t in (pp, mid, death)):
            lines.append(
                f"🎯 **No bowler-friendly trend.** All phases moved in batters' "
                "favour as the season went on."
            )
        else:
            lines.append(
                "🎯 **Mixed phase behaviour** — no single phase is driving "
                "the overall trend."
            )

    return "\n\n".join(lines)


def verdict_pace_spin(ps_df: pd.DataFrame, metric: str, metric_label: str) -> str:
    """Verdict for the pace vs spin chart."""
    sub = ps_df.dropna(subset=[metric])
    pace = sub[sub["bowler_type"] == "Pace"].sort_values("match_num")
    spin = sub[sub["bowler_type"] == "Spin"].sort_values("match_num")
    if len(pace) < 3 or len(spin) < 3:
        return "_Not enough games yet for pace/spin analysis._"

    pace_e, _, pace_l = _trisect_means(pace[metric])
    spin_e, _, spin_l = _trisect_means(spin[metric])
    pace_delta = pace_l - pace_e
    spin_delta = spin_l - spin_e
    pace_avg = pace[metric].mean()
    spin_avg = spin[metric].mean()

    def _phrase(name, early, late, delta):
        word = _trend_word(delta)
        if word == "held flat":
            return f"**{name}** held flat ({early:.2f} → {late:.2f})"
        return f"**{name}** {word} {delta:+.2f} ({early:.2f} → {late:.2f})"

    lines = [
        f"{_phrase('Pace', pace_e, pace_l, pace_delta)} · "
        f"{_phrase('Spin', spin_e, spin_l, spin_delta)}"
    ]

    # Cheaper / more effective overall
    if abs(pace_avg - spin_avg) < (0.2 if metric == "economy" else 2.0):
        if metric == "economy":
            lines.append(
                f"Pace and spin pricing roughly the same overall "
                f"(~{pace_avg:.2f} vs ~{spin_avg:.2f} rpo)."
            )
        else:
            lines.append(
                f"Pace and spin equally effective overall "
                f"(~{pace_avg:.1f} vs ~{spin_avg:.1f} runs/wkt)."
            )
    else:
        better = "Spin" if spin_avg < pace_avg else "Pace"
        b_avg = min(pace_avg, spin_avg)
        w_avg = max(pace_avg, spin_avg)
        unit = "rpo" if metric == "economy" else "runs/wkt"
        label = "more economical" if metric == "economy" else "more effective"
        lines.append(f"**{better}** is {label} overall ({b_avg:.2f} vs {w_avg:.2f} {unit}).")

    pace_word = _trend_word(pace_delta)
    spin_word = _trend_word(spin_delta)

    if pace_word == "dropped" and spin_word != "dropped":
        lines.append(
            f"⚡ **Pace-friendly drift:** pacers improving while spinners "
            f"hold steady — pitches firming up / new ball doing more."
        )
    elif spin_word == "dropped" and pace_word != "dropped":
        lines.append(
            f"🌀 **Spin-friendly drift:** spinners getting better while "
            f"pace holds steady — surfaces gripping more for spin."
        )
    elif pace_word == "dropped" and spin_word == "dropped":
        lines.append(
            "🔻 **Bowlers gaining on both fronts** — pace and spin both improving. "
            "Surfaces favouring bowlers across the board."
        )
    elif pace_word == "rose" and spin_word == "rose":
        lines.append(
            "🔺 **Batter-friendly drift:** pace and spin both leaking more as "
            "the season progresses — surfaces flattening for both bowler types."
        )
    else:
        lines.append(
            "⚖️ **No clear shift** — pace and spin within normal noise so far. "
            "Pitch behaviour roughly stable."
        )

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("⚙️ Filters")

if st.sidebar.button("🔄 Refresh data", use_container_width=True,
                     help="Clears cache and reloads the latest Excel file."):
    st.cache_data.clear()
    st.rerun()

try:
    raw_df = load_data(DEFAULT_FILE)
except FileNotFoundError:
    st.error(
        f"Could not find `{DEFAULT_FILE}`. "
        "Make sure the data file is in the same directory as this script."
    )
    st.stop()

last_updated = raw_df["date"].max()
st.sidebar.caption(f"Latest match in data: **{last_updated.strftime('%d %b %Y')}**")
st.sidebar.divider()

OVERALL_LABEL = "🌐 Overall (all grounds)"
all_grounds = sorted(raw_df["ground"].unique().tolist())
ground_options = [OVERALL_LABEL] + all_grounds
ground = st.sidebar.selectbox(
    "Ground", ground_options, index=0,
    help="Pick one ground for venue-specific analysis, or 'Overall' for the league.",
)
is_overall = (ground == OVERALL_LABEL)

# --- Metric toggle (the new bit)
METRIC_OPTIONS = {
    "Economy (runs/over)": ("economy", "Economy", "rpo"),
    "Bowling Effectiveness (runs/wkt)": ("bowling_avg", "Bowling avg", "runs/wkt"),
}
metric_choice = st.sidebar.radio(
    "Metric",
    list(METRIC_OPTIONS.keys()),
    index=0,
    help=("Economy = runs conceded per over (lower = bowler-friendly).  "
          "Bowling Effectiveness = runs conceded per wicket; lower = more effective. "
          "Games where 0 wickets fell in scope are dropped from the line."),
)
METRIC_KEY, METRIC_LABEL, METRIC_UNIT = METRIC_OPTIONS[metric_choice]

innings_filter = st.sidebar.radio(
    "Innings",
    ["Combined", "1st innings only", "2nd innings only"],
    index=0,
    help="1st innings is usually the cleanest pitch signal (no dew / chasing pressure).",
)

session_filter = st.sidebar.radio(
    "Session",
    ["Both", "Day only", "Night only"],
    index=0,
    help=("Uses the official `daynight` column. "
          "**Day** = afternoon games that start in daylight (`day/night match` "
          "in source data, ~3:30 PM start). **Night** = pure evening games "
          "under lights (~7:30 PM start)."),
)

# ---------------------------------------------------------------------------
# Filter universe
# ---------------------------------------------------------------------------
work = raw_df.copy() if is_overall else raw_df[raw_df["ground"] == ground].copy()
work = filter_innings(work, innings_filter)
work = filter_session(work, session_filter)

if work.empty:
    st.title("🏏 IPL 2026 Live Pitch Analyzer")
    st.warning("No data for this combination. Try widening the filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏏 IPL 2026 Live Pitch Analyzer")
ground_label = "All grounds" if is_overall else ground.split(",")[0]
st.caption(
    f"**{ground_label}** · Metric: **{METRIC_LABEL}** · "
    f"Innings: {innings_filter} · Session: {session_filter}"
)

# ---------------------------------------------------------------------------
# 1. KPI strip
# ---------------------------------------------------------------------------
match_stats = compute_bowling_stats(work, ["p_match", "date"])
match_stats = assign_match_seq(match_stats)
meta = match_meta(raw_df)
match_stats = match_stats.merge(meta, on="p_match", how="left")

# Drop rows where the chosen metric is NaN (i.e., 0 wickets for bowling avg)
plottable = match_stats.dropna(subset=[METRIC_KEY])

n_games = match_stats["p_match"].nunique()
games_label = "Games (all grounds)" if is_overall else "Games at this ground"

c1, c2, c3, c4 = st.columns(4)
c1.metric(games_label, f"{n_games}")
if not plottable.empty:
    avg_val = plottable[METRIC_KEY].mean()
    high_row = plottable.loc[plottable[METRIC_KEY].idxmax()]
    low_row = plottable.loc[plottable[METRIC_KEY].idxmin()]
    c2.metric(f"Avg {METRIC_LABEL.lower()}", f"{avg_val:.2f}")
    c3.metric(f"Highest {METRIC_LABEL.lower()}", f"{high_row[METRIC_KEY]:.2f}",
              help=f"{high_row['date'].strftime('%d %b %Y')}")
    c4.metric(f"Lowest {METRIC_LABEL.lower()}", f"{low_row[METRIC_KEY]:.2f}",
              help=f"{low_row['date'].strftime('%d %b %Y')}")
else:
    c2.metric(f"Avg {METRIC_LABEL.lower()}", "—")
    c3.metric("Highest", "—")
    c4.metric("Lowest", "—")

st.divider()

# ---------------------------------------------------------------------------
# 2. Metric per match
# ---------------------------------------------------------------------------
st.subheader(f"📈 {METRIC_LABEL} per match")
if METRIC_KEY == "economy":
    st.caption(
        "Each dot is one match's bowling economy. Faint horizontal line is the "
        "season average so far — dips below it are slower-than-typical games."
    )
else:
    st.caption(
        "Each dot is one match's bowling average (runs per wicket). Lower is "
        "better for bowlers. Games with 0 wickets in scope are skipped. "
        "Faint horizontal line is the season average so far."
    )

fig_overall = go.Figure()

if not plottable.empty:
    sub = plottable.sort_values("match_num")

    if is_overall:
        custom = np.stack([
            sub["date"].dt.strftime("%d %b %Y"),
            sub["matchup"],
            sub["winner"].fillna("—"),
            sub["total_runs"],
            sub["overs"].round(1),
            sub["wickets"],
            sub["ground"].apply(lambda g: g.split(",")[0]),
        ], axis=-1)
        hover = (
            "<b>Game %{x}</b><br>"
            f"{METRIC_LABEL}: %{{y:.2f}} {METRIC_UNIT}<br>"
            "Date: %{customdata[0]}<br>"
            "Match: %{customdata[1]}<br>"
            "Winner: %{customdata[2]}<br>"
            "Ground: %{customdata[6]}<br>"
            "Runs: %{customdata[3]} in %{customdata[4]} overs · "
            "Wkts: %{customdata[5]}<extra></extra>"
        )
    else:
        custom = np.stack([
            sub["date"].dt.strftime("%d %b %Y"),
            sub["matchup"],
            sub["winner"].fillna("—"),
            sub["total_runs"],
            sub["overs"].round(1),
            sub["wickets"],
        ], axis=-1)
        hover = (
            "<b>Game %{x}</b><br>"
            f"{METRIC_LABEL}: %{{y:.2f}} {METRIC_UNIT}<br>"
            "Date: %{customdata[0]}<br>"
            "Match: %{customdata[1]}<br>"
            "Winner: %{customdata[2]}<br>"
            "Runs: %{customdata[3]} in %{customdata[4]} overs · "
            "Wkts: %{customdata[5]}<extra></extra>"
        )

    fig_overall.add_trace(go.Scatter(
        x=sub["match_num"], y=sub[METRIC_KEY],
        mode="lines+markers",
        name="2026",
        line=dict(color=YEAR_COLOR, width=2.5),
        marker=dict(size=9 if not is_overall else 6),
        customdata=custom,
        hovertemplate=hover,
    ))

    avg_v = sub[METRIC_KEY].mean()
    fig_overall.add_hline(
        y=avg_v,
        line=dict(color=YEAR_COLOR, width=1, dash="dot"),
        opacity=0.5,
        annotation_text=f"Season avg: {avg_v:.2f}",
        annotation_position="right",
        annotation_font_color=YEAR_COLOR,
        annotation_font_size=10,
    )

xaxis_dtick = 5 if is_overall else 1
fig_overall.update_layout(
    xaxis_title="Match number (chronological)",
    yaxis_title=f"{METRIC_LABEL} ({METRIC_UNIT})",
    hovermode="closest",
    height=460,
    showlegend=False,
    xaxis=dict(dtick=xaxis_dtick),
)
st.plotly_chart(fig_overall, use_container_width=True)

with st.container(border=True):
    st.markdown("**📋 Verdict**")
    st.markdown(verdict_overall(match_stats, METRIC_KEY, METRIC_LABEL))

st.divider()

# ---------------------------------------------------------------------------
# 3. Phase split
# ---------------------------------------------------------------------------
st.subheader(f"🎯 Phase split — {METRIC_LABEL} by Powerplay / Middle / Death")
st.caption(
    "Same matches, split by phase. Compare how each phase has trended through "
    "the season — the phase moving the most tells you where pitch behaviour "
    "is shifting."
)

work_phased = work.copy()
def _phase_for_over(o):
    for name, (lo, hi) in PHASE_DEFS.items():
        if lo <= o <= hi:
            return name
    return None
work_phased["phase"] = work_phased["over"].apply(_phase_for_over)
work_phased = work_phased.dropna(subset=["phase"])

phase_stats = compute_bowling_stats(work_phased, ["p_match", "date", "phase"])
phase_stats = phase_stats.merge(
    match_stats[["p_match", "match_num"]], on="p_match", how="left"
)

phase_xaxis_dtick = 5 if is_overall else 1
fig_phase = go.Figure()
for phase_name in PHASE_DEFS.keys():
    ph = (
        phase_stats[phase_stats["phase"] == phase_name]
        .dropna(subset=[METRIC_KEY])
        .sort_values("match_num")
    )
    if ph.empty:
        continue
    fig_phase.add_trace(go.Scatter(
        x=ph["match_num"], y=ph[METRIC_KEY],
        mode="lines+markers",
        name=phase_name,
        line=dict(color=PHASE_COLORS[phase_name], width=2.5),
        marker=dict(size=7 if is_overall else 8),
        hovertemplate=(
            f"<b>{phase_name}</b><br>"
            "Game %{x}<br>"
            f"{METRIC_LABEL}: %{{y:.2f}} {METRIC_UNIT}<extra></extra>"
        ),
    ))
fig_phase.update_layout(
    xaxis_title="Match number (chronological)",
    yaxis_title=f"{METRIC_LABEL} ({METRIC_UNIT})",
    height=460,
    hovermode="x unified",
    legend_title="Phase",
    xaxis=dict(dtick=phase_xaxis_dtick),
)
st.plotly_chart(fig_phase, use_container_width=True)

with st.container(border=True):
    st.markdown("**📋 Verdict**")
    st.markdown(verdict_phase(phase_stats, METRIC_KEY, METRIC_LABEL))

st.divider()

# ---------------------------------------------------------------------------
# 4. Pace vs Spin
# ---------------------------------------------------------------------------
st.subheader(f"⚡ Pace vs Spin — {METRIC_LABEL} per match")
st.caption(
    "Same matches, split by bowler type. Diverging lines tell the story: "
    "if pace improves while spin holds, surfaces are firming up; if spin "
    "improves while pace holds, surfaces are gripping for spin."
)

ps_work = work[work["bowl_kind"].isin(["pace bowler", "spin bowler"])].copy()
ps_stats = compute_bowling_stats(ps_work, ["p_match", "date", "bowl_kind"])
ps_stats = ps_stats.merge(
    match_stats[["p_match", "match_num"]], on="p_match", how="left"
)
ps_stats["bowler_type"] = ps_stats["bowl_kind"].map(
    {"pace bowler": "Pace", "spin bowler": "Spin"}
)

fig_ps = go.Figure()
style_map = {"Pace": ("#3366CC", "solid"), "Spin": ("#DC3912", "dash")}
for bt in ["Pace", "Spin"]:
    s = (
        ps_stats[ps_stats["bowler_type"] == bt]
        .dropna(subset=[METRIC_KEY])
        .sort_values("match_num")
    )
    if s.empty:
        continue
    color, dash = style_map[bt]
    fig_ps.add_trace(go.Scatter(
        x=s["match_num"], y=s[METRIC_KEY],
        mode="lines+markers",
        name=bt,
        line=dict(color=color, width=2.5, dash=dash),
        marker=dict(size=8 if is_overall else 9),
        hovertemplate=(
            f"<b>{bt}</b><br>"
            "Game %{x}<br>"
            f"{METRIC_LABEL}: %{{y:.2f}} {METRIC_UNIT}<extra></extra>"
        ),
    ))
fig_ps.update_layout(
    xaxis_title="Match number (chronological)",
    yaxis_title=f"{METRIC_LABEL} ({METRIC_UNIT})",
    height=460,
    legend_title="Bowler type",
    hovermode="x unified",
    xaxis=dict(dtick=phase_xaxis_dtick),
)
st.plotly_chart(fig_ps, use_container_width=True)

# Quick season summary table
st.markdown("**Pace vs Spin — season summary**")
ps_summary = (
    ps_stats.groupby("bowler_type")
    .agg(
        avg_economy=("economy", "mean"),
        avg_bowling=("bowling_avg", "mean"),
        wickets=("wickets", "sum"),
    )
    .round(2)
)
ps_summary.columns = ["Avg economy", "Avg bowling avg", "Total wickets"]
st.dataframe(ps_summary, use_container_width=True)

with st.container(border=True):
    st.markdown("**📋 Verdict**")
    st.markdown(verdict_pace_spin(ps_stats, METRIC_KEY, METRIC_LABEL))

st.divider()

# ---------------------------------------------------------------------------
# Raw data
# ---------------------------------------------------------------------------
with st.expander("Show match-level raw data"):
    cols = ["match_num", "date", "p_match", "matchup", "winner"]
    if is_overall:
        cols.append("ground")
    cols += ["total_runs", "overs", "wickets", "economy", "bowling_avg"]
    show = match_stats[cols].copy()
    show["date"] = show["date"].dt.strftime("%d %b %Y")
    show["economy"] = show["economy"].round(2)
    show["bowling_avg"] = show["bowling_avg"].round(2)
    show["overs"] = show["overs"].round(1)
    if is_overall and "ground" in show.columns:
        show["ground"] = show["ground"].apply(lambda g: g.split(",")[0])
    show = show.sort_values("match_num")
    st.dataframe(show, use_container_width=True, hide_index=True)

st.caption(
    "Economy includes wides & no-balls in runs; overs use legal balls only. "
    "Bowling average excludes run-outs and retirements (non-bowler dismissals). "
    f"Latest data point: {last_updated.strftime('%d %b %Y')}."
)
