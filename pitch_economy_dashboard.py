"""
IPL Pitch Slowdown Analyzer (2023–2025)
========================================
Pick ONE ground and ONE or MORE years from the sidebar. The page shows
economy game-by-game at that ground, with each year as its own line
(resetting at game #1 each season).

Sections (top to bottom, single page, no tabs):
  1. KPI strip
  2. Overall economy per match (line per year) + auto verdict
  3. Phase split: Powerplay (1–6) / Middle (7–16) / Death (17–20) + auto verdict
  4. Pace vs Spin economy per match + auto verdict

Run:
    pip install streamlit pandas numpy plotly openpyxl
    streamlit run pitch_economy_dashboard.py
"""

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="IPL Pitch Slowdown Analyzer",
    page_icon="🏏",
    layout="wide",
)

DEFAULT_FILE = "IPL_2023_to_2025_Base_Data.xlsx"

YEAR_COLORS = {2023: "#636EFA", 2024: "#EF553B", 2025: "#00CC96"}

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


# ---------------------------------------------------------------------------
# Loading & enrichment
# ---------------------------------------------------------------------------
# Columns the dashboard actually consumes. Listed here so a schema change
# upstream fails loudly at load time instead of silently deep in a chart.
REQUIRED_COLUMNS = [
    "p_match",      # match identifier — also used to order doubleheaders
    "inns",         # 1 or 2 — innings filter
    "team_bat",     # for the "Team A vs Team B" hover tooltip
    "ball",         # ball number within the over (kept for future use / sanity)
    "score",        # runs off the bat for this delivery
    "over",         # over number — drives phase split
    "noball",       # 1 if no-ball, else 0 — extras + legal-ball logic
    "wide",         # wide runs — extras + legal-ball logic
    "date",         # match date — chronological ordering, hover, D/N heuristic
    "year",         # season — sidebar filter, line colour
    "ground",       # venue — sidebar filter
    "bowl_kind",    # 'pace bowler' / 'spin bowler' — pace vs spin section
]


@st.cache_data(show_spinner="Loading ball-by-ball data...")
def load_data(path_or_buffer):
    df = pd.read_excel(path_or_buffer, usecols=REQUIRED_COLUMNS)
    # Verify all required columns arrived (pandas silently ignores missing
    # names in usecols when the file lacks them, so check explicitly)
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"Input file is missing required column(s): {sorted(missing)}"
        )
    df["date"] = pd.to_datetime(df["date"])
    df["total_runs"] = df["score"] + df["wide"] + df["noball"]
    df["legal_ball"] = ((df["wide"] == 0) & (df["noball"] == 0)).astype(int)
    return df


@st.cache_data
def classify_day_night(df: pd.DataFrame) -> pd.DataFrame:
    """
    Heuristic day/night classification — the dataset has no time-of-day column.
      - Doubleheader date (2 matches same day): lower p_match ID = Day,
        higher = Night.
      - Single-match date: classified as Night (standard IPL evening slot).
    """
    matches = (
        df[["p_match", "date"]]
        .drop_duplicates()
        .sort_values(["date", "p_match"])
        .reset_index(drop=True)
    )
    matches["rank_in_day"] = matches.groupby("date").cumcount()
    matches["matches_in_day"] = matches.groupby("date")["p_match"].transform("count")
    matches["session"] = np.where(
        matches["matches_in_day"] == 2,
        np.where(matches["rank_in_day"] == 0, "Day", "Night"),
        "Night",
    )
    return matches[["p_match", "session"]]


def filter_innings(df: pd.DataFrame, innings_filter: str) -> pd.DataFrame:
    if innings_filter == "1st innings only":
        return df[df["inns"] == 1]
    if innings_filter == "2nd innings only":
        return df[df["inns"] == 2]
    return df


def filter_session(df: pd.DataFrame, session_filter: str, sessions: pd.DataFrame) -> pd.DataFrame:
    if session_filter == "Both":
        return df
    label = session_filter.replace(" only", "")
    keep = sessions[sessions["session"] == label]["p_match"]
    return df[df["p_match"].isin(keep)]


def compute_economy(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    g = (
        df.groupby(group_cols, as_index=False)
        .agg(total_runs=("total_runs", "sum"),
             legal_balls=("legal_ball", "sum"))
    )
    g["overs"] = g["legal_balls"] / 6.0
    g["economy"] = np.where(g["overs"] > 0, g["total_runs"] / g["overs"], np.nan)
    return g


def assign_match_seq_within_year(match_df: pd.DataFrame) -> pd.DataFrame:
    """Match sequence resets at 1 each season so years compare directly."""
    out = match_df.sort_values(["year", "date", "p_match"]).reset_index(drop=True)
    out["match_num"] = out.groupby("year").cumcount() + 1
    return out


@st.cache_data
def match_meta(df: pd.DataFrame) -> pd.DataFrame:
    """Per-match metadata for hover tooltips: matchup, total runs, ground."""
    teams = (
        df.groupby("p_match")["team_bat"]
        .apply(lambda s: " vs ".join(sorted(s.unique())))
        .reset_index(name="matchup")
    )
    runs = df.groupby("p_match")["total_runs"].sum().reset_index(name="match_runs")
    grounds = df[["p_match", "ground"]].drop_duplicates()
    return teams.merge(runs, on="p_match").merge(grounds, on="p_match")


# ---------------------------------------------------------------------------
# Verdict generators — rule-based plain English summaries of each chart.
# Each one takes the same dataframe the chart uses and returns a markdown
# string of 2–4 short lines.
# ---------------------------------------------------------------------------
def _trend_word(delta: float, threshold: float = 0.3) -> str:
    """Map a numeric change to a direction word."""
    if delta <= -threshold:
        return "dropped"
    if delta >= threshold:
        return "rose"
    return "held flat"


def _trisect_means(series: pd.Series) -> tuple:
    """Split a series into thirds and return (early, mid, late) means."""
    n = len(series)
    if n < 3:
        return (series.mean(), series.mean(), series.mean())
    third = n // 3
    early = series.iloc[:third].mean()
    mid = series.iloc[third:2 * third].mean()
    late = series.iloc[2 * third:].mean()
    return (early, mid, late)


def verdict_overall(match_econ: pd.DataFrame) -> str:
    """Verdict for the 'Economy per match' chart."""
    lines = []
    season_summaries = []
    for yr, sub in match_econ.groupby("year"):
        sub = sub.sort_values("match_num")
        if len(sub) < 3:
            continue
        early, _, late = _trisect_means(sub["economy"])
        delta = late - early
        word = _trend_word(delta)
        # Find biggest single-game outlier vs season median
        median_econ = sub["economy"].median()
        sub_dev = sub.assign(dev=sub["economy"] - median_econ)
        big_dip = sub_dev.loc[sub_dev["dev"].idxmin()]
        big_spike = sub_dev.loc[sub_dev["dev"].idxmax()]

        season_summaries.append({
            "year": yr,
            "n": len(sub),
            "early": early,
            "late": late,
            "delta": delta,
            "word": word,
            "avg": sub["economy"].mean(),
            "dip_game": int(big_dip["match_num"]),
            "dip_econ": big_dip["economy"],
            "dip_match": big_dip.get("matchup", "—"),
            "spike_game": int(big_spike["match_num"]),
            "spike_econ": big_spike["economy"],
        })

    if not season_summaries:
        return "_Not enough games to summarise._"

    # Line 1: per-season trend
    trend_bits = []
    for s in season_summaries:
        if s["word"] == "held flat":
            trend_bits.append(
                f"**{s['year']}** held flat at ~{s['avg']:.2f} rpo"
            )
        else:
            trend_bits.append(
                f"**{s['year']}** {s['word']} from {s['early']:.2f} → "
                f"{s['late']:.2f} rpo ({s['delta']:+.2f})"
            )
    lines.append(" · ".join(trend_bits))

    # Line 2: cross-season comparison if more than one
    if len(season_summaries) > 1:
        hottest = max(season_summaries, key=lambda s: s["avg"])
        coldest = min(season_summaries, key=lambda s: s["avg"])
        if hottest["year"] != coldest["year"]:
            lines.append(
                f"Highest scoring season overall: **{hottest['year']}** "
                f"({hottest['avg']:.2f} rpo). Lowest: **{coldest['year']}** "
                f"({coldest['avg']:.2f} rpo)."
            )

    # Line 3: notable single game (biggest dip across all seasons shown)
    biggest_dip = min(season_summaries, key=lambda s: s["dip_econ"])
    lines.append(
        f"Slowest game in scope: {biggest_dip['year']} game "
        f"#{biggest_dip['dip_game']} ({biggest_dip['dip_econ']:.2f} rpo, "
        f"{biggest_dip['dip_match']})."
    )

    # Line 4: verdict on the slowdown hypothesis
    declining = [s for s in season_summaries if s["word"] == "dropped"]
    rising = [s for s in season_summaries if s["word"] == "rose"]
    if len(declining) == len(season_summaries) and len(declining) > 1:
        lines.append(
            "🔻 **Slowdown signal: consistent.** Every season in scope shows "
            "economy declining as games progress."
        )
    elif len(rising) == len(season_summaries) and len(rising) > 1:
        lines.append(
            "🔺 **No slowdown.** Every season shows economy rising as games "
            "progress — surfaces flattening, not slowing."
        )
    elif declining and rising:
        d_yrs = ", ".join(str(s["year"]) for s in declining)
        r_yrs = ", ".join(str(s["year"]) for s in rising)
        lines.append(
            f"⚖️ **Mixed signal.** Slowdown in {d_yrs}; surfaces sped up in "
            f"{r_yrs}. Not a consistent year-over-year pattern."
        )

    return "\n\n".join(lines)


def verdict_phase(phase_econ: pd.DataFrame) -> str:
    """Verdict for the 'Phase split' chart."""
    if phase_econ.empty:
        return "_No phase data in scope._"

    lines = []
    # Per phase: trend across the season (averaged across years if multiple)
    phase_trends = {}
    for phase_name, sub in phase_econ.groupby("phase"):
        sub = sub.sort_values("match_num")
        if len(sub) < 3:
            continue
        early, _, late = _trisect_means(sub["economy"])
        phase_trends[phase_name] = {
            "early": early,
            "late": late,
            "delta": late - early,
            "avg": sub["economy"].mean(),
            "word": _trend_word(late - early),
        }

    if not phase_trends:
        return "_Not enough games for phase analysis._"

    # Line 1: each phase's trend
    bits = []
    for phase_name, t in phase_trends.items():
        short = phase_name.split(" ")[0]  # "Powerplay" / "Middle" / "Death"
        if t["word"] == "held flat":
            bits.append(f"**{short}** flat (~{t['avg']:.2f})")
        else:
            bits.append(f"**{short}** {t['word']} {t['delta']:+.2f}")
    lines.append(" · ".join(bits))

    # Line 2: overall scoring level by phase
    avgs = [(name, t["avg"]) for name, t in phase_trends.items()]
    avgs.sort(key=lambda x: x[1], reverse=True)
    if len(avgs) >= 2:
        lines.append(
            f"Most expensive phase: **{avgs[0][0].split(' ')[0]}** "
            f"({avgs[0][1]:.2f} rpo). Cheapest: **{avgs[-1][0].split(' ')[0]}** "
            f"({avgs[-1][1]:.2f} rpo)."
        )

    # Line 3: interpretive verdict
    pp = phase_trends.get("Powerplay (1–6)")
    mid = phase_trends.get("Middle (7–16)")
    death = phase_trends.get("Death (17–20)")

    if pp and mid and death:
        if mid["word"] == "dropped" and pp["word"] != "dropped":
            lines.append(
                "🎯 **Spinner-grip signal:** middle overs got cheaper while "
                "powerplay held — pitches gripping more for spin as the season wore on."
            )
        elif death["word"] == "dropped" and mid["word"] != "dropped":
            lines.append(
                "🎯 **Death-overs slowdown:** late-innings economy dropped while "
                "middle held — slower surfaces taking pace off finishing shots."
            )
        elif all(t["word"] == "dropped" for t in (pp, mid, death)):
            lines.append(
                "🎯 **Across-the-board slowdown:** every phase got cheaper as "
                "games went on. Surfaces deteriorating uniformly."
            )
        elif all(t["word"] == "rose" for t in (pp, mid, death)):
            lines.append(
                "🎯 **No slowdown signal.** All three phases got more expensive "
                "as the season progressed — surfaces flattening, batters adapting."
            )
        else:
            lines.append(
                "🎯 **Mixed phase behaviour** — no single phase is driving the "
                "trend; the slowdown isn't concentrated."
            )

    return "\n\n".join(lines)


def verdict_pace_spin(ps_econ: pd.DataFrame) -> str:
    """Verdict for the 'Pace vs Spin' chart."""
    if ps_econ.empty:
        return "_No pace/spin data in scope._"

    pace = ps_econ[ps_econ["bowler_type"] == "Pace"].sort_values("match_num")
    spin = ps_econ[ps_econ["bowler_type"] == "Spin"].sort_values("match_num")

    if len(pace) < 3 or len(spin) < 3:
        return "_Not enough games for pace/spin analysis._"

    pace_early, _, pace_late = _trisect_means(pace["economy"])
    spin_early, _, spin_late = _trisect_means(spin["economy"])
    pace_delta = pace_late - pace_early
    spin_delta = spin_late - spin_early
    pace_avg = pace["economy"].mean()
    spin_avg = spin["economy"].mean()

    lines = []

    # Line 1: trends for each
    pace_phrase = (
        f"**Pace** held flat ({pace_early:.2f} → {pace_late:.2f})"
        if _trend_word(pace_delta) == "held flat"
        else f"**Pace** {_trend_word(pace_delta)} {pace_delta:+.2f} rpo "
             f"({pace_early:.2f} → {pace_late:.2f})"
    )
    spin_phrase = (
        f"**Spin** held flat ({spin_early:.2f} → {spin_late:.2f})"
        if _trend_word(spin_delta) == "held flat"
        else f"**Spin** {_trend_word(spin_delta)} {spin_delta:+.2f} rpo "
             f"({spin_early:.2f} → {spin_late:.2f})"
    )
    lines.append(f"{pace_phrase} · {spin_phrase}")

    # Line 2: who's cheaper overall
    if abs(pace_avg - spin_avg) < 0.2:
        lines.append(
            f"Pace and spin are pricing roughly the same overall "
            f"(~{pace_avg:.2f} vs ~{spin_avg:.2f} rpo)."
        )
    else:
        cheaper = "Spin" if spin_avg < pace_avg else "Pace"
        c_avg = min(pace_avg, spin_avg)
        e_avg = max(pace_avg, spin_avg)
        lines.append(
            f"**{cheaper}** is the more economical option overall "
            f"({c_avg:.2f} vs {e_avg:.2f} rpo)."
        )

    # Line 3: interpretive verdict
    pace_word = _trend_word(pace_delta)
    spin_word = _trend_word(spin_delta)

    if pace_word == "dropped" and spin_word != "dropped":
        lines.append(
            "⚡ **Pace-friendly drift:** pacers tightening up while spinners "
            "held steady — likely pitches firming up / new ball doing more."
        )
    elif spin_word == "dropped" and pace_word != "dropped":
        lines.append(
            "🌀 **Spin-friendly drift:** spinners getting cheaper while pace "
            "held steady — pitches gripping more / surfaces slowing for spin."
        )
    elif pace_word == "dropped" and spin_word == "dropped":
        lines.append(
            "🔻 **Bowlers gaining the upper hand on both fronts** — pace and "
            "spin both got cheaper. Surfaces favouring bowlers as games progressed."
        )
    elif pace_word == "rose" and spin_word == "rose":
        lines.append(
            "🔺 **Batter-friendly drift:** pace and spin both leaked more runs "
            "as games went on — surfaces flattening for both bowler types."
        )
    else:
        lines.append(
            "⚖️ **No clear shift** — pace and spin economies stayed within normal "
            "noise. Pitch behaviour roughly stable across the period."
        )

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("⚙️ Filters")

try:
    raw_df = load_data(DEFAULT_FILE)
except FileNotFoundError:
    st.error(
        f"Could not find `{DEFAULT_FILE}`. "
        "Make sure the data file is in the same directory as this script."
    )
    st.stop()

sessions_df = classify_day_night(raw_df)

OVERALL_LABEL = "🌐 Overall (all grounds)"

all_grounds = sorted(raw_df["ground"].unique().tolist())
ground_options = [OVERALL_LABEL] + all_grounds
ground = st.sidebar.selectbox(
    "Ground", ground_options, index=0,
    help="Pick one ground for venue-specific analysis, or 'Overall' to see "
         "league-wide trends across all grounds chronologically.",
)
is_overall = (ground == OVERALL_LABEL)

all_years = sorted(raw_df["year"].unique().tolist())
years_selected = st.sidebar.multiselect(
    "Season(s)", options=all_years, default=all_years,
    help="Pick one year for a single line, or multiple to compare seasons.",
)

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
    help=("Heuristic: doubleheader dates split into Day/Night by match-ID order; "
          "single-match dates default to Night (standard IPL slot)."),
)

# ---------------------------------------------------------------------------
# Filter universe
# ---------------------------------------------------------------------------
if is_overall:
    work = raw_df.copy()
else:
    work = raw_df[raw_df["ground"] == ground].copy()
work = work[work["year"].isin(years_selected)]
work = filter_innings(work, innings_filter)
work = filter_session(work, session_filter, sessions_df)

if work.empty or not years_selected:
    st.title("🏏 IPL Pitch Slowdown Analyzer")
    st.warning("No data for this combination. Try widening the filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏏 IPL Pitch Slowdown Analyzer")
ground_label = "All grounds" if is_overall else ground.split(",")[0]
st.caption(
    f"**{ground_label}** · "
    f"Seasons: {', '.join(str(y) for y in sorted(years_selected))} · "
    f"Innings: {innings_filter} · Session: {session_filter}"
)

# ---------------------------------------------------------------------------
# 1. KPI strip
# ---------------------------------------------------------------------------
match_econ_full = compute_economy(work, ["p_match", "year", "date"])
match_econ_full = assign_match_seq_within_year(match_econ_full)

n_games = match_econ_full["p_match"].nunique()
avg_econ = match_econ_full["economy"].mean()
high_row = match_econ_full.loc[match_econ_full["economy"].idxmax()]
low_row = match_econ_full.loc[match_econ_full["economy"].idxmin()]

c1, c2, c3, c4 = st.columns(4)
games_label = "Games (all grounds)" if is_overall else "Games at this ground"
c1.metric(games_label, f"{n_games}")
c2.metric("Avg economy", f"{avg_econ:.2f}")
c3.metric("Highest econ", f"{high_row['economy']:.2f}",
          help=f"{high_row['date'].strftime('%d %b %Y')}")
c4.metric("Lowest econ", f"{low_row['economy']:.2f}",
          help=f"{low_row['date'].strftime('%d %b %Y')}")

st.divider()

# Attach hover metadata
meta = match_meta(raw_df)
match_econ_full = match_econ_full.merge(meta, on="p_match", how="left")
seq_lookup = match_econ_full[["p_match", "match_num"]]

# ---------------------------------------------------------------------------
# 2. Overall economy per match
# ---------------------------------------------------------------------------
st.subheader("📈 Economy per match")
if is_overall:
    st.caption(
        "Each line is one full IPL season, games numbered chronologically "
        "across all grounds. Faint horizontal lines are season averages."
    )
else:
    st.caption(
        "Each line is one season at this ground. X-axis is match number "
        "*within that season*. Faint horizontal line per season is its average — "
        "dips below it are slower-than-typical games."
    )

fig_overall = go.Figure()
for yr, sub in match_econ_full.groupby("year"):
    sub = sub.sort_values("match_num")
    color = YEAR_COLORS.get(yr, "#888888")

    # Hover differs slightly between modes — include ground in Overall view
    if is_overall:
        custom = np.stack([
            sub["date"].dt.strftime("%d %b %Y"),
            sub["matchup"],
            sub["total_runs"],
            sub["overs"].round(1),
            sub["ground"].apply(lambda g: g.split(",")[0]),
        ], axis=-1)
        hover = (
            f"<b>{yr} · Game %{{x}}</b><br>"
            "Economy: %{y:.2f} rpo<br>"
            "Date: %{customdata[0]}<br>"
            "Match: %{customdata[1]}<br>"
            "Ground: %{customdata[4]}<br>"
            "Runs: %{customdata[2]} in %{customdata[3]} overs<extra></extra>"
        )
    else:
        custom = np.stack([
            sub["date"].dt.strftime("%d %b %Y"),
            sub["matchup"],
            sub["total_runs"],
            sub["overs"].round(1),
        ], axis=-1)
        hover = (
            f"<b>{yr} · Game %{{x}}</b><br>"
            "Economy: %{y:.2f} rpo<br>"
            "Date: %{customdata[0]}<br>"
            "Match: %{customdata[1]}<br>"
            "Runs: %{customdata[2]} in %{customdata[3]} overs<extra></extra>"
        )

    # Smaller markers + thinner line in Overall mode (lots of dots)
    marker_size = 5 if is_overall else 9
    line_width = 2 if is_overall else 2.5

    fig_overall.add_trace(go.Scatter(
        x=sub["match_num"], y=sub["economy"],
        mode="lines+markers",
        name=str(yr),
        line=dict(color=color, width=line_width),
        marker=dict(size=marker_size),
        customdata=custom,
        hovertemplate=hover,
    ))

    yr_avg = sub["economy"].mean()
    fig_overall.add_hline(
        y=yr_avg,
        line=dict(color=color, width=1, dash="dot"),
        opacity=0.4,
        annotation_text=f"{yr} avg: {yr_avg:.2f}",
        annotation_position="right",
        annotation_font_color=color,
        annotation_font_size=10,
    )

# X-axis tick density adapts to game count
xaxis_dtick = 5 if is_overall else 1

fig_overall.update_layout(
    xaxis_title="Match number (within season, chronological)",
    yaxis_title="Bowling economy (runs/over)",
    hovermode="closest",
    height=460,
    legend_title="Season",
    xaxis=dict(dtick=xaxis_dtick),
)
st.plotly_chart(fig_overall, use_container_width=True)

with st.container(border=True):
    st.markdown("**📋 Verdict**")
    st.markdown(verdict_overall(match_econ_full))

st.divider()

# ---------------------------------------------------------------------------
# 3. Phase split (1–6 / 7–16 / 17–20)
# ---------------------------------------------------------------------------
st.subheader("🎯 Phase split — where does the slowdown live?")
st.caption(
    "Same matches, economy split by phase. If middle-overs economy drops "
    "across the season but powerplay holds steady, that's the spinner-grip "
    "signal you're after."
)

work_phased = work.copy()
def _phase_for_over(o):
    for name, (lo, hi) in PHASE_DEFS.items():
        if lo <= o <= hi:
            return name
    return None
work_phased["phase"] = work_phased["over"].apply(_phase_for_over)
work_phased = work_phased.dropna(subset=["phase"])

phase_econ = compute_economy(work_phased, ["p_match", "year", "date", "phase"])
phase_econ = phase_econ.merge(seq_lookup, on="p_match", how="left")

years_sorted = sorted(years_selected)
n_years = len(years_sorted)
phase_xaxis_dtick = 5 if is_overall else 1

if n_years == 1:
    yr = years_sorted[0]
    sub_y = phase_econ[phase_econ["year"] == yr]
    fig_phase = go.Figure()
    for phase_name in PHASE_DEFS.keys():
        ph = sub_y[sub_y["phase"] == phase_name].sort_values("match_num")
        if ph.empty:
            continue
        fig_phase.add_trace(go.Scatter(
            x=ph["match_num"], y=ph["economy"],
            mode="lines+markers",
            name=phase_name,
            line=dict(color=PHASE_COLORS[phase_name], width=2.5),
            marker=dict(size=8),
            hovertemplate=(
                f"<b>{phase_name}</b><br>"
                f"{yr} · Game %{{x}}<br>"
                "Economy: %{y:.2f} rpo<extra></extra>"
            ),
        ))
    fig_phase.update_layout(
        title=f"Phase economies — {yr}",
        xaxis_title="Match number (within season)",
        yaxis_title="Economy (runs/over)",
        height=460,
        hovermode="x unified",
        legend_title="Phase",
        xaxis=dict(dtick=phase_xaxis_dtick),
    )
    st.plotly_chart(fig_phase, use_container_width=True)
else:
    # Multi-year: one chart per phase, lines per year
    cols = st.columns(len(PHASE_DEFS))
    for col, phase_name in zip(cols, PHASE_DEFS.keys()):
        fig = go.Figure()
        sub_p = phase_econ[phase_econ["phase"] == phase_name]
        for yr, ph in sub_p.groupby("year"):
            ph = ph.sort_values("match_num")
            fig.add_trace(go.Scatter(
                x=ph["match_num"], y=ph["economy"],
                mode="lines+markers",
                name=str(yr),
                line=dict(color=YEAR_COLORS.get(yr, "#888"), width=2),
                marker=dict(size=7),
                hovertemplate=(
                    f"<b>{yr} · Game %{{x}}</b><br>"
                    f"{phase_name}<br>"
                    "Economy: %{y:.2f} rpo<extra></extra>"
                ),
            ))
        fig.update_layout(
            title=phase_name,
            xaxis_title="Game # in season",
            yaxis_title="Economy (rpo)",
            height=380,
            legend_title="Season",
            margin=dict(t=50, b=40, l=50, r=10),
            xaxis=dict(dtick=phase_xaxis_dtick),
        )
        col.plotly_chart(fig, use_container_width=True)

with st.container(border=True):
    st.markdown("**📋 Verdict**")
    st.markdown(verdict_phase(phase_econ))

st.divider()

# ---------------------------------------------------------------------------
# 4. Pace vs Spin
# ---------------------------------------------------------------------------
st.subheader("⚡ Pace vs Spin economy per match")
st.caption(
    "Same matches, split by bowler type. Diverging lines tell the story: "
    "pacers cheaper while spinners hold = pitch hardening; spinners cheaper "
    "while pacers hold = pitch gripping more."
)

ps_work = work[work["bowl_kind"].isin(["pace bowler", "spin bowler"])].copy()
ps_econ = compute_economy(ps_work, ["p_match", "year", "date", "bowl_kind"])
ps_econ = ps_econ.merge(seq_lookup, on="p_match", how="left")
ps_econ["bowler_type"] = ps_econ["bowl_kind"].map(
    {"pace bowler": "Pace", "spin bowler": "Spin"}
)

if n_years == 1:
    yr = years_sorted[0]
    fig_ps = go.Figure()
    style_map = {"Pace": ("#3366CC", "solid"), "Spin": ("#DC3912", "dash")}
    for bt in ["Pace", "Spin"]:
        s = ps_econ[(ps_econ["year"] == yr) & (ps_econ["bowler_type"] == bt)]
        s = s.sort_values("match_num")
        if s.empty:
            continue
        color, dash = style_map[bt]
        fig_ps.add_trace(go.Scatter(
            x=s["match_num"], y=s["economy"],
            mode="lines+markers",
            name=bt,
            line=dict(color=color, width=2.5, dash=dash),
            marker=dict(size=9),
            hovertemplate=(
                f"<b>{bt} · {yr}</b><br>"
                "Game %{x} · Economy %{y:.2f} rpo<extra></extra>"
            ),
        ))
    fig_ps.update_layout(
        xaxis_title="Match number (within season)",
        yaxis_title="Economy (runs/over)",
        height=460,
        legend_title="Bowler type",
        hovermode="x unified",
        xaxis=dict(dtick=phase_xaxis_dtick),
    )
    st.plotly_chart(fig_ps, use_container_width=True)
else:
    cols = st.columns(2)
    for col, bt in zip(cols, ["Pace", "Spin"]):
        fig = go.Figure()
        s_bt = ps_econ[ps_econ["bowler_type"] == bt]
        for yr, s in s_bt.groupby("year"):
            s = s.sort_values("match_num")
            fig.add_trace(go.Scatter(
                x=s["match_num"], y=s["economy"],
                mode="lines+markers",
                name=str(yr),
                line=dict(color=YEAR_COLORS.get(yr, "#888"), width=2.5),
                marker=dict(size=8),
                hovertemplate=(
                    f"<b>{yr} · Game %{{x}}</b><br>"
                    f"{bt}: %{{y:.2f}} rpo<extra></extra>"
                ),
            ))
        fig.update_layout(
            title=f"{bt} bowlers",
            xaxis_title="Game # in season",
            yaxis_title="Economy (rpo)",
            height=420,
            legend_title="Season",
            xaxis=dict(dtick=phase_xaxis_dtick),
        )
        col.plotly_chart(fig, use_container_width=True)

# Pace vs Spin summary table
st.markdown("**Season summary — Pace vs Spin**")
ps_summary = (
    ps_econ.groupby(["year", "bowler_type"])
    .agg(avg_econ=("economy", "mean"))
    .reset_index()
    .pivot(index="year", columns="bowler_type", values="avg_econ")
    .round(2)
)
ps_summary.columns.name = None
st.dataframe(ps_summary, use_container_width=True)

with st.container(border=True):
    st.markdown("**📋 Verdict**")
    st.markdown(verdict_pace_spin(ps_econ))

st.divider()

# ---------------------------------------------------------------------------
# Raw data
# ---------------------------------------------------------------------------
with st.expander("Show match-level raw data"):
    cols_to_show = ["year", "match_num", "date", "p_match", "matchup"]
    if is_overall:
        cols_to_show.append("ground")
    cols_to_show += ["total_runs", "overs", "economy"]
    show = match_econ_full[cols_to_show].copy()
    show["date"] = show["date"].dt.strftime("%d %b %Y")
    show["economy"] = show["economy"].round(2)
    show["overs"] = show["overs"].round(1)
    if is_overall and "ground" in show.columns:
        show["ground"] = show["ground"].apply(lambda g: g.split(",")[0])
    show = show.sort_values(["year", "match_num"])
    st.dataframe(show, use_container_width=True, hide_index=True)

st.caption(
    "Economy includes wides & no-balls in runs; overs use legal balls only. "
    "Match sequence resets at game #1 each season for direct year-on-year comparison."
)
