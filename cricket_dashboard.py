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

st.set_page_config(page_title="Cricket Analytics Dashboard", layout="wide", page_icon="🏏")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e1e2e;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ── Load & clean data ──────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, usecols=range(13))
    df.columns = df.columns.str.strip()

    # Normalize text columns
    df['Bowler'] = df['Bowler'].str.strip().str.title()
    df['Batter'] = df['Batter'].str.strip().str.title()
    df['Ground'] = df['Ground'].str.strip().str.title()
    df['Type'] = df['Type'].str.strip().str.title().replace({'Spin': 'Spinner'})
    df['Bowling Hand'] = df['Bowling Hand'].str.strip().str.title()
    df['Bowling Hand'] = df['Bowling Hand'].replace({
        'Right Hand': 'Right Arm', 'Left Hand': 'Left Arm',
        'Right-Arm': 'Right Arm', 'Left-Arm': 'Left Arm'
    })
    df['Pitching Length'] = df['Pitching Length'].str.strip().str.title()
    df['Pitching Line']   = df['Pitching Line'].str.strip().str.title()
    df['Bowling Side'] = df['Bowling Side'].str.strip().str.title()

    # Numeric
    df['Speed']     = pd.to_numeric(df['Speed'], errors='coerce')
    df['Run']       = pd.to_numeric(df['Run'], errors='coerce').fillna(0)
    df['Dismissed'] = pd.to_numeric(df['Dismissed'], errors='coerce').fillna(0)

    df = df.dropna(subset=['Speed', 'Bowler'])

    # Speed buckets (5 km/h)
    speed_min = int(df['Speed'].min() // 5) * 5
    speed_max = int(df['Speed'].max() // 5 + 1) * 5
    bins  = list(range(speed_min, speed_max + 5, 5))
    labels = [f"{b}–{b+4}" for b in bins[:-1]]
    df['Speed Bucket'] = pd.cut(df['Speed'], bins=bins, labels=labels, right=False)

    return df


FILE = "ipl_data.xlsx"   # <-- update path if needed
try:
    df = load_data(FILE)
except FileNotFoundError:
    uploaded = st.file_uploader("Upload ipl_data.xlsx", type=["xlsx"])
    if uploaded:
        df = load_data(uploaded)
    else:
        st.info("Please upload your ipl_data.xlsx file to get started.")
        st.stop()

# ── Sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.title("🏏 Filters")

bowler_type = st.sidebar.multiselect(
    "Bowler Type", options=sorted(df['Type'].dropna().unique()),
    default=sorted(df['Type'].dropna().unique())
)
bowling_hand = st.sidebar.multiselect(
    "Bowling Arm", options=sorted(df['Bowling Hand'].dropna().unique()),
    default=sorted(df['Bowling Hand'].dropna().unique())
)
bowling_side = st.sidebar.multiselect(
    "Bowling Side (Over / Around)", options=sorted(df['Bowling Side'].dropna().unique()),
    default=sorted(df['Bowling Side'].dropna().unique())
)

all_buckets = [str(b) for b in df['Speed Bucket'].cat.categories]
speed_range = st.sidebar.select_slider(
    "Speed Bucket Range",
    options=all_buckets,
    value=(all_buckets[0], all_buckets[-1])
)
start_idx = all_buckets.index(speed_range[0])
end_idx   = all_buckets.index(speed_range[1])
selected_buckets = all_buckets[start_idx:end_idx + 1]

length_opts = sorted(df['Pitching Length'].dropna().unique())
sel_length = st.sidebar.multiselect("Pitching Length", options=length_opts, default=length_opts)

line_opts = sorted(df['Pitching Line'].dropna().unique())
sel_line = st.sidebar.multiselect("Pitching Line", options=line_opts, default=line_opts)

ground_opts = sorted(df['Ground'].dropna().unique())
sel_ground = st.sidebar.multiselect("Ground", options=ground_opts, default=ground_opts)

# ── Apply filters ──────────────────────────────────────────────────────────────
filt = (
    df['Type'].isin(bowler_type) &
    df['Bowling Hand'].isin(bowling_hand) &
    df['Bowling Side'].isin(bowling_side) &
    df['Speed Bucket'].astype(str).isin(selected_buckets) &
    df['Pitching Length'].isin(sel_length) &
    df['Pitching Line'].isin(sel_line) &
    df['Ground'].isin(sel_ground)
)
dff = df[filt]

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🏏 Cricket Pace & Analytics Dashboard")
st.caption(f"Showing **{len(dff):,}** deliveries after filters  |  Speed buckets: 5 km/h intervals")

if dff.empty:
    st.warning("No data matches the current filters. Please adjust the sidebar.")
    st.stop()

# ── KPI cards ──────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Deliveries", f"{len(dff):,}")
k2.metric("Unique Bowlers", dff['Bowler'].nunique())
k3.metric("Avg Speed (km/h)", f"{dff['Speed'].mean():.1f}")
k4.metric("Total Wickets", int(dff['Dismissed'].sum()))
overall_econ = (dff['Run'].sum() / (len(dff) / 6)) if len(dff) > 0 else 0
k5.metric("Avg Economy", f"{overall_econ:.2f}")

st.divider()

# ── Tab layout ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Bowler Efficiency by Speed Bucket",
    "📏 Length & Line Analysis",
    "🏹 Bowler Deep Dive",
    "📋 Raw Data"
])

# ── TAB 1: Bowler efficiency by speed bucket ───────────────────────────────────
with tab1:
    st.subheader("Bowler Efficiency Across Speed Buckets")

    # Aggregate per bowler per bucket
    grp = (
        dff.groupby(['Bowler', 'Speed Bucket'], observed=True)
        .agg(Balls=('Run', 'count'), Runs=('Run', 'sum'), Wickets=('Dismissed', 'sum'))
        .reset_index()
    )
    grp['Economy']   = (grp['Runs'] / (grp['Balls'] / 6)).round(2)
    grp['SR']        = (grp['Balls'] / grp['Wickets'].replace(0, np.nan)).round(1)
    grp['Speed Bucket'] = grp['Speed Bucket'].astype(str)

    min_balls = st.slider("Minimum balls bowled (filter noise)", 5, 50, 10)
    grp_f = grp[grp['Balls'] >= min_balls]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Economy Rate by Speed Bucket (bubble = balls bowled)**")
        fig = px.scatter(
            grp_f, x='Speed Bucket', y='Economy',
            size='Balls', color='Bowler', hover_data=['Wickets', 'Balls', 'SR'],
            title="Economy Rate per Speed Bucket",
            height=450
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Wickets taken per Speed Bucket**")
        wkt_grp = grp_f.groupby('Speed Bucket')[['Wickets', 'Balls']].sum().reset_index()
        wkt_grp['WicketRate'] = (wkt_grp['Wickets'] / wkt_grp['Balls'] * 100).round(2)
        fig2 = px.bar(
            wkt_grp, x='Speed Bucket', y='Wickets',
            text='Wickets', color='WicketRate',
            color_continuous_scale='RdYlGn_r',
            title="Total Wickets by Speed Bucket",
            height=450
        )
        fig2.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)

    # Summary table
    st.markdown("**Bowler Summary Table (filtered)**")
    bowler_summary = (
        dff.groupby('Bowler')
        .agg(Balls=('Run', 'count'), Runs=('Run', 'sum'), Wickets=('Dismissed', 'sum'),
             AvgSpeed=('Speed', 'mean'), MaxSpeed=('Speed', 'max'))
        .reset_index()
    )
    bowler_summary['Economy'] = (bowler_summary['Runs'] / (bowler_summary['Balls'] / 6)).round(2)
    bowler_summary['Strike Rate'] = (bowler_summary['Balls'] / bowler_summary['Wickets'].replace(0, np.nan)).round(1)
    bowler_summary['AvgSpeed'] = bowler_summary['AvgSpeed'].round(1)
    bowler_summary['MaxSpeed'] = bowler_summary['MaxSpeed'].round(1)
    bowler_summary = bowler_summary[bowler_summary['Balls'] >= min_balls].sort_values('Economy')
    st.dataframe(bowler_summary.reset_index(drop=True), use_container_width=True)

# ── TAB 2: Length & Line ───────────────────────────────────────────────────────
with tab2:
    st.subheader("Pitching Length & Line Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Economy by Pitching Length**")
        len_grp = (
            dff.groupby('Pitching Length')
            .agg(Balls=('Run', 'count'), Runs=('Run', 'sum'), Wickets=('Dismissed', 'sum'))
            .reset_index()
        )
        len_grp['Economy'] = (len_grp['Runs'] / (len_grp['Balls'] / 6)).round(2)
        fig = px.bar(len_grp, x='Pitching Length', y='Economy',
                     color='Economy', color_continuous_scale='RdYlGn_r',
                     text='Economy', height=400,
                     title="Economy by Length")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Wickets by Pitching Length**")
        fig2 = px.bar(len_grp, x='Pitching Length', y='Wickets',
                      color='Wickets', color_continuous_scale='Blues',
                      text='Wickets', height=400,
                      title="Wickets by Length")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**Economy by Pitching Line**")
        line_grp = (
            dff.groupby('Pitching Line')
            .agg(Balls=('Run', 'count'), Runs=('Run', 'sum'), Wickets=('Dismissed', 'sum'))
            .reset_index()
        )
        line_grp['Economy'] = (line_grp['Runs'] / (line_grp['Balls'] / 6)).round(2)
        fig3 = px.bar(line_grp, x='Pitching Line', y='Economy',
                      color='Economy', color_continuous_scale='RdYlGn_r',
                      text='Economy', height=400, title="Economy by Line")
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown("**Heatmap: Length vs Line (Economy)**")
        pivot = dff.groupby(['Pitching Length', 'Pitching Line']).agg(
            Balls=('Run', 'count'), Runs=('Run', 'sum')
        ).reset_index()
        pivot['Economy'] = (pivot['Runs'] / (pivot['Balls'] / 6)).round(2)
        heat = pivot.pivot(index='Pitching Length', columns='Pitching Line', values='Economy')
        fig4 = px.imshow(heat, color_continuous_scale='RdYlGn_r',
                         text_auto=True, height=400,
                         title="Economy Heatmap: Length × Line")
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("**Speed Bucket × Length: Delivery Distribution**")
    cross = dff.groupby(['Speed Bucket', 'Pitching Length'], observed=True).size().reset_index(name='Deliveries')
    cross['Speed Bucket'] = cross['Speed Bucket'].astype(str)
    fig5 = px.bar(cross, x='Speed Bucket', y='Deliveries', color='Pitching Length',
                  barmode='stack', height=400,
                  title="Delivery Distribution by Speed Bucket and Length")
    fig5.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig5, use_container_width=True)

# ── TAB 3: Bowler deep dive ────────────────────────────────────────────────────
with tab3:
    st.subheader("Individual Bowler Deep Dive")

    selected_bowler = st.selectbox(
        "Select a Bowler", options=sorted(dff['Bowler'].unique())
    )
    bdf = dff[dff['Bowler'] == selected_bowler]

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Balls Bowled", len(bdf))
    b2.metric("Runs Conceded", int(bdf['Run'].sum()))
    b3.metric("Wickets", int(bdf['Dismissed'].sum()))
    becon = (bdf['Run'].sum() / (len(bdf) / 6)) if len(bdf) > 0 else 0
    b4.metric("Economy", f"{becon:.2f}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Speed Distribution**")
        fig = px.histogram(bdf, x='Speed', nbins=20,
                           title=f"{selected_bowler} – Speed Distribution",
                           color_discrete_sequence=['#636EFA'])
        fig.add_vline(x=bdf['Speed'].mean(), line_dash='dash', line_color='orange',
                      annotation_text=f"Avg: {bdf['Speed'].mean():.1f}")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Economy by Speed Bucket**")
        b_grp = (
            bdf.groupby('Speed Bucket', observed=True)
            .agg(Balls=('Run', 'count'), Runs=('Run', 'sum'), Wickets=('Dismissed', 'sum'))
            .reset_index()
        )
        b_grp['Economy'] = (b_grp['Runs'] / (b_grp['Balls'] / 6)).round(2)
        b_grp['Speed Bucket'] = b_grp['Speed Bucket'].astype(str)
        fig2 = px.bar(b_grp, x='Speed Bucket', y='Economy',
                      text='Economy', color='Economy',
                      color_continuous_scale='RdYlGn_r',
                      title=f"{selected_bowler} – Economy by Speed Bucket")
        fig2.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**Length Breakdown**")
        lf = bdf['Pitching Length'].value_counts().reset_index()
        lf.columns = ['Length', 'Count']
        fig3 = px.pie(lf, names='Length', values='Count',
                      title=f"{selected_bowler} – Length Breakdown")
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown("**Line Breakdown**")
        lnf = bdf['Pitching Line'].value_counts().reset_index()
        lnf.columns = ['Line', 'Count']
        fig4 = px.pie(lnf, names='Line', values='Count',
                      title=f"{selected_bowler} – Line Breakdown")
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("**Runs per Delivery (Ball-by-Ball)**")
    bdf_reset = bdf.reset_index(drop=True)
    bdf_reset['Delivery #'] = bdf_reset.index + 1
    fig5 = px.scatter(bdf_reset, x='Delivery #', y='Run',
                      color='Pitching Length', hover_data=['Speed', 'Pitching Line', 'Batter'],
                      title=f"{selected_bowler} – Runs per Delivery")
    st.plotly_chart(fig5, use_container_width=True)

# ── TAB 4: Raw data ────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Filtered Raw Data")
    st.dataframe(dff.reset_index(drop=True), use_container_width=True)
    csv = dff.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download filtered data as CSV", csv, "filtered_cricket_data.csv", "text/csv")