import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(
    page_title="IPL Momentum Dashboard",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
    h1 { font-size: 2rem !important; font-weight: 700 !important; }
    .metric-card {
        background: #f8fafc; border: 1px solid #e2e8f0;
        border-radius: 10px; padding: 12px 16px; text-align: center;
        height: 90px; display: flex; flex-direction: column; justify-content: center;
    }
    .metric-label { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
    .metric-value { font-size: 26px; font-weight: 700; color: #1e293b; line-height: 1.1; }
    .metric-sub   { font-size: 11px; margin-top: 2px; }
    .insight-box {
        background: #fff7ed; border-left: 4px solid #f97316;
        border-radius: 8px; padding: 12px 16px;
        font-size: 13.5px; color: #7c2d12; margin-top: 0.75rem; line-height: 1.8;
    }
</style>
""", unsafe_allow_html=True)

TEAM_COLORS = {
    "CSK":"#F5B800","MI":"#005DA0","RCB":"#EC1C24","KKR":"#3A225D",
    "DC":"#0078BC","SRH":"#F7A721","PBKS":"#C8102E","RR":"#254AA5",
    "GT":"#1C4B9B","LSG":"#A72056",
}

@st.cache_data
def load_excel(file_bytes):
    buf = BytesIO(file_bytes)
    match_df   = pd.read_excel(buf, sheet_name="Match Results")
    buf.seek(0)
    detail_df  = pd.read_excel(buf, sheet_name="Full Detail")
    buf.seek(0)
    summary_df = pd.read_excel(buf, sheet_name="Season Summary")
    match_df["Season"]  = match_df["Season"].astype(int)
    detail_df["Season"] = detail_df["Season"].astype(int)
    return match_df, detail_df, summary_df

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏏 IPL Momentum")
    st.markdown("---")

    uploaded = st.file_uploader("Upload ipl_data_accurate.xlsx", type=["xlsx"])
    if uploaded is None:
        st.info("Upload the Excel file to get started.")
        st.stop()

    match_df, detail_df, summary_df = load_excel(uploaded.read())

    all_seasons = sorted(match_df["Season"].unique().tolist())
    all_teams   = sorted(match_df["Team"].unique().tolist())

    st.markdown("#### Seasons")
    sel_seasons = st.multiselect("seasons", all_seasons, default=all_seasons, label_visibility="collapsed")

    st.markdown("#### Teams")
    sel_teams = st.multiselect("teams", all_teams, default=all_teams, label_visibility="collapsed")

    st.markdown("#### Match cutoff")
    cutoff = st.slider("cutoff", min_value=1, max_value=13, value=7, step=1, label_visibility="collapsed")
    col_a, col_b = st.columns(2)
    col_a.metric("First N", cutoff)
    col_b.metric("Last", 14 - cutoff)
    st.markdown("---")
    st.caption("Source: Cricsheet.org · IPL 2022–2025")

# ── Guards ────────────────────────────────────────────────────────────────────
if not sel_seasons:
    st.warning("Please select at least one season.")
    st.stop()
if not sel_teams:
    st.warning("Please select at least one team.")
    st.stop()

# ── Filter & compute ──────────────────────────────────────────────────────────
df = match_df[match_df["Season"].isin(sel_seasons) & match_df["Team"].isin(sel_teams)].copy()
match_cols  = [c for c in [f"M{i+1}" for i in range(14)] if c in df.columns]
before_cols = match_cols[:cutoff]
after_cols  = match_cols[cutoff:]

def safe_pct(wins, games):
    return round(wins / games * 100) if games > 0 else 0

stats = []
for team in sel_teams:
    t = df[df["Team"] == team]
    if t.empty:
        continue
    b_df = t[before_cols].apply(pd.to_numeric, errors="coerce")
    a_df = t[after_cols].apply(pd.to_numeric, errors="coerce")
    b_wins, b_games = b_df.sum().sum(), b_df.notna().sum().sum()
    a_wins, a_games = a_df.sum().sum(), a_df.notna().sum().sum()
    cumulative = []
    for c in match_cols:
        vals = pd.to_numeric(t[c], errors="coerce").dropna()
        cumulative.append(round(vals.mean() * 100) if len(vals) > 0 else None)
    before_pct = safe_pct(b_wins, b_games)
    after_pct  = safe_pct(a_wins, a_games)
    stats.append({
        "team": team, "before_pct": before_pct, "after_pct": after_pct,
        "diff": after_pct - before_pct, "cumulative": cumulative,
        "b_games": int(b_games), "a_games": int(a_games),
    })

stats_df = pd.DataFrame(stats).sort_values("team").reset_index(drop=True)
if stats_df.empty:
    st.warning("No data for the selected filters.")
    st.stop()

top_riser = stats_df.loc[stats_df["diff"].idxmax()]
top_fader = stats_df.loc[stats_df["diff"].idxmin()]

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏏 IPL Momentum Dashboard")
st.caption(f"Seasons: **{', '.join(map(str, sel_seasons))}**  ·  Teams: **{len(sel_teams)}**  ·  Cutoff: first **{cutoff}** vs last **{14-cutoff}** games")

# ── Metric cards ──────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Seasons</div><div class="metric-value" style="color:#3b82f6">{len(sel_seasons)}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Teams</div><div class="metric-value" style="color:#f97316">{len(sel_teams)}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Cutoff match</div><div class="metric-value" style="color:#8b5cf6">{cutoff}</div></div>', unsafe_allow_html=True)
with m4:
    d = int(top_riser["diff"]); sign = "+" if d >= 0 else ""
    st.markdown(f'<div class="metric-card"><div class="metric-label">Top back-end riser</div><div class="metric-value" style="color:#16a34a">{top_riser["team"]}</div><div class="metric-sub" style="color:#16a34a">{sign}{d}% after cutoff</div></div>', unsafe_allow_html=True)
with m5:
    d = int(top_fader["diff"]); sign = "+" if d >= 0 else ""
    st.markdown(f'<div class="metric-card"><div class="metric-label">Top front-runner fader</div><div class="metric-value" style="color:#dc2626">{top_fader["team"]}</div><div class="metric-sub" style="color:#dc2626">{sign}{d}% after cutoff</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Charts ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown(f"##### Win % · games 1–{cutoff} vs games {cutoff+1}–14")
    fig_bar = go.Figure()
    teams_list = stats_df["team"].tolist()
    fig_bar.add_trace(go.Bar(
        name=f"Games 1–{cutoff}", x=teams_list, y=stats_df["before_pct"].tolist(),
        marker_color="#3b82f6", marker_line_width=0,
        text=[f"{v}%" for v in stats_df["before_pct"].tolist()],
        textposition="outside", textfont=dict(size=11, color="#1e293b"),
    ))
    fig_bar.add_trace(go.Bar(
        name=f"Games {cutoff+1}–14", x=teams_list, y=stats_df["after_pct"].tolist(),
        marker_color="#f97316", marker_line_width=0,
        text=[f"{v}%" for v in stats_df["after_pct"].tolist()],
        textposition="outside", textfont=dict(size=11, color="#1e293b"),
    ))
    fig_bar.update_layout(
        barmode="group", height=380, plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(title="Win %", range=[0,115], gridcolor="#f1f5f9", ticksuffix="%"),
        xaxis=dict(tickfont=dict(size=12, color="#1e293b")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        margin=dict(l=10, r=10, t=40, b=10), font=dict(family="Arial", size=12),
        bargap=0.25, bargroupgap=0.05,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    st.markdown("##### Cumulative win % · match by match")
    fig_line = go.Figure()
    match_labels = [f"M{i+1}" for i in range(14)]
    for _, row in stats_df.iterrows():
        team  = row["team"]
        color = TEAM_COLORS.get(team, "#888888")
        fig_line.add_trace(go.Scatter(
            x=match_labels, y=row["cumulative"], name=team,
            mode="lines+markers", connectgaps=True,
            line=dict(color=color, width=2.5),
            marker=dict(size=6, color=color, line=dict(width=1.5, color="white")),
            hovertemplate=f"<b>{team}</b>  %{{x}}: %{{y}}%<extra></extra>",
        ))
    fig_line.add_vline(
        x=cutoff - 0.5, line_dash="dash",
        line_color="rgba(100,100,100,0.45)", line_width=1.5,
        annotation_text=f"  cutoff M{cutoff}",
        annotation_position="top left",
        annotation_font_size=10, annotation_font_color="#64748b",
    )
    fig_line.update_layout(
        height=380, plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(title="Win %", range=[0,105], gridcolor="#f1f5f9", ticksuffix="%"),
        xaxis=dict(gridcolor="#f1f5f9", tickfont=dict(size=10)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(family="Arial", size=12), hovermode="x unified",
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ── Insight ───────────────────────────────────────────────────────────────────
risers     = stats_df[stats_df["diff"] >  10].sort_values("diff", ascending=False)
faders     = stats_df[stats_df["diff"] < -10].sort_values("diff")
consistent = stats_df[stats_df["diff"].abs() <= 10]
parts = []
if not risers.empty:
    parts.append("📈 <b>Back-end risers</b> (get stronger after cutoff): " +
                 ", ".join([f"<b>{r.team}</b> (+{int(r.diff)}%)" for r in risers.itertuples()]))
if not faders.empty:
    parts.append("📉 <b>Front-runners who fade</b> (weaker after cutoff): " +
                 ", ".join([f"<b>{r.team}</b> ({int(r.diff)}%)" for r in faders.itertuples()]))
if not parts:
    parts.append("All teams are fairly consistent — try adjusting the cutoff slider to reveal patterns.")
elif not consistent.empty:
    parts.append("⚖️ <b>Consistent throughout:</b> " +
                 ", ".join([f"<b>{r.team}</b>" for r in consistent.itertuples()]))
st.markdown(f'<div class="insight-box">{"<br>".join(parts)}</div>', unsafe_allow_html=True)

# ── Summary table ─────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("##### Team comparison table")
display = stats_df[["team","before_pct","after_pct","diff","b_games","a_games"]].copy()
display.columns = ["Team", f"Win% M1–M{cutoff}", f"Win% M{cutoff+1}–14", "Diff", "Games (before)", "Games (after)"]
display["Diff"] = display["Diff"].apply(lambda x: f"+{int(x)}%" if x >= 0 else f"{int(x)}%")
st.dataframe(display.reset_index(drop=True), use_container_width=True,
             height=min(42 * len(display) + 55, 440), hide_index=True)

# ── Expanders ─────────────────────────────────────────────────────────────────
with st.expander("📋 Raw match results (M1–M14)"):
    show_cols = ["Team","Season"] + [c for c in match_cols if c in df.columns] + ["Total Wins","Win %"]
    available = [c for c in show_cols if c in df.columns]
    st.dataframe(df[available].sort_values(["Season","Team"]).reset_index(drop=True),
                 use_container_width=True, height=320, hide_index=True)

with st.expander("📅 Match-by-match detail per team"):
    for team in sel_teams:
        t_d = detail_df[(detail_df["Team"]==team) & (detail_df["Season"].isin(sel_seasons))].sort_values(["Season","Team_Match_Num"])
        if t_d.empty: continue
        st.markdown(f"**{team}**")
        show = t_d[["Season","Team_Match_Num","Date","Opponent","Won"]].copy()
        show.columns = ["Season","Match #","Date","Opponent","Result"]
        show["Result"] = show["Result"].apply(lambda x: "Win" if x==1 else ("No Result" if x==0.5 else "Loss"))
        st.dataframe(show.reset_index(drop=True), use_container_width=True, height=220, hide_index=True)
