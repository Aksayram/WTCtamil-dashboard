import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ── Password ───────────────────────────────────────────────────────────────────
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

st.set_page_config(page_title="Pace Analytics Dashboard", layout="wide", page_icon="🏏")

# ── Load & clean ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, usecols=range(13))
    df.columns = df.columns.str.strip()
    df['Bowler']       = df['Bowler'].str.strip().str.title()
    df['Batter']       = df['Batter'].str.strip().str.title()
    df['Ground']       = df['Ground'].str.strip().str.title()
    df['Type']         = df['Type'].str.strip().str.title().replace({'Spin':'Spinner'}).fillna('Unknown')
    df['Bowling Hand'] = df['Bowling Hand'].str.strip().str.title().replace({
        'Right Hand':'Right Arm','Left Hand':'Left Arm',
        'Right-Arm':'Right Arm','Left-Arm':'Left Arm'
    }).fillna('Unknown')
    df['Bowling Side'] = df['Bowling Side'].str.strip().str.title().fillna('Unknown')
    df['Speed']     = pd.to_numeric(df['Speed'],     errors='coerce')
    df['Run']       = pd.to_numeric(df['Run'],       errors='coerce').fillna(0)
    df['Dismissed'] = pd.to_numeric(df['Dismissed'], errors='coerce').fillna(0)
    df['Over']      = pd.to_numeric(df['Over'],      errors='coerce')
    df = df.dropna(subset=['Speed','Bowler'])

    def phase(o):
        if o <= 6:  return 'Powerplay (1-6)'
        if o <= 16: return 'Middle (7-16)'
        return 'Death (17-20)'
    df['Phase'] = df['Over'].apply(phase)
    df['Phase'] = pd.Categorical(df['Phase'],
                    categories=['Powerplay (1-6)','Middle (7-16)','Death (17-20)'], ordered=True)

    speed_min = int(df['Speed'].min() // 5) * 5
    speed_max = int(df['Speed'].max() // 5 + 1) * 5
    bins   = list(range(speed_min, speed_max + 5, 5))
    labels = [f"{b}-{b+4}" for b in bins[:-1]]
    df['Speed Bucket'] = pd.cut(df['Speed'], bins=bins, labels=labels, right=False)
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

def economy(runs, balls):
    return round(runs / (balls / 6), 2) if balls > 0 else 0.0

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🏏 Pace Filters")
bowler_type  = st.sidebar.multiselect("Bowler Type", sorted(df['Type'].unique()), default=sorted(df['Type'].unique()))
bowling_hand = st.sidebar.multiselect("Bowling Arm", sorted(df['Bowling Hand'].unique()), default=sorted(df['Bowling Hand'].unique()))
bowling_side = st.sidebar.multiselect("Bowling Side", sorted(df['Bowling Side'].unique()), default=sorted(df['Bowling Side'].unique()))
sel_ground   = st.sidebar.multiselect("Ground", sorted(df['Ground'].unique()), default=sorted(df['Ground'].unique()))

filt = (
    df['Type'].isin(bowler_type) &
    df['Bowling Hand'].isin(bowling_hand) &
    df['Bowling Side'].isin(bowling_side) &
    df['Ground'].isin(sel_ground)
)
dff = df[filt]

st.title("🏏 Pace Analytics Dashboard")
st.caption(f"**{len(dff):,}** deliveries  |  **{dff['Bowler'].nunique()}** bowlers  |  Speed: {dff['Speed'].min():.1f} – {dff['Speed'].max():.1f} km/h")

if dff.empty:
    st.warning("No data matches current filters.")
    st.stop()

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Total Deliveries", f"{len(dff):,}")
k2.metric("Avg Speed", f"{dff['Speed'].mean():.1f} km/h")
k3.metric("Max Speed", f"{dff['Speed'].max():.1f} km/h")
k4.metric("Total Wickets", int(dff['Dismissed'].sum()))
k5.metric("Overall Economy", f"{economy(dff['Run'].sum(), len(dff)):.2f}")
st.divider()

tab1, tab2, tab3 = st.tabs([
    "⚡ Pace Effectiveness Index",
    "🔍 Bowler Deep Dive",
    "🎯 Speed Dynamics & Variation"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Pace Effectiveness Index
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("⚡ Pace Effectiveness Index")
    st.caption("Select a speed range and find which bowlers are most effective at that pace")

    all_buckets = [str(b) for b in dff['Speed Bucket'].cat.categories]
    speed_range = st.select_slider("Select Speed Range (km/h)", options=all_buckets,
                                    value=(all_buckets[0], all_buckets[-1]))
    start_idx = all_buckets.index(speed_range[0])
    end_idx   = all_buckets.index(speed_range[1])
    selected_buckets = all_buckets[start_idx:end_idx + 1]
    pace_df = dff[dff['Speed Bucket'].astype(str).isin(selected_buckets)]
    min_balls = st.slider("Minimum balls bowled", 5, 50, 10)

    if pace_df.empty:
        st.warning("No data in this speed range.")
    else:
        st.markdown(f"**{len(pace_df):,} deliveries** in **{speed_range[0]} – {speed_range[1]} km/h**")
        st.divider()

        bowl_grp = pace_df.groupby('Bowler').agg(
            Balls=('Run','count'), Runs=('Run','sum'), Wickets=('Dismissed','sum'),
            Avg_Speed=('Speed','mean'), Max_Speed=('Speed','max')
        ).reset_index()
        bowl_grp = bowl_grp[bowl_grp['Balls'] >= min_balls]
        bowl_grp['Economy']   = (bowl_grp['Runs']/(bowl_grp['Balls']/6)).round(2)
        bowl_grp['Avg']       = (bowl_grp['Runs']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)
        bowl_grp['SR']        = (bowl_grp['Balls']/bowl_grp['Wickets'].replace(0,np.nan)).round(1)
        bowl_grp['Avg_Speed'] = bowl_grp['Avg_Speed'].round(1)
        dots = pace_df.groupby('Bowler').apply(lambda x: (x['Run']==0).sum()).reset_index()
        dots.columns = ['Bowler','Dots']
        bowl_grp = pd.merge(bowl_grp, dots, on='Bowler', how='left')
        bowl_grp['Dot%'] = (bowl_grp['Dots']/bowl_grp['Balls']*100).round(1)
        # PEI = (Wickets per over) / Economy
        bowl_grp['PEI'] = ((bowl_grp['Wickets']/bowl_grp['Balls']*6) /
                            bowl_grp['Economy'].replace(0,np.nan)).round(3)
        bowl_grp = bowl_grp.sort_values('PEI', ascending=False).reset_index(drop=True)
        bowl_grp.index += 1

        metric_sel = st.radio("Rank by", ['PEI','Economy','Wickets','Dot%','SR'],
                               horizontal=True, key='pei_m')
        asc = metric_sel in ['Economy','SR']

        c1,c2 = st.columns([1.2,1])
        with c1:
            top15 = bowl_grp.nsmallest(15,metric_sel) if asc else bowl_grp.nlargest(15,metric_sel)
            fig = px.bar(top15, x='Bowler', y=metric_sel,
                         color=metric_sel,
                         color_continuous_scale='RdYlGn_r' if asc else 'RdYlGn',
                         text=metric_sel,
                         title=f"Top 15 – {metric_sel} at {speed_range[0]}–{speed_range[1]} km/h",
                         height=420)
            fig.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("**Full Leaderboard**")
            st.dataframe(bowl_grp[['Bowler','Balls','Runs','Economy','Wickets','SR','Dot%','Avg_Speed','PEI']],
                         use_container_width=True, height=400)

        st.divider()
        st.markdown("### 📊 Economy vs Wickets")
        fig2 = px.scatter(bowl_grp, x='Economy', y='Wickets',
                          size='Balls', text='Bowler', color='PEI',
                          color_continuous_scale='RdYlGn',
                          title="Economy vs Wickets (size=balls, color=PEI)", height=450)
        fig2.update_traces(textposition='top center', textfont_size=9)
        st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        st.markdown("### 📈 Speed Bucket Distribution")
        bkt_all = dff.groupby(['Bowler','Speed Bucket'], observed=True).agg(
            Balls=('Run','count'), Runs=('Run','sum'), Wickets=('Dismissed','sum')
        ).reset_index()
        bkt_all['Economy'] = (bkt_all['Runs']/(bkt_all['Balls']/6)).round(2)
        bkt_all['Speed Bucket'] = bkt_all['Speed Bucket'].astype(str)
        top10 = bowl_grp.head(10)['Bowler'].tolist()
        fig3 = px.bar(bkt_all[bkt_all['Bowler'].isin(top10)],
                      x='Speed Bucket', y='Balls', color='Bowler', barmode='group',
                      title="Balls per Speed Bucket – Top 10 Bowlers", height=420)
        fig3.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Bowler Deep Dive
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("🔍 Bowler Deep Dive")
    sel_bowl = st.selectbox("Select Bowler", sorted(dff['Bowler'].unique()))
    bdf = dff[dff['Bowler']==sel_bowl]

    b1,b2,b3,b4,b5,b6 = st.columns(6)
    b1.metric("Balls", len(bdf))
    b2.metric("Runs", int(bdf['Run'].sum()))
    b3.metric("Wickets", int(bdf['Dismissed'].sum()))
    b4.metric("Economy", f"{economy(bdf['Run'].sum(), len(bdf)):.2f}")
    b5.metric("Avg Speed", f"{bdf['Speed'].mean():.1f} km/h")
    b6.metric("Top Speed", f"{bdf['Speed'].max():.1f} km/h")
    st.divider()

    # Speed Bucket Analysis
    st.markdown("#### 📊 Performance by Speed Bucket")
    bkt = bdf.groupby('Speed Bucket', observed=True).agg(
        Balls=('Run','count'), Runs=('Run','sum'), Wickets=('Dismissed','sum')
    ).reset_index()
    bkt['Economy'] = (bkt['Runs']/(bkt['Balls']/6)).round(2)
    bkt['SR']      = (bkt['Balls']/bkt['Wickets'].replace(0,np.nan)).round(1)
    bkt['Balls%']  = (bkt['Balls']/bkt['Balls'].sum()*100).round(1)
    bkt['Speed Bucket'] = bkt['Speed Bucket'].astype(str)

    c1,c2,c3 = st.columns(3)
    with c1:
        fig = px.bar(bkt, x='Speed Bucket', y='Balls', color='Balls%',
                     color_continuous_scale='Blues', text='Balls',
                     title=f"{sel_bowl} – Balls per Speed Bucket", height=350)
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.bar(bkt, x='Speed Bucket', y='Economy', color='Economy',
                      color_continuous_scale='RdYlGn_r', text='Economy',
                      title=f"{sel_bowl} – Economy by Speed Bucket", height=350)
        fig2.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig2, use_container_width=True)
    with c3:
        fig3 = px.bar(bkt, x='Speed Bucket', y='Wickets', color='Wickets',
                      color_continuous_scale='Reds', text='Wickets',
                      title=f"{sel_bowl} – Wickets by Speed Bucket", height=350)
        fig3.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(bkt[['Speed Bucket','Balls','Balls%','Runs','Economy','Wickets','SR']],
                 use_container_width=True)

    st.divider()

    # Killer Zone
    st.markdown("#### 🎯 Killer Zone")
    if bkt['Wickets'].sum() > 0:
        killer = bkt.loc[bkt['Wickets'].idxmax()]
        st.success(f"**{sel_bowl}'s Killer Zone: {killer['Speed Bucket']} km/h** — "
                   f"{int(killer['Wickets'])} wickets at Economy {killer['Economy']}")
        bkt['Is_Killer'] = bkt['Speed Bucket'] == killer['Speed Bucket']
        fig_k = px.bar(bkt, x='Speed Bucket', y='Wickets',
                       color='Is_Killer',
                       color_discrete_map={True:'#e74c3c', False:'#95a5a6'},
                       title=f"{sel_bowl} – Killer Zone (red)", height=350, text='Wickets')
        fig_k.update_layout(xaxis_tickangle=-30, showlegend=False)
        st.plotly_chart(fig_k, use_container_width=True)
    else:
        st.info("No wickets recorded yet.")

    st.divider()

    # Phase-wise
    st.markdown("#### 📅 Speed by Phase")
    ph = bdf.groupby('Phase', observed=True).agg(
        Balls=('Run','count'), Runs=('Run','sum'), Wickets=('Dismissed','sum'),
        Avg_Speed=('Speed','mean'), Max_Speed=('Speed','max')
    ).reset_index()
    ph['Economy']   = (ph['Runs']/(ph['Balls']/6)).round(2)
    ph['Avg_Speed'] = ph['Avg_Speed'].round(1)
    ph['Max_Speed'] = ph['Max_Speed'].round(1)

    cp1,cp2 = st.columns(2)
    with cp1:
        fig_p1 = px.bar(ph, x='Phase', y='Avg_Speed', color='Phase', text='Avg_Speed',
                        color_discrete_map={'Powerplay (1-6)':'#636EFA',
                                            'Middle (7-16)':'#EF553B',
                                            'Death (17-20)':'#00CC96'},
                        title=f"{sel_bowl} – Avg Speed by Phase", height=350)
        st.plotly_chart(fig_p1, use_container_width=True)
    with cp2:
        fig_p2 = px.bar(ph, x='Phase', y='Economy', color='Phase', text='Economy',
                        color_discrete_map={'Powerplay (1-6)':'#636EFA',
                                            'Middle (7-16)':'#EF553B',
                                            'Death (17-20)':'#00CC96'},
                        title=f"{sel_bowl} – Economy by Phase", height=350)
        st.plotly_chart(fig_p2, use_container_width=True)

    st.dataframe(ph[['Phase','Balls','Avg_Speed','Max_Speed','Economy','Wickets']],
                 use_container_width=True)

    st.divider()

    # Over vs Around
    st.markdown("#### 🏏 Over vs Around the Wicket")
    side = bdf.groupby('Bowling Side').agg(
        Balls=('Run','count'), Runs=('Run','sum'), Wickets=('Dismissed','sum'),
        Avg_Speed=('Speed','mean')
    ).reset_index()
    side['Economy']   = (side['Runs']/(side['Balls']/6)).round(2)
    side['Avg_Speed'] = side['Avg_Speed'].round(1)

    cs1,cs2,cs3 = st.columns(3)
    with cs1:
        fig_s1 = px.bar(side, x='Bowling Side', y='Economy', color='Bowling Side',
                        text='Economy', title=f"{sel_bowl} – Economy", height=300)
        st.plotly_chart(fig_s1, use_container_width=True)
    with cs2:
        fig_s2 = px.bar(side, x='Bowling Side', y='Wickets', color='Bowling Side',
                        text='Wickets', title=f"{sel_bowl} – Wickets", height=300)
        st.plotly_chart(fig_s2, use_container_width=True)
    with cs3:
        fig_s3 = px.bar(side, x='Bowling Side', y='Avg_Speed', color='Bowling Side',
                        text='Avg_Speed', title=f"{sel_bowl} – Avg Speed", height=300)
        st.plotly_chart(fig_s3, use_container_width=True)

    st.divider()

    # Speed distribution
    st.markdown("#### 📈 Speed Distribution")
    fig_dist = px.histogram(bdf, x='Speed', nbins=20,
                            color_discrete_sequence=['#636EFA'],
                            title=f"{sel_bowl} – Speed Distribution", height=350)
    fig_dist.add_vline(x=bdf['Speed'].mean(), line_dash='dash', line_color='orange',
                       annotation_text=f"Avg: {bdf['Speed'].mean():.1f}")
    fig_dist.add_vline(x=bdf['Speed'].max(), line_dash='dash', line_color='red',
                       annotation_text=f"Max: {bdf['Speed'].max():.1f}")
    st.plotly_chart(fig_dist, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Speed Dynamics & Variation
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("🎯 Speed Dynamics & Variation Analysis")
    st.caption("Speed Dynamic Score — higher = more unpredictable = better T20 bowler")
    st.divider()

    min_balls_dyn = st.slider("Minimum balls", 5, 50, 15, key='dyn_min')

    dyn_data = []
    for bowl in dff['Bowler'].unique():
        bdf_d = dff[dff['Bowler']==bowl]
        if len(bdf_d) < min_balls_dyn:
            continue
        avg   = bdf_d['Speed'].mean()
        std   = bdf_d['Speed'].std()
        rng   = bdf_d['Speed'].max() - bdf_d['Speed'].min()
        balls = len(bdf_d)
        runs  = bdf_d['Run'].sum()
        wkts  = bdf_d['Dismissed'].sum()
        econ  = economy(runs, balls)
        sds   = round((std * rng) / avg * 10, 2) if avg > 0 else 0
        thresh    = avg - 1.5 * std
        normal    = bdf_d[bdf_d['Speed'] >= thresh]
        variation = bdf_d[bdf_d['Speed'] < thresh]

        dyn_data.append({
            'Bowler'         : bowl,
            'Balls'          : balls,
            'Avg_Speed'      : round(avg, 1),
            'Max_Speed'      : round(bdf_d['Speed'].max(), 1),
            'Min_Speed'      : round(bdf_d['Speed'].min(), 1),
            'Speed_Range'    : round(rng, 1),
            'Std_Dev'        : round(std, 2),
            'SDS'            : sds,
            'Economy'        : econ,
            'Wickets'        : int(wkts),
            'Normal_Balls'   : len(normal),
            'Variation_Balls': len(variation),
            'Variation%'     : round(len(variation)/balls*100, 1),
            'Normal_Econ'    : economy(normal['Run'].sum(), len(normal)),
            'Variation_Econ' : economy(variation['Run'].sum(), len(variation)) if len(variation) > 0 else None,
            'Normal_Wkts'    : int(normal['Dismissed'].sum()),
            'Variation_Wkts' : int(variation['Dismissed'].sum()),
            'Threshold'      : round(thresh, 1)
        })

    dyn_df = pd.DataFrame(dyn_data).sort_values('SDS', ascending=False).reset_index(drop=True)
    dyn_df.index += 1

    # SDS Leaderboard
    st.markdown("### 🏆 Speed Dynamic Score Leaderboard")
    cd1,cd2 = st.columns([1.2,1])
    with cd1:
        fig_sds = px.bar(dyn_df.head(15), x='Bowler', y='SDS',
                         color='SDS', color_continuous_scale='RdYlGn',
                         text='SDS',
                         title="Top 15 – Speed Dynamic Score", height=420)
        fig_sds.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_sds, use_container_width=True)
    with cd2:
        st.dataframe(dyn_df[['Bowler','Balls','Avg_Speed','Max_Speed','Min_Speed',
                              'Speed_Range','Std_Dev','SDS','Economy','Wickets']],
                     use_container_width=True, height=400)

    st.divider()

    # Variation leaderboard
    st.markdown("### 🔄 Variation Ball Analysis")
    st.caption("Variation = delivery significantly slower than bowler's own average (1.5 std below their mean)")
    var_df = dyn_df[dyn_df['Variation_Balls'] > 0].copy()

    if var_df.empty:
        st.info("No variation balls detected with current filters.")
    else:
        cv1,cv2 = st.columns(2)
        with cv1:
            fig_var = px.bar(var_df.sort_values('Variation%',ascending=False).head(15),
                             x='Bowler', y='Variation%',
                             color='Variation%', color_continuous_scale='Oranges',
                             text='Variation%',
                             title="Variation Ball % per Bowler", height=400)
            fig_var.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_var, use_container_width=True)
        with cv2:
            var_compare = var_df[['Bowler','Normal_Econ','Variation_Econ']].dropna()
            var_melt = var_compare.melt(id_vars='Bowler',
                                        value_vars=['Normal_Econ','Variation_Econ'],
                                        var_name='Type', value_name='Economy')
            var_melt['Type'] = var_melt['Type'].map({
                'Normal_Econ':'Normal Delivery',
                'Variation_Econ':'Variation Ball'
            })
            fig_ve = px.bar(var_melt, x='Bowler', y='Economy', color='Type', barmode='group',
                            color_discrete_map={'Normal Delivery':'#636EFA',
                                                'Variation Ball':'#EF553B'},
                            title="Economy: Normal vs Variation Ball", height=400)
            fig_ve.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig_ve, use_container_width=True)

        st.dataframe(var_df[['Bowler','Balls','Avg_Speed','Threshold',
                              'Normal_Balls','Variation_Balls','Variation%',
                              'Normal_Econ','Variation_Econ',
                              'Normal_Wkts','Variation_Wkts']],
                     use_container_width=True)

    st.divider()

    # Individual dynamics
    st.markdown("### 🔍 Individual Bowler Speed Dynamics")
    sel_dyn = st.selectbox("Select Bowler", sorted(dff['Bowler'].unique()), key='dyn_bowl')
    bdf_dyn = dff[dff['Bowler']==sel_dyn].copy()

    avg_d  = bdf_dyn['Speed'].mean()
    std_d  = bdf_dyn['Speed'].std()
    rng_d  = bdf_dyn['Speed'].max() - bdf_dyn['Speed'].min()
    sds_v  = round((std_d * rng_d) / avg_d * 10, 2) if avg_d > 0 else 0
    thresh = avg_d - 1.5 * std_d
    normal    = bdf_dyn[bdf_dyn['Speed'] >= thresh]
    variation = bdf_dyn[bdf_dyn['Speed'] < thresh]

    dg1,dg2,dg3,dg4,dg5 = st.columns(5)
    dg1.metric("Speed Dynamic Score", f"{sds_v}")
    dg2.metric("Avg Speed", f"{avg_d:.1f} km/h")
    dg3.metric("Speed Range", f"{rng_d:.1f} km/h")
    dg4.metric("Normal Balls", f"{len(normal)} ({len(normal)/len(bdf_dyn)*100:.0f}%)")
    dg5.metric("Variation Balls", f"{len(variation)} ({len(variation)/len(bdf_dyn)*100:.0f}%)")

    bdf_dyn['Delivery Type'] = np.where(bdf_dyn['Speed'] < thresh, 'Variation Ball', 'Normal Delivery')
    bdf_dyn['Ball No'] = range(1, len(bdf_dyn)+1)

    di1,di2 = st.columns(2)
    with di1:
        fig_bb = px.scatter(bdf_dyn, x='Ball No', y='Speed',
                            color='Delivery Type',
                            color_discrete_map={'Normal Delivery':'#636EFA',
                                                'Variation Ball':'#e74c3c'},
                            title=f"{sel_dyn} – Ball by Ball Speed (red=variation)",
                            height=380)
        fig_bb.add_hline(y=avg_d, line_dash='dash', line_color='orange',
                         annotation_text=f"Avg: {avg_d:.1f}")
        fig_bb.add_hline(y=thresh, line_dash='dot', line_color='red',
                         annotation_text=f"Threshold: {thresh:.1f}")
        st.plotly_chart(fig_bb, use_container_width=True)
    with di2:
        fig_hist = px.histogram(bdf_dyn, x='Speed', color='Delivery Type', nbins=20,
                                color_discrete_map={'Normal Delivery':'#636EFA',
                                                    'Variation Ball':'#e74c3c'},
                                title=f"{sel_dyn} – Speed Distribution",
                                height=380)
        st.plotly_chart(fig_hist, use_container_width=True)

    if len(variation) > 0:
        st.markdown(f"**{sel_dyn} – Normal vs Variation Comparison**")
        comp = pd.DataFrame({
            'Type'     : ['Normal Delivery','Variation Ball'],
            'Balls'    : [len(normal), len(variation)],
            'Pct%'     : [round(len(normal)/len(bdf_dyn)*100,1), round(len(variation)/len(bdf_dyn)*100,1)],
            'Avg Speed': [round(normal['Speed'].mean(),1), round(variation['Speed'].mean(),1)],
            'Runs'     : [int(normal['Run'].sum()), int(variation['Run'].sum())],
            'Economy'  : [economy(normal['Run'].sum(), len(normal)),
                          economy(variation['Run'].sum(), len(variation))],
            'Wickets'  : [int(normal['Dismissed'].sum()), int(variation['Dismissed'].sum())]
        })
        st.dataframe(comp, use_container_width=True)
    else:
        st.info(f"No variation balls for {sel_dyn} — all deliveries within their normal pace range.")

    st.divider()

    # Phase dynamics
    st.markdown(f"#### 📅 {sel_dyn} – Speed Dynamics by Phase")
    ph_dyn = bdf_dyn.groupby('Phase', observed=True).agg(
        Balls=('Run','count'), Avg_Speed=('Speed','mean'),
        Max_Speed=('Speed','max'), Std_Dev=('Speed','std'),
        Runs=('Run','sum'), Wickets=('Dismissed','sum')
    ).reset_index()
    ph_dyn['Economy']   = (ph_dyn['Runs']/(ph_dyn['Balls']/6)).round(2)
    ph_dyn['Avg_Speed'] = ph_dyn['Avg_Speed'].round(1)
    ph_dyn['Max_Speed'] = ph_dyn['Max_Speed'].round(1)
    ph_dyn['Std_Dev']   = ph_dyn['Std_Dev'].round(2)

    dp1,dp2 = st.columns(2)
    with dp1:
        fig_phd1 = px.bar(ph_dyn, x='Phase', y='Avg_Speed', color='Phase', text='Avg_Speed',
                          color_discrete_map={'Powerplay (1-6)':'#636EFA',
                                              'Middle (7-16)':'#EF553B',
                                              'Death (17-20)':'#00CC96'},
                          title=f"{sel_dyn} – Avg Speed by Phase", height=320)
        st.plotly_chart(fig_phd1, use_container_width=True)
    with dp2:
        fig_phd2 = px.bar(ph_dyn, x='Phase', y='Std_Dev', color='Phase', text='Std_Dev',
                          color_discrete_map={'Powerplay (1-6)':'#636EFA',
                                              'Middle (7-16)':'#EF553B',
                                              'Death (17-20)':'#00CC96'},
                          title=f"{sel_dyn} – Speed Variation (Std Dev) by Phase", height=320)
        st.plotly_chart(fig_phd2, use_container_width=True)

    st.dataframe(ph_dyn[['Phase','Balls','Avg_Speed','Max_Speed','Std_Dev','Economy','Wickets']],
                 use_container_width=True)
