import os
import pandas as pd
import plotly.express as px
import streamlit as st
from google.cloud import bigquery

# 1. Page Configuration
st.set_page_config(
    page_title="Document Pipeline Dashboard",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize BigQuery Client
try:
    bq_client = bigquery.Client()
    PROJECT_ID = bq_client.project
except Exception as e:
    st.error(f"Error initializing BigQuery client: {e}")
    st.stop()

# 2. Theme Toggle State
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

IS_DARK = st.session_state.theme == "dark"

# 3. Inject CSS Design System
# Color variables based on dark/light mode
bg = "#09090b" if IS_DARK else "#ffffff"
bg_subtle = "#0c0c0f" if IS_DARK else "#f9fafb"
card = "#0c0c0f" if IS_DARK else "#ffffff"
card_hover = "#131316" if IS_DARK else "#f4f4f5"
border = "#1e1e24" if IS_DARK else "#e4e4e7"
border_subtle = "#16161a" if IS_DARK else "#f0f0f2"
text = "#fafafa" if IS_DARK else "#09090b"
text_muted = "#71717a"
text_dim = "#52525b" if IS_DARK else "#a1a1aa"
accent = "#2563eb"
shadow = "none" if IS_DARK else "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)"
radius = "10px"

css = f"""
<style>
/* Hide Streamlit chrome */
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"], .stDeployButton,
div[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}

/* Global Styling */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main, .block-container, section[data-testid="stMain"] {{
    background-color: {bg} !important;
    color: {text} !important;
    font-family: 'DM Sans', -apple-system, sans-serif !important;
}}
.block-container {{
    padding: 2rem 3rem 3rem !important;
    max-width: 1400px !important;
}}

/* Layout spacing */
[data-testid="stHorizontalBlock"] {{
    gap: 1.25rem !important;
}}
[data-testid="stVerticalBlock"] > div:has(> [data-testid="stHorizontalBlock"]) {{
    margin-bottom: 0.5rem !important;
}}

/* Brand header */
.brand {{
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.brand-icon {{
    font-size: 1.6rem;
    color: {accent};
}}
.brand-name {{
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: {text};
}}

/* Styled card containers */
.metric-card {{
    background: {card};
    border: 1px solid {border};
    border-radius: {radius};
    padding: 1.25rem 1.4rem;
    box-shadow: {shadow};
}}
.metric-label {{
    font-size: 0.78rem;
    color: {text_muted};
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.metric-value {{
    font-size: 1.85rem;
    font-weight: 700;
    color: {text};
    letter-spacing: -0.03em;
    margin-top: 0.2rem;
}}
.metric-subtitle {{
    font-size: 0.72rem;
    color: {text_dim};
    margin-top: 0.3rem;
}}

/* Chart wrapping card */
.chart-wrap {{
    background: {card};
    border: 1px solid {border};
    border-radius: {radius};
    padding: 1.5rem;
    box-shadow: {shadow};
    margin-bottom: 1.5rem;
}}
.chart-title {{
    font-size: 0.85rem;
    font-weight: 600;
    color: {text};
    letter-spacing: -0.01em;
}}
.chart-subtitle {{
    font-size: 0.72rem;
    color: {text_dim};
    margin-bottom: 1.2rem;
}}

/* Filter Panel Styling */
div[data-testid="stExpander"] {{
    background: {card} !important;
    border: 1px solid {border} !important;
    border-radius: {radius} !important;
}}

/* Custom Data Table */
.data-table-container {{
    background: {card};
    border: 1px solid {border};
    border-radius: {radius};
    box-shadow: {shadow};
    overflow: hidden;
    margin-top: 1rem;
}}
.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    text-align: left;
}}
.data-table th {{
    padding: 0.9rem 1.2rem;
    color: {text_muted};
    font-weight: 600;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid {border};
    background: {bg_subtle};
}}
.data-table td {{
    padding: 0.9rem 1.2rem;
    color: {text};
    border-bottom: 1px solid {border_subtle};
}}
.data-table tr:last-child td {{
    border-bottom: none;
}}
.data-table tr:hover td {{
    background: {card_hover};
}}

/* Status Badge Styles */
.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 500;
    margin-right: 4px;
    margin-bottom: 4px;
}}
.badge-tag {{
    color: {accent};
    background: rgba(37, 99, 235, 0.08);
    border: 1px solid rgba(37, 99, 235, 0.15);
}}

/* Tab Styling override */
button[data-baseweb="tab"] {{
    background: transparent !important;
    color: {text_muted} !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    border: 1px solid transparent !important;
    border-radius: 7px !important;
    transition: all 0.2s ease !important;
}}
button[data-baseweb="tab"]:hover {{
    color: {text} !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {text} !important;
    background: {card} !important;
    border-color: {border} !important;
}}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{
    display: none !important;
}}
[data-baseweb="tab-list"] {{
    gap: 4px !important;
    background: {bg_subtle} !important;
    border: 1px solid {border} !important;
    border-radius: 10px !important;
    padding: 4px;
    margin-bottom: 1.5rem;
}}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# Helper for custom KPI cards
def metric_card(label, value, subtitle=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

# 4. Header Bar
head_left, head_right = st.columns([9, 1.2])
with head_left:
    st.markdown(f"""
    <div class="brand">
        <span class="brand-icon">◆</span>
        <span class="brand-name">Pipeline Dashboard</span>
    </div>
    """, unsafe_allow_html=True)
with head_right:
    theme_label = "☀️ Light" if IS_DARK else "🌙 Dark"
    st.button(theme_label, on_click=toggle_theme, use_container_width=True)

# 5. Data Retrieval (Cached)
@st.cache_data(ttl=10)  # Short cache timeout to allow refresh on uploads
def get_pipeline_data():
    query = f"""
    SELECT filename, date AS upload_date, tags, word_count
    FROM `{PROJECT_ID}.doc_processing.metadata`
    ORDER BY date DESC
    """
    try:
        query_job = bq_client.query(query)
        res_df = query_job.to_dataframe()
        return res_df
    except Exception as query_err:
        st.error(f"Error querying BigQuery: {query_err}")
        return pd.DataFrame()

df = get_pipeline_data()

# Check if data exists
if df.empty:
    st.info("No processed documents found in the database. Try uploading some files to your bucket first.")
    st.stop()

# 6. Extract unique tags for filtering
all_tags = set()
for item in df["tags"]:
    if isinstance(item, list) or isinstance(item, (pd.Series, tuple)):
        all_tags.update(item)
    elif isinstance(item, str):
        all_tags.add(item)
all_tags_list = sorted(list(all_tags))

# 7. Sidebar Filter section (Using an expander at the top)
with st.expander("Filter Documents by Tag", expanded=True):
    selected_tags = st.multiselect(
        "Select tags to display:",
        options=all_tags_list,
        default=[],
        placeholder="Showing all documents. Select tags to filter..."
    )

# Filter Dataframe
if selected_tags:
    # Filter rows where at least one selected tag is present
    filtered_df = df[df["tags"].apply(lambda t: any(tag in t for tag in selected_tags))]
else:
    filtered_df = df

# 8. Compute KPI values
total_docs = len(df)
avg_word_count = int(df["word_count"].mean()) if not df.empty else 0
unique_tags_count = len(all_tags)
latest_doc = df["filename"].iloc[0] if not df.empty else "N/A"
if len(latest_doc) > 22:
    latest_doc = latest_doc[:19] + "..."

# Row of KPIs
c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Total Documents", f"{total_docs}", f"Filtered: {len(filtered_df)}")
with c2:
    metric_card("Average Word Count", f"{avg_word_count}", "Words per document")
with c3:
    metric_card("Unique Tags", f"{unique_tags_count}", f"Across {total_docs} files")
with c4:
    metric_card("Latest Document", f"{latest_doc}", f"Uploaded recently")

st.markdown("<br>", unsafe_allow_html=True)

# 9. Main Tabs
tab1, tab2 = st.tabs(["Processed Documents", "Analytics & Insights"])

with tab1:
    st.markdown("##### Document Logs")
    if filtered_df.empty:
        st.warning("No documents match the selected filters.")
    else:
        # Generate custom styled HTML table
        table_rows = ""
        for _, row in filtered_df.iterrows():
            # Format date readably
            try:
                date_str = pd.to_datetime(row["upload_date"]).strftime("%b %d, %Y, %H:%M:%S")
            except Exception:
                date_str = str(row["upload_date"])
                
            # Create tag badges HTML
            badges_html = ""
            for tag in row["tags"]:
                badges_html += f'<span class="badge badge-tag">{tag}</span>'
                
            table_rows += f"""
            <tr>
                <td style="font-weight: 500;">{row['filename']}</td>
                <td style="color: {text_muted};">{date_str}</td>
                <td>{badges_html}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 500;">{row['word_count']:,}</td>
            </tr>
            """
            
        st.markdown(f"""
        <div class="data-table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Filename</th>
                        <th>Upload Date (UTC)</th>
                        <th>Tags</th>
                        <th>Word Count</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

with tab2:
    st.markdown("##### Visualizations & Statistics")
    
    # Plotly Layout variables
    PLOT_LAYOUT = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color="#71717a" if not IS_DARK else "#a1a1aa", size=11),
        margin=dict(l=0, r=0, t=25, b=0),
        xaxis=dict(
            gridcolor="rgba(0,0,0,0.04)" if not IS_DARK else "rgba(255,255,255,0.04)",
            zerolinecolor="rgba(0,0,0,0.04)" if not IS_DARK else "rgba(255,255,255,0.04)",
            tickfont=dict(size=10, color="#71717a"),
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0.04)" if not IS_DARK else "rgba(255,255,255,0.04)",
            zerolinecolor="rgba(0,0,0,0.04)" if not IS_DARK else "rgba(255,255,255,0.04)",
            tickfont=dict(size=10, color="#71717a"),
        ),
    )
    
    plot_c1, plot_c2 = st.columns(2)
    
    with plot_c1:
        # Chart 1: Tag Distribution
        st.markdown("""
        <div class="chart-wrap">
            <div class="chart-title">Tag Distribution</div>
            <div class="chart-subtitle">Frequency of classified tags across documents</div>
        """, unsafe_allow_html=True)
        
        # Calculate tag frequency for plotting
        tag_counts = {}
        for item in filtered_df["tags"]:
            for tag in item:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        if tag_counts:
            tag_counts_df = pd.DataFrame([{"Tag": k, "Count": v} for k, v in tag_counts.items()]).sort_values(by="Count", ascending=True)
            
            fig1 = px.bar(
                tag_counts_df,
                y="Tag",
                x="Count",
                orientation="h",
                color_discrete_sequence=[accent],
                labels={"Tag": "", "Count": "Number of Files"}
            )
            fig1.update_layout(**PLOT_LAYOUT)
            fig1.update_traces(marker_line_width=0, opacity=0.85)
            st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No tags found to display.")
            
        st.markdown("</div>", unsafe_allow_html=True)
        
    with plot_c2:
        # Chart 2: Word Count Comparison
        st.markdown("""
        <div class="chart-wrap">
            <div class="chart-title">Word Count Comparison</div>
            <div class="chart-subtitle">Word counts per document</div>
        """, unsafe_allow_html=True)
        
        if not filtered_df.empty:
            # Sort by upload date to show sequential changes
            sorted_filtered = filtered_df.sort_values(by="upload_date")
            
            # Shorten filenames for display
            sorted_filtered["short_name"] = sorted_filtered["filename"].apply(lambda n: n[:15] + "..." if len(n) > 18 else n)
            
            fig2 = px.line(
                sorted_filtered,
                x="short_name",
                y="word_count",
                markers=True,
                color_discrete_sequence=[accent],
                labels={"short_name": "Document Name", "word_count": "Word Count"}
            )
            fig2.update_layout(**PLOT_LAYOUT)
            fig2.update_traces(line=dict(width=3), marker=dict(size=8), opacity=0.85)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No data found to display.")
            
        st.markdown("</div>", unsafe_allow_html=True)
