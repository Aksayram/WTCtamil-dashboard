import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="IPL Analytics 2023–2025", layout="wide", page_icon="🏏")

# ── Load & clean ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    df = pd.read_excel(path)

    # Normalize names
    df['bat']       = df['bat'].str.strip().str.title()
    df['bowl']      = df['bowl'].str.strip().str.title()
    df['team_bat']  = df['team_bat'].str.strip().str.replace('Royal Challengers Bangalore','RCB').str.replace('Royal Challengers Bengaluru','RCB')
    df['team_bowl'] = df['team_bowl'].str.strip().str.replace('Royal Challengers Bangalore','RCB').str.replace('Royal Challengers Bengaluru','RCB')
    df['ground']    = df['ground'].str.strip()
    df['shot']      = df['shot'].str.strip()
    df['line']      = df['line'].str.strip()
    df['length']    = df['length'].str.strip()

    # Numerics
    for c in ['score','batruns','over','out','control','wagonX','wagonY','wagonZone','wprob']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['out'] = df['out'].fillna(0).astype(int)

    # Phase
    def phase(o):
        if o <= 6:  return 'Powerplay (1–6)'
        if o <= 16: return 'Middle (7–16)'
        return 'Death (17–20)'
    df['phase'] = df['over'].apply(phase)
    df['phase'] = pd.Categorical(df['phase'],
                    categories=['Powerplay (1–6)','Middle (7–16)','Death (17–20)'], ordered=True)

    # Readable labels
    df['line_label']   = df['line'].str.replace('_',' ').str.title()
    df['length_label'] = df['length'].str.replace('_',' ').str.title()
    df['shot_label']   = df['shot'].str.replace('_',' ').str.title()

    return df

FILE = "IPL_2023_to_2025_Base_Data.xlsx"
try:
    df = load_data(FILE)
except FileNotFoundError:
    uploaded = st.file_uploader("Upload IPL_2023_to_2025_Base_Data.xlsx", type=["xlsx"])
    if uploaded:
        df = load_data(uploaded)
    else:
        st.info("Please upload the IPL data file.")
        st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🏏 IPL Filters")

sel_year = st.sidebar.multiselect("Year", sorted(df['year'].unique()), default=sorted(df['year'].unique()))
sel_phase = st.sidebar.multiselect("Phase", ['Powerplay (1–6)','Middle (7–16)','Death (17–20)'],
                                    default=['Powerplay (1–6)','Middle (7–16)','Death (17–20)'])
sel_bowl_kind = st.sidebar.multiselect("Bowler Kind", sorted(df['bowl_kind'].dropna().unique()),
                                        default=sorted(df['bowl_kind'].dropna().unique()))
sel_bat_hand = st.sidebar.multiselect("Batter Hand", sorted(df['bat_hand'].dropna().unique()),
                                       default=sorted(df['bat_hand'].dropna().unique()))
sel_team_bat = st.sidebar.multiselect("Batting Team", sorted(df['team_bat'].dropna().unique()),
                                       default=sorted(df['team_bat'].dropna().unique()))
min_balls = st.sidebar.slider("Min balls (filter noise)", 5, 60, 15)

# Apply filters
filt = (
    df['year'].isin(sel_year) &
    df['phase'].isin(sel_phase) &
    df['bowl_kind'].isin(sel_bowl_kind) &
    df['bat_hand'].isin(sel_bat_hand) &
    df['team_bat'].isin(sel_team_bat)
)
dff = df[filt]

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🏏 IPL Analytics Dashboard  |  2023 – 2025")
st.caption(f"**{len(dff):,}** deliveries  |  **{dff['p_match'].nunique()}** matches  |  **{dff['bat'].nunique()}** batters  |  **{dff['bowl'].nunique()}** bowlers")

if dff.empty:
    st.warning("No data matches current filters.")
    st.stop()

# KPIs
k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.metric("Deliveries", f"{len(dff):,}")
k2.metric("Runs Scored", f"{int(dff['batruns'].sum()):,}")
k3.metric("Wickets", f"{int(dff['out'].sum()):,}")
k4.metric("Fours", f"{int((dff['score']==4).sum()):,}")
k5.metric("Sixes", f"{int((dff['score']==6).sum()):,}")
sr = dff['batruns'].sum() / dff[dff['wide']==0]['score'].count() * 100
k6.metric("Overall SR", f"{sr:.1f}")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs([
    "🎯 Shot Analysis",
    "📍 Line & Length",
    "🏏 Batter Analysis",
    "🎳 Bowler Analysis",
    "🏆 Team Analysis",
    "📅 Year on Year",
    "💥 Game Changers",
    "📋 Raw Data"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Shot Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Shot Effectiveness Analysis")

    shot_df = dff.dropna(subset=['shot'])
    shot_grp = shot_df.groupby('shot_label').agg(
        Balls  =('batruns','count'),
        Runs   =('batruns','sum'),
        Outs   =('out','sum'),
        Controlled=('control','sum')
    ).reset_index()
    shot_grp = shot_grp[shot_grp['Balls'] >= 10]
    shot_grp['Avg Runs']     = (shot_grp['Runs'] / shot_grp['Balls']).round(2)
    shot_grp['Dismissal%']   = (shot_grp['Outs'] / shot_grp['Balls'] * 100).round(1)
    shot_grp['Control%']     = (shot_grp['Controlled'] / shot_grp['Balls'] * 100).round(1)
    shot_grp['Frequency%']   = (shot_grp['Balls'] / shot_grp['Balls'].sum() * 100).round(1)
    shot_grp['Effectiveness']= (shot_grp['Avg Runs'] / (shot_grp['Dismissal%']/100 + 0.01)).round(2)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Average Runs per Shot**")
        fig = px.bar(shot_grp.sort_values('Avg Runs', ascending=True),
                     x='Avg Runs', y='shot_label', orientation='h',
                     color='Avg Runs', color_continuous_scale='RdYlGn',
                     text='Avg Runs', height=550,
                     title="Avg Runs per Ball by Shot Type")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Dismissal Risk vs Run Reward**")
        fig2 = px.scatter(shot_grp, x='Avg Runs', y='Dismissal%',
                          size='Balls', text='shot_label', color='Control%',
                          color_continuous_scale='RdYlGn',
                          title="Risk vs Reward (size = frequency)",
                          height=550)
        fig2.update_traces(textposition='top center', textfont_size=9)
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**Shot Frequency (How often each shot is played)**")
        fig3 = px.pie(shot_grp.nlargest(12,'Balls'), names='shot_label', values='Balls',
                      title="Shot Frequency – Top 12", height=420)
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown("**Control Rate by Shot**")
        fig4 = px.bar(shot_grp.sort_values('Control%', ascending=True),
                      x='Control%', y='shot_label', orientation='h',
                      color='Control%', color_continuous_scale='Blues',
                      text='Control%', height=420,
                      title="% of Controlled Shots")
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    st.subheader("Shot Performance by Phase")
    sp = shot_df.groupby(['shot_label','phase'], observed=True).agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    sp = sp[sp['Balls'] >= 5]
    sp['Avg Runs'] = (sp['Runs']/sp['Balls']).round(2)
    top_shots = shot_grp.nlargest(10,'Balls')['shot_label'].tolist()
    sp_top = sp[sp['shot_label'].isin(top_shots)]
    fig5 = px.bar(sp_top, x='shot_label', y='Avg Runs', color='phase', barmode='group',
                  color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                  title="Avg Runs by Shot × Phase (Top 10 shots)", height=420)
    fig5.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown("**Full Shot Summary Table**")
    st.dataframe(shot_grp.sort_values('Avg Runs', ascending=False).reset_index(drop=True), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Line & Length
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Line & Length Analysis")

    ll = dff.dropna(subset=['line','length'])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**SR Heatmap: Line × Length**")
        ll_grp = ll.groupby(['length_label','line_label']).agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
        ).reset_index()
        ll_grp['SR'] = (ll_grp['Runs']/ll_grp['Balls']*100).round(1)
        pivot_sr = ll_grp.pivot(index='length_label', columns='line_label', values='SR')
        fig = px.imshow(pivot_sr, color_continuous_scale='RdYlGn', text_auto=True,
                        title="Strike Rate: Length × Line", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Dismissal% Heatmap: Line × Length**")
        ll_grp['Dismissal%'] = (ll_grp['Outs']/ll_grp['Balls']*100).round(2)
        pivot_dis = ll_grp.pivot(index='length_label', columns='line_label', values='Dismissal%')
        fig2 = px.imshow(pivot_dis, color_continuous_scale='RdYlGn_r', text_auto=True,
                         title="Dismissal %: Length × Line", height=400)
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**Runs by Length**")
        llen = ll.groupby('length_label').agg(Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')).reset_index()
        llen['SR'] = (llen['Runs']/llen['Balls']*100).round(1)
        llen['Dis%'] = (llen['Outs']/llen['Balls']*100).round(2)
        fig3 = px.bar(llen, x='length_label', y='SR', color='SR',
                      color_continuous_scale='RdYlGn', text='SR',
                      title="Strike Rate by Length", height=380)
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown("**Runs by Line**")
        lline = ll.groupby('line_label').agg(Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')).reset_index()
        lline['SR'] = (lline['Runs']/lline['Balls']*100).round(1)
        fig4 = px.bar(lline, x='line_label', y='SR', color='SR',
                      color_continuous_scale='RdYlGn', text='SR',
                      title="Strike Rate by Line", height=380)
        fig4.update_layout(xaxis_tickangle=-20)
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    st.subheader("Line & Length by Phase")
    ll_phase = ll.groupby(['phase','length_label'], observed=True).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')
    ).reset_index()
    ll_phase['SR'] = (ll_phase['Runs']/ll_phase['Balls']*100).round(1)
    fig5 = px.bar(ll_phase, x='length_label', y='SR', color='phase', barmode='group',
                  color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                  title="SR by Length Across Phases", height=400)
    fig5.update_layout(xaxis_tickangle=-20)
    st.plotly_chart(fig5, use_container_width=True)

    st.divider()
    st.subheader("Most Effective Shot per Line & Length")
    ll_shot = dff.dropna(subset=['line','length','shot']).groupby(
        ['length_label','line_label','shot_label']
    ).agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    ll_shot = ll_shot[ll_shot['Balls'] >= 5]
    ll_shot['Avg'] = (ll_shot['Runs']/ll_shot['Balls']).round(2)
    best_shot = ll_shot.loc[ll_shot.groupby(['length_label','line_label'])['Avg'].idxmax()]
    pivot_shot = best_shot.pivot(index='length_label', columns='line_label', values='shot_label')
    fig6 = px.imshow(pivot_shot, text_auto=True, color_continuous_scale='Blues',
                     title="Best Scoring Shot per Line & Length Zone", height=380)
    st.plotly_chart(fig6, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Batter Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Batter Performance Analysis")

    batter_grp = dff.groupby('bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    batter_grp = batter_grp[batter_grp['Balls'] >= min_balls]
    batter_grp['SR']  = (batter_grp['Runs']/batter_grp['Balls']*100).round(1)
    batter_grp['Avg'] = (batter_grp['Runs']/batter_grp['Outs'].replace(0,np.nan)).round(1).fillna(batter_grp['Runs'])

    col1, col2 = st.columns(2)
    with col1:
        top_n = st.slider("Top N batters", 5, 30, 15, key='bat_n')
        metric = st.radio("Rank by", ['SR','Runs','Avg'], horizontal=True, key='bat_metric')
        fig = px.bar(batter_grp.nlargest(top_n, metric),
                     x='bat', y=metric, color=metric,
                     color_continuous_scale='Teal', text=metric,
                     title=f"Top {top_n} Batters by {metric}", height=420)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**SR vs Average (bubble = balls faced)**")
        fig2 = px.scatter(batter_grp.nlargest(40,'Balls'),
                          x='Avg', y='SR', size='Balls', text='bat',
                          color='Runs', color_continuous_scale='Viridis',
                          title="SR vs Average – Top 40 Batters", height=420)
        fig2.update_traces(textposition='top center', textfont_size=8)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("Individual Batter Deep Dive")
    sel_bat = st.selectbox("Select Batter", sorted(dff['bat'].unique()))
    bdf = dff[dff['bat']==sel_bat]

    b1,b2,b3,b4,b5 = st.columns(5)
    b1.metric("Balls", len(bdf))
    b2.metric("Runs", int(bdf['batruns'].sum()))
    b3.metric("Dismissals", int(bdf['out'].sum()))
    b4.metric("SR", f"{bdf['batruns'].sum()/len(bdf)*100:.1f}")
    b5.metric("4s / 6s", f"{int((bdf['score']==4).sum())} / {int((bdf['score']==6).sum())}")

    col3,col4 = st.columns(2)
    with col3:
        ph = bdf.groupby('phase', observed=True).agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
        ph['SR'] = (ph['Runs']/ph['Balls']*100).round(1)
        fig3 = px.bar(ph, x='phase', y='SR', color='phase', text='SR',
                      title=f"{sel_bat} – SR by Phase", height=350)
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        pk = bdf.groupby('bowl_kind').agg(Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')).reset_index()
        pk['SR'] = (pk['Runs']/pk['Balls']*100).round(1)
        fig4 = px.bar(pk, x='bowl_kind', y='SR', color='bowl_kind', text='SR',
                      title=f"{sel_bat} – SR vs Pace/Spin", height=350)
        st.plotly_chart(fig4, use_container_width=True)

    col5,col6 = st.columns(2)
    with col5:
        bs = bdf.dropna(subset=['shot']).groupby('shot_label').agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
        ).reset_index()
        bs = bs[bs['Balls']>=3]
        bs['Avg Runs'] = (bs['Runs']/bs['Balls']).round(2)
        fig5 = px.bar(bs.sort_values('Avg Runs', ascending=False),
                      x='shot_label', y='Avg Runs', color='Avg Runs',
                      color_continuous_scale='RdYlGn', text='Avg Runs',
                      title=f"{sel_bat} – Best Shots", height=380)
        fig5.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig5, use_container_width=True)

    with col6:
        bl = bdf.dropna(subset=['length']).groupby('length_label').agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
        ).reset_index()
        bl['SR'] = (bl['Runs']/bl['Balls']*100).round(1)
        bl['Dis%'] = (bl['Outs']/bl['Balls']*100).round(1)
        fig6 = px.bar(bl, x='length_label', y='SR', color='Dis%',
                      color_continuous_scale='RdYlGn_r', text='SR',
                      title=f"{sel_bat} – SR by Length (color=dismissal risk)", height=380)
        st.plotly_chart(fig6, use_container_width=True)

    # Wagon wheel
    st.markdown(f"**{sel_bat} – Scoring Zones (Wagon Wheel)**")
    wz = bdf.groupby('wagonZone').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    wz['SR'] = (wz['Runs']/wz['Balls']*100).round(1)
    zone_labels = {0:'Dot Zone',1:'Fine Leg',2:'Square Leg',3:'Mid Wicket',
                   4:'Mid On',5:'Mid Off',6:'Cover',7:'Point',8:'Third Man'}
    wz['Zone'] = wz['wagonZone'].map(zone_labels)
    fig7 = px.bar_polar(wz, r='Runs', theta='Zone', color='SR',
                        color_continuous_scale='RdYlGn',
                        title=f"{sel_bat} – Runs by Wagon Zone", height=420)
    st.plotly_chart(fig7, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Bowler Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Bowler Performance Analysis")

    bowl_grp = dff[dff['wide']==0].groupby('bowl').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('out','sum')
    ).reset_index()
    bowl_grp = bowl_grp[bowl_grp['Balls'] >= min_balls]
    bowl_grp['Economy']  = (bowl_grp['Runs']/(bowl_grp['Balls']/6)).round(2)
    bowl_grp['SR']       = (bowl_grp['Balls']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)
    bowl_grp['Avg']      = (bowl_grp['Runs']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)

    col1,col2 = st.columns(2)
    with col1:
        top_nb = st.slider("Top N bowlers", 5, 30, 15, key='bowl_n')
        bmetric = st.radio("Rank by", ['Economy','Wickets','Avg'], horizontal=True, key='bowl_metric')
        ascending = bmetric in ['Economy','Avg']
        fig = px.bar(bowl_grp.nsmallest(top_nb, bmetric) if ascending else bowl_grp.nlargest(top_nb, bmetric),
                     x='bowl', y=bmetric, color=bmetric,
                     color_continuous_scale='RdYlGn_r' if ascending else 'Teal',
                     text=bmetric,
                     title=f"Top {top_nb} Bowlers by {bmetric}", height=420)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Economy vs Wickets (bubble = balls bowled)**")
        fig2 = px.scatter(bowl_grp.nlargest(40,'Balls'),
                          x='Economy', y='Wickets', size='Balls', text='bowl',
                          color='Avg', color_continuous_scale='RdYlGn_r',
                          title="Economy vs Wickets – Top 40 Bowlers", height=420)
        fig2.update_traces(textposition='top center', textfont_size=8)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("Bowler's Most Used Line & Length")
    sel_bowl = st.selectbox("Select Bowler", sorted(dff['bowl'].unique()))
    bwdf = dff[dff['bowl']==sel_bowl].dropna(subset=['line','length'])

    bw1,bw2,bw3,bw4 = st.columns(4)
    bw1.metric("Balls", len(dff[dff['bowl']==sel_bowl]))
    bw2.metric("Wickets", int(dff[dff['bowl']==sel_bowl]['out'].sum()))
    econ = dff[dff['bowl']==sel_bowl]['batruns'].sum() / (len(dff[dff['bowl']==sel_bowl])/6)
    bw3.metric("Economy", f"{econ:.2f}")
    bw4.metric("Bowl Kind", dff[dff['bowl']==sel_bowl]['bowl_kind'].mode()[0] if len(dff[dff['bowl']==sel_bowl]) else "N/A")

    col3,col4 = st.columns(2)
    with col3:
        ll_b = bwdf.groupby(['length_label','line_label']).agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('out','sum')
        ).reset_index()
        ll_b['Economy'] = (ll_b['Runs']/(ll_b['Balls']/6)).round(2)
        pivot_b = ll_b.pivot(index='length_label', columns='line_label', values='Balls')
        fig3 = px.imshow(pivot_b, text_auto=True, color_continuous_scale='Blues',
                         title=f"{sel_bowl} – Delivery Map (balls bowled)", height=380)
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        pivot_wk = ll_b.pivot(index='length_label', columns='line_label', values='Wickets')
        fig4 = px.imshow(pivot_wk, text_auto=True, color_continuous_scale='Reds',
                         title=f"{sel_bowl} – Wickets by Line & Length", height=380)
        st.plotly_chart(fig4, use_container_width=True)

    # Dismissal by shot
    col5,col6 = st.columns(2)
    with col5:
        dis_shot = dff[(dff['bowl']==sel_bowl) & (dff['out']==1)].dropna(subset=['shot'])
        ds = dis_shot['shot_label'].value_counts().reset_index()
        ds.columns = ['Shot','Wickets']
        fig5 = px.bar(ds, x='Shot', y='Wickets', color='Wickets',
                      color_continuous_scale='Reds', text='Wickets',
                      title=f"{sel_bowl} – Wickets by Shot Type", height=380)
        fig5.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig5, use_container_width=True)

    with col6:
        ph_b = dff[dff['bowl']==sel_bowl].groupby('phase', observed=True).agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('out','sum')
        ).reset_index()
        ph_b['Economy'] = (ph_b['Runs']/(ph_b['Balls']/6)).round(2)
        fig6 = px.bar(ph_b, x='phase', y='Economy', color='phase', text='Economy',
                      title=f"{sel_bowl} – Economy by Phase", height=380)
        st.plotly_chart(fig6, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Team Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Team Performance Analysis")

    team_bat = dff.groupby('team_bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    team_bat['SR']  = (team_bat['Runs']/team_bat['Balls']*100).round(1)
    team_bat['Avg'] = (team_bat['Runs']/team_bat['Outs'].replace(0,np.nan)).round(1)

    col1,col2 = st.columns(2)
    with col1:
        fig = px.bar(team_bat.sort_values('SR', ascending=False),
                     x='team_bat', y='SR', color='SR',
                     color_continuous_scale='RdYlGn', text='SR',
                     title="Team Batting SR", height=380)
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig2 = px.bar(team_bat.sort_values('Runs', ascending=False),
                      x='team_bat', y='Runs', color='Runs',
                      color_continuous_scale='Blues', text='Runs',
                      title="Total Runs by Team", height=380)
        fig2.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("Team vs Pace & Spin")
    team_ps = dff.groupby(['team_bat','bowl_kind']).agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    team_ps['SR'] = (team_ps['Runs']/team_ps['Balls']*100).round(1)
    fig3 = px.bar(team_ps, x='team_bat', y='SR', color='bowl_kind', barmode='group',
                  title="Team SR vs Pace / Spin / Mixed", height=420,
                  text='SR')
    fig3.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.subheader("Team Preferred Scoring Zones")
    sel_team = st.selectbox("Select Team", sorted(dff['team_bat'].unique()))
    tdf = dff[dff['team_bat']==sel_team]
    wz_t = tdf.groupby('wagonZone').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    wz_t['Zone'] = wz_t['wagonZone'].map({0:'Dot Zone',1:'Fine Leg',2:'Square Leg',
                                           3:'Mid Wicket',4:'Mid On',5:'Mid Off',
                                           6:'Cover',7:'Point',8:'Third Man'})
    fig4 = px.bar_polar(wz_t, r='Runs', theta='Zone', color='Runs',
                        color_continuous_scale='RdYlGn',
                        title=f"{sel_team} – Scoring Zones", height=420)
    st.plotly_chart(fig4, use_container_width=True)

    st.subheader("Team Batting by Phase")
    team_phase = dff.groupby(['team_bat','phase'], observed=True).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')
    ).reset_index()
    team_phase['SR'] = (team_phase['Runs']/team_phase['Balls']*100).round(1)
    fig5 = px.bar(team_phase, x='team_bat', y='SR', color='phase', barmode='group',
                  color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                  title="Team SR by Phase", height=420, text='SR')
    fig5.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig5, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Year on Year
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.subheader("Year on Year Trends (2023 → 2024 → 2025)")

    yoy = dff.groupby('year').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x: (x==4).sum()),
        Sixes=('score', lambda x: (x==6).sum())
    ).reset_index()
    yoy['SR']        = (yoy['Runs']/yoy['Balls']*100).round(1)
    yoy['Boundary%'] = ((yoy['Fours']+yoy['Sixes'])/yoy['Balls']*100).round(1)

    col1,col2,col3 = st.columns(3)
    with col1:
        fig = px.line(yoy, x='year', y='SR', markers=True, text='SR',
                      title="Overall SR Trend", height=320)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig2 = px.line(yoy, x='year', y='Boundary%', markers=True, text='Boundary%',
                       title="Boundary % Trend", height=320)
        st.plotly_chart(fig2, use_container_width=True)
    with col3:
        fig3 = px.bar(yoy, x='year', y=['Fours','Sixes'], barmode='group',
                      title="Fours vs Sixes by Year", height=320)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.subheader("Most Popular Shots by Year")
    shot_yr = dff.dropna(subset=['shot']).groupby(['year','shot_label']).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')
    ).reset_index()
    shot_yr['Avg'] = (shot_yr['Runs']/shot_yr['Balls']).round(2)
    top_s = dff['shot_label'].value_counts().head(8).index.tolist()
    fig4 = px.bar(shot_yr[shot_yr['shot_label'].isin(top_s)],
                  x='shot_label', y='Balls', color='year', barmode='group',
                  title="Shot Frequency by Year (Top 8 shots)", height=400)
    fig4.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig4, use_container_width=True)

    st.subheader("Team SR Trend by Year")
    team_yr = dff.groupby(['team_bat','year']).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')
    ).reset_index()
    team_yr['SR'] = (team_yr['Runs']/team_yr['Balls']*100).round(1)
    fig5 = px.line(team_yr, x='year', y='SR', color='team_bat', markers=True,
                   title="Team SR Trend 2023–2025", height=420)
    st.plotly_chart(fig5, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — Game Changers
# ══════════════════════════════════════════════════════════════════════════════
with tab7:
    st.subheader("💥 Game Changers – Who Dominates an Over?")
    st.caption("A batter is a Game Changer when they score 10+ runs in a single over")

    # Build over-level data from filtered df
    over_data = dff.groupby(
        ['p_match','inns','over','bat','team_bat','bowl_kind','phase','year'], observed=True
    ).agg(
        over_runs =('batruns','sum'),
        balls     =('batruns','count'),
        outs      =('out','sum')
    ).reset_index()

    run_threshold = st.slider("Impact Over: Minimum runs in one over", 6, 20, 10)
    impact = over_data[over_data['over_runs'] >= run_threshold].copy()

    if impact.empty:
        st.warning("No data found for this threshold. Try lowering the minimum runs.")
    else:
        st.markdown(f"**Total {run_threshold}+ run overs found: {len(impact):,}**")
        st.divider()

        # ── Pre-compute total overs batted per batter (used across all tables) ──
        total_overs_all = over_data.groupby('bat').agg(
            Total_Overs_Batted=('over_runs','count')
        ).reset_index()

        # Helper to add Impact Frequency % to any leaderboard df
        def add_freq(df, total_col='Total_Overs_Batted'):
            df = pd.merge(df, total_overs_all, on='bat', how='left')
            df['Impact_Freq%'] = (df['Impact_Overs'] / df[total_col] * 100).round(1)
            return df

        # ── Overall leaderboard ──
        st.markdown("### 🏆 Overall Game Changer Leaderboard")
        overall = impact.groupby('bat').agg(
            Impact_Overs  =('over_runs','count'),
            Total_Runs    =('over_runs','sum'),
            Best_Over     =('over_runs','max'),
            Avg_Runs      =('over_runs','mean')
        ).reset_index().sort_values('Impact_Overs', ascending=False).reset_index(drop=True)
        overall = add_freq(overall)
        overall['Avg_Runs'] = overall['Avg_Runs'].round(1)
        overall.index += 1

        col1, col2 = st.columns([1.2, 1])
        with col1:
            fig = px.bar(
                overall.head(15), x='bat', y='Impact_Overs',
                color='Impact_Overs', color_continuous_scale='Plasma',
                text='Impact_Overs',
                title=f"Top 15 – Most {run_threshold}+ Run Overs", height=420
            )
            fig.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Full Leaderboard**")
            st.dataframe(overall[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over','Avg_Runs']],
                         use_container_width=True, height=400)

        st.divider()

        # ── Pace vs Spin ──
        st.markdown("### ⚡ Game Changers: Pace vs Spin")
        col3, col4 = st.columns(2)

        with col3:
            pace_lb = impact[impact['bowl_kind']=='pace bowler'].groupby('bat').agg(
                Impact_Overs=('over_runs','count'),
                Total_Runs  =('over_runs','sum'),
                Best_Over   =('over_runs','max')
            ).reset_index().sort_values('Impact_Overs', ascending=False).reset_index(drop=True)
            pace_lb = add_freq(pace_lb)
            pace_lb.index += 1
            fig2 = px.bar(pace_lb.head(10), x='bat', y='Impact_Overs',
                          color='Impact_Overs', color_continuous_scale='Reds',
                          text='Impact_Overs',
                          title=f"Top 10 vs PACE – {run_threshold}+ Run Overs", height=400)
            fig2.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(pace_lb[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over']],
                         use_container_width=True)

        with col4:
            spin_lb = impact[impact['bowl_kind']=='spin bowler'].groupby('bat').agg(
                Impact_Overs=('over_runs','count'),
                Total_Runs  =('over_runs','sum'),
                Best_Over   =('over_runs','max')
            ).reset_index().sort_values('Impact_Overs', ascending=False).reset_index(drop=True)
            spin_lb = add_freq(spin_lb)
            spin_lb.index += 1
            fig3 = px.bar(spin_lb.head(10), x='bat', y='Impact_Overs',
                          color='Impact_Overs', color_continuous_scale='Blues',
                          text='Impact_Overs',
                          title=f"Top 10 vs SPIN – {run_threshold}+ Run Overs", height=400)
            fig3.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig3, use_container_width=True)
            st.dataframe(spin_lb[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over']],
                         use_container_width=True)

        # ── Impact Frequency % Chart (Overall) ──
        st.divider()
        st.markdown("### 🎯 Impact Frequency % – Most Consistent Game Changers")
        st.caption("Impact Frequency = (10+ run overs) ÷ (Total overs batted) × 100")
        freq_df = overall.sort_values('Impact_Freq%', ascending=False).reset_index(drop=True)
        col_f1, col_f2 = st.columns([1.2, 1])
        with col_f1:
            fig_freq = px.bar(
                freq_df.head(15), x='bat', y='Impact_Freq%',
                color='Impact_Freq%', color_continuous_scale='RdYlGn',
                text='Impact_Freq%',
                title="Top 15 – Highest Impact Frequency %", height=420
            )
            fig_freq.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_freq, use_container_width=True)
        with col_f2:
            st.markdown("**Full Impact Frequency Table**")
            st.dataframe(
                freq_df[['bat','Impact_Freq%','Impact_Overs','Total_Overs_Batted','Total_Runs','Best_Over','Avg_Runs']],
                use_container_width=True, height=400
            )

        st.divider()

        # ── Phase-wise Game Changers (CHART + FULL LIST) ──
        st.markdown("### 📊 Game Changers by Phase")
        for ph_name, color in zip(
            ['Powerplay (1–6)', 'Middle (7–16)', 'Death (17–20)'],
            ['Teal', 'Oranges', 'Purples']
        ):
            st.markdown(f"#### 🏏 {ph_name}")

            # Build phase total overs for frequency
            phase_total_overs = over_data[over_data['phase'].astype(str)==ph_name].groupby('bat').agg(
                Total_Overs_Batted=('over_runs','count')
            ).reset_index()

            ph_lb = impact[impact['phase'].astype(str)==ph_name].groupby('bat').agg(
                Impact_Overs=('over_runs','count'),
                Total_Runs  =('over_runs','sum'),
                Best_Over   =('over_runs','max'),
                Avg_Runs    =('over_runs','mean')
            ).reset_index().sort_values('Impact_Overs', ascending=False).reset_index(drop=True)

            # Use phase-specific total overs for frequency
            ph_lb = pd.merge(ph_lb, phase_total_overs, on='bat', how='left')
            ph_lb['Impact_Freq%'] = (ph_lb['Impact_Overs'] / ph_lb['Total_Overs_Batted'] * 100).round(1)
            ph_lb['Avg_Runs'] = ph_lb['Avg_Runs'].round(1)

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                fig_ph1 = px.bar(
                    ph_lb.head(15), x='bat', y='Impact_Overs',
                    color='Impact_Overs', color_continuous_scale=color,
                    text='Impact_Overs',
                    title=f"Most Impact Overs – {ph_name}", height=380
                )
                fig_ph1.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_ph1, use_container_width=True)

            with col_b:
                fig_ph2 = px.bar(
                    ph_lb.sort_values('Impact_Freq%', ascending=False).head(15),
                    x='bat', y='Impact_Freq%',
                    color='Impact_Freq%', color_continuous_scale='RdYlGn',
                    text='Impact_Freq%',
                    title=f"Highest Impact Freq% – {ph_name}", height=380
                )
                fig_ph2.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_ph2, use_container_width=True)

            with col_c:
                st.markdown(f"**Full List – {ph_name}**")
                ph_lb.index = ph_lb.index + 1
                st.dataframe(
                    ph_lb[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over','Avg_Runs']],
                    use_container_width=True, height=380
                )

        st.divider()

        # ── Individual batter impact profile ──
        st.markdown("### 🔍 Individual Batter Impact Profile")
        sel_gc = st.selectbox("Select Batter", sorted(impact['bat'].unique()), key='gc_bat')
        bat_impact = impact[impact['bat']==sel_gc]

        # Calculate Impact Freq% for selected batter
        bat_total_overs = over_data[over_data['bat']==sel_gc].shape[0]
        bat_impact_freq = (len(bat_impact) / bat_total_overs * 100) if bat_total_overs > 0 else 0

        gc1, gc2, gc3, gc4, gc5 = st.columns(5)
        gc1.metric("Total Impact Overs", len(bat_impact))
        gc2.metric("Total Overs Batted", bat_total_overs)
        gc3.metric("Impact Freq%", f"{bat_impact_freq:.1f}%")
        gc4.metric("Best Over", int(bat_impact['over_runs'].max()))
        gc5.metric("Total Runs in Impact Overs", int(bat_impact['over_runs'].sum()))

        st.markdown("#### ⚡ vs Pace & Spin")
        # Build pace/spin stats with frequency
        bk = bat_impact.groupby('bowl_kind').agg(
            Impact_Overs=('over_runs','count'),
            Avg_Runs    =('over_runs','mean')
        ).reset_index()
        bk['Avg_Runs'] = bk['Avg_Runs'].round(1)
        # Total overs vs each bowl kind for frequency
        bk_total = over_data[over_data['bat']==sel_gc].groupby('bowl_kind').agg(
            Total_Overs=('over_runs','count')
        ).reset_index()
        bk = pd.merge(bk, bk_total, on='bowl_kind', how='left')
        bk['Impact_Freq%'] = (bk['Impact_Overs'] / bk['Total_Overs'] * 100).round(1)

        col8, col9 = st.columns(2)
        with col8:
            fig_bk1 = px.bar(bk, x='bowl_kind', y='Impact_Overs',
                             color='bowl_kind', text='Impact_Overs',
                             title=f"{sel_gc} – Impact Overs Count vs Pace/Spin",
                             height=350)
            fig_bk1.update_layout(showlegend=False)
            st.plotly_chart(fig_bk1, use_container_width=True)

        with col9:
            fig_bk2 = px.bar(bk, x='bowl_kind', y='Impact_Freq%',
                             color='bowl_kind', text='Impact_Freq%',
                             color_discrete_sequence=['#EF553B','#636EFA'],
                             title=f"{sel_gc} – Impact Frequency % vs Pace/Spin",
                             height=350)
            fig_bk2.update_layout(showlegend=False)
            st.plotly_chart(fig_bk2, use_container_width=True)

        st.markdown("#### 📊 Phase-wise")
        # Build phase stats with frequency
        ph_b = bat_impact.groupby('phase', observed=True).agg(
            Impact_Overs=('over_runs','count'),
            Avg_Runs    =('over_runs','mean')
        ).reset_index()
        ph_b['Avg_Runs'] = ph_b['Avg_Runs'].round(1)
        # Total overs per phase for frequency
        ph_total = over_data[over_data['bat']==sel_gc].groupby(
            'phase', observed=True
        ).agg(Total_Overs=('over_runs','count')).reset_index()
        ph_b = pd.merge(ph_b, ph_total, on='phase', how='left')
        ph_b['Impact_Freq%'] = (ph_b['Impact_Overs'] / ph_b['Total_Overs'] * 100).round(1)

        col10, col11 = st.columns(2)
        with col10:
            fig_pb1 = px.bar(ph_b, x='phase', y='Impact_Overs',
                             color='phase', text='Impact_Overs',
                             color_discrete_map={
                                 'Powerplay (1–6)':'#636EFA',
                                 'Middle (7–16)':'#EF553B',
                                 'Death (17–20)':'#00CC96'
                             },
                             title=f"{sel_gc} – Impact Overs Count by Phase",
                             height=350)
            fig_pb1.update_layout(showlegend=False)
            st.plotly_chart(fig_pb1, use_container_width=True)

        with col11:
            fig_pb2 = px.bar(ph_b, x='phase', y='Impact_Freq%',
                             color='phase', text='Impact_Freq%',
                             color_discrete_map={
                                 'Powerplay (1–6)':'#636EFA',
                                 'Middle (7–16)':'#EF553B',
                                 'Death (17–20)':'#00CC96'
                             },
                             title=f"{sel_gc} – Impact Frequency % by Phase",
                             height=350)
            fig_pb2.update_layout(showlegend=False)
            st.plotly_chart(fig_pb2, use_container_width=True)

        # Year trend
        yr_b = bat_impact.groupby('year').agg(Impact_Overs=('over_runs','count')).reset_index()
        fig_yr = px.line(yr_b, x='year', y='Impact_Overs', markers=True,
                         text='Impact_Overs',
                         title=f"{sel_gc} – Impact Overs Trend 2023–2025", height=320)
        st.plotly_chart(fig_yr, use_container_width=True)

        # Distribution of runs scored in impact overs
        fig_hist = px.histogram(bat_impact, x='over_runs', nbins=15,
                                title=f"{sel_gc} – Distribution of Runs in Impact Overs",
                                color_discrete_sequence=['#636EFA'], height=320)
        st.plotly_chart(fig_hist, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — Raw Data
# ══════════════════════════════════════════════════════════════════════════════
with tab8:
    st.subheader("Filtered Raw Data")
    cols_show = ['year','bat','team_bat','bowl','team_bowl','over','phase',
                 'score','batruns','out','shot_label','line_label','length_label',
                 'bowl_kind','bat_hand','wagonZone','control']
    st.dataframe(dff[cols_show].reset_index(drop=True), use_container_width=True)
    csv = dff[cols_show].to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download filtered data as CSV", csv, "ipl_filtered.csv", "text/csv")
