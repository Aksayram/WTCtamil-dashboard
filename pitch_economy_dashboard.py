"""
IPL Pitch Slowdown Analyzer (2023–2025)
========================================
Pick ONE ground and ONE or MORE years from the sidebar. The page shows
economy game-by-game at that ground, with each year as its own line
(resetting at game #1 each season).

Sections (top to bottom, single page, no tabs):
  1. KPI strip
  2. Overall economy per match (line per year)
  3. Phase split: Powerplay (1–6) / Middle (7–16) / Death (17–20)
  4. Pace vs Spin economy per match

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
        "across all grounds. Faded line = per-game economy; thick line = "
        "5-game rolling average to cut through noise. Faint horizontal "
        "lines are season averages."
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
    line_width = 1.5 if is_overall else 2.5

    fig_overall.add_trace(go.Scatter(
        x=sub["match_num"], y=sub["economy"],
        mode="lines+markers",
        name=str(yr),
        line=dict(color=color, width=line_width),
        marker=dict(size=marker_size),
        customdata=custom,
        hovertemplate=hover,
        opacity=0.55 if is_overall else 1.0,
    ))

    # Rolling average overlay — only in Overall mode where noise dominates
    if is_overall and len(sub) >= 5:
        roll = sub["economy"].rolling(window=5, min_periods=3, center=True).mean()
        fig_overall.add_trace(go.Scatter(
            x=sub["match_num"], y=roll,
            mode="lines",
            name=f"{yr} (5-game avg)",
            line=dict(color=color, width=3),
            hoverinfo="skip",
            showlegend=True,
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
