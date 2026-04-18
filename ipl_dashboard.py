import streamlit as st
import pandas as pd
import plotly.express as px
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
    return True

if not check_password():
    st.stop()

st.set_page_config(page_title="IPL Analytics 2023–2025", layout="wide", page_icon="🏏")

# ── Load & clean ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    df = pd.read_excel(path)
    df['bat']        = df['bat'].str.strip().str.title()
    df['bowl']       = df['bowl'].str.strip().str.title()
    df['team_bat']   = df['team_bat'].str.strip().str.replace('Royal Challengers Bangalore','RCB').str.replace('Royal Challengers Bengaluru','RCB')
    df['team_bowl']  = df['team_bowl'].str.strip().str.replace('Royal Challengers Bangalore','RCB').str.replace('Royal Challengers Bengaluru','RCB')
    df['ground']     = df['ground'].str.strip()
    df['shot']       = df['shot'].str.strip()
    df['line']       = df['line'].str.strip()
    df['length']     = df['length'].str.strip()
    df['bowl_style'] = df['bowl_style'].str.strip()

    for c in ['score','batruns','over','out','control','wagonX','wagonY','wagonZone','wprob','ball','wide','noball','inns_wkts']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['out']    = df['out'].fillna(0).astype(int)
    df['wide']   = df['wide'].fillna(0).astype(int)
    df['noball'] = df['noball'].fillna(0).astype(int)
    df['ball']   = df['ball'].fillna(0).astype(int)
    df['batruns']= df['batruns'].fillna(0)
    df['score']  = df['score'].fillna(0)

    # Dot ball = score 0, not wide, not noball
    df['is_dot'] = ((df['score']==0) & (df['wide']==0) & (df['noball']==0)).astype(int)

    def phase(o):
        if o <= 6:  return 'Powerplay (1–6)'
        if o <= 16: return 'Middle (7–16)'
        return 'Death (17–20)'
    df['phase'] = df['over'].apply(phase)
    df['phase'] = pd.Categorical(df['phase'],
                    categories=['Powerplay (1–6)','Middle (7–16)','Death (17–20)'], ordered=True)

    def phase_detail(o):
        if o <= 6:  return 'Powerplay (1–6)'
        if o <= 11: return 'Early Middle (7–11)'
        if o <= 16: return 'Late Middle (12–16)'
        return 'Death (17–20)'
    df['phase_detail'] = df['over'].apply(phase_detail)
    df['phase_detail'] = pd.Categorical(df['phase_detail'],
        categories=['Powerplay (1–6)','Early Middle (7–11)','Late Middle (12–16)','Death (17–20)'], ordered=True)

    df['line_label']      = df['line'].str.replace('_',' ').str.title()
    df['length_label']    = df['length'].str.replace('_',' ').str.title()
    df['shot_label']      = df['shot'].str.replace('_',' ').str.title()

    # Valid bowling dismissals — exclude run outs and retired
    bowling_dismissals = ['caught','bowled','leg before wicket','stumped','hit wicket']
    df['bowl_wicket'] = ((df['out']==1) & (df['dismissal'].isin(bowling_dismissals))).astype(int)

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

# ── Helpers ────────────────────────────────────────────────────────────────────
def bpb(balls, fours, sixes):
    b = fours + sixes
    return round(balls/b, 1) if b > 0 else np.nan

def dot_pct(dots, balls):
    return round(dots/balls*100, 1) if balls > 0 else np.nan

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🏏 IPL 2026 Filters")
sel_phase     = st.sidebar.multiselect("Phase", ['Powerplay (1–6)','Middle (7–16)','Death (17–20)'],
                                        default=['Powerplay (1–6)','Middle (7–16)','Death (17–20)'])
sel_bowl_kind = st.sidebar.multiselect("Bowler Kind", sorted(df['bowl_kind'].dropna().unique()),
                                        default=sorted(df['bowl_kind'].dropna().unique()))
sel_bat_hand  = st.sidebar.multiselect("Batter Hand", sorted(df['bat_hand'].dropna().unique()),
                                        default=sorted(df['bat_hand'].dropna().unique()))
sel_team_bat  = st.sidebar.multiselect("Batting Team", sorted(df['team_bat'].dropna().unique()),
                                        default=sorted(df['team_bat'].dropna().unique()))
sel_year      = st.sidebar.multiselect("Year", sorted(df['year'].unique()), default=sorted(df['year'].unique()))
min_balls     = st.sidebar.slider("Min balls (filter noise)", 5, 60, 15)

filt = (
    df['year'].isin(sel_year) &
    df['phase'].isin(sel_phase) &
    df['bowl_kind'].isin(sel_bowl_kind) &
    df['bat_hand'].isin(sel_bat_hand) &
    df['team_bat'].isin(sel_team_bat)
)
dff = df[filt]

st.title("🏏 IPL Analytics Dashboard  |  2023 – 2025")
st.caption(f"**{len(dff):,}** deliveries  |  **{dff['p_match'].nunique()}** matches  |  **{dff['bat'].nunique()}** batters  |  **{dff['bowl'].nunique()}** bowlers  |  **{dff['year'].nunique()}** years")

if dff.empty:
    st.warning("No data matches current filters.")
    st.stop()

k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.metric("Deliveries", f"{len(dff):,}")
k2.metric("Runs Scored", f"{int(dff['batruns'].sum()):,}")
k3.metric("Wickets", f"{int(dff['out'].sum()):,}")
k4.metric("Fours", f"{int((dff['score']==4).sum()):,}")
k5.metric("Sixes", f"{int((dff['score']==6).sum()):,}")
valid = dff[dff['wide']==0]
sr_val = valid['batruns'].sum()/max(len(valid),1)*100
k6.metric("Overall SR", f"{sr_val:.1f}")
st.divider()

tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs([
    "🎯 Shot Analysis","📍 Line & Length","🏏 Batter Analysis",
    "🎳 Bowler Analysis","🏆 Team Analysis","📅 Year on Year",
    "💥 Game Changers","⚡ Momentum Controllers"
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
                  color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                  title="Avg Runs by Shot × Phase", height=420)
    fig5.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig5, use_container_width=True)
    st.dataframe(shot_grp.sort_values('Avg Runs',ascending=False).reset_index(drop=True), use_container_width=True)

    st.divider()
    st.subheader("🔍 Who Plays a Specific Shot Best?")
    shot_opts = sorted(shot_df['shot_label'].dropna().unique())
    sel_shot  = st.selectbox("Select a Shot", shot_opts)
    shot_bat_grp = shot_df[shot_df['shot_label']==sel_shot].groupby('bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    shot_bat_grp = shot_bat_grp[shot_bat_grp['Balls'] >= 3]
    total_sb = shot_bat_grp['Balls'].sum()
    shot_bat_grp['SR']         = (shot_bat_grp['Runs']/shot_bat_grp['Balls']*100).round(1)
    shot_bat_grp['Avg']        = (shot_bat_grp['Runs']/shot_bat_grp['Outs'].replace(0,np.nan)).round(1).fillna(shot_bat_grp['Runs'])
    shot_bat_grp['Frequency%'] = (shot_bat_grp['Balls']/max(total_sb,1)*100).round(1)
    shot_bat_grp = shot_bat_grp.sort_values('Runs',ascending=False).reset_index(drop=True)
    shot_bat_grp.index += 1
    sb1,sb2 = st.columns([1.2,1])
    with sb1:
        fig_sb = px.bar(shot_bat_grp.head(15), x='bat', y='Runs',
                        color='SR', color_continuous_scale='RdYlGn',
                        text='Runs', title=f"Who Hits '{sel_shot}' Most? (color=SR)", height=420)
        fig_sb.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_sb, use_container_width=True)
    with sb2:
        st.markdown(f"**Full List – {sel_shot}**")
        st.dataframe(shot_bat_grp[['bat','Balls','Runs','SR','Avg','Frequency%']], use_container_width=True, height=400)

# ══ TAB 2 — Line & Length ═════════════════════════════════════════════════════
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
                        title="SR: Length × Line", height=500)
        fig.update_traces(textfont_size=14)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        pivot_dis = ll_grp.pivot(index='length_label', columns='line_label', values='Dismissal%')
        fig2 = px.imshow(pivot_dis, color_continuous_scale='RdYlGn_r', text_auto=True,
                         title="Dismissal %: Length × Line", height=500)
        fig2.update_traces(textfont_size=14)
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
                  color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                  title="SR by Length Across Phases", height=400)
    fig5.update_layout(xaxis_tickangle=-20)
    st.plotly_chart(fig5, use_container_width=True)

    st.divider()
    st.subheader("🔍 Bowler Performance by Length")
    len_opts   = sorted(ll['length_label'].dropna().unique())
    total_ll_balls = len(ll)
    sel_len    = st.selectbox("Select a Length", len_opts)
    len_bowl   = ll[ll['length_label']==sel_len].groupby('bowl').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('bowl_wicket','sum')
    ).reset_index()
    len_bowl = len_bowl[len_bowl['Balls'] >= 5]
    len_total_balls = len_bowl['Balls'].sum()
    len_bowl['Economy']  = (len_bowl['Runs']/(len_bowl['Balls']/6)).round(2)
    len_bowl['Avg']      = (len_bowl['Runs']/len_bowl['Wickets'].replace(0,np.nan)).round(1)
    len_bowl['Balls%']   = (len_bowl['Balls']/max(len_total_balls,1)*100).round(1)
    len_bowl = len_bowl.sort_values('Economy',ascending=True).reset_index(drop=True)
    len_bowl.index += 1

    lb1,lb2 = st.columns([1.2,1])
    with lb1:
        fig_lb = px.bar(len_bowl.head(15), x='bowl', y='Economy',
                        color='Economy', color_continuous_scale='RdYlGn_r',
                        text='Economy', title=f"Best Economy at '{sel_len}'", height=420)
        fig_lb.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_lb, use_container_width=True)
    with lb2:
        st.markdown(f"**Full Bowler List at {sel_len}**")
        st.dataframe(len_bowl[['bowl','Balls','Balls%','Runs','Economy','Wickets','Avg']], use_container_width=True, height=400)

# ══ TAB 3 — Batter Analysis ═══════════════════════════════════════════════════
with tab3:
    st.subheader("Batter Performance Analysis")

    # Only legal balls for batter stats
    dff_legal = dff[dff['wide']==0]

    bat_grp = dff_legal.groupby('bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum()),
        Dots=('is_dot','sum'), Controlled=('control','sum'), Ctrl_Balls=('control','count')
    ).reset_index()
    bat_grp = bat_grp[bat_grp['Balls'] >= min_balls]
    bat_grp['SR']       = (bat_grp['Runs']/bat_grp['Balls']*100).round(1)
    bat_grp['Avg']      = (bat_grp['Runs']/bat_grp['Outs'].replace(0,np.nan)).round(1).fillna(bat_grp['Runs'])
    bat_grp['BPB']      = bat_grp.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
    bat_grp['Dot%']     = (bat_grp['Dots']/bat_grp['Balls']*100).round(1)
    bat_grp['Control%'] = (bat_grp['Controlled']/bat_grp['Ctrl_Balls'].replace(0,np.nan)*100).round(1)

    c1,c2 = st.columns(2)
    with c1:
        top_n  = st.slider("Top N batters", 5, 30, 15, key='bat_n')
        metric = st.radio("Rank by", ['SR','Runs','Avg','BPB','Dot%','Control%'], horizontal=True, key='bat_m')
        asc = metric in ['BPB','Dot%']
        fig = px.bar(bat_grp.nsmallest(top_n,metric) if asc else bat_grp.nlargest(top_n,metric),
                     x='bat', y=metric, color=metric,
                     color_continuous_scale='RdYlGn_r' if asc else 'Teal',
                     text=metric, title=f"Top {top_n} Batters by {metric}", height=420)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.scatter(bat_grp.nlargest(40,'Balls'), x='Avg', y='SR', size='Balls',
                          text='bat', color='Dot%', color_continuous_scale='RdYlGn_r',
                          title="SR vs Average (color=Dot%)", height=420)
        fig2.update_traces(textposition='top center', textfont_size=8)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("**Full Batter Leaderboard**")
    st.dataframe(bat_grp.sort_values('SR',ascending=False).reset_index(drop=True)
                 [['bat','Balls','Runs','SR','Avg','Fours','Sixes','BPB','Dot%','Dots']],
                 use_container_width=True)

    st.divider()
    st.subheader("🎯 Dominant Batters vs Bowling Style")
    style_opts = sorted(dff['bowl_style_label'].dropna().unique())
    sel_style  = st.selectbox("Select Bowling Style", style_opts)
    sdf = dff_legal[dff['bowl_style_label']==sel_style]
    s_grp = sdf.groupby('bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum()),
        Dots=('is_dot','sum')
    ).reset_index()
    s_grp = s_grp[s_grp['Balls'] >= 5]
    s_grp['SR']   = (s_grp['Runs']/s_grp['Balls']*100).round(1)
    s_grp['Avg']  = (s_grp['Runs']/s_grp['Outs'].replace(0,np.nan)).round(1).fillna(s_grp['Runs'])
    s_grp['BPB']  = s_grp.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
    s_grp['Dot%'] = (s_grp['Dots']/s_grp['Balls']*100).round(1)
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
        st.dataframe(s_grp[['bat','Balls','Runs','SR','Avg','Fours','Sixes','BPB','Dot%']],
                     use_container_width=True, height=380)

    st.divider()
    st.subheader("🔍 Individual Batter Deep Dive")
    sel_bat = st.selectbox("Select Batter", sorted(dff['bat'].unique()))
    bdf     = dff_legal[dff_legal['bat']==sel_bat]
    f4 = int((bdf['score']==4).sum()); f6 = int((bdf['score']==6).sum())
    bpb_v  = bpb(len(bdf), f4, f6)
    dot_v  = dot_pct(int(bdf['is_dot'].sum()), len(bdf))

    b1,b2,b3,b4,b5,b6,b7 = st.columns(7)
    b1.metric("Balls", len(bdf)); b2.metric("Runs", int(bdf['batruns'].sum()))
    b3.metric("Dismissals", int(bdf['out'].sum()))
    b4.metric("SR", f"{bdf['batruns'].sum()/max(len(bdf),1)*100:.1f}")
    b5.metric("4s / 6s", f"{f4} / {f6}")
    b6.metric("Balls/Boundary", f"{bpb_v}" if not np.isnan(bpb_v) else "N/A")
    b7.metric("Dot%", f"{dot_v}%" if dot_v else "N/A")

    c3,c4 = st.columns(2)
    with c3:
        ph = bdf.groupby('phase',observed=True).agg(
            Balls=('batruns','count'), Runs=('batruns','sum'),
            Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum()),
            Dots=('is_dot','sum')
        ).reset_index()
        ph['SR']   = (ph['Runs']/ph['Balls']*100).round(1)
        ph['BPB']  = ph.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
        ph['Dot%'] = (ph['Dots']/ph['Balls']*100).round(1)
        fig3 = px.bar(ph, x='phase', y='SR', color='phase', text='SR',
                      color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                      title=f"{sel_bat} – SR by Phase", height=350)
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        fig_dot_ph = px.bar(ph, x='phase', y='Dot%', color='phase', text='Dot%',
                            color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                            title=f"{sel_bat} – Dot% by Phase (lower=better)", height=350)
        st.plotly_chart(fig_dot_ph, use_container_width=True)

    pk = bdf.groupby('bowl_kind').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum()),
        Dots=('is_dot','sum'), Controlled=('control','sum'), Ctrl_Balls=('control','count')
    ).reset_index()
    pk['SR']       = (pk['Runs']/pk['Balls']*100).round(1)
    pk['Avg']      = (pk['Runs']/pk['Outs'].replace(0,np.nan)).round(1).fillna(pk['Runs'])
    pk['BPB']      = pk.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
    pk['Dot%']     = (pk['Dots']/pk['Balls']*100).round(1)
    pk['Control%'] = (pk['Controlled']/pk['Ctrl_Balls'].replace(0,np.nan)*100).round(1)

    st.markdown("**Matchup – Pace & Spin**")
    st.dataframe(pk[['bowl_kind','Balls','Runs','SR','Avg','Fours','Sixes','BPB','Dot%','Control%']], use_container_width=True)

    st.divider()
    st.markdown(f"**{sel_bat} – vs Each Bowling Style**")
    bs = bdf.groupby('bowl_style_label').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum()),
        Dots=('is_dot','sum'), Controlled=('control','sum'), Ctrl_Balls=('control','count')
    ).reset_index()
    bs = bs[bs['Balls']>=3]
    bs['SR']       = (bs['Runs']/bs['Balls']*100).round(1)
    bs['Avg']      = (bs['Runs']/bs['Outs'].replace(0,np.nan)).round(1).fillna(bs['Runs'])
    bs['BPB']      = bs.apply(lambda r: bpb(r['Balls'],r['Fours'],r['Sixes']), axis=1)
    bs['Dot%']     = (bs['Dots']/bs['Balls']*100).round(1)
    bs['Control%'] = (bs['Controlled']/bs['Ctrl_Balls'].replace(0,np.nan)*100).round(1)

    c5,c6 = st.columns(2)
    with c5:
        fig5 = px.bar(bs.sort_values('SR',ascending=False), x='bowl_style_label', y='SR',
                      color='SR', color_continuous_scale='RdYlGn', text='SR',
                      title=f"{sel_bat} – SR by Bowling Style", height=380)
        fig5.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig5, use_container_width=True)
    with c6:
        st.dataframe(bs[['bowl_style_label','Balls','Runs','SR','Avg','Fours','Sixes','BPB','Dot%','Control%']].sort_values('SR',ascending=False),
                     use_container_width=True)

    c7,c8 = st.columns(2)
    with c7:
        bl = bdf.dropna(subset=['length']).groupby('length_label').agg(
            Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
            Dots=('is_dot','sum')
        ).reset_index()
        bl['SR']   = (bl['Runs']/bl['Balls']*100).round(1)
        bl['Dis%'] = (bl['Outs']/bl['Balls']*100).round(1)
        bl['Dot%'] = (bl['Dots']/bl['Balls']*100).round(1)
        fig7 = px.bar(bl, x='length_label', y='SR', color='Dis%',
                      color_continuous_scale='RdYlGn_r', text='SR',
                      title=f"{sel_bat} – SR by Length (color=Dis%)", height=350)
        st.plotly_chart(fig7, use_container_width=True)
    with c8:
        wz = bdf.groupby('wagonZone').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
        wz['Zone'] = wz['wagonZone'].map({0:'Dot Zone',1:'Fine Leg',2:'Square Leg',3:'Mid Wicket',
                                          4:'Mid On',5:'Mid Off',6:'Cover',7:'Point',8:'Third Man'})
        fig8 = px.bar_polar(wz, r='Runs', theta='Zone', color='Runs',
                            color_continuous_scale='RdYlGn', title=f"{sel_bat} – Scoring Zones", height=350)
        st.plotly_chart(fig8, use_container_width=True)

    # ── Dismissal Heatmap ──
    st.divider()
    st.markdown(f"#### 🎯 {sel_bat} – Dismissal Heatmap (Line & Length)")
    st.caption("Where does this batter get out? Darker = more dismissals")
    dis_all = bdf.dropna(subset=['line','length'])
    if dis_all.empty or dis_all['out'].sum() == 0:
        st.info("No dismissal data available for this batter with current filters.")
    else:
        # All balls faced at each length & line
        all_grp = dis_all.groupby(['length_label','line_label']).agg(
            Balls=('batruns','count'),
            Dismissals=('out','sum')
        ).reset_index()
        all_grp['Dis%'] = (all_grp['Dismissals']/all_grp['Balls']*100).round(1)

        # Heatmap shows dismissal count (darker = got out more times)
        pivot_dis = all_grp.pivot(index='length_label', columns='line_label', values='Dismissals').fillna(0)
        fig_dis = px.imshow(pivot_dis, color_continuous_scale='Reds',
                            text_auto=True,
                            title=f"{sel_bat} – Dismissals by Line & Length (count)",
                            height=500)
        fig_dis.update_traces(textfont_size=14)
        fig_dis.update_layout(
            xaxis_title="Line",
            yaxis_title="Length",
            coloraxis_colorbar_title="Dismissals"
        )
        st.plotly_chart(fig_dis, use_container_width=True)

        st.markdown("**Dismissal Table – Balls Faced, Times Out & Dismissal Rate**")
        st.caption("Dis% = Dismissals ÷ Total balls faced at that length & line × 100")
        dis_table = all_grp.sort_values('Dismissals', ascending=False).reset_index(drop=True)
        dis_table.index += 1
        st.dataframe(dis_table[['length_label','line_label','Balls','Dismissals','Dis%']],
                     use_container_width=True)
with tab4:
    st.subheader("Bowler Performance Analysis")

    dff_bowl = dff[dff['wide']==0]
    bowl_grp = dff_bowl.groupby('bowl').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('bowl_wicket','sum'),
        Dots=('is_dot','sum')
    ).reset_index()
    bowl_grp = bowl_grp[bowl_grp['Balls'] >= min_balls]
    bowl_grp['Economy'] = (bowl_grp['Runs']/(bowl_grp['Balls']/6)).round(2)
    bowl_grp['SR']      = (bowl_grp['Balls']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)
    bowl_grp['Avg']     = (bowl_grp['Runs']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)
    bowl_grp['Dot%']    = (bowl_grp['Dots']/bowl_grp['Balls']*100).round(1)

    c1,c2 = st.columns(2)
    with c1:
        top_nb = st.slider("Top N bowlers", 5, 30, 15, key='bowl_n')
        bm     = st.radio("Rank by", ['Economy','Wickets','Avg','Dot%'], horizontal=True, key='bowl_m')
        asc_b  = bm in ['Economy','Avg']
        desc_b = bm in ['Wickets','Dot%']
        fig = px.bar(bowl_grp.nsmallest(top_nb,bm) if asc_b else bowl_grp.nlargest(top_nb,bm),
                     x='bowl', y=bm, color=bm,
                     color_continuous_scale='RdYlGn_r' if asc_b else 'Teal',
                     text=bm, title=f"Top {top_nb} Bowlers by {bm}", height=420)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.scatter(bowl_grp.nlargest(40,'Balls'), x='Economy', y='Wickets',
                          size='Balls', text='bowl', color='Dot%',
                          color_continuous_scale='RdYlGn',
                          title="Economy vs Wickets (color=Dot%)", height=420)
        fig2.update_traces(textposition='top center', textfont_size=8)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("**Full Bowler Leaderboard**")
    st.dataframe(bowl_grp.sort_values('Dot%',ascending=False).reset_index(drop=True)
                 [['bowl','Balls','Runs','Wickets','Economy','SR','Avg','Dot%','Dots']],
                 use_container_width=True)

    st.divider()
    st.subheader("🎯 Best Bowlers vs Left Hand / Right Hand Batters")
    hand_sel = st.radio("Select Batter Hand", ['LHB','RHB'], horizontal=True, key='hand_sel')
    hand_df  = dff_bowl[dff_bowl['bat_hand']==hand_sel]
    hand_grp = hand_df.groupby('bowl').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('bowl_wicket','sum'), Dots=('is_dot','sum')
    ).reset_index()
    hand_grp = hand_grp[hand_grp['Balls'] >= min_balls]
    hand_grp['Economy'] = (hand_grp['Runs']/(hand_grp['Balls']/6)).round(2)
    hand_grp['Avg']     = (hand_grp['Runs']/hand_grp['Wickets'].replace(0,np.nan)).round(1)
    hand_grp['Dot%']    = (hand_grp['Dots']/hand_grp['Balls']*100).round(1)
    hand_grp = hand_grp.sort_values('Economy',ascending=True).reset_index(drop=True)
    hand_grp.index += 1

    hb1,hb2 = st.columns([1.2,1])
    with hb1:
        fig_hb = px.bar(hand_grp.head(15), x='bowl', y='Economy',
                        color='Economy', color_continuous_scale='RdYlGn_r',
                        text='Economy', title=f"Best Bowlers vs {hand_sel} (Economy)", height=420)
        fig_hb.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_hb, use_container_width=True)
    with hb2:
        st.markdown(f"**Full list vs {hand_sel}**")
        st.dataframe(hand_grp[['bowl','Balls','Runs','Economy','Wickets','Avg','Dot%']], use_container_width=True, height=400)

    st.divider()
    st.subheader("🔍 Individual Bowler Deep Dive")
    sel_bowl = st.selectbox("Select Bowler", sorted(dff['bowl'].unique()))
    bwdf     = dff_bowl[dff_bowl['bowl']==sel_bowl]
    bwdf_ll  = bwdf.dropna(subset=['line','length'])

    bw1,bw2,bw3,bw4,bw5 = st.columns(5)
    bw1.metric("Balls", len(bwdf)); bw2.metric("Wickets", int(bwdf['bowl_wicket'].sum()))
    econ = bwdf['batruns'].sum()/max(len(bwdf)/6,0.1)
    bw3.metric("Economy", f"{econ:.2f}")
    bw4.metric("Bowl Kind", bwdf['bowl_kind'].mode()[0] if len(bwdf) else "N/A")
    bw5.metric("Dot%", f"{dot_pct(int(bwdf['is_dot'].sum()),len(bwdf))}%")

    c3,c4 = st.columns(2)
    with c3:
        ll_b = bwdf_ll.groupby(['length_label','line_label']).agg(
            Balls=('batruns','count'), Wickets=('bowl_wicket','sum')).reset_index()
        pivot_b = ll_b.pivot(index='length_label', columns='line_label', values='Balls')
        fig3 = px.imshow(pivot_b, text_auto=True, color_continuous_scale='Blues',
                         title=f"{sel_bowl} – Delivery Map", height=480)
        fig3.update_traces(textfont_size=14)
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        pivot_wk = ll_b.pivot(index='length_label', columns='line_label', values='Wickets')
        fig4 = px.imshow(pivot_wk, text_auto=True, color_continuous_scale='Reds',
                         title=f"{sel_bowl} – Wickets by Line & Length", height=480)
        fig4.update_traces(textfont_size=14)
        st.plotly_chart(fig4, use_container_width=True)

    # Phase breakdown with Dot%
    ph_b = bwdf.groupby('phase_detail',observed=True).agg(
        Balls=('batruns','count'), Runs=('batruns','sum'),
        Wickets=('bowl_wicket','sum'), Dots=('is_dot','sum')
    ).reset_index()
    ph_b['Economy'] = (ph_b['Runs']/(ph_b['Balls']/6)).round(2)
    ph_b['Dot%']    = (ph_b['Dots']/ph_b['Balls']*100).round(1)
    ph_b['Util%']   = (ph_b['Balls']/ph_b['Balls'].sum()*100).round(1)

    c5,c6,c7 = st.columns(3)
    with c5:
        fig5 = px.bar(ph_b, x='phase_detail', y='Util%', color='Util%',
                      color_continuous_scale='Teal', text='Util%',
                      title=f"{sel_bowl} – Over Utilisation %", height=320)
        st.plotly_chart(fig5, use_container_width=True)
    with c6:
        fig6 = px.bar(ph_b, x='phase_detail', y='Economy', color='Economy',
                      color_continuous_scale='RdYlGn_r', text='Economy',
                      title=f"{sel_bowl} – Economy by Phase", height=320)
        st.plotly_chart(fig6, use_container_width=True)
    with c7:
        fig7 = px.bar(ph_b, x='phase_detail', y='Dot%', color='Dot%',
                      color_continuous_scale='RdYlGn', text='Dot%',
                      title=f"{sel_bowl} – Dot% by Phase (higher=better)", height=320)
        st.plotly_chart(fig7, use_container_width=True)

    st.dataframe(ph_b[['phase_detail','Balls','Util%','Runs','Economy','Wickets','Dot%']], use_container_width=True)

    # Natural length
    st.divider()
    nat = bwdf_ll.groupby('length_label').agg(Balls=('batruns','count')).reset_index()
    nat['Pct'] = (nat['Balls']/nat['Balls'].sum()*100).round(1)
    nat = nat.sort_values('Pct', ascending=False)
    c8,c9 = st.columns(2)
    with c8:
        fig8 = px.bar(nat, x='length_label', y='Pct', color='Pct',
                      color_continuous_scale='Blues', text='Pct',
                      title=f"{sel_bowl} – Natural Length %", height=320)
        st.plotly_chart(fig8, use_container_width=True)
    with c9:
        fig9 = px.pie(nat, names='length_label', values='Balls',
                      title=f"{sel_bowl} – Natural Length", height=320)
        st.plotly_chart(fig9, use_container_width=True)

# ══ TAB 5 — Team Analysis ═════════════════════════════════════════════════════
with tab5:
    st.subheader("Team Performance Analysis")

    # ── Team Batting ──
    st.markdown("### 🏏 Team Batting")
    t_bat = dff[dff['wide']==0].groupby('team_bat').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()), Sixes=('score', lambda x:(x==6).sum()),
        Dots=('is_dot','sum')
    ).reset_index()
    t_bat['SR']        = (t_bat['Runs']/t_bat['Balls']*100).round(1)
    t_bat['Dot%_Bat']  = (t_bat['Dots']/t_bat['Balls']*100).round(1)

    c1,c2,c3 = st.columns(3)
    with c1:
        fig = px.bar(t_bat.sort_values('SR',ascending=False), x='team_bat', y='SR',
                     color='SR', color_continuous_scale='RdYlGn', text='SR',
                     title="Team SR", height=360)
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.bar(t_bat.sort_values('Fours',ascending=False), x='team_bat', y='Fours',
                      color='Fours', color_continuous_scale='Blues', text='Fours',
                      title="Team Fours", height=360)
        fig2.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig2, use_container_width=True)
    with c3:
        fig3 = px.bar(t_bat.sort_values('Sixes',ascending=False), x='team_bat', y='Sixes',
                      color='Sixes', color_continuous_scale='Reds', text='Sixes',
                      title="Team Sixes", height=360)
        fig3.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig3, use_container_width=True)

    # Dot% batting
    fig_db = px.bar(t_bat.sort_values('Dot%_Bat',ascending=True), x='team_bat', y='Dot%_Bat',
                    color='Dot%_Bat', color_continuous_scale='RdYlGn_r', text='Dot%_Bat',
                    title="Team Batting Dot% (lower=better)", height=360)
    fig_db.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig_db, use_container_width=True)

    st.divider()
    # ── Team Bowling ──
    st.markdown("### 🎳 Team Bowling")
    t_bowl = dff[dff['wide']==0].groupby('team_bowl').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Wickets=('bowl_wicket','sum'),
        Dots=('is_dot','sum')
    ).reset_index()
    t_bowl['Economy']    = (t_bowl['Runs']/(t_bowl['Balls']/6)).round(2)
    t_bowl['Dot%_Bowl']  = (t_bowl['Dots']/t_bowl['Balls']*100).round(1)

    c4,c5 = st.columns(2)
    with c4:
        fig4 = px.bar(t_bowl.sort_values('Economy',ascending=True), x='team_bowl', y='Economy',
                      color='Economy', color_continuous_scale='RdYlGn_r', text='Economy',
                      title="Team Bowling Economy (lower=better)", height=360)
        fig4.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig4, use_container_width=True)
    with c5:
        fig5 = px.bar(t_bowl.sort_values('Dot%_Bowl',ascending=False), x='team_bowl', y='Dot%_Bowl',
                      color='Dot%_Bowl', color_continuous_scale='RdYlGn', text='Dot%_Bowl',
                      title="Team Bowling Dot% (higher=better)", height=360)
        fig5.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig5, use_container_width=True)

    st.divider()
    # Pace/Spin and Phase
    tps = dff.groupby(['team_bat','bowl_kind']).agg(
        Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    tps['SR'] = (tps['Runs']/tps['Balls']*100).round(1)
    fig6 = px.bar(tps, x='team_bat', y='SR', color='bowl_kind', barmode='group',
                  title="Team SR vs Pace/Spin", height=380, text='SR')
    fig6.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig6, use_container_width=True)

    st.divider()
    sel_team = st.selectbox("Select Team – Scoring Zones", sorted(dff['team_bat'].unique()))
    tdf = dff[tdf['team_bat']==sel_team] if False else dff[dff['team_bat']==sel_team]
    wz_t = tdf.groupby('wagonZone').agg(Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
    wz_t['Zone'] = wz_t['wagonZone'].map({0:'Dot Zone',1:'Fine Leg',2:'Square Leg',3:'Mid Wicket',
                                           4:'Mid On',5:'Mid Off',6:'Cover',7:'Point',8:'Third Man'})
    c6,c7 = st.columns(2)
    with c6:
        fig7 = px.bar_polar(wz_t, r='Runs', theta='Zone', color='Runs',
                            color_continuous_scale='RdYlGn', title=f"{sel_team} – Zones", height=380)
        st.plotly_chart(fig7, use_container_width=True)
    with c7:
        tph = dff.groupby(['team_bat','phase'],observed=True).agg(
            Balls=('batruns','count'), Runs=('batruns','sum')).reset_index()
        tph['SR'] = (tph['Runs']/tph['Balls']*100).round(1)
        fig8 = px.bar(tph, x='team_bat', y='SR', color='phase', barmode='group',
                      color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                      title="Team SR by Phase", height=380, text='SR')
        fig8.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig8, use_container_width=True)

# ══ TAB 6 — Year on Year ══════════════════════════════════════════════════════
with tab6:
    st.subheader("Year on Year Trends (2023 → 2024 → 2025)")

    yoy = dff.groupby('year').agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum'),
        Fours=('score', lambda x:(x==4).sum()),
        Sixes=('score', lambda x:(x==6).sum())
    ).reset_index()
    yoy['SR']        = (yoy['Runs']/yoy['Balls']*100).round(1)
    yoy['Boundary%'] = ((yoy['Fours']+yoy['Sixes'])/yoy['Balls']*100).round(1)

    c1,c2,c3 = st.columns(3)
    with c1:
        fig = px.line(yoy, x='year', y='SR', markers=True, text='SR',
                      title="Overall SR Trend", height=320)
        fig.update_traces(textposition='top center')
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.line(yoy, x='year', y='Boundary%', markers=True, text='Boundary%',
                       title="Boundary % Trend", height=320)
        fig2.update_traces(textposition='top center')
        st.plotly_chart(fig2, use_container_width=True)
    with c3:
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

    st.subheader("Top Batters by Year")
    bat_yr = dff.groupby(['bat','year']).agg(
        Balls=('batruns','count'), Runs=('batruns','sum'), Outs=('out','sum')
    ).reset_index()
    bat_yr = bat_yr[bat_yr['Balls'] >= min_balls]
    bat_yr['SR']  = (bat_yr['Runs']/bat_yr['Balls']*100).round(1)
    bat_yr['Avg'] = (bat_yr['Runs']/bat_yr['Outs'].replace(0,np.nan)).round(1).fillna(bat_yr['Runs'])
    top_bats = dff.groupby('bat')['batruns'].sum().nlargest(10).index.tolist()
    fig6 = px.bar(bat_yr[bat_yr['bat'].isin(top_bats)], x='bat', y='SR',
                  color='year', barmode='group', text='SR',
                  title="SR by Year – Top 10 Batters by Total Runs", height=420)
    fig6.update_layout(xaxis_tickangle=-40)
    st.plotly_chart(fig6, use_container_width=True)

# ══ TAB 7 — Game Changers ═════════════════════════════════════════════════════
with tab7:
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
                st.dataframe(lb[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over']], use_container_width=True)

        st.divider()
        st.markdown("### 📊 By Phase")
        for ph_n, color in zip(['Powerplay (1–6)','Middle (7–16)','Death (17–20)'],['Teal','Oranges','Purples']):
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
                               text='Impact_Overs', title="Impact Overs Count", height=320)
                fig_a.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_a, use_container_width=True)
            with cb:
                fig_b = px.bar(ph_lb.sort_values('Impact_Freq%',ascending=False).head(15),
                               x='bat', y='Impact_Freq%', color='Impact_Freq%',
                               color_continuous_scale='RdYlGn', text='Impact_Freq%',
                               title="Impact Freq%", height=320)
                fig_b.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_b, use_container_width=True)
            with cc:
                ph_lb.index = ph_lb.index + 1
                st.dataframe(ph_lb[['bat','Impact_Overs','Total_Overs_Batted','Impact_Freq%','Total_Runs','Best_Over','Avg_Runs']],
                             use_container_width=True, height=320)

        st.divider()
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
            ov_lb = ov_lb.sort_values('Impact_Overs',ascending=False).reset_index(drop=True); ov_lb.index += 1
            co1,co2 = st.columns([1.2,1])
            with co1:
                fig_o = px.bar(ov_lb.head(15), x='bat', y='Impact_Overs',
                               color='Impact_Overs', color_continuous_scale='Plasma',
                               text='Impact_Overs', title=f"Over {sel_ov} – Impact Overs", height=380)
                fig_o.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_o, use_container_width=True)
            with co2:
                fig_o2 = px.bar(ov_lb.sort_values('Impact_Freq%',ascending=False).head(15),
                                x='bat', y='Impact_Freq%', color='Impact_Freq%',
                                color_continuous_scale='RdYlGn', text='Impact_Freq%',
                                title=f"Over {sel_ov} – Impact Freq%", height=380)
                fig_o2.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_o2, use_container_width=True)
            st.dataframe(ov_lb[['bat','Impact_Overs','Total_Times_Batted','Impact_Freq%','Total_Runs','Best_Over','Avg_Runs']],
                         use_container_width=True)

        st.divider()
        st.markdown("### 🔍 Individual Batter Profile")
        sel_gc = st.selectbox("Select Batter", sorted(impact['bat'].unique()), key='gc_bat')
        bi     = impact[impact['bat']==sel_gc]
        bi_tot = over_data[over_data['bat']==sel_gc].shape[0]
        bi_freq= (len(bi)/bi_tot*100) if bi_tot > 0 else 0
        bi_avg = bi['over_runs'].mean()

        g1,g2,g3,g4,g5,g6 = st.columns(6)
        g1.metric("Impact Overs", len(bi)); g2.metric("Total Overs", bi_tot)
        g3.metric("Impact Freq%", f"{bi_freq:.1f}%"); g4.metric("Best Over", int(bi['over_runs'].max()))
        g5.metric("Avg in Impact Over", f"{bi_avg:.1f}"); g6.metric("Total Runs", int(bi['over_runs'].sum()))

        # Consecutive
        st.markdown("#### 🔥 Consecutive Impact Overs")
        c_data = []
        for mid in bi['p_match'].unique():
            mi = bi[bi['p_match']==mid].sort_values(['inns','over'])
            ol = mi['over'].tolist(); mc=1; cc=1
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
        st.markdown("#### 🏆 Who Has Most Consecutive Impact Overs?")
        ca_all = []
        for batter in impact['bat'].unique():
            for mid in impact[impact['bat']==batter]['p_match'].unique():
                mi = impact[(impact['bat']==batter)&(impact['p_match']==mid)].sort_values(['inns','over'])
                ol = mi['over'].tolist(); mc=1; cc=1
                for i in range(1,len(ol)):
                    if ol[i]==ol[i-1]+1: cc+=1; mc=max(mc,cc)
                    else: cc=1
                if mc >= 2:
                    ca_all.append({'bat':batter,'match':mid,'Max_Consecutive':mc})
        if ca_all:
            ca_df  = pd.DataFrame(ca_all)
            ca_sum = ca_df.groupby('bat').agg(Times=('Max_Consecutive','count'), Max=('Max_Consecutive','max')).reset_index()
            ca_sum = ca_sum.sort_values('Times',ascending=False).reset_index(drop=True); ca_sum.index += 1
            cc1,cc2 = st.columns([1.2,1])
            with cc1:
                fig_cc = px.bar(ca_sum.head(15), x='bat', y='Times',
                                color='Times', color_continuous_scale='Plasma', text='Times',
                                title="Most Consecutive Impact Overs", height=360)
                fig_cc.update_layout(xaxis_tickangle=-40)
                st.plotly_chart(fig_cc, use_container_width=True)
            with cc2:
                st.dataframe(ca_sum, use_container_width=True, height=360)

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
        ph_b2 = bi.groupby('phase',observed=True).agg(Impact_Overs=('over_runs','count'), Avg_Runs=('over_runs','mean')).reset_index()
        ph_b2['Avg_Runs'] = ph_b2['Avg_Runs'].round(1)
        ph_t = over_data[over_data['bat']==sel_gc].groupby('phase',observed=True).agg(Total=('over_runs','count')).reset_index()
        ph_b2 = pd.merge(ph_b2, ph_t, on='phase', how='left')
        ph_b2['Impact_Freq%'] = (ph_b2['Impact_Overs']/ph_b2['Total']*100).round(1)
        cp1,cp2 = st.columns(2)
        with cp1:
            fig_p1 = px.bar(ph_b2, x='phase', y='Impact_Overs', color='phase', text='Impact_Overs',
                            color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                            title=f"{sel_gc} – Impact Overs by Phase", height=300)
            fig_p1.update_layout(showlegend=False)
            st.plotly_chart(fig_p1, use_container_width=True)
        with cp2:
            fig_p2 = px.bar(ph_b2, x='phase', y='Impact_Freq%', color='phase', text='Impact_Freq%',
                            color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
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

# ══ TAB 8 — Momentum Controllers ══════════════════════════════════════════════
with tab8:
    st.subheader("⚡ Momentum Controllers")
    mc1, mc2, mc3, mc4 = st.tabs([
        "🏏 Over Start Dominance", "🎳 Bowler Resilience", "🩹 Post-Wicket Scoring", "📊 Team Momentum"
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
        bat_s = bat_s.sort_values('Dom_Starts',ascending=False).reset_index(drop=True); bat_s.index += 1

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
        team_s = team_s.sort_values('Dom_Starts',ascending=False).reset_index(drop=True); team_s.index += 1
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
                        color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                        title="Dominant Starts by Phase – Top 12", height=400)
        fig_ps.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_ps, use_container_width=True)

        st.divider()
        st.markdown("### 🔍 Individual Batter Start Profile")
        sel_sb = st.selectbox("Select Batter", sorted(os_grp['bat'].unique()), key='sb')
        sb_all = os_grp[os_grp['bat']==sel_sb]
        sb_dom = dom[dom['bat']==sel_sb]
        sg1,sg2,sg3,sg4 = st.columns(4)
        sg1.metric("Total Starts", len(sb_all)); sg2.metric("Dominant Starts", len(sb_dom))
        sg3.metric("Freq%", f"{len(sb_dom)/max(len(sb_all),1)*100:.1f}%")
        sg4.metric("Avg in Dominant", f"{sb_dom['Runs'].mean():.1f}" if len(sb_dom) > 0 else "N/A")
        si1,si2 = st.columns(2)
        with si1:
            ph_sb = sb_dom.groupby('phase',observed=True).agg(Count=('Runs','count')).reset_index()
            fig_si1 = px.bar(ph_sb, x='phase', y='Count', color='phase', text='Count',
                             color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                             title=f"{sel_sb} – Dominant Starts by Phase", height=320)
            st.plotly_chart(fig_si1, use_container_width=True)
        with si2:
            fig_si2 = px.histogram(sb_all, x='Runs', nbins=10,
                                   title=f"{sel_sb} – First 3 Ball Score Distribution",
                                   color_discrete_sequence=['#636EFA'], height=320)
            st.plotly_chart(fig_si2, use_container_width=True)

    # ── MC TAB 2: Bowler Resilience (REBUILT) ─────────────────────────────────
    with mc2:
        st.subheader("🎳 Bowler Resilience – Who Controls After a Bad Start?")
        st.caption("Bad start = first 3 balls go for X+ runs. Then see how the bowler responds in last 3 balls.")

        bad_thr = st.slider("Bad start threshold (first 3 balls runs)", 4, 15, 6, key='bt')

        # Build over-level data with ball-level detail
        bowl_ov = dff.groupby(['p_match','inns','over','bowl','phase'],observed=True).apply(
            lambda x: pd.Series({
                'first3_runs'      : x[x['ball']<=3]['score'].sum(),
                'last3_runs'       : x[x['ball']>3]['score'].sum(),
                'last3_balls'      : len(x[x['ball']>3]),
                'last3_fours'      : int((x[x['ball']>3]['score']==4).sum()),
                'last3_sixes'      : int((x[x['ball']>3]['score']==6).sum()),
                'last3_dots'       : int(((x[x['ball']>3]['score']==0)&(x[x['ball']>3]['wide']==0)).sum()),
                'last3_boundaries' : int((x[x['ball']>3]['score']>=4).sum()),
            })
        ).reset_index()

        bad = bowl_ov[bowl_ov['first3_runs'] >= bad_thr].copy()

        # Three comeback tags
        bad['Strict']  = ((bad['last3_fours']==0) & (bad['last3_sixes']==0)).astype(int)
        bad['Good']    = ((bad['last3_fours']==1) & (bad['last3_sixes']==0)).astype(int)
        bad['Blown']   = ((bad['last3_sixes']>=1) | (bad['last3_fours']>=2)).astype(int)

        # Dot% and Boundary% in last 3
        bad['Last3_Dot%']      = (bad['last3_dots']/bad['last3_balls'].replace(0,np.nan)*100).round(1)
        bad['Last3_Boundary%'] = (bad['last3_boundaries']/bad['last3_balls'].replace(0,np.nan)*100).round(1)

        st.markdown(f"**Overs with {bad_thr}+ in first 3 balls: {len(bad):,}**")
        st.divider()

        st.markdown("### 🏆 Resilience Leaderboard")
        res = bad.groupby('bowl').agg(
            Bad_Starts   =('first3_runs','count'),
            Strict_Count =('Strict','sum'),
            Good_Count   =('Good','sum'),
            Blown_Count  =('Blown','sum'),
            Avg_First3   =('first3_runs','mean'),
            Avg_Last3    =('last3_runs','mean'),
            Dot_Pct      =('Last3_Dot%','mean'),
            Boundary_Pct =('Last3_Boundary%','mean'),
            Last3_Wkts   =('last3_dots','count')   # placeholder, fix below
        ).reset_index()

        # Recalculate last3 wickets properly
        last3_wkts = bad.groupby('bowl').apply(
            lambda x: x['last3_dots'].sum()  # dummy, replace
        ).reset_index()

        # Fix wickets - recompute from raw
        bowl_wkts = dff[dff['ball']>3].groupby('bowl').agg(Wkts=('bowl_wicket','sum')).reset_index()
        res = res.drop(columns=['Last3_Wkts'])
        res = pd.merge(res, bowl_wkts, on='bowl', how='left')

        res['Strict%']       = (res['Strict_Count']/res['Bad_Starts']*100).round(1)
        res['Good%']         = (res['Good_Count']/res['Bad_Starts']*100).round(1)
        res['Blown%']        = (res['Blown_Count']/res['Bad_Starts']*100).round(1)
        res['Avg_First3']    = res['Avg_First3'].round(1)
        res['Avg_Last3']     = res['Avg_Last3'].round(1)
        res['Dot_Pct']       = res['Dot_Pct'].round(1)
        res['Boundary_Pct']  = res['Boundary_Pct'].round(1)
        res = res[res['Bad_Starts']>=2].sort_values('Strict%',ascending=False).reset_index(drop=True)
        res.index += 1

        cr1,cr2 = st.columns([1.2,1])
        with cr1:
            fig_r = px.bar(res.head(15), x='bowl', y='Strict%',
                           color='Strict%', color_continuous_scale='RdYlGn',
                           text='Strict%', title=f"Strict Comeback % (0 boundaries in last 3)", height=400)
            fig_r.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_r, use_container_width=True)
        with cr2:
            fig_r2 = px.bar(res.head(15).sort_values('Good%',ascending=False),
                            x='bowl', y='Good%', color='Good%',
                            color_continuous_scale='Blues', text='Good%',
                            title="Good Comeback % (max 1 four, no sixes)", height=400)
            fig_r2.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_r2, use_container_width=True)

        st.markdown("**Full Resilience Table**")
        st.dataframe(res[['bowl','Bad_Starts','Strict_Count','Strict%','Good_Count','Good%',
                           'Blown_Count','Blown%','Avg_First3','Avg_Last3','Dot_Pct','Boundary_Pct']],
                     use_container_width=True)

        st.divider()
        # Blown It leaderboard
        st.markdown("### ❌ Who Ends Overs Badly? (Blown It)")
        blown_lb = res.sort_values('Blown%',ascending=False).head(15)
        cb1,cb2 = st.columns([1.2,1])
        with cb1:
            fig_bl = px.bar(blown_lb, x='bowl', y='Blown%',
                            color='Blown%', color_continuous_scale='Reds',
                            text='Blown%', title="Blown It % (sixes or 2+ boundaries)", height=380)
            fig_bl.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_bl, use_container_width=True)
        with cb2:
            fig_bnd = px.bar(res.sort_values('Boundary_Pct',ascending=False).head(15),
                             x='bowl', y='Boundary_Pct', color='Boundary_Pct',
                             color_continuous_scale='Reds', text='Boundary_Pct',
                             title="Boundary% in Last 3 Balls (higher=worse)", height=380)
            fig_bnd.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_bnd, use_container_width=True)

        st.divider()
        # Dot ball in last 3
        st.markdown("### 🎯 Dot Ball % in Last 3 Balls (higher=better)")
        fig_dot = px.bar(res.sort_values('Dot_Pct',ascending=False).head(15),
                         x='bowl', y='Dot_Pct', color='Dot_Pct',
                         color_continuous_scale='RdYlGn', text='Dot_Pct',
                         title="Dot% in Last 3 Balls After Bad Start", height=380)
        fig_dot.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_dot, use_container_width=True)

        st.divider()
        # Phase-wise — only Strict comeback by phase
        st.markdown("### 📊 Phase-wise Resilience")
        ph_res = bad.groupby(['bowl','phase'],observed=True).agg(
            Bad_Starts=('first3_runs','count'),
            Strict=('Strict','sum'), Good=('Good','sum'), Blown=('Blown','sum')
        ).reset_index()
        ph_res['Strict%'] = (ph_res['Strict']/ph_res['Bad_Starts']*100).round(1)
        top10_r = res.head(10)['bowl'].tolist()

        fig_pr1 = px.bar(ph_res[ph_res['bowl'].isin(top10_r)],
                         x='bowl', y='Strict%', color='phase', barmode='group',
                         color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                         title="Strict Comeback% by Phase – Top 10", height=400)
        fig_pr1.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_pr1, use_container_width=True)

        st.divider()
        # Team resilience leaderboard
        st.markdown("### 🏆 Team Resilience Leaderboard")
        st.caption("Which team's bowlers bounce back best after a bad start?")
        team_res = bad.groupby('bowl').agg(
            Bad_Starts=('first3_runs','count'),
            Strict=('Strict','sum'), Good=('Good','sum'), Blown=('Blown','sum'),
            Dot_Pct=('Last3_Dot%','mean'), Boundary_Pct=('Last3_Boundary%','mean')
        ).reset_index()
        # Map bowler to team
        bowl_team_map = dff.groupby('bowl')['team_bowl'].agg(lambda x: x.mode()[0]).to_dict()
        team_res['team'] = team_res['bowl'].astype(str).map(bowl_team_map)
        team_res_grp = team_res.groupby('team').agg(
            Bad_Starts=('Bad_Starts','sum'),
            Strict=('Strict','sum'), Good=('Good','sum'), Blown=('Blown','sum'),
            Dot_Pct=('Dot_Pct','mean'), Boundary_Pct=('Boundary_Pct','mean')
        ).reset_index()
        team_res_grp['Strict%']      = (team_res_grp['Strict']/team_res_grp['Bad_Starts']*100).round(1)
        team_res_grp['Good%']        = (team_res_grp['Good']/team_res_grp['Bad_Starts']*100).round(1)
        team_res_grp['Blown%']       = (team_res_grp['Blown']/team_res_grp['Bad_Starts']*100).round(1)
        team_res_grp['Dot_Pct']      = team_res_grp['Dot_Pct'].round(1)
        team_res_grp['Boundary_Pct'] = team_res_grp['Boundary_Pct'].round(1)
        team_res_grp = team_res_grp.sort_values('Strict%',ascending=False).reset_index(drop=True)
        team_res_grp.index += 1

        tr1,tr2 = st.columns([1.2,1])
        with tr1:
            fig_tr = px.bar(team_res_grp, x='team', y='Strict%',
                            color='Strict%', color_continuous_scale='RdYlGn',
                            text='Strict%', title="Team – Strict Comeback% (Bowlers)", height=400)
            fig_tr.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig_tr, use_container_width=True)
        with tr2:
            st.dataframe(team_res_grp[['team','Bad_Starts','Strict%','Good%','Blown%','Dot_Pct','Boundary_Pct']],
                         use_container_width=True, height=380)

        st.divider()
        # Individual bowler
        st.markdown("### 🔍 Individual Bowler Resilience Profile")
        sel_rb = st.selectbox("Select Bowler", sorted(bad['bowl'].unique()), key='rb')
        rb = bad[bad['bowl']==sel_rb]

        rg1,rg2,rg3,rg4,rg5,rg6 = st.columns(6)
        rg1.metric("Bad Starts", len(rb))
        rg2.metric("Strict Comebacks", int(rb['Strict'].sum()))
        rg3.metric("Strict%", f"{rb['Strict'].mean()*100:.1f}%")
        rg4.metric("Good Comebacks", int(rb['Good'].sum()))
        rg5.metric("Blown It", int(rb['Blown'].sum()))
        rg6.metric("Avg Last 3 Runs", f"{rb['last3_runs'].mean():.1f}")

        ri1,ri2 = st.columns(2)
        with ri1:
            # Tag breakdown pie
            tag_data = pd.DataFrame({
                'Tag':  ['Strict','Good','Blown'],
                'Count':[int(rb['Strict'].sum()), int(rb['Good'].sum()), int(rb['Blown'].sum())]
            })
            fig_ri1 = px.pie(tag_data, names='Tag', values='Count',
                             color='Tag', color_discrete_map={'Strict':'green','Good':'orange','Blown':'red'},
                             title=f"{sel_rb} – Comeback Tag Breakdown", height=360)
            st.plotly_chart(fig_ri1, use_container_width=True)
        with ri2:
            ph_rb = rb.groupby('phase',observed=True).agg(
                Bad=('first3_runs','count'), Strict=('Strict','sum'),
                Good=('Good','sum'), Blown=('Blown','sum')
            ).reset_index()
            ph_rb['Strict%'] = (ph_rb['Strict']/ph_rb['Bad']*100).round(1)
            ph_rb['Blown%']  = (ph_rb['Blown']/ph_rb['Bad']*100).round(1)
            fig_ri2 = px.bar(ph_rb, x='phase', y='Strict%', color='phase', text='Strict%',
                             color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                             title=f"{sel_rb} – Strict Comeback% by Phase", height=360)
            st.plotly_chart(fig_ri2, use_container_width=True)

        ri3,ri4 = st.columns(2)
        with ri3:
            fig_ri3 = px.scatter(rb, x='first3_runs', y='last3_runs',
                                 color=rb.apply(lambda r: 'Strict' if r['Strict'] else ('Good' if r['Good'] else 'Blown'), axis=1),
                                 color_discrete_map={'Strict':'green','Good':'orange','Blown':'red'},
                                 title=f"{sel_rb} – First 3 vs Last 3 Runs", height=360,
                                 labels={'first3_runs':'First 3 Runs','last3_runs':'Last 3 Runs'})
            st.plotly_chart(fig_ri3, use_container_width=True)
        with ri4:
            fig_ri4 = px.histogram(rb, x='last3_runs', nbins=10,
                                   color=rb.apply(lambda r: 'Strict' if r['Strict'] else ('Good' if r['Good'] else 'Blown'), axis=1),
                                   color_discrete_map={'Strict':'green','Good':'orange','Blown':'red'},
                                   title=f"{sel_rb} – Last 3 Ball Runs Distribution", height=360)
            st.plotly_chart(fig_ri4, use_container_width=True)

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
                        'bat':new_bat,'p_match':pm,
                        'balls':len(nbb),'runs':nbb['batruns'].sum(),
                        'fours':int((nbb['score']==4).sum()),'sixes':int((nbb['score']==6).sum()),
                        'out':int(nbb['out'].sum()),'phase':str(nbb.iloc[0]['phase']),
                        # Split into first 6 and 7-12
                        'runs_1_6' :nbb[nbb['ball_seq']<=ws+6]['batruns'].sum(),
                        'balls_1_6':len(nbb[nbb['ball_seq']<=ws+6]),
                        'runs_7_12':nbb[nbb['ball_seq']>ws+6]['batruns'].sum(),
                        'balls_7_12':len(nbb[nbb['ball_seq']>ws+6]),
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
            pw_lb = pw_lb.sort_values('SR',ascending=False).reset_index(drop=True); pw_lb.index += 1

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
            # Team post-wicket leaderboard
            st.markdown("### 🏆 Team Post-Wicket Leaderboard")
            st.caption("Which team's batters score best after a wicket falls?")
            # Need team info — merge from df
            bat_team_map = dff.groupby('bat')['team_bat'].agg(lambda x: x.mode()[0]).to_dict()
            pw['team'] = pw['bat'].astype(str).map(bat_team_map)
            team_pw = pw.groupby('team').agg(
                Times=('runs','count'), Total_Runs=('runs','sum'),
                Total_Balls=('balls','sum'), Fours=('fours','sum'), Sixes=('sixes','sum')
            ).reset_index()
            team_pw['SR']  = (team_pw['Total_Runs']/team_pw['Total_Balls']*100).round(1)
            team_pw = team_pw.sort_values('SR',ascending=False).reset_index(drop=True)
            team_pw.index += 1

            tp1,tp2 = st.columns([1.2,1])
            with tp1:
                fig_tp = px.bar(team_pw, x='team', y='SR',
                                color='SR', color_continuous_scale='RdYlGn',
                                text='SR', title=f"Team SR in First {pw_n} Balls Post-Wicket", height=400)
                fig_tp.update_layout(xaxis_tickangle=-30)
                st.plotly_chart(fig_tp, use_container_width=True)
            with tp2:
                st.dataframe(team_pw[['team','Times','Total_Balls','Total_Runs','SR','Fours','Sixes']],
                             use_container_width=True, height=380)

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
                ph_pw = pw_bat.groupby('phase').agg(Count=('runs','count'), SR=('SR','mean')).reset_index()
                ph_pw['SR'] = ph_pw['SR'].round(1)
                fig_pi1 = px.bar(ph_pw, x='phase', y='SR', color='phase', text='SR',
                                 color_discrete_map={'Powerplay (1–6)':'#636EFA','Middle (7–16)':'#EF553B','Death (17–20)':'#00CC96'},
                                 title=f"{sel_pw} – Post-Wicket SR by Phase", height=320)
                st.plotly_chart(fig_pi1, use_container_width=True)
            with pi2:
                fig_pi2 = px.histogram(pw_bat, x='SR', nbins=10,
                                       title=f"{sel_pw} – Post-Wicket SR Distribution",
                                       color_discrete_sequence=['#636EFA'], height=320)
                st.plotly_chart(fig_pi2, use_container_width=True)

    # ── MC TAB 4: Team Momentum ───────────────────────────────────────────────
    with mc4:
        st.subheader("📊 Team Momentum – Batting vs Bowling Over Analysis")
        st.caption("Classify every over by runs scored/conceded and see which teams dominate")

        # Over-level data including extras (all deliveries per over)
        over_full = df.groupby(['p_match','inns','over','team_bat','team_bowl']).agg(
            over_runs=('score','sum'),
            balls    =('score','count'),
            wickets  =('bowl_wicket','sum')
        ).reset_index()

        # Classification function
        def classify_over(r):
            if r < 7:   return '🔒 Dot Dominant (0-6)'
            if r < 10:  return '💤 Soft Over (7-9)'
            if r < 12:  return '⚡ Impact Over (10-11)'
            if r < 20:  return '🔥 High Capacity (12-19)'
            return '💥 Game Changer (20+)'

        over_full['Classification'] = over_full['over_runs'].apply(classify_over)
        cat_order = ['🔒 Dot Dominant (0-6)','💤 Soft Over (7-9)','⚡ Impact Over (10-11)',
                     '🔥 High Capacity (12-19)','💥 Game Changer (20+)']
        over_full['Classification'] = pd.Categorical(over_full['Classification'],
                                                      categories=cat_order, ordered=True)
        color_map = {
            '🔒 Dot Dominant (0-6)' :'#2ecc71',
            '💤 Soft Over (7-9)'    :'#f1c40f',
            '⚡ Impact Over (10-11)' :'#e67e22',
            '🔥 High Capacity (12-19)':'#e74c3c',
            '💥 Game Changer (20+)'  :'#9b59b6'
        }

        run_thr_tm = st.slider("Threshold – highlight overs above this run total", 0, 36, 10, key='tm_thr')
        st.divider()

        # ── BATTING SIDE ──
        st.markdown("### 🏏 Batting – Which Teams Score Big Overs?")

        bat_overs = over_full.copy()
        bat_overs['Above_Threshold'] = (bat_overs['over_runs'] >= run_thr_tm).astype(int)

        # Team batting classification breakdown
        team_bat_cls = bat_overs.groupby(['team_bat','Classification'], observed=True).agg(
            Count=('over_runs','count')
        ).reset_index()
        team_bat_total = bat_overs.groupby('team_bat').agg(Total_Overs=('over_runs','count')).reset_index()
        team_bat_cls = pd.merge(team_bat_cls, team_bat_total, on='team_bat', how='left')
        team_bat_cls['Freq%'] = (team_bat_cls['Count']/team_bat_cls['Total_Overs']*100).round(1)

        # Above threshold leaderboard
        bat_thr = bat_overs[bat_overs['over_runs'] >= run_thr_tm].groupby('team_bat').agg(
            Above_Count=('over_runs','count'),
            Avg_Runs   =('over_runs','mean'),
            Max_Over   =('over_runs','max')
        ).reset_index()
        bat_thr = pd.merge(bat_thr, team_bat_total, on='team_bat', how='left')
        bat_thr['Freq%'] = (bat_thr['Above_Count']/bat_thr['Total_Overs']*100).round(1)
        bat_thr['Avg_Runs'] = bat_thr['Avg_Runs'].round(1)
        bat_thr = bat_thr.sort_values('Above_Count',ascending=False).reset_index(drop=True)
        bat_thr.index += 1

        cb1,cb2 = st.columns([1.2,1])
        with cb1:
            fig_bt = px.bar(bat_thr, x='team_bat', y='Above_Count',
                            color='Freq%', color_continuous_scale='RdYlGn',
                            text='Above_Count',
                            title=f"Teams with Most {run_thr_tm}+ Run Overs (Batting)", height=380)
            fig_bt.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig_bt, use_container_width=True)
        with cb2:
            st.dataframe(bat_thr[['team_bat','Above_Count','Total_Overs','Freq%','Avg_Runs','Max_Over']],
                         use_container_width=True, height=360)

        # Classification stacked bar — batting
        fig_bc = px.bar(team_bat_cls, x='team_bat', y='Count', color='Classification',
                        color_discrete_map=color_map, barmode='stack',
                        title="Batting – Over Classification Breakdown per Team", height=420)
        fig_bc.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_bc, use_container_width=True)

        # Freq% heatmap batting
        bat_heat = team_bat_cls.pivot_table(index='team_bat', columns='Classification', values='Freq%', fill_value=0)
        fig_bh = px.imshow(bat_heat[cat_order], text_auto=True, color_continuous_scale='RdYlGn',
                           title="Batting – Over Classification Frequency % Heatmap", height=500)
        fig_bh.update_traces(textfont_size=13)
        st.plotly_chart(fig_bh, use_container_width=True)

        st.divider()

        # ── BOWLING SIDE ──
        st.markdown("### 🎳 Bowling – Which Teams Concede Big Overs?")

        bowl_overs = over_full.copy()
        bowl_overs['Above_Threshold'] = (bowl_overs['over_runs'] >= run_thr_tm).astype(int)

        team_bowl_cls = bowl_overs.groupby(['team_bowl','Classification'], observed=True).agg(
            Count=('over_runs','count')
        ).reset_index()
        team_bowl_total = bowl_overs.groupby('team_bowl').agg(Total_Overs=('over_runs','count')).reset_index()
        team_bowl_cls = pd.merge(team_bowl_cls, team_bowl_total, on='team_bowl', how='left')
        team_bowl_cls['Freq%'] = (team_bowl_cls['Count']/team_bowl_cls['Total_Overs']*100).round(1)

        bowl_thr = bowl_overs[bowl_overs['over_runs'] >= run_thr_tm].groupby('team_bowl').agg(
            Above_Count=('over_runs','count'),
            Avg_Runs   =('over_runs','mean'),
            Max_Over   =('over_runs','max')
        ).reset_index()
        bowl_thr = pd.merge(bowl_thr, team_bowl_total, on='team_bowl', how='left')
        bowl_thr['Freq%'] = (bowl_thr['Above_Count']/bowl_thr['Total_Overs']*100).round(1)
        bowl_thr['Avg_Runs'] = bowl_thr['Avg_Runs'].round(1)
        bowl_thr = bowl_thr.sort_values('Above_Count',ascending=False).reset_index(drop=True)
        bowl_thr.index += 1

        cw1,cw2 = st.columns([1.2,1])
        with cw1:
            fig_bwt = px.bar(bowl_thr, x='team_bowl', y='Above_Count',
                             color='Freq%', color_continuous_scale='RdYlGn_r',
                             text='Above_Count',
                             title=f"Teams Conceding Most {run_thr_tm}+ Run Overs (Bowling)", height=380)
            fig_bwt.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig_bwt, use_container_width=True)
        with cw2:
            st.dataframe(bowl_thr[['team_bowl','Above_Count','Total_Overs','Freq%','Avg_Runs','Max_Over']],
                         use_container_width=True, height=360)

        # Classification stacked bar — bowling
        fig_bwc = px.bar(team_bowl_cls, x='team_bowl', y='Count', color='Classification',
                         color_discrete_map=color_map, barmode='stack',
                         title="Bowling – Over Classification Breakdown per Team", height=420)
        fig_bwc.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_bwc, use_container_width=True)

        st.divider()

        # ── INDIVIDUAL BOWLER BREAKDOWN per team ──
        st.markdown("### 🔍 Which Bowler Leaked the Most Big Overs?")
        sel_tm_team = st.selectbox("Select Team (Bowling)", sorted(over_full['team_bowl'].unique()), key='tm_team')

        # Over-level per bowler
        over_bowl = df.groupby(['p_match','inns','over','bowl','team_bowl']).agg(
            over_runs=('score','sum'), balls=('score','count')
        ).reset_index()
        over_bowl['Classification'] = over_bowl['over_runs'].apply(classify_over)

        team_bowl_df = over_bowl[over_bowl['team_bowl']==sel_tm_team]
        bowl_leak = team_bowl_df[team_bowl_df['over_runs'] >= run_thr_tm].groupby('bowl').agg(
            Big_Overs =('over_runs','count'),
            Avg_Runs  =('over_runs','mean'),
            Max_Over  =('over_runs','max')
        ).reset_index()
        bowl_total_ov = team_bowl_df.groupby('bowl').agg(Total_Overs=('over_runs','count')).reset_index()
        bowl_leak = pd.merge(bowl_leak, bowl_total_ov, on='bowl', how='left')
        bowl_leak['Freq%']    = (bowl_leak['Big_Overs']/bowl_leak['Total_Overs']*100).round(1)
        bowl_leak['Avg_Runs'] = bowl_leak['Avg_Runs'].round(1)
        bowl_leak = bowl_leak.sort_values('Big_Overs',ascending=False).reset_index(drop=True)
        bowl_leak.index += 1

        bl1,bl2 = st.columns([1.2,1])
        with bl1:
            fig_bl = px.bar(bowl_leak, x='bowl', y='Big_Overs',
                            color='Freq%', color_continuous_scale='Reds',
                            text='Big_Overs',
                            title=f"{sel_tm_team} – Bowler Big Over Leakage ({run_thr_tm}+)", height=400)
            fig_bl.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_bl, use_container_width=True)
        with bl2:
            st.dataframe(bowl_leak[['bowl','Big_Overs','Total_Overs','Freq%','Avg_Runs','Max_Over']],
                         use_container_width=True, height=380)

        # Classification breakdown per bowler in selected team
        bowl_cls = team_bowl_df.groupby(['bowl','Classification'], observed=True).agg(
            Count=('over_runs','count')).reset_index()
        fig_bcls = px.bar(bowl_cls, x='bowl', y='Count', color='Classification',
                          color_discrete_map=color_map, barmode='stack',
                          title=f"{sel_tm_team} – Bowler Over Classification Breakdown", height=420)
        fig_bcls.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_bcls, use_container_width=True)

        st.divider()

        # ── BATTING vs BOWLING COMPARISON per team ──
        st.markdown("### ⚔️ Batting vs Bowling – Who Dominates? Who Leaks?")
        compare = pd.merge(
            bat_thr[['team_bat','Above_Count','Freq%']].rename(columns={'team_bat':'team','Above_Count':'Bat_Big_Overs','Freq%':'Bat_Freq%'}),
            bowl_thr[['team_bowl','Above_Count','Freq%']].rename(columns={'team_bowl':'team','Above_Count':'Bowl_Big_Overs','Freq%':'Bowl_Freq%'}),
            on='team', how='outer'
        ).fillna(0)
        compare['Net'] = compare['Bat_Big_Overs'] - compare['Bowl_Big_Overs']
        compare = compare.sort_values('Net',ascending=False).reset_index(drop=True)
        compare.index += 1

        cmp1,cmp2 = st.columns([1.2,1])
        with cmp1:
            fig_cmp = px.bar(compare, x='team', y=['Bat_Big_Overs','Bowl_Big_Overs'],
                             barmode='group',
                             color_discrete_map={'Bat_Big_Overs':'#2ecc71','Bowl_Big_Overs':'#e74c3c'},
                             title=f"Batting vs Bowling Big Overs ({run_thr_tm}+) per Team", height=420)
            fig_cmp.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig_cmp, use_container_width=True)
        with cmp2:
            st.markdown("**Net = Batting Big Overs − Bowling Big Overs (positive = team dominates)**")
            st.dataframe(compare[['team','Bat_Big_Overs','Bat_Freq%','Bowl_Big_Overs','Bowl_Freq%','Net']],
                         use_container_width=True, height=400)

# ── Raw Data ──────────────────────────────────────────────────────────────────
with st.expander("📋 Raw Data"):
    cols_s = ['year','bat','team_bat','bowl','team_bowl','over','phase','score','batruns','out',
              'shot_label','line_label','length_label','bowl_kind','bowl_style_label','bat_hand','wagonZone','control','is_dot']
    st.dataframe(dff[cols_s].reset_index(drop=True), use_container_width=True)
    csv = dff[cols_s].to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download CSV", csv, "ipl_2023_2025_filtered.csv", "text/csv")
