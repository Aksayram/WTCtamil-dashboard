import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ---------------- PASSWORD ----------------
def check_password():
    def password_entered():
        if st.session_state["password"] == "wtc123":  # change password here
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
    else:
        return True

if not check_password():
    st.stop()


st.set_page_config(page_title="Batter Analytics Dashboard", layout="wide", page_icon="🏏")

# ── Load & clean ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, usecols=range(13))
    df.columns = df.columns.str.strip()

    df['Batter']         = df['Batter'].str.strip().str.title()
    df['Bowler']         = df['Bowler'].str.strip().str.title()
    df['Ground']         = df['Ground'].str.strip().str.title()
    df['Type']           = df['Type'].str.strip().str.title().replace({'Spin': 'Spinner'})
    df['Bowling Hand']   = df['Bowling Hand'].str.strip().str.title().replace(
                               {'Right Hand': 'Right Arm', 'Left Hand': 'Left Arm',
                                'Right-Arm': 'Right Arm', 'Left-Arm': 'Left Arm'})
    df['Pitching Length']= df['Pitching Length'].str.strip().str.title()
    df['Pitching Line']  = df['Pitching Line'].str.strip().str.title()
    df['Bowling Side']   = df['Bowling Side'].str.strip().str.title()

    df['Speed']     = pd.to_numeric(df['Speed'],     errors='coerce')
    df['Run']       = pd.to_numeric(df['Run'],       errors='coerce').fillna(0)
    df['Dismissed'] = pd.to_numeric(df['Dismissed'], errors='coerce').fillna(0)
    df['Over']      = pd.to_numeric(df['Over'],      errors='coerce')

    df = df.dropna(subset=['Batter', 'Over'])

    # Phase
    def phase(o):
        if o <= 6:  return 'Powerplay (1–6)'
        if o <= 16: return 'Middle (7–16)'
        return 'Death (17–20)'
    df['Phase'] = df['Over'].apply(phase)
    df['Phase'] = pd.Categorical(df['Phase'],
                    categories=['Powerplay (1–6)', 'Middle (7–16)', 'Death (17–20)'],
                    ordered=True)
    return df

FILE = "ipl_data.xlsx"
try:
    df = load_data(FILE)
except FileNotFoundError:
    uploaded = st.file_uploader("Upload ipl_data.xlsx", type=["xlsx"])
    if uploaded:
        df = load_data(uploaded)
    else:
        st.info("Please upload your ipl_data.xlsx file.")
        st.stop()

# ── Helper ─────────────────────────────────────────────────────────────────────
def batter_stats(data, group_cols):
    g = data.groupby(group_cols, observed=True).agg(
        Balls   =('Run','count'),
        Runs    =('Run','sum'),
        Dismissals=('Dismissed','sum')
    ).reset_index()
    g['SR']  = (g['Runs'] / g['Balls'] * 100).round(1)
    g['Avg'] = (g['Runs'] / g['Dismissals'].replace(0, np.nan)).round(1)
    g['Avg'] = g['Avg'].fillna(g['Runs'])   # not out = runs scored
    return g

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🏏 Batter Filters")

phase_opts = ['Powerplay (1–6)', 'Middle (7–16)', 'Death (17–20)']
sel_phase = st.sidebar.multiselect("Phase", phase_opts, default=phase_opts)

type_opts = sorted(df['Type'].dropna().unique())
sel_type = st.sidebar.multiselect("Bowler Type", type_opts, default=type_opts)

hand_opts = sorted(df['Bowling Hand'].dropna().unique())
sel_hand = st.sidebar.multiselect("Bowling Arm", hand_opts, default=hand_opts)

len_opts = sorted(df['Pitching Length'].dropna().unique())
sel_len = st.sidebar.multiselect("Pitching Length", len_opts, default=len_opts)

line_opts = sorted(df['Pitching Line'].dropna().unique())
sel_line = st.sidebar.multiselect("Pitching Line", line_opts, default=line_opts)

ground_opts = sorted(df['Ground'].dropna().unique())
sel_ground = st.sidebar.multiselect("Ground", ground_opts, default=ground_opts)

min_balls = st.sidebar.slider("Min balls faced (filter noise)", 5, 50, 10)

# ── Filter ─────────────────────────────────────────────────────────────────────
filt = (
    df['Phase'].isin(sel_phase) &
    df['Type'].isin(sel_type) &
    df['Bowling Hand'].isin(sel_hand) &
    df['Pitching Length'].isin(sel_len) &
    df['Pitching Line'].isin(sel_line) &
    df['Ground'].isin(sel_ground)
)
dff = df[filt]

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🏏 Batter Analytics Dashboard")
st.caption(f"Showing **{len(dff):,}** deliveries | **{dff['Batter'].nunique()}** batters")

if dff.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── KPIs ───────────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Deliveries", f"{len(dff):,}")
k2.metric("Total Runs", f"{int(dff['Run'].sum()):,}")
k3.metric("Total Dismissals", int(dff['Dismissed'].sum()))
k4.metric("Overall SR", f"{(dff['Run'].sum()/len(dff)*100):.1f}")
disms = dff['Dismissed'].sum()
k5.metric("Overall Avg", f"{(dff['Run'].sum()/disms):.1f}" if disms else "N/A")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏆 Phase Leaderboard",
    "⚡ Pacer vs Spinner",
    "📏 Length Struggles",
    "🔍 Batter Deep Dive",
    "📋 Raw Data"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Phase Leaderboard
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Batter Leaderboard by Phase")

    phase_sel = st.radio("Select Phase", ["Overall"] + phase_opts, horizontal=True)
    metric_sel = st.radio("Rank by", ["SR", "Runs", "Avg"], horizontal=True)

    # Use all data for Overall, otherwise filter by phase
    phase_df = dff if phase_sel == "Overall" else dff[dff['Phase'] == phase_sel]

    if phase_df.empty:
        st.warning("No data for this phase with current filters.")
    else:
        lb = batter_stats(phase_df, ['Batter'])
        lb = lb[lb['Balls'] >= min_balls].sort_values(metric_sel, ascending=False).reset_index(drop=True)
        lb.index += 1

        if phase_sel == "Overall":
            st.markdown("#### 🏏 Overall – All Phases Combined")
            col1, col2 = st.columns([1.2, 1])
            with col1:
                top_n = st.slider("Show top N batters", 5, min(30, len(lb)), min(10, len(lb)))
                fig = px.bar(
                    lb.head(top_n), x='Batter', y=metric_sel,
                    color=metric_sel, color_continuous_scale='Teal',
                    text=metric_sel,
                    title=f"Top {top_n} Batters – Overall – Ranked by {metric_sel}",
                    height=450
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown("**Full Overall Leaderboard**")
                st.dataframe(lb[['Batter','Balls','Runs','SR','Avg','Dismissals']],
                             use_container_width=True, height=420)

            st.divider()

            # Best batter vs Pacer overall
            st.markdown("#### ⚡ Best Batters vs Pacer (All Phases)")
            pace_df = dff[dff['Type'] == 'Pacer']
            pace_lb = batter_stats(pace_df, ['Batter'])
            pace_lb = pace_lb[pace_lb['Balls'] >= min_balls].sort_values(metric_sel, ascending=False).reset_index(drop=True)
            pace_lb.index += 1
            col3, col4 = st.columns([1.2, 1])
            with col3:
                fig_p = px.bar(
                    pace_lb.head(top_n), x='Batter', y=metric_sel,
                    color=metric_sel, color_continuous_scale='Reds',
                    text=metric_sel,
                    title=f"Top {top_n} Batters vs Pacer – Ranked by {metric_sel}",
                    height=420
                )
                fig_p.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_p, use_container_width=True)
            with col4:
                st.markdown("**Full Pacer Leaderboard**")
                st.dataframe(pace_lb[['Batter','Balls','Runs','SR','Avg','Dismissals']],
                             use_container_width=True, height=400)

            st.divider()

            # Best batter vs Spinner overall
            st.markdown("#### 🌀 Best Batters vs Spinner (All Phases)")
            spin_df = dff[dff['Type'] == 'Spinner']
            spin_lb = batter_stats(spin_df, ['Batter'])
            spin_lb = spin_lb[spin_lb['Balls'] >= min_balls].sort_values(metric_sel, ascending=False).reset_index(drop=True)
            spin_lb.index += 1
            col5, col6 = st.columns([1.2, 1])
            with col5:
                fig_s = px.bar(
                    spin_lb.head(top_n), x='Batter', y=metric_sel,
                    color=metric_sel, color_continuous_scale='Blues',
                    text=metric_sel,
                    title=f"Top {top_n} Batters vs Spinner – Ranked by {metric_sel}",
                    height=420
                )
                fig_s.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_s, use_container_width=True)
            with col6:
                st.markdown("**Full Spinner Leaderboard**")
                st.dataframe(spin_lb[['Batter','Balls','Runs','SR','Avg','Dismissals']],
                             use_container_width=True, height=400)

        else:
            col1, col2 = st.columns([1.2, 1])
            with col1:
                top_n = st.slider("Show top N batters", 5, min(30, len(lb)), min(10, len(lb)))
                fig = px.bar(
                    lb.head(top_n), x='Batter', y=metric_sel,
                    color=metric_sel, color_continuous_scale='Teal',
                    text=metric_sel,
                    title=f"Top {top_n} Batters – {phase_sel} – Ranked by {metric_sel}",
                    height=450
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown(f"**Full Leaderboard – {phase_sel}**")
                st.dataframe(
                    lb[['Batter','Balls','Runs','SR','Avg','Dismissals']],
                    use_container_width=True, height=420
                )

    st.divider()
    st.subheader("Phase-wise SR Comparison (all phases)")
    phase_all = batter_stats(dff, ['Batter', 'Phase'])
    phase_all = phase_all[phase_all['Balls'] >= min_balls]

    # pick top batters by total runs for readability
    top_batters = (
        dff.groupby('Batter')['Run'].sum()
        .nlargest(15).index.tolist()
    )
    phase_top = phase_all[phase_all['Batter'].isin(top_batters)]

    fig2 = px.bar(
        phase_top, x='Batter', y='SR', color='Phase',
        barmode='group', text='SR',
        color_discrete_map={
            'Powerplay (1–6)': '#636EFA',
            'Middle (7–16)':   '#EF553B',
            'Death (17–20)':   '#00CC96'
        },
        title="Strike Rate Across Phases – Top 15 Batters by Runs",
        height=450
    )
    fig2.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Pacer vs Spinner
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Batter Performance: Pacer vs Spinner")

    ps = batter_stats(dff, ['Batter', 'Type'])
    ps = ps[ps['Balls'] >= min_balls]

    col1, col2 = st.columns(2)

    with col1:
        metric_ps = st.radio("Metric", ["SR", "Avg", "Runs"], horizontal=True, key='ps_metric')
        pivot_ps = ps.pivot_table(index='Batter', columns='Type', values=metric_ps).reset_index()
        pivot_ps = pivot_ps.dropna()

        if 'Pacer' in pivot_ps.columns and 'Spinner' in pivot_ps.columns:
            pivot_ps['Difference'] = (pivot_ps['Pacer'] - pivot_ps['Spinner']).round(1)
            pivot_ps = pivot_ps.sort_values('Difference', ascending=False)

            fig = px.bar(
                pivot_ps, x='Batter', y='Difference',
                color='Difference', color_continuous_scale='RdBu',
                title=f"{metric_ps}: Pacer minus Spinner (+ = better vs Pacer)",
                height=430, text='Difference'
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough Pacer/Spinner data with current filters.")

    with col2:
        st.markdown("**Side-by-side comparison**")
        if 'Pacer' in pivot_ps.columns and 'Spinner' in pivot_ps.columns:
            fig2 = px.scatter(
                pivot_ps, x='Pacer', y='Spinner',
                text='Batter', color='Difference',
                color_continuous_scale='RdBu',
                title=f"{metric_ps} – Pacer (x) vs Spinner (y)",
                height=430
            )
            fig2.add_shape(type='line',
                x0=pivot_ps['Pacer'].min(), y0=pivot_ps['Pacer'].min(),
                x1=pivot_ps['Pacer'].max(), y1=pivot_ps['Pacer'].max(),
                line=dict(dash='dash', color='grey'))
            fig2.update_traces(textposition='top center')
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("Dismissal Rate: Pacer vs Spinner")
    dis = dff.groupby(['Batter', 'Type'], observed=True).agg(
        Balls=('Run','count'), Dismissals=('Dismissed','sum')
    ).reset_index()
    dis = dis[dis['Balls'] >= min_balls]
    dis['Dismissal%'] = (dis['Dismissals'] / dis['Balls'] * 100).round(2)

    dis_pivot = dis.pivot_table(index='Batter', columns='Type', values='Dismissal%').reset_index().dropna()
    if 'Pacer' in dis_pivot.columns and 'Spinner' in dis_pivot.columns:
        dis_pivot['Diff'] = (dis_pivot['Pacer'] - dis_pivot['Spinner']).round(2)
        dis_pivot = dis_pivot.sort_values('Diff', ascending=False)
        fig3 = px.bar(
            dis_pivot, x='Batter', y=['Pacer','Spinner'],
            barmode='group',
            title="Dismissal % per ball – Pacer vs Spinner",
            height=400,
            labels={'value': 'Dismissal %', 'variable': 'Bowler Type'}
        )
        fig3.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.subheader("Phase × Bowler Type SR Heatmap")
    phase_type = batter_stats(dff, ['Batter', 'Phase', 'Type'])
    phase_type = phase_type[phase_type['Balls'] >= min_balls]
    top10 = dff.groupby('Batter')['Run'].sum().nlargest(12).index.tolist()
    pt_top = phase_type[phase_type['Batter'].isin(top10)]
    pt_top['Label'] = pt_top['Phase'].astype(str) + ' vs ' + pt_top['Type'].astype(str)
    heat = pt_top.pivot_table(index='Batter', columns='Label', values='SR')
    fig4 = px.imshow(heat, color_continuous_scale='RdYlGn', text_auto=True,
                     title="SR Heatmap: Batter × Phase × Bowler Type (top 12 by runs)",
                     height=500)
    st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Length Struggles
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Which Lengths Do Batters Struggle Against?")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**SR by Pitching Length (top 12 batters)**")
        top12 = dff.groupby('Batter')['Run'].sum().nlargest(12).index.tolist()
        len_df = batter_stats(dff[dff['Batter'].isin(top12)], ['Batter','Pitching Length'])
        len_df = len_df[len_df['Balls'] >= 5]
        heat_len = len_df.pivot_table(index='Batter', columns='Pitching Length', values='SR')
        fig = px.imshow(heat_len, color_continuous_scale='RdYlGn', text_auto=True,
                        title="SR Heatmap: Batter × Length", height=480)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Dismissal % by Length (top 12 batters)**")
        dis_len = dff[dff['Batter'].isin(top12)].groupby(
            ['Batter','Pitching Length'], observed=True
        ).agg(Balls=('Run','count'), Dismissals=('Dismissed','sum')).reset_index()
        dis_len = dis_len[dis_len['Balls'] >= 5]
        dis_len['Dismissal%'] = (dis_len['Dismissals'] / dis_len['Balls'] * 100).round(2)
        heat_dis = dis_len.pivot_table(index='Batter', columns='Pitching Length', values='Dismissal%')
        fig2 = px.imshow(heat_dis, color_continuous_scale='RdYlGn_r', text_auto=True,
                         title="Dismissal % Heatmap: Batter × Length", height=480)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("Overall: Which Length Costs Most Wickets?")
    olen = dff.groupby('Pitching Length', observed=True).agg(
        Balls=('Run','count'), Runs=('Run','sum'), Dismissals=('Dismissed','sum')
    ).reset_index()
    olen['SR']         = (olen['Runs'] / olen['Balls'] * 100).round(1)
    olen['Dismissal%'] = (olen['Dismissals'] / olen['Balls'] * 100).round(2)

    col3, col4 = st.columns(2)
    with col3:
        fig3 = px.bar(olen, x='Pitching Length', y='SR',
                      color='SR', color_continuous_scale='RdYlGn',
                      text='SR', title="Strike Rate by Length", height=380)
        st.plotly_chart(fig3, use_container_width=True)
    with col4:
        fig4 = px.bar(olen, x='Pitching Length', y='Dismissal%',
                      color='Dismissal%', color_continuous_scale='RdYlGn_r',
                      text='Dismissal%', title="Dismissal % by Length", height=380)
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    st.subheader("Length Performance by Phase")
    phase_len = dff.groupby(['Phase','Pitching Length'], observed=True).agg(
        Balls=('Run','count'), Runs=('Run','sum'), Dismissals=('Dismissed','sum')
    ).reset_index()
    phase_len['SR'] = (phase_len['Runs'] / phase_len['Balls'] * 100).round(1)
    fig5 = px.bar(phase_len, x='Pitching Length', y='SR', color='Phase',
                  barmode='group', text='SR',
                  color_discrete_map={
                      'Powerplay (1–6)': '#636EFA',
                      'Middle (7–16)':   '#EF553B',
                      'Death (17–20)':   '#00CC96'
                  },
                  title="SR by Length Across Phases", height=420)
    fig5.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig5, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Batter Deep Dive
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Individual Batter Deep Dive")

    sel_batter = st.selectbox("Select Batter", sorted(dff['Batter'].unique()))
    bdf = dff[dff['Batter'] == sel_batter]

    b1, b2, b3, b4, b5 = st.columns(5)
    b1.metric("Balls Faced", len(bdf))
    b2.metric("Runs Scored", int(bdf['Run'].sum()))
    b3.metric("Dismissals", int(bdf['Dismissed'].sum()))
    sr_val = bdf['Run'].sum() / len(bdf) * 100 if len(bdf) else 0
    b4.metric("Strike Rate", f"{sr_val:.1f}")
    avg_val = bdf['Run'].sum() / bdf['Dismissed'].sum() if bdf['Dismissed'].sum() else bdf['Run'].sum()
    b5.metric("Average", f"{avg_val:.1f}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Phase-wise Performance**")
        ph = batter_stats(bdf, ['Phase'])
        fig = px.bar(ph, x='Phase', y='SR', color='Phase', text='SR',
                     color_discrete_map={
                         'Powerplay (1–6)': '#636EFA',
                         'Middle (7–16)':   '#EF553B',
                         'Death (17–20)':   '#00CC96'
                     },
                     title=f"{sel_batter} – SR by Phase", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Pacer vs Spinner**")
        pt = batter_stats(bdf, ['Type'])
        fig2 = px.bar(pt, x='Type', y='SR', color='Type', text='SR',
                      title=f"{sel_batter} – SR vs Pacer/Spinner", height=380)
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**SR by Pitching Length**")
        pl = batter_stats(bdf, ['Pitching Length'])
        fig3 = px.bar(pl, x='Pitching Length', y='SR', color='SR',
                      color_continuous_scale='RdYlGn', text='SR',
                      title=f"{sel_batter} – SR by Length", height=380)
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown("**SR by Pitching Line**")
        pln = batter_stats(bdf, ['Pitching Line'])
        fig4 = px.bar(pln, x='Pitching Line', y='SR', color='SR',
                      color_continuous_scale='RdYlGn', text='SR',
                      title=f"{sel_batter} – SR by Line", height=380)
        fig4.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("**Phase × Bowler Type Breakdown**")
    ph_pt = batter_stats(bdf, ['Phase', 'Type'])
    fig5 = px.bar(ph_pt, x='Phase', y='SR', color='Type', barmode='group',
                  text='SR', title=f"{sel_batter} – SR by Phase & Bowler Type", height=380)
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown("**Ball-by-ball Runs**")
    bdf_r = bdf.reset_index(drop=True)
    bdf_r['Delivery #'] = bdf_r.index + 1
    fig6 = px.scatter(bdf_r, x='Delivery #', y='Run',
                      color='Phase', symbol='Type',
                      hover_data=['Bowler','Speed','Pitching Length','Pitching Line'],
                      title=f"{sel_batter} – Ball by Ball", height=380)
    st.plotly_chart(fig6, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Raw Data
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Filtered Raw Data")
    st.dataframe(dff.reset_index(drop=True), use_container_width=True)
    csv = dff.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download filtered data as CSV", csv,
                       "filtered_batter_data.csv", "text/csv")
