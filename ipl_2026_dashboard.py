import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

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
    else:
        return True

if not check_password():
    st.stop()

st.set_page_config(page_title="IPL 2026 Analytics", layout="wide", page_icon="🏏")

# ── Load & clean ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, sheet_name='t20_bbb (1)')
    df['bat']        = df['bat'].str.strip().str.title()
    df['bowl']       = df['bowl'].str.strip().str.title()
    df['team_bat']   = df['team_bat'].str.strip().str.replace('Royal Challengers Bangalore','RCB').str.replace('Royal Challengers Bengaluru','RCB')
    df['team_bowl']  = df['team_bowl'].str.strip().str.replace('Royal Challengers Bangalore','RCB').str.replace('Royal Challengers Bengaluru','RCB')
    df['ground']     = df['ground'].str.strip()
    df['shot']       = df['shot'].str.strip().replace('-', np.nan)
    df['line']       = df['line'].str.strip().replace('-', np.nan)
    df['length']     = df['length'].str.strip().replace('-', np.nan)
    df['bowl_style'] = df['bowl_style'].str.strip()

    for c in ['score','batruns','over','out','control','wagonX','wagonY','wagonZone','wprob','ball','wide','noball','inns_wkts']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['out']  = df['out'].fillna(0).astype(int)
    df['wide'] = df['wide'].fillna(0).astype(int)
    df['ball'] = df['ball'].fillna(0).astype(int)

    def phase(o):
        if o <= 6:  return 'Powerplay (1-6)'
        if o <= 16: return 'Middle (7-16)'
        return 'Death (17-20)'
    df['phase'] = df['over'].apply(phase)
    df['phase'] = pd.Categorical(df['phase'],
                    categories=['Powerplay (1-6)','Middle (7-16)','Death (17-20)'], ordered=True)

    def phase_detail(o):
        if o <= 6:  return 'Powerplay (1-6)'
        if o <= 11: return 'Early Middle (7-11)'
        if o <= 16: return 'Late Middle (12-16)'
        return 'Death (17-20)'
    df['phase_detail'] = df['over'].apply(phase_detail)
    df['phase_detail'] = pd.Categorical(df['phase_detail'],
        categories=['Powerplay (1-6)','Early Middle (7-11)','Late Middle (12-16)','Death (17-20)'], ordered=True)

    df['line_label']   = df['line'].str.replace('_',' ').str.title()
    df['length_label'] = df['length'].str.replace('_',' ').str.title()
    df['shot_label']   = df['shot'].str.replace('_',' ').str.title()

    style_map = {
        'RF':'Right Arm Fast','RFM':'Right Arm Fast Medium','RMF':'Right Arm Fast Medium',
        'RM':'Right Arm Medium','LF':'Left Arm Fast','LFM':'Left Arm Fast Medium',
        'LMF':'Left Arm Fast Medium','LM':'Left Arm Medium',
        'OB':'Off Break','LB':'Leg Break','LBG':'Leg Break Googly',
        'SLA':'Slow Left Arm','LWS':'Left Wrist Spin',
        'OB/LB':'Off/Leg Break','RM/OB':'Right Medium/Off Break'
    }
    df['bowl_style_label'] = df['bowl_style'].map(style_map).fillna(df['bowl_style'])
    return df

FILE = "IPL_2026_hg.xlsx"
try:
    df = load_data(FILE)
except FileNotFoundError:
    uploaded = st.file_uploader("Upload IPL_2026_hg.xlsx", type=["xlsx"])
    if uploaded:
        df = load_data(uploaded)
    else:
        st.info("Please upload the IPL 2026 data file.")
        st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🏏 IPL 2026 Filters")
sel_phase     = st.sidebar.multiselect("Phase", ['Powerplay (1-6)','Middle (7-16)','Death (17-20)'],
                                        default=['Powerplay (1-6)','Middle (7-16)','Death (17-20)'])
sel_bowl_kind = st.sidebar.multiselect("Bowler Kind", sorted(df['bowl_kind'].dropna().unique()),
                                        default=sorted(df['bowl_kind'].dropna().unique()))
sel_bat_hand  = st.sidebar.multiselect("Batter Hand", sorted(df['bat_hand'].dropna().unique()),
                                        default=sorted(df['bat_hand'].dropna().unique()))
sel_team_bat  = st.sidebar.multiselect("Batting Team", sorted(df['team_bat'].dropna().unique()),
                                        default=sorted(df['team_bat'].dropna().unique()))
min_balls     = st.sidebar.slider("Min balls (filter noise)", 5, 60, 10)

filt = (
    df['phase'].isin(sel_phase) &
    df['bowl_kind'].isin(sel_bowl_kind) &
    df['bat_hand'].isin(sel_bat_hand) &
    df['team_bat'].isin(sel_team_bat)
)
dff = df[filt]

st.title("🏏 IPL 2026 Analytics Dashboard")
st.caption(f"**{len(dff):,}** deliveries | **{dff['p_match'].nunique()}** matches | **{dff['bat'].nunique()}** batters | **{dff['bowl'].nunique()}** bowlers")

if dff.empty:
    st.warning("No data matches current filters.")
    st.stop()

k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.metric("Deliveries", f"{len(dff):,}")
k2.metric("Runs Scored", f"{int(dff['batruns'].sum()):,}")
k3.metric("Wickets", f"{int(dff['out'].sum()):,}")
k4.metric("Fours", f"{int((dff['score']==4).sum()):,}")
k5.metric("Sixes", f"{int((dff['score']==6).sum()):,}")
sr = dff['batruns'].sum() / max(dff[dff['wide']==0]['score'].count(), 1) * 100
k6.metric("Overall SR", f"{sr:.1f}")
st.divider()

tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "🎯 Shot Analysis","📍 Line & Length","🏏 Batter Analysis",
    "🎳 Bowler Analysis","🏆 Team Analysis","💥 Game Changers","⚡ Momentum Controllers"
])

# ══ TAB 1 — Shot Analysis ═════════════════════════════════════════════════════
with tab1:
    st.subheader("Shot Effectiveness Analysis")
    shot_df  = dff.dropna(subset=['shot'])
    shot_grp = shot_df.groupby('shot_label').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'),
        Outs=('out','sum'), Controlled=('control','sum')
    ).reset_index()
    shot_grp = shot_grp[shot_grp['Balls'] >= 5]
    shot_grp['Avg Runs']   = (shot_grp['Runs']/shot_grp['Balls']).round(2)
    shot_grp['Dismissal%'] = (shot_grp['Outs']/shot_grp['Balls']*100).round(1)
    shot_grp['Control%']   = (shot_grp['Controlled']/shot_grp['Balls']*100).round(1)
    shot_grp['Frequency%'] = (shot_grp['Balls']/shot_grp['Balls'].sum()*100).round(1)

    c1,c2 = st.columns(2)
    with c1:
        fig = px.bar(shot_grp.sort_values('Avg Runs',ascending=True), x='Avg Runs', y='shot_label',
                     orientation='h', color='Avg Runs', color_continuous_scale='RdYlGn',
                     text='Avg Runs', height=550, title="Avg Runs per Ball by Shot Type")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.scatter(shot_grp, x='Avg Runs', y='Dismissal%', size='Balls',
                          text='shot_label', color='Control%', color_continuous_scale='RdYlGn',
                          title="Risk vs Reward", height=550)
        fig2.update_traces(textposition='top center', textfont_size=9)
        st.plotly_chart(fig2, use_container_width=True)

    c3,c4 = st.columns(2)
    with c3:
        fig3 = px.pie(shot_grp.nlargest(12,'Balls'), names='shot_label', values='Balls',
                      title="Shot Frequency – Top 12", height=400)
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        fig4 = px.bar(shot_grp.sort_values('Control%',ascending=True), x='Control%', y='shot_label',
                      orientation='h', color='Control%', color_continuous_scale='Blues',
                      text='Control%', height=400, title="% Controlled Shots")
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    sp = shot_df.groupby(['shot_label','phase'],observed=True).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    sp = sp[sp['Balls']>=3]
    sp['Avg Runs'] = (sp['Runs']/sp['Balls']).round(2)
    fig5 = px.bar(sp[sp['shot_label'].isin(shot_grp.nlargest(10,'Balls')['shot_label'])],
                  x='shot_label', y='Avg Runs', color='phase', barmode='group',
                  color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                  title="Avg Runs by Shot × Phase", height=420)
    fig5.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig5, use_container_width=True)
    st.dataframe(shot_grp.sort_values('Avg Runs',ascending=False).reset_index(drop=True), use_container_width=True)

# ══ TAB 2 — Line & Length (no Most Effective Shot section) ════════════════════
with tab2:
    st.subheader("Line & Length Analysis")
    ll = dff.dropna(subset=['line','length'])
    ll_grp = ll.groupby(['length_label','line_label']).agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    ll_grp['SR']         = (ll_grp['Runs']/ll_grp['Balls']*100).round(1)
    ll_grp['Dismissal%'] = (ll_grp['Outs']/ll_grp['Balls']*100).round(2)

    c1,c2 = st.columns(2)
    with c1:
        pivot_sr = ll_grp.pivot(index='length_label', columns='line_label', values='SR')
        fig = px.imshow(pivot_sr, color_continuous_scale='RdYlGn', text_auto=True,
                        title="SR: Length × Line", height=380)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        pivot_dis = ll_grp.pivot(index='length_label', columns='line_label', values='Dismissal%')
        fig2 = px.imshow(pivot_dis, color_continuous_scale='RdYlGn_r', text_auto=True,
                         title="Dismissal %: Length × Line", height=380)
        st.plotly_chart(fig2, use_container_width=True)

    c3,c4 = st.columns(2)
    with c3:
        llen = ll.groupby('length_label').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
        llen['SR'] = (llen['Runs']/llen['Balls']*100).round(1)
        fig3 = px.bar(llen, x='length_label', y='SR', color='SR',
                      color_continuous_scale='RdYlGn', text='SR', title="SR by Length", height=350)
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        lline = ll.groupby('line_label').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
        lline['SR'] = (lline['Runs']/lline['Balls']*100).round(1)
        fig4 = px.bar(lline, x='line_label', y='SR', color='SR',
                      color_continuous_scale='RdYlGn', text='SR', title="SR by Line", height=350)
        fig4.update_layout(xaxis_tickangle=-20)
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    ll_ph = ll.groupby(['phase','length_label'],observed=True).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    ll_ph['SR'] = (ll_ph['Runs']/ll_ph['Balls']*100).round(1)
    fig5 = px.bar(ll_ph, x='length_label', y='SR', color='phase', barmode='group',
                  color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                  title="SR by Length Across Phases", height=400)
    fig5.update_layout(xaxis_tickangle=-20)
    st.plotly_chart(fig5, use_container_width=True)

# ══ TAB 3 — Batter Analysis ═══════════════════════════════════════════════════
with tab3:
    st.subheader("Batter Performance Analysis")

    def bpb(balls, fours, sixes):
        b = fours + sixes
        return round(balls/b, 1) if b > 0 else np.nan

    bat_grp = dff.groupby('bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum())
    ).reset_index()
    bat_grp = bat_grp[bat_grp['Balls'] >= min_balls]
    bat_grp['SR']  = (bat_grp['Runs']/bat_grp['Balls']*100).round(1)
    bat_grp['Avg'] = (bat_grp['Runs']/bat_grp['Outs'].replace(0,np.nan)).round(1).fillna(bat_grp['Runs'])
    bat_grp['BPB'] = bat_grp.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)

    c1,c2 = st.columns(2)
    with c1:
        top_n  = st.slider("Top N batters", 5, 30, 15, key='bat_n')
        metric = st.radio("Rank by", ['SR','Runs','Avg','BPB'], horizontal=True, key='bat_m')
        asc = metric == 'BPB'
        fig = px.bar(bat_grp.nsmallest(top_n,metric) if asc else bat_grp.nlargest(top_n,metric),
                     x='bat', y=metric, color=metric,
                     color_continuous_scale='RdYlGn_r' if asc else 'Teal',
                     text=metric, title=f"Top {top_n} Batters by {metric}", height=420)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.scatter(bat_grp.nlargest(40,'Balls'), x='Avg', y='SR', size='Balls',
                          text='bat', color='Runs', color_continuous_scale='Viridis',
                          title="SR vs Average", height=420)
        fig2.update_traces(textposition='top center', textfont_size=8)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("🎯 Dominant Batters vs Bowling Style")
    style_opts = sorted(dff['bowl_style_label'].dropna().unique())
    sel_style  = st.selectbox("Select Bowling Style", style_opts)
    sdf = dff[dff['bowl_style_label']==sel_style]
    s_grp = sdf.groupby('bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum())
    ).reset_index()
    s_grp = s_grp[s_grp['Balls'] >= 5]
    s_grp['SR']  = (s_grp['Runs']/s_grp['Balls']*100).round(1)
    s_grp['Avg'] = (s_grp['Runs']/s_grp['Outs'].replace(0,np.nan)).round(1).fillna(s_grp['Runs'])
    s_grp['BPB'] = s_grp.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
    s_grp = s_grp.sort_values('SR', ascending=False).reset_index(drop=True)
    s_grp.index += 1

    cs1,cs2 = st.columns([1.2,1])
    with cs1:
        fig_s = px.bar(s_grp.head(15), x='bat', y='SR', color='SR',
                       color_continuous_scale='Teal', text='SR',
                       title=f"Top 15 vs {sel_style}", height=400)
        fig_s.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_s, use_container_width=True)
    with cs2:
        st.dataframe(s_grp[['bat','Balls','Runs','SR','Avg','Fours','Sixes','BPB']],
                     use_container_width=True, height=380)

    st.divider()
    st.subheader("🔍 Individual Batter Deep Dive")
    sel_bat = st.selectbox("Select Batter", sorted(dff['bat'].unique()))
    bdf     = dff[dff['bat']==sel_bat]
    f4 = int((bdf['score']==4).sum()); f6 = int((bdf['score']==6).sum())
    bpb_v = bpb(len(bdf), f4, f6)

    b1,b2,b3,b4,b5,b6 = st.columns(6)
    b1.metric("Balls", len(bdf)); b2.metric("Runs", int(bdf['batruns'].sum()))
    b3.metric("Dismissals", int(bdf['out'].sum()))
    b4.metric("SR", f"{bdf['batruns'].sum()/max(len(bdf),1)*100:.1f}")
    b5.metric("4s / 6s", f"{f4} / {f6}")
    b6.metric("Balls/Boundary", f"{bpb_v}" if not np.isnan(bpb_v) else "N/A")

    c3,c4 = st.columns(2)
    with c3:
        ph = bdf.groupby('phase',observed=True).agg(
            Balls=('batruns','count'), Runs=('batruns','sum'),
            Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum())
        ).reset_index()
        ph['SR']  = (ph['Runs']/ph['Balls']*100).round(1)
        ph['BPB'] = ph.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
        fig3 = px.bar(ph, x='phase', y='SR', color='phase', text='SR',
                      color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                      title=f"{sel_bat} – SR by Phase", height=350)
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        pk = bdf.groupby('bowl_kind').agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
            Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum())
        ).reset_index()
        pk['SR']  = (pk['Runs']/pk['Balls']*100).round(1)
        pk['Avg'] = (pk['Runs']/pk['Outs'].replace(0,np.nan)).round(1).fillna(pk['Runs'])
        pk['BPB'] = pk.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
        fig4 = px.bar(pk, x='bowl_kind', y='SR', color='bowl_kind', text='SR',
                      title=f"{sel_bat} – SR vs Pace/Spin", height=350)
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("**Matchup – Pace & Spin Summary**")
    st.dataframe(pk[['bowl_kind','Balls','Runs','SR','Avg','Fours','Sixes','BPB']], use_container_width=True)

    st.divider()
    st.markdown(f"**{sel_bat} – vs Each Bowling Style**")
    bs = bdf.groupby('bowl_style_label').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum())
    ).reset_index()
    bs = bs[bs['Balls']>=3]
    bs['SR']  = (bs['Runs']/bs['Balls']*100).round(1)
    bs['Avg'] = (bs['Runs']/bs['Outs'].replace(0,np.nan)).round(1).fillna(bs['Runs'])
    bs['BPB'] = bs.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)

    c5,c6 = st.columns(2)
    with c5:
        fig5 = px.bar(bs.sort_values('SR',ascending=False), x='bowl_style_label', y='SR',
                      color='SR', color_continuous_scale='RdYlGn', text='SR',
                      title=f"{sel_bat} – SR by Bowling Style", height=380)
        fig5.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig5, use_container_width=True)
    with c6:
        st.dataframe(bs[['bowl_style_label','Balls','Runs','SR','Avg','Fours','Sixes','BPB']].sort_values('SR',ascending=False),
                     use_container_width=True)

    c7,c8 = st.columns(2)
    with c7:
        bl = bdf.dropna(subset=['length']).groupby('length_label').agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
        ).reset_index()
        bl['SR']   = (bl['Runs']/bl['Balls']*100).round(1)
        bl['Dis%'] = (bl['Outs']/bl['Balls']*100).round(1)
        fig7 = px.bar(bl, x='length_label', y='SR', color='Dis%',
                      color_continuous_scale='RdYlGn_r', text='SR',
                      title=f"{sel_bat} – SR by Length (color=dismissal%)", height=380)
        st.plotly_chart(fig7, use_container_width=True)
    with c8:
        wz = bdf.groupby('wagonZone').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
        wz['Zone'] = wz['wagonZone'].map({0:'Dot Zone',1:'Fine Leg',2:'Square Leg',3:'Mid Wicket',
                                          4:'Mid On',5:'Mid Off',6:'Cover',7:'Point',8:'Third Man'})
        fig8 = px.bar_polar(wz, r='Runs', theta='Zone', color='Runs',
                            color_continuous_scale='RdYlGn', title=f"{sel_bat} – Scoring Zones", height=380)
        st.plotly_chart(fig8, use_container_width=True)

# ══ TAB 4 — Bowler Analysis ═══════════════════════════════════════════════════
with tab4:
    st.subheader("Bowler Performance Analysis")
    bowl_grp = dff[dff['wide']==0].groupby('bowl').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('out','sum')
    ).reset_index()
    bowl_grp = bowl_grp[bowl_grp['Balls'] >= min_balls]
    bowl_grp['Economy'] = (bowl_grp['Runs']/(bowl_grp['Balls']/6)).round(2)
    bowl_grp['SR']      = (bowl_grp['Balls']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)
    bowl_grp['Avg']     = (bowl_grp['Runs']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)

    c1,c2 = st.columns(2)
    with c1:
        top_nb  = st.slider("Top N bowlers", 5, 30, 15, key='bowl_n')
        bm      = st.radio("Rank by", ['Economy','Wickets','Avg'], horizontal=True, key='bowl_m')
        asc_b   = bm in ['Economy','Avg']
        fig = px.bar(bowl_grp.nsmallest(top_nb,bm) if asc_b else bowl_grp.nlargest(top_nb,bm),
                     x='bowl', y=bm, color=bm,
                     color_continuous_scale='RdYlGn_r' if asc_b else 'Teal',
                     text=bm, title=f"Top {top_nb} Bowlers by {bm}", height=420)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.scatter(bowl_grp.nlargest(40,'Balls'), x='Economy', y='Wickets',
                          size='Balls', text='bowl', color='Avg',
                          color_continuous_scale='RdYlGn_r', title="Economy vs Wickets", height=420)
        fig2.update_traces(textposition='top center', textfont_size=8)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("🔍 Individual Bowler Deep Dive")
    sel_bowl = st.selectbox("Select Bowler", sorted(dff['bowl'].unique()))
    bwdf     = dff[dff['bowl']==sel_bowl]
    bwdf_ll  = bwdf.dropna(subset=['line','length'])

    bw1,bw2,bw3,bw4 = st.columns(4)
    bw1.metric("Balls", len(bwdf)); bw2.metric("Wickets", int(bwdf['out'].sum()))
    econ = bwdf['batruns'].sum()/max(len(bwdf)/6,0.1)
    bw3.metric("Economy", f"{econ:.2f}")
    bw4.metric("Bowl Kind", bwdf['bowl_kind'].mode()[0] if len(bwdf) else "N/A")

    c3,c4 = st.columns(2)
    with c3:
        ll_b = bwdf_ll.groupby(['length_label','line_label']).agg(
            Balls=('batruns','count'), Wickets=('out','sum')).reset_index()
        pivot_b = ll_b.pivot(index='length_label', columns='line_label', values='Balls')
        fig3 = px.imshow(pivot_b, text_auto=True, color_continuous_scale='Blues',
                         title=f"{sel_bowl} – Delivery Map", height=350)
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        pivot_wk = ll_b.pivot(index='length_label', columns='line_label', values='Wickets')
        fig4 = px.imshow(pivot_wk, text_auto=True, color_continuous_scale='Reds',
                         title=f"{sel_bowl} – Wickets by Line & Length", height=350)
        st.plotly_chart(fig4, use_container_width=True)

    # Natural length
    st.divider()
    st.markdown(f"### 📏 Natural Length – {sel_bowl}")
    nat = bwdf_ll.groupby('length_label').agg(Balls=('batruns','count')).reset_index()
    nat['Pct'] = (nat['Balls']/nat['Balls'].sum()*100).round(1)
    nat = nat.sort_values('Pct', ascending=False)
    c5,c6 = st.columns(2)
    with c5:
        fig5 = px.bar(nat, x='length_label', y='Pct', color='Pct',
                      color_continuous_scale='Blues', text='Pct',
                      title=f"{sel_bowl} – Length Distribution %", height=350)
        st.plotly_chart(fig5, use_container_width=True)
    with c6:
        fig6 = px.pie(nat, names='length_label', values='Balls',
                      title=f"{sel_bowl} – Natural Length", height=350)
        st.plotly_chart(fig6, use_container_width=True)

    # Over utilisation
    st.divider()
    st.markdown(f"### 📊 Over Utilisation – {sel_bowl}")
    util = bwdf.groupby('phase_detail',observed=True).agg(Balls=('batruns','count')).reset_index()
    util['Overs'] = (util['Balls']/6).round(1)
    util['Pct']   = (util['Balls']/util['Balls'].sum()*100).round(1)
    econ_ph = bwdf.groupby('phase_detail',observed=True).agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('out','sum')
    ).reset_index()
    econ_ph['Economy'] = (econ_ph['Runs']/(econ_ph['Balls']/6)).round(2)

    c7,c8 = st.columns(2)
    with c7:
        fig7 = px.bar(util, x='phase_detail', y='Pct', color='Pct',
                      color_continuous_scale='Teal', text='Pct',
                      title=f"{sel_bowl} – Over Utilisation %", height=350)
        st.plotly_chart(fig7, use_container_width=True)
    with c8:
        fig8 = px.bar(econ_ph, x='phase_detail', y='Economy', color='Economy',
                      color_continuous_scale='RdYlGn_r', text='Economy',
                      title=f"{sel_bowl} – Economy by Phase", height=350)
        st.plotly_chart(fig8, use_container_width=True)

    merged = pd.merge(util, econ_ph[['phase_detail','Economy','Wickets']], on='phase_detail', how='left')
    st.dataframe(merged[['phase_detail','Overs','Pct','Economy','Wickets']], use_container_width=True)

# ══ TAB 5 — Team Analysis ═════════════════════════════════════════════════════
with tab5:
    st.subheader("Team Performance Analysis")
    t_grp = dff.groupby('team_bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    t_grp['SR']  = (t_grp['Runs']/t_grp['Balls']*100).round(1)
    t_grp['Avg'] = (t_grp['Runs']/t_grp['Outs'].replace(0,np.nan)).round(1)

    c1,c2 = st.columns(2)
    with c1:
        fig = px.bar(t_grp.sort_values('SR',ascending=False), x='team_bat', y='SR',
                     color='SR', color_continuous_scale='RdYlGn', text='SR',
                     title="Team SR", height=380)
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.bar(t_grp.sort_values('Runs',ascending=False), x='team_bat', y='Runs',
                      color='Runs', color_continuous_scale='Blues', text='Runs',
                      title="Total Runs", height=380)
        fig2.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    tps = dff.groupby(['team_bat','bowl_kind']).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    tps['SR'] = (tps['Runs']/tps['Balls']*100).round(1)
    fig3 = px.bar(tps, x='team_bat', y='SR', color='bowl_kind', barmode='group',
                  title="Team SR vs Pace/Spin", height=400, text='SR')
    fig3.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    sel_team = st.selectbox("Select Team – Scoring Zones", sorted(dff['team_bat'].unique()))
    tdf = dff[dff['team_bat']==sel_team]
    wz_t = tdf.groupby('wagonZone').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    wz_t['Zone'] = wz_t['wagonZone'].map({0:'Dot Zone',1:'Fine Leg',2:'Square Leg',3:'Mid Wicket',
                                           4:'Mid On',5:'Mid Off',6:'Cover',7:'Point',8:'Third Man'})
    c3,c4 = st.columns(2)
    with c3:
        fig4 = px.bar_polar(wz_t, r='Runs', theta='Zone', color='Runs',
                            color_continuous_scale='RdYlGn', title=f"{sel_team} – Zones", height=400)
        st.plotly_chart(fig4, use_container_width=True)
    with c4:
        tph = dff.groupby(['team_bat','phase'],observed=True).agg(
            Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
        tph['SR'] = (tph['Runs']/tph['Balls']*100).round(1)
        fig5 = px.bar(tph, x='team_bat', y='SR', color='phase', barmode='group',
                      color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                      title="Team SR by Phase", height=400, text='SR')
        fig5.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig5, use_container_width=True)

# ══ TAB 6 — Game Changers ═════════════════════════════════════════════════════
with tab6:
    st.subheader("💥 Game Changers")

    over_data = dff.groupby(
        ['p_match','inns','over','bat','team_bat','bowl_kind','phase'], observed=True
    ).agg(over_runs=('batruns','sum'), balls=('batruns','count'), outs=('out','sum')).reset_index()

    run_thr = st.slider("Impact Over: Min runs in one over", 6, 20, 10)
    impact  = over_data[over_data['over_runs'] >= run_thr].copy()

    if impact.empty:
        st.warning("No data. Lower the threshold.")
    else:
        tot_ov = over_data.groupby('bat').agg(Total_Overs_Batted=('over_runs','count')).reset_index()

        def add_freq(d):
            d = pd.merge(d, tot_ov, on='bat', how='left')
            d['Impact_Freq%'] = (d['Impact_Overs']/d['Total_Overs_Batted']*100).round(1)
            return d

        # Overall
        st.markdown("### 🏆 Overall Leaderboard")
        overall = impact.groupby('bat').agg(
            Impact_Overs=('over_runs','count'), Total_Runs=('over_runs','sum'),
            Best_Over=('over_runs','max'), Avg_Runs=('over_runs','mean')
        ).reset_index().sort_values('Impact_Overs',ascending=False).reset_index(drop=True)
        overall = add_freq(overall); overall['Avg_Runs'] = overall['Avg_Runs'].round(1); overall.index += 1

        c1,c2 = st.columns([1.2,1])
        with c1:
            fig = px.bar(overall.head(15), x='bat', y='Impact_Overs',
                         color='Impact_Overs', color_continuous_scale='Plasma',
                         text='Impact_Overs', title=f"Most {run_thr}+ Run Overs", height=400)
            fig.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(overall[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over','Avg_Runs']],
                         use_container_width=True, height=380)

        st.divider()
        st.markdown("### 🎯 Impact Frequency %")
        freq_df = overall.sort_values('Impact_Freq%',ascending=False).reset_index(drop=True)
        cf1,cf2 = st.columns([1.2,1])
        with cf1:
            fig_f = px.bar(freq_df.head(15), x='bat', y='Impact_Freq%',
                           color='Impact_Freq%', color_continuous_scale='RdYlGn',
                           text='Impact_Freq%', title="Highest Impact Freq%", height=400)
            fig_f.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_f, use_container_width=True)
        with cf2:
            st.dataframe(freq_df[['bat','Impact_Freq%','Impact_Overs','Total_Overs_Batted','Total_Runs','Best_Over','Avg_Runs']],
                         use_container_width=True, height=380)

        st.divider()
        # Pace vs Spin
        st.markdown("### ⚡ Pace vs Spin")
        cp1,cp2 = st.columns(2)
        for col, kind, cscale, title in [
            (cp1,'pace bowler','Reds','vs PACE'),
            (cp2,'spin bowler','Blues','vs SPIN')
        ]:
            with col:
                lb = impact[impact['bowl_kind']==kind].groupby('bat').agg(
                    Impact_Overs=('over_runs','count'), Total_Runs=('over_runs','sum'), Best_Over=('over_runs','max')
                ).reset_index().sort_values('Impact_Overs',ascending=False).reset_index(drop=True)
                lb = add_freq(lb); lb.index += 1
                fig_k = px.bar(lb.head(10), x='bat', y='Impact_Overs',
                               color='Impact_Overs', color_continuous_scale=cscale,
                               text='Impact_Overs', title=f"Top 10 {title}", height=360)
                fig_k.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_k, use_container_width=True)
                st.dataframe(lb[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over']],
                             use_container_width=True)

        st.divider()
        # Phase-wise
        st.markdown("### 📊 By Phase")
        for ph_n, color in zip(['Powerplay (1-6)','Middle (7-16)','Death (17-20)'],['Teal','Oranges','Purples']):
            st.markdown(f"#### 🏏 {ph_n}")
            ph_tot = over_data[over_data['phase'].astype(str)==ph_n].groupby('bat').agg(
                Total_Overs_Batted=('over_runs','count')).reset_index()
            ph_lb = impact[impact['phase'].astype(str)==ph_n].groupby('bat').agg(
                Impact_Overs=('over_runs','count'), Total_Runs=('over_runs','sum'),
                Best_Over=('over_runs','max'), Avg_Runs=('over_runs','mean')
            ).reset_index().sort_values('Impact_Overs',ascending=False).reset_index(drop=True)
            ph_lb = pd.merge(ph_lb, ph_tot, on='bat', how='left')
            ph_lb['Impact_Freq%'] = (ph_lb['Impact_Overs']/ph_lb['Total_Overs_Batted']*100).round(1)
            ph_lb['Avg_Runs'] = ph_lb['Avg_Runs'].round(1)
            ca,cb,cc = st.columns(3)
            with ca:
                fig_a = px.bar(ph_lb.head(15), x='bat', y='Impact_Overs',
                               color='Impact_Overs', color_continuous_scale=color,
                               text='Impact_Overs', title="Impact Overs Count", height=340)
                fig_a.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_a, use_container_width=True)
            with cb:
                fig_b = px.bar(ph_lb.sort_values('Impact_Freq%',ascending=False).head(15),
                               x='bat', y='Impact_Freq%', color='Impact_Freq%',
                               color_continuous_scale='RdYlGn', text='Impact_Freq%',
                               title="Impact Freq%", height=340)
                fig_b.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_b, use_container_width=True)
            with cc:
                ph_lb.index = ph_lb.index + 1
                st.dataframe(ph_lb[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over','Avg_Runs']],
                             use_container_width=True, height=340)

        st.divider()
        # Over-wise
        st.markdown("### 🎯 Over-wise Leaderboard")
        sel_ov = st.slider("Select Over", 1, 20, 1, key='gc_ov')
        ov_f   = impact[impact['over']==sel_ov]
        if ov_f.empty:
            st.info(f"No {run_thr}+ run overs in Over {sel_ov}.")
        else:
            ov_tot = over_data[over_data['over']==sel_ov].groupby('bat').agg(
                Total_Times_Batted=('over_runs','count')).reset_index()
            ov_lb = ov_f.groupby('bat').agg(
                Impact_Overs=('over_runs','count'), Total_Runs=('over_runs','sum'),
                Best_Over=('over_runs','max'), Avg_Runs=('over_runs','mean')
            ).reset_index()
            ov_lb = pd.merge(ov_lb, ov_tot, on='bat', how='left')
            ov_lb['Impact_Freq%'] = (ov_lb['Impact_Overs']/ov_lb['Total_Times_Batted']*100).round(1)
            ov_lb['Avg_Runs'] = ov_lb['Avg_Runs'].round(1)
            ov_lb = ov_lb.sort_values('Impact_Overs',ascending=False).reset_index(drop=True)
            ov_lb.index += 1
            co1,co2 = st.columns([1.2,1])
            with co1:
                fig_o = px.bar(ov_lb.head(15), x='bat', y='Impact_Overs',
                               color='Impact_Overs', color_continuous_scale='Plasma',
                               text='Impact_Overs', title=f"Over {sel_ov} – Impact Overs", height=400)
                fig_o.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_o, use_container_width=True)
            with co2:
                fig_o2 = px.bar(ov_lb.sort_values('Impact_Freq%',ascending=False).head(15),
                                x='bat', y='Impact_Freq%', color='Impact_Freq%',
                                color_continuous_scale='RdYlGn', text='Impact_Freq%',
                                title=f"Over {sel_ov} – Impact Freq%", height=400)
                fig_o2.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_o2, use_container_width=True)
            st.dataframe(ov_lb[['bat','Impact_Overs','Total_Times_Batted','Impact_Freq%','Total_Runs','Best_Over','Avg_Runs']],
                         use_container_width=True)

        st.divider()
        # Individual profile
        st.markdown("### 🔍 Individual Batter Profile")
        sel_gc  = st.selectbox("Select Batter", sorted(impact['bat'].unique()), key='gc_bat')
        bi      = impact[impact['bat']==sel_gc]
        bi_tot  = over_data[over_data['bat']==sel_gc].shape[0]
        bi_freq = (len(bi)/bi_tot*100) if bi_tot > 0 else 0
        bi_avg  = bi['over_runs'].mean()

        g1,g2,g3,g4,g5,g6 = st.columns(6)
        g1.metric("Impact Overs", len(bi)); g2.metric("Total Overs", bi_tot)
        g3.metric("Impact Freq%", f"{bi_freq:.1f}%"); g4.metric("Best Over", int(bi['over_runs'].max()))
        g5.metric("Avg in Impact Over", f"{bi_avg:.1f}"); g6.metric("Total Runs", int(bi['over_runs'].sum()))

        # Consecutive impact overs
        st.markdown("#### 🔥 Consecutive Impact Overs")
        c_data = []
        for mid in bi['p_match'].unique():
            mi = bi[bi['p_match']==mid].sort_values(['inns','over'])
            ol = mi['over'].tolist(); mc = 1; cc = 1
            for i in range(1,len(ol)):
                if ol[i]==ol[i-1]+1: cc+=1; mc=max(mc,cc)
                else: cc=1
            c_data.append({'Match':mid,'Impact_In_Match':len(ol),'Max_Consecutive':mc,'Runs':mi['over_runs'].sum()})
        c_df = pd.DataFrame(c_data).sort_values('Impact_In_Match',ascending=False)
        c_df.index = range(1,len(c_df)+1)

        cg1,cg2,cg3 = st.columns(3)
        cg1.metric("Matches 2+ Impact Overs", int((c_df['Impact_In_Match']>=2).sum()))
        cg2.metric("Max Impact in a Match", int(c_df['Impact_In_Match'].max()))
        cg3.metric("Max Consecutive", int(c_df['Max_Consecutive'].max()))
        st.dataframe(c_df, use_container_width=True)

        # Consecutive overall leaderboard
        st.markdown("#### 🏆 Who Has Most Consecutive Impact Overs? (All Batters)")
        ca_all = []
        for batter in impact['bat'].unique():
            for mid in impact[impact['bat']==batter]['p_match'].unique():
                mi = impact[(impact['bat']==batter)&(impact['p_match']==mid)].sort_values(['inns','over'])
                ol = mi['over'].tolist(); mc = 1; cc = 1
                for i in range(1,len(ol)):
                    if ol[i]==ol[i-1]+1: cc+=1; mc=max(mc,cc)
                    else: cc=1
                if mc >= 2:
                    ca_all.append({'bat':batter,'match':mid,'Max_Consecutive':mc})
        if ca_all:
            ca_df = pd.DataFrame(ca_all)
            ca_sum = ca_df.groupby('bat').agg(
                Times=('Max_Consecutive','count'), Max=('Max_Consecutive','max')
            ).reset_index().sort_values('Times',ascending=False).reset_index(drop=True)
            ca_sum.index += 1
            cc1,cc2 = st.columns([1.2,1])
            with cc1:
                fig_cc = px.bar(ca_sum.head(15), x='bat', y='Times',
                                color='Times', color_continuous_scale='Plasma', text='Times',
                                title="Most Times with Consecutive Impact Overs", height=380)
                fig_cc.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_cc, use_container_width=True)
            with cc2:
                st.dataframe(ca_sum, use_container_width=True, height=380)

        # Pace/Spin & Phase charts
        st.markdown("#### ⚡ vs Pace & Spin")
        bk = bi.groupby('bowl_kind').agg(Impact_Overs=('over_runs','count'), Avg_Runs=('over_runs','mean')).reset_index()
        bk['Avg_Runs'] = bk['Avg_Runs'].round(1)
        bk_t = over_data[over_data['bat']==sel_gc].groupby('bowl_kind').agg(Total=('over_runs','count')).reset_index()
        bk = pd.merge(bk, bk_t, on='bowl_kind', how='left')
        bk['Impact_Freq%'] = (bk['Impact_Overs']/bk['Total']*100).round(1)
        ck1,ck2 = st.columns(2)
        with ck1:
            fig_k1 = px.bar(bk, x='bowl_kind', y='Impact_Overs', color='bowl_kind', text='Impact_Overs',
                            title=f"{sel_gc} – Impact Overs vs Pace/Spin", height=300)
            fig_k1.update_layout(showlegend=False)
            st.plotly_chart(fig_k1, use_container_width=True)
        with ck2:
            fig_k2 = px.bar(bk, x='bowl_kind', y='Impact_Freq%', color='bowl_kind', text='Impact_Freq%',
                            color_discrete_sequence=['#EF553B','#636EFA'],
                            title=f"{sel_gc} – Impact Freq% vs Pace/Spin", height=300)
            fig_k2.update_layout(showlegend=False)
            st.plotly_chart(fig_k2, use_container_width=True)

        st.markdown("#### 📊 Phase-wise")
        ph_b = bi.groupby('phase',observed=True).agg(Impact_Overs=('over_runs','count'), Avg_Runs=('over_runs','mean')).reset_index()
        ph_b['Avg_Runs'] = ph_b['Avg_Runs'].round(1)
        ph_t = over_data[over_data['bat']==sel_gc].groupby('phase',observed=True).agg(Total=('over_runs','count')).reset_index()
        ph_b = pd.merge(ph_b, ph_t, on='phase', how='left')
        ph_b['Impact_Freq%'] = (ph_b['Impact_Overs']/ph_b['Total']*100).round(1)
        cp1,cp2 = st.columns(2)
        with cp1:
            fig_p1 = px.bar(ph_b, x='phase', y='Impact_Overs', color='phase', text='Impact_Overs',
                            color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                            title=f"{sel_gc} – Impact Overs by Phase", height=300)
            fig_p1.update_layout(showlegend=False)
            st.plotly_chart(fig_p1, use_container_width=True)
        with cp2:
            fig_p2 = px.bar(ph_b, x='phase', y='Impact_Freq%', color='phase', text='Impact_Freq%',
                            color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                            title=f"{sel_gc} – Impact Freq% by Phase", height=300)
            fig_p2.update_layout(showlegend=False)
            st.plotly_chart(fig_p2, use_container_width=True)

        st.markdown("#### 🎯 Distributions")
        cd1,cd2 = st.columns(2)
        with cd1:
            fig_h = px.histogram(bi, x='over_runs', nbins=15,
                                 title=f"{sel_gc} – Runs in Impact Overs",
                                 color_discrete_sequence=['#636EFA'], height=300)
            st.plotly_chart(fig_h, use_container_width=True)
        with cd2:
            ow = bi.groupby('over').agg(Count=('over_runs','count')).reset_index()
            ow['over'] = ow['over'].astype(int)
            fig_ow = px.bar(ow.sort_values('over'), x='over', y='Count',
                            color='Count', color_continuous_scale='Plasma', text='Count',
                            title=f"{sel_gc} – Which Over He Dominates", height=300)
            fig_ow.update_layout(xaxis=dict(tickmode='linear',tick0=1,dtick=1))
            st.plotly_chart(fig_ow, use_container_width=True)

# ══ TAB 7 — Momentum Controllers ══════════════════════════════════════════════
with tab7:
    st.subheader("⚡ Momentum Controllers")
    mc1, mc2, mc3 = st.tabs([
        "🏏 Over Start Dominance", "🎳 Bowler Resilience", "🩹 Post-Wicket Scoring"
    ])

    # ── MC TAB 1: Over Start Dominance ────────────────────────────────────────
    with mc1:
        st.subheader("🏏 Over Start Dominance – First 3 Balls")
        start_thr = st.slider("Dominant start threshold (runs in first 3 balls)", 3, 10, 4, key='st')
        f3 = dff[dff['ball'] <= 3].copy()
        os_grp = f3.groupby(['p_match','inns','over','bat','team_bat','phase'],observed=True).agg(
            Runs=('score','sum'), Balls=('score','count'),
            Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum())
        ).reset_index()
        os_grp['SR'] = (os_grp['Runs']/os_grp['Balls']*100).round(1)
        dom = os_grp[os_grp['Runs'] >= start_thr]

        st.markdown(f"**Dominant starts ({start_thr}+ in first 3 balls): {len(dom):,}**")
        st.divider()

        st.markdown("### 🏆 Batter Leaderboard")
        bat_s = dom.groupby('bat').agg(
            Dom_Starts=('Runs','count'), Total_Runs=('Runs','sum'),
            Avg_Runs=('Runs','mean'), Fours=('Fours','sum'), Sixes=('Sixes','sum')
        ).reset_index()
        bat_s_tot = os_grp.groupby('bat').agg(Total_Starts=('Runs','count')).reset_index()
        bat_s = pd.merge(bat_s, bat_s_tot, on='bat', how='left')
        bat_s['Freq%']    = (bat_s['Dom_Starts']/bat_s['Total_Starts']*100).round(1)
        bat_s['Avg_Runs'] = bat_s['Avg_Runs'].round(1)
        bat_s = bat_s.sort_values('Dom_Starts',ascending=False).reset_index(drop=True)
        bat_s.index += 1

        cs1,cs2 = st.columns([1.2,1])
        with cs1:
            fig_s1 = px.bar(bat_s.head(15), x='bat', y='Dom_Starts',
                            color='Dom_Starts', color_continuous_scale='Plasma',
                            text='Dom_Starts', title=f"Most {start_thr}+ Run Starts", height=400)
            fig_s1.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_s1, use_container_width=True)
        with cs2:
            fig_s2 = px.bar(bat_s.sort_values('Freq%',ascending=False).head(15),
                            x='bat', y='Freq%', color='Freq%',
                            color_continuous_scale='RdYlGn', text='Freq%',
                            title="Start Frequency %", height=400)
            fig_s2.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_s2, use_container_width=True)
        st.dataframe(bat_s[['bat','Dom_Starts','Total_Starts','Freq%','Total_Runs','Avg_Runs','Fours','Sixes']],
                     use_container_width=True)

        st.divider()
        st.markdown("### 🏆 Team Leaderboard")
        team_s = dom.groupby('team_bat').agg(Dom_Starts=('Runs','count'), Total_Runs=('Runs','sum')).reset_index()
        team_s_tot = os_grp.groupby('team_bat').agg(Total_Starts=('Runs','count')).reset_index()
        team_s = pd.merge(team_s, team_s_tot, on='team_bat', how='left')
        team_s['Freq%'] = (team_s['Dom_Starts']/team_s['Total_Starts']*100).round(1)
        team_s = team_s.sort_values('Dom_Starts',ascending=False).reset_index(drop=True)
        team_s.index += 1

        ct1,ct2 = st.columns(2)
        with ct1:
            fig_t1 = px.bar(team_s, x='team_bat', y='Dom_Starts',
                            color='Dom_Starts', color_continuous_scale='Teal',
                            text='Dom_Starts', title="Team – Dominant Starts", height=360)
            fig_t1.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig_t1, use_container_width=True)
        with ct2:
            fig_t2 = px.bar(team_s, x='team_bat', y='Freq%',
                            color='Freq%', color_continuous_scale='RdYlGn',
                            text='Freq%', title="Team – Start Freq%", height=360)
            fig_t2.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig_t2, use_container_width=True)

        st.divider()
        st.markdown("### 📊 Phase-wise")
        ph_s = dom.groupby(['bat','phase'],observed=True).agg(Dom_Starts=('Runs','count')).reset_index()
        top12_s = bat_s.head(12)['bat'].tolist()
        fig_ps = px.bar(ph_s[ph_s['bat'].isin(top12_s)], x='bat', y='Dom_Starts',
                        color='phase', barmode='group',
                        color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                        title="Dominant Starts by Phase – Top 12", height=400)
        fig_ps.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_ps, use_container_width=True)

        st.divider()
        st.markdown("### 🔍 Individual Batter Start Profile")
        sel_sb = st.selectbox("Select Batter", sorted(os_grp['bat'].unique()), key='sb')
        sb_all = os_grp[os_grp['bat']==sel_sb]
        sb_dom = dom[dom['bat']==sel_sb]

        sg1,sg2,sg3,sg4 = st.columns(4)
        sg1.metric("Total Starts", len(sb_all))
        sg2.metric("Dominant Starts", len(sb_dom))
        sg3.metric("Freq%", f"{len(sb_dom)/max(len(sb_all),1)*100:.1f}%")
        sg4.metric("Avg in Dominant", f"{sb_dom['Runs'].mean():.1f}" if len(sb_dom) > 0 else "N/A")

        si1,si2 = st.columns(2)
        with si1:
            ph_sb = sb_dom.groupby('phase',observed=True).agg(Count=('Runs','count')).reset_index()
            fig_si1 = px.bar(ph_sb, x='phase', y='Count', color='phase', text='Count',
                             color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                             title=f"{sel_sb} – Dominant Starts by Phase", height=320)
            st.plotly_chart(fig_si1, use_container_width=True)
        with si2:
            fig_si2 = px.histogram(sb_all, x='Runs', nbins=10,
                                   title=f"{sel_sb} – First 3 Ball Score Distribution",
                                   color_discrete_sequence=['#636EFA'], height=320)
            st.plotly_chart(fig_si2, use_container_width=True)

    # ── MC TAB 2: Bowler Resilience ───────────────────────────────────────────
    with mc2:
        st.subheader("🎳 Bowler Resilience – Who Controls After a Bad Start?")
        bad_thr = st.slider("Bad start threshold (first 3 balls runs)", 4, 15, 6, key='bt')

        bowl_ov = dff.groupby(['p_match','inns','over','bowl','phase'],observed=True).apply(
            lambda x: pd.Series({
                'first3_runs' : x[x['ball']<=3]['score'].sum(),
                'last3_runs'  : x[x['ball']>3]['score'].sum(),
                'first3_balls': len(x[x['ball']<=3]),
                'last3_balls' : len(x[x['ball']>3]),
                'last3_wkts'  : x[x['ball']>3]['out'].sum(),
                'total_runs'  : x['score'].sum()
            })
        ).reset_index()

        bad = bowl_ov[bowl_ov['first3_runs'] >= bad_thr].copy()
        bad['Controlled']    = (bad['last3_runs'] < bad['first3_runs']).astype(int)
        bad['Econ_Last3']    = (bad['last3_runs'] / bad['last3_balls'].replace(0,np.nan) * 6).round(2)

        st.markdown(f"**Overs with {bad_thr}+ in first 3 balls: {len(bad):,}**")
        st.divider()

        st.markdown("### 🏆 Resilience Leaderboard")
        res = bad.groupby('bowl').agg(
            Bad_Starts=('first3_runs','count'), Controlled=('Controlled','sum'),
            Avg_Last3=('last3_runs','mean'), Avg_First3=('first3_runs','mean'),
            Last3_Wkts=('last3_wkts','sum')
        ).reset_index()
        res['Control%']  = (res['Controlled']/res['Bad_Starts']*100).round(1)
        res['Avg_Last3'] = res['Avg_Last3'].round(1)
        res['Avg_First3']= res['Avg_First3'].round(1)
        res = res[res['Bad_Starts'] >= 2].sort_values('Control%',ascending=False).reset_index(drop=True)
        res.index += 1

        cr1,cr2 = st.columns([1.2,1])
        with cr1:
            fig_r = px.bar(res.head(15), x='bowl', y='Control%',
                           color='Control%', color_continuous_scale='RdYlGn',
                           text='Control%', title=f"Control% After {bad_thr}+ Start", height=400)
            fig_r.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_r, use_container_width=True)
        with cr2:
            st.dataframe(res[['bowl','Bad_Starts','Controlled','Control%','Avg_First3','Avg_Last3','Last3_Wkts']],
                         use_container_width=True, height=380)

        st.divider()
        st.markdown("### 📊 Phase-wise Resilience")
        ph_res = bad.groupby(['bowl','phase'],observed=True).agg(
            Bad_Starts=('first3_runs','count'), Controlled=('Controlled','sum')
        ).reset_index()
        ph_res['Control%'] = (ph_res['Controlled']/ph_res['Bad_Starts']*100).round(1)
        top10_r = res.head(10)['bowl'].tolist()
        fig_pr = px.bar(ph_res[ph_res['bowl'].isin(top10_r)], x='bowl', y='Control%',
                        color='phase', barmode='group',
                        color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                        title="Control% by Phase – Top 10", height=400)
        fig_pr.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_pr, use_container_width=True)

        st.divider()
        st.markdown("### 🔍 Individual Bowler Resilience")
        sel_rb = st.selectbox("Select Bowler", sorted(bad['bowl'].unique()), key='rb')
        rb = bad[bad['bowl']==sel_rb]

        rg1,rg2,rg3,rg4,rg5 = st.columns(5)
        rg1.metric("Bad Starts", len(rb)); rg2.metric("Times Controlled", int(rb['Controlled'].sum()))
        rg3.metric("Control%", f"{rb['Controlled'].mean()*100:.1f}%")
        rg4.metric("Avg First 3", f"{rb['first3_runs'].mean():.1f}")
        rg5.metric("Avg Last 3", f"{rb['last3_runs'].mean():.1f}")

        ri1,ri2 = st.columns(2)
        with ri1:
            fig_ri1 = px.scatter(rb, x='first3_runs', y='last3_runs',
                                 color='Controlled', color_discrete_map={1:'green',0:'red'},
                                 title=f"{sel_rb} – First 3 vs Last 3 (green=controlled)", height=360)
            st.plotly_chart(fig_ri1, use_container_width=True)
        with ri2:
            ph_rb = rb.groupby('phase',observed=True).agg(
                Bad=('first3_runs','count'), Ctrl=('Controlled','sum')
            ).reset_index()
            ph_rb['Control%'] = (ph_rb['Ctrl']/ph_rb['Bad']*100).round(1)
            fig_ri2 = px.bar(ph_rb, x='phase', y='Control%', color='phase', text='Control%',
                             color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                             title=f"{sel_rb} – Control% by Phase", height=360)
            st.plotly_chart(fig_ri2, use_container_width=True)

        fig_ri3 = px.histogram(rb, x='last3_runs', nbins=10,
                               color='Controlled', color_discrete_map={1:'green',0:'red'},
                               title=f"{sel_rb} – Last 3 Ball Run Distribution", height=300)
        st.plotly_chart(fig_ri3, use_container_width=True)

    # ── MC TAB 3: Post-Wicket Scoring ─────────────────────────────────────────
    with mc3:
        st.subheader("🩹 Post-Wicket Scoring – Who Hits the Ground Running?")
        pw_n = st.slider("First N balls after coming in", 4, 12, 6, key='pw')

        df_s = df.sort_values(['p_match','inns','over','ball']).reset_index(drop=True)
        df_s['ball_seq'] = df_s.groupby(['p_match','inns']).cumcount()
        wk_rows = df_s[df_s['out']==1][['p_match','inns','ball_seq']].copy()
        wk_rows.columns = ['p_match','inns','wk_seq']

        pw_recs = []
        for _, wr in wk_rows.iterrows():
            pm, inn, ws = wr['p_match'], wr['inns'], wr['wk_seq']
            nb = df_s[(df_s['p_match']==pm)&(df_s['inns']==inn)&
                      (df_s['ball_seq']>ws)&(df_s['ball_seq']<=ws+pw_n)]
            if len(nb) > 0:
                new_bat = nb.iloc[0]['bat']
                nbb = nb[nb['bat']==new_bat]
                if len(nbb) > 0:
                    pw_recs.append({
                        'bat':new_bat, 'p_match':pm,
                        'balls':len(nbb), 'runs':nbb['batruns'].sum(),
                        'fours':int((nbb['score']==4).sum()), 'sixes':int((nbb['score']==6).sum()),
                        'out':int(nbb['out'].sum()), 'phase':nbb.iloc[0]['phase']
                    })

        if not pw_recs:
            st.warning("No post-wicket data.")
        else:
            pw = pd.DataFrame(pw_recs)
            pw['SR'] = (pw['runs']/pw['balls']*100).round(1)

            pw_lb = pw.groupby('bat').agg(
                Times=('runs','count'), Total_Runs=('runs','sum'),
                Total_Balls=('balls','sum'), Fours=('fours','sum'),
                Sixes=('sixes','sum'), Dismissals=('out','sum')
            ).reset_index()
            pw_lb = pw_lb[pw_lb['Times'] >= 2]
            pw_lb['SR']  = (pw_lb['Total_Runs']/pw_lb['Total_Balls']*100).round(1)
            pw_lb['Avg'] = (pw_lb['Total_Runs']/pw_lb['Dismissals'].replace(0,np.nan)).round(1).fillna(pw_lb['Total_Runs'])
            pw_lb = pw_lb.sort_values('SR',ascending=False).reset_index(drop=True)
            pw_lb.index += 1

            st.markdown(f"### 🏆 Post-Wicket Leaderboard – First {pw_n} Balls")
            cw1,cw2 = st.columns([1.2,1])
            with cw1:
                fig_w = px.bar(pw_lb.head(15), x='bat', y='SR',
                               color='SR', color_continuous_scale='RdYlGn',
                               text='SR', title=f"SR in First {pw_n} Balls Post-Wicket", height=400)
                fig_w.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_w, use_container_width=True)
            with cw2:
                st.dataframe(pw_lb[['bat','Times','Total_Balls','Total_Runs','SR','Avg','Fours','Sixes']],
                             use_container_width=True, height=380)

            st.divider()
            # Threshold comparison
            st.markdown("### 📊 SR at 6 / 8 / 10 / 12 Ball Thresholds")
            thr_data = []
            for t in [6,8,10,12]:
                tmp = pw.groupby(['bat','p_match']).apply(
                    lambda x: pd.Series({'runs':x.head(t)['runs'].sum(),'balls':min(len(x),t)})
                ).reset_index()
                tmp_lb = tmp.groupby('bat').agg(Runs=('runs','sum'), Balls=('balls','sum')).reset_index()
                tmp_lb['SR'] = (tmp_lb['Runs']/tmp_lb['Balls']*100).round(1)
                tmp_lb['Thresh'] = f"{t} balls"
                thr_data.append(tmp_lb[['bat','SR','Thresh']])
            thr_all = pd.concat(thr_data)
            top12_pw = pw_lb.head(12)['bat'].tolist()
            fig_thr = px.bar(thr_all[thr_all['bat'].isin(top12_pw)],
                             x='bat', y='SR', color='Thresh', barmode='group',
                             title="Post-Wicket SR at 6/8/10/12 Balls – Top 12", height=420)
            fig_thr.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_thr, use_container_width=True)

            st.divider()
            st.markdown("### 🔍 Individual Post-Wicket Profile")
            sel_pw = st.selectbox("Select Batter", sorted(pw['bat'].unique()), key='pw_bat')
            pw_bat = pw[pw['bat']==sel_pw]

            pw1,pw2,pw3,pw4 = st.columns(4)
            pw1.metric("Times Came In", len(pw_bat))
            pw2.metric("Avg SR", f"{pw_bat['SR'].mean():.1f}")
            pw3.metric("Total Runs", int(pw_bat['runs'].sum()))
            pw4.metric("4s / 6s", f"{int(pw_bat['fours'].sum())} / {int(pw_bat['sixes'].sum())}")

            pi1,pi2 = st.columns(2)
            with pi1:
                ph_pw = pw_bat.groupby('phase',observed=True).agg(
                    Count=('runs','count'), SR=('SR','mean')
                ).reset_index()
                ph_pw['SR'] = ph_pw['SR'].round(1)
                fig_pi1 = px.bar(ph_pw, x='phase', y='SR', color='phase', text='SR',
                                 color_discrete_map={'Powerplay (1-6)':'#636EFA','Middle (7-16)':'#EF553B','Death (17-20)':'#00CC96'},
                                 title=f"{sel_pw} – Post-Wicket SR by Phase", height=320)
                st.plotly_chart(fig_pi1, use_container_width=True)
            with pi2:
                fig_pi2 = px.histogram(pw_bat, x='SR', nbins=10,
                                       title=f"{sel_pw} – Post-Wicket SR Distribution",
                                       color_discrete_sequence=['#636EFA'], height=320)
                st.plotly_chart(fig_pi2, use_container_width=True)

# ── Raw Data ──────────────────────────────────────────────────────────────────
with st.expander("📋 Raw Data"):
    cols_s = ['bat','team_bat','bowl','team_bowl','over','phase','score','batruns','out',
              'shot_label','line_label','length_label','bowl_kind','bowl_style_label','bat_hand','wagonZone','control']
    st.dataframe(dff[cols_s].reset_index(drop=True), use_container_width=True)
    csv = dff[cols_s].to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download CSV", csv, "ipl_2026_filtered.csv", "text/csv")
