import streamlit as st
import pandas as pd
import os
import time
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import io
from dotenv import load_dotenv
import re
import html
from google import genai
from google.genai import types

# Load environment variables from .env file (for API key)
load_dotenv()

# File path configuration - change this to your actual CSV file path
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), "financial_metrics.csv")

# Configure Streamlit page
st.set_page_config(
    page_title="Financial Data Analysis Platform",
    page_icon="📊",
    layout="wide"
)

# Set up styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        margin-bottom: 1rem;
    }
    .chat-message {
        padding: 1.5rem; 
        border-radius: 0.5rem; 
        margin-bottom: 1rem; 
        display: flex;
        align-items: flex-start;
    }
    .chat-message.user {
        background-color: #F0F2F6;
    }
    .chat-message.assistant {
        background-color: #E3F2FD;
    }
    .chat-message .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 1rem;
    }
    .chat-message .content {
        width: calc(100% - 60px);
    }
    .chat-message.user .content {
        text-align: left;
    }
    .chat-message.assistant .content {
        text-align: left;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #F0F2F6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E3F2FD;
        border-radius: 4px 4px 0px 0px;
    }
    .plot-description {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #4e8cff;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }
    .insight-title {
        font-weight: 600;
        margin-bottom: 8px;
    }
    .insight-list {
        margin-top: 5px;
        margin-left: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []

if "df" not in st.session_state:
    # Automatically load the CSV file
    try:
        st.session_state.df = pd.read_csv(CSV_FILE_PATH)
        st.session_state.file_name = CSV_FILE_PATH
        st.session_state.file_loaded = True
    except Exception as e:
        st.session_state.df = None
        st.session_state.file_name = None
        st.session_state.file_loaded = False

if "agent" not in st.session_state:
    st.session_state.agent = None

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

# Add this for unique key generation
if "used_keys" not in st.session_state:
    st.session_state.used_keys = set()
    st.session_state.key_counter = 0

# Get API key from environment variable
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    os.environ["GEMINI_API_KEY"] = api_key

# Function to generate unique keys
def get_unique_key(prefix="plot"):
    """Generate a unique key that hasn't been used in this session"""
    while True:
        st.session_state.key_counter += 1
        new_key = f"{prefix}_{st.session_state.key_counter}"
        if new_key not in st.session_state.used_keys:
            st.session_state.used_keys.add(new_key)
            return new_key

# Function to add plot descriptions
def add_plot_description(title, description, insights=None):
    """
    Create a standardized description for plots
    
    Parameters:
    - title: Title of the visualization
    - description: General description of what the visualization shows
    - insights: List of specific insights that can be drawn from this visualization
    """
    
    st.markdown(f"""
    <div class="plot-description">
        <p><strong>{title}</strong></p>
        <p>{description}</p>
    """, unsafe_allow_html=True)
    
    if insights:
        st.markdown("""
        <p class="insight-title">Key insights to look for:</p>
        <ul class="insight-list">
        """, unsafe_allow_html=True)
        
        for insight in insights:
            st.markdown(f"<li>{insight}</li>", unsafe_allow_html=True)
        
        st.markdown("</ul>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# Sidebar for navigation
with st.sidebar:
    st.title("Navigation")
    
    # Navigation buttons
    if st.button("📊 Dashboard", use_container_width=True):
        st.session_state.page = "Dashboard"
        st.rerun()
        
    if st.button("💬 AI Chat Assistant", use_container_width=True):
        st.session_state.page = "Chat"
        st.rerun()
    
    # Add a separator
    st.markdown("---")
    
    # Show small data status indicator
    if st.session_state.df is not None:
        st.success(f"✓ Data loaded: {st.session_state.df.shape[0]} rows")
    else:
        st.error("✗ Data not loaded")
    
    # Footer
    st.markdown("---")
    st.caption("Powered by Streamlit, Plotly & Gemini")

# Function to identify common metrics
def get_common_metrics(df, threshold=0.9):
    # Get unique companies if company column exists
    if 'Company' in df.columns:
        companies = df['Company'].unique()
    else:
        # Create a dummy company if there's no Company column
        companies = ['Dataset']
        df['Company'] = 'Dataset'
    
    metrics = {}
    # Try to identify numeric columns that could be financial metrics
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    exclude_cols = ['Page_Numbers']
    numeric_cols = [col for col in numeric_cols if col not in exclude_cols]
    # For non-company specific data, all numeric columns are potential metrics
    if len(companies) <= 1:
        for col in numeric_cols:
            metrics[col] = {"key": col, "type": "direct"}
        return metrics
    
    # For company data, use the original approach
    for col in numeric_cols:
        availability = {}
        
        for company in companies:
            company_df = df[df['Company'] == company]
            non_null_count = company_df[col].notna().sum()
            availability[company] = non_null_count / len(company_df)
        
        # Only include metrics that meet the threshold for all companies
        if all(pct >= threshold for pct in availability.values()):
            metrics[col] = {"key": col, "type": "direct"}
    
    return metrics

# Main page content based on selected page
if st.session_state.page == "Dashboard":
    # DASHBOARD PAGE
    st.markdown("<div class='main-header'>Financial Analysis Dashboard</div>", unsafe_allow_html=True)
    
    if st.session_state.df is None:
        st.error(f"Could not load data from {CSV_FILE_PATH}. Please check the file path.")
    else:
        # Show data preview
        with st.expander("Data Preview", expanded=False):
            st.dataframe(st.session_state.df.head())
            st.caption(f"Showing 5 of {st.session_state.df.shape[0]} rows and {st.session_state.df.shape[1]} columns")
        
        # Get metrics based on the data
        common_metrics = get_common_metrics(st.session_state.df)
        if 'Page Number' in common_metrics:
            del common_metrics['Page_Numbers ']
        
        if not common_metrics:
            st.warning("No numeric metrics found in the dataset.")
        else:
            # Determine if we have company data
            has_company_col = 'Company' in st.session_state.df.columns
            
            # Dashboard filters
            with st.container():
                st.subheader("Dashboard Filters")
                
                filter_col1, filter_col2 = st.columns([1, 1])
                
                with filter_col1:
                    if has_company_col:
                        companies = st.session_state.df['Company'].unique()
                        selected_companies = st.multiselect(
                            "Select Entities to Compare",
                            options=companies,
                            default=companies[:2] if len(companies) >= 2 else companies
                        )
                        
                        # Filter data based on company selection
                        if selected_companies:
                            filtered_df = st.session_state.df[st.session_state.df['Company'].isin(selected_companies)]
                        else:
                            filtered_df = st.session_state.df
                    else:
                        filtered_df = st.session_state.df
                        selected_companies = ['Dataset']  # Use a placeholder
                
                with filter_col2:
                    # Select metrics for display
                    metric_options = {name: info["key"] for name, info in common_metrics.items()}
                    
                    selected_metrics = st.multiselect(
                        "Select Metrics to Display",
                        options=list(metric_options.keys()),
                        default=list(metric_options.keys())[:3] if len(metric_options) >= 3 else list(metric_options.keys())
                    )
            
            # Main dashboard content
            if filtered_df.empty or not selected_metrics:
                st.warning("Please select at least one metric and entity (if applicable).")
            else:
                # Create visualization tabs
                viz_tab1, viz_tab2, viz_tab3 = st.tabs(["Time Series", "Comparisons", "Summary"])
                
                # Check if we have date columns for time series
                date_cols = filtered_df.select_dtypes(include=['datetime64']).columns.tolist()
                if not date_cols:
                    # Directly specify the known date columns
                    known_date_cols = ['Comparative_Period_End_Date', 'Period_End_Date']
                    
                    # Only keep the columns that actually exist in the dataframe
                    potential_date_cols = [col for col in known_date_cols if col in filtered_df.columns]
                    
                    # Try to convert them to datetime
                    for col in potential_date_cols:
                        try:
                            filtered_df[col] = pd.to_datetime(filtered_df[col])
                            date_cols.append(col)
                        except:
                            pass
                
                with viz_tab1:
                    if date_cols:
                        st.subheader("Revenue & Profitability Over Time")
                        
                        # Date column selection
                        date_col = st.selectbox("Select Date Column", options=date_cols)
                        
                        # Sort by date for proper time series
                        filtered_df = filtered_df.sort_values(by=date_col)
                        
                        # 1. Revenue & Gross Profit Analysis
                        revenue_cols = [col for col in filtered_df.columns if 'revenue' in col.lower()]
                        gross_profit_cols = [col for col in filtered_df.columns if 'gross_profit' in col.lower() and not 'margin' in col.lower()]
                        cost_sales_cols = [col for col in filtered_df.columns if 'cost_of_sales' in col.lower()]
                        margin_cols = [col for col in filtered_df.columns if 'margin' in col.lower() or 'gross_profit_margin_pct' in col.lower()]
                        
                        # Calculate gross profit margin dynamically instead of reading it directly
                        current_rev_col = next((col for col in revenue_cols if 'current' in col.lower()), None)
                        current_cost_col = next((col for col in cost_sales_cols if 'current' in col.lower()), None)

                        if current_rev_col and current_cost_col:
                            # Calculate Gross Profit Margin: (Revenue - Cost of Goods Sold) / Revenue × 100
                            filtered_df['Calculated_Gross_Profit_Margin'] = (
                                (filtered_df[current_rev_col] - filtered_df[current_cost_col]) / 
                                filtered_df[current_rev_col] * 100
                            )
                            
                            # Do the same for comparative period if those columns exist
                            comparative_rev_col = next((col for col in revenue_cols if 'comparative' in col.lower()), None)
                            comparative_cost_col = next((col for col in cost_sales_cols if 'comparative' in col.lower()), None)
                            
                            if comparative_rev_col and comparative_cost_col:
                                filtered_df['Calculated_Comparative_Gross_Profit_Margin'] = (
                                    (filtered_df[comparative_rev_col] - filtered_df[comparative_cost_col]) / 
                                    filtered_df[comparative_rev_col] * 100
                                )
                        
                        if revenue_cols or gross_profit_cols:
                            st.subheader("Revenue & Gross Profit Trends")
                            
                            # Create a figure with dual Y-axis
                            fig = make_subplots(specs=[[{"secondary_y": True}]])
                            
                            # Add revenue lines
                            for company in selected_companies if has_company_col else ['Dataset']:
                                company_data = filtered_df[filtered_df['Company'] == company] if has_company_col else filtered_df
                                
                                # Add current revenue
                                current_rev_col = next((col for col in revenue_cols if 'current' in col.lower()), None)
                                if current_rev_col and not company_data[current_rev_col].isna().all():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=company_data[date_col],
                                            y=company_data[current_rev_col],
                                            name=f"{company} - Current Revenue" if has_company_col else "Current Revenue",
                                            mode='lines+markers',
                                            line=dict(width=3)
                                        ),
                                        secondary_y=False
                                    )
                                
                                # Add current gross profit
                                current_gp_col = next((col for col in gross_profit_cols if 'current' in col.lower()), None)
                                if current_gp_col and not company_data[current_gp_col].isna().all():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=company_data[date_col],
                                            y=company_data[current_gp_col],
                                            name=f"{company} - Gross Profit" if has_company_col else "Gross Profit",
                                            mode='lines+markers',
                                            line=dict(width=3, dash='dot')
                                        ),
                                        secondary_y=False
                                    )
                                
                                # Add margin as a secondary y-axis
                                if 'Calculated_Gross_Profit_Margin' in company_data.columns and not company_data['Calculated_Gross_Profit_Margin'].isna().all():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=company_data[date_col],
                                            y=company_data['Calculated_Gross_Profit_Margin'],
                                            name=f"{company} - Gross Margin %" if has_company_col else "Gross Margin %",
                                            mode='lines+markers',
                                            line=dict(width=2, dash='dash'),
                                            marker=dict(symbol='diamond')
                                        ),
                                        secondary_y=True
                                    )
                                                        
                            # Update layout
                            fig.update_layout(
                                title="Revenue & Gross Profit Trends",
                                hovermode="x unified",
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                height=500
                            )
                            
                            # Set y-axes titles
                            fig.update_yaxes(title_text="Amount", secondary_y=False)
                            fig.update_yaxes(title_text="Margin %", secondary_y=True)
                            
                            st.plotly_chart(fig, use_container_width=True, key=get_unique_key("revenue_trend"))
                            
                            # Add explanation for the revenue & profit chart
                            add_plot_description(
                                title="Revenue & Gross Profit Trends",
                                description="This chart shows revenue (solid line) and gross profit (dotted line) over time. The secondary axis (right side) displays the gross profit margin percentage (dashed line with diamond markers).",
                                insights=[
                                    "Look for consistent growth in both revenue and gross profit lines",
                                    "A widening gap between revenue and gross profit indicates increasing costs",
                                    "The gross margin percentage should ideally remain stable or increase over time",
                                    "Seasonal patterns may appear as regular peaks and valleys",
                                    "Compare performance across different companies to identify market leaders"
                                ]
                            )
                        
                        # 2. Operating & Net Profit
                        operating_profit_cols = [col for col in filtered_df.columns if 'operating_profit' in col.lower()]
                        profit_period_cols = [col for col in filtered_df.columns if 'profit_for_period' in col.lower()]
                        
                        if operating_profit_cols or profit_period_cols:
                            st.subheader("Operating & Net Profit Trends")
                            
                            fig = go.Figure()
                            
                            for company in selected_companies if has_company_col else ['Dataset']:
                                company_data = filtered_df[filtered_df['Company'] == company] if has_company_col else filtered_df
                                
                                # Add current operating profit
                                current_op_col = next((col for col in operating_profit_cols if 'current' in col.lower()), None)
                                if current_op_col and not company_data[current_op_col].isna().all():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=company_data[date_col],
                                            y=company_data[current_op_col],
                                            name=f"{company} - Operating Profit" if has_company_col else "Operating Profit",
                                            mode='lines+markers',
                                            line=dict(width=3)
                                        )
                                    )
                                
                                # Add net profit
                                current_np_col = next((col for col in profit_period_cols if 'current' in col.lower()), None)
                                if current_np_col and not company_data[current_np_col].isna().all():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=company_data[date_col],
                                            y=company_data[current_np_col],
                                            name=f"{company} - Net Profit" if has_company_col else "Net Profit",
                                            mode='lines+markers',
                                            line=dict(width=3, dash='dot')
                                        )
                                    )
                                
                                # Add comparative year data with lighter colors if available
                                comp_op_col = next((col for col in operating_profit_cols if 'comparative' in col.lower()), None)
                                if comp_op_col and not company_data[comp_op_col].isna().all():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=company_data[date_col],
                                            y=company_data[comp_op_col],
                                            name=f"{company} - Operating Profit (Previous Year)" if has_company_col else "Operating Profit (Previous Year)",
                                            mode='lines',
                                            line=dict(width=2, dash='dot'),
                                            opacity=0.6
                                        )
                                    )
                                
                                comp_np_col = next((col for col in profit_period_cols if 'comparative' in col.lower()), None)
                                if comp_np_col and not company_data[comp_np_col].isna().all():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=company_data[date_col],
                                            y=company_data[comp_np_col],
                                            name=f"{company} - Net Profit (Previous Year)" if has_company_col else "Net Profit (Previous Year)",
                                            mode='lines',
                                            line=dict(width=2, dash='dash'),
                                            opacity=0.6
                                        )
                                    )
                            
                            # Update layout
                            fig.update_layout(
                                title="Operating & Net Profit Trends",
                                hovermode="x unified",
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True, key=get_unique_key("profit_trend"))
                            
                            # Add explanation for profit trends
                            add_plot_description(
                                title="Operating & Net Profit Trends",
                                description="This chart compares operating profit (solid line) and net profit (dotted line) over time, with previous year data shown in lighter colors with dashed lines.",
                                insights=[
                                    "The difference between operating and net profit represents non-operating expenses, taxes, and other costs",
                                    "A narrowing gap between these lines suggests improving efficiency in managing non-operating expenses",
                                    "Compare current year (solid lines) with previous year (lighter dashed lines) to gauge year-over-year growth",
                                    "Consistent upward trends in both metrics indicate strong financial performance",
                                    "Sharp drops may indicate one-time expenses or market challenges"
                                ]
                            )
                        
                        # 3. Earnings Per Share
                        eps_cols = [col for col in filtered_df.columns if 'earnings_per_share' in col.lower()]
                        
                        if eps_cols:
                            st.subheader("Earnings Per Share (EPS) Trends")
                            
                            fig = go.Figure()
                            
                            for company in selected_companies if has_company_col else ['Dataset']:
                                company_data = filtered_df[filtered_df['Company'] == company] if has_company_col else filtered_df
                                
                                current_eps_col = next((col for col in eps_cols if 'current' in col.lower()), None)
                                if current_eps_col and not company_data[current_eps_col].isna().all():
                                    fig.add_trace(
                                        go.Bar(
                                            x=company_data[date_col],
                                            y=company_data[current_eps_col],
                                            name=f"{company} - Current EPS" if has_company_col else "Current EPS",
                                            marker_color='rgb(55, 83, 109)'
                                        )
                                    )
                                
                                comp_eps_col = next((col for col in eps_cols if 'comparative' in col.lower()), None)
                                if comp_eps_col and not company_data[comp_eps_col].isna().all():
                                    fig.add_trace(
                                        go.Bar(
                                            x=company_data[date_col],
                                            y=company_data[comp_eps_col],
                                            name=f"{company} - Previous Year EPS" if has_company_col else "Previous Year EPS",
                                            marker_color='rgba(55, 83, 109, 0.5)'
                                        )
                                    )
                            
                            # Update layout
                            fig.update_layout(
                                title="Earnings Per Share Comparison",
                                hovermode="x unified",
                                barmode='group',
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True, key=get_unique_key("eps_trend"))
                            
                            # Add explanation for EPS chart
                            add_plot_description(
                                title="Earnings Per Share (EPS) Comparison",
                                description="This bar chart shows Earnings Per Share (EPS) for the current period (darker bars) compared to the previous year (lighter bars).",
                                insights=[
                                    "EPS is a key indicator of profitability from a shareholder perspective",
                                    "Higher EPS values generally indicate better financial performance per share of stock",
                                    "Compare current period (darker bars) with previous year (lighter bars) to assess growth",
                                    "Consistent or increasing EPS suggests strong and sustainable financial performance",
                                    "For investors, EPS growth often correlates with higher stock valuations"
                                ]
                            )
                        
                        # For other generic metrics (create time series as before)
                        remaining_metrics = [m for m in selected_metrics 
                                            if m not in revenue_cols + gross_profit_cols + margin_cols + 
                                            operating_profit_cols + profit_period_cols + eps_cols]
                        
                        if remaining_metrics:
                            st.subheader("Other Selected Metrics")
                            
                            for metric_name in remaining_metrics:
                                # Skip if data is mostly null
                                if filtered_df[metric_name].isna().mean() > 0.5:
                                    st.info(f"Insufficient data for {metric_name}")
                                    continue
                                
                                fig = px.line(
                                    filtered_df, 
                                    x=date_col, 
                                    y=metric_name,
                                    color="Company" if has_company_col else None,
                                    markers=True,
                                    title=f"{metric_name} Over Time",
                                )
                                
                                # Improve layout
                                fig.update_layout(
                                    xaxis_title=date_col,
                                    yaxis_title=metric_name,
                                    legend_title="Entity" if has_company_col else None,
                                    hovermode="x unified"
                                )
                                
                                st.plotly_chart(fig, use_container_width=True, key=get_unique_key(f"metric_{metric_name}"))
                                
                                # Add explanation for custom metrics
                                metric_friendly_name = metric_name.replace('_', ' ').title()
                                add_plot_description(
                                    title=f"{metric_friendly_name} Over Time",
                                    description=f"This line chart shows how {metric_friendly_name.lower()} changes over time for each selected entity.",
                                    insights=[
                                        f"Track the overall trend in {metric_friendly_name.lower()} - is it increasing, decreasing, or stable?",
                                        "Look for significant changes that might indicate important business events",
                                        "Compare performance between different entities to identify leaders and laggards",
                                        "Consider how this metric correlates with other financial indicators"
                                    ]
                                )
                    else:
                        st.info("No date columns detected. Time series visualization is not available.")
                
                with viz_tab2:
                    st.subheader("Financial Performance Comparison")
                    
                    # Financial metrics specific visualizations
                    revenue_cols = [col for col in filtered_df.columns if 'revenue' in col.lower()]
                    cost_sales_cols = [col for col in filtered_df.columns if 'cost_of_sales' in col.lower()]
                    profit_cols = [col for col in filtered_df.columns if 'profit' in col.lower() and not 'margin' in col.lower()]
                    yoy_cols = [col for col in filtered_df.columns if 'yoy_change_pct' in col.lower()]
                    
                    # 1. Cost vs Revenue Comparison
                    if revenue_cols and cost_sales_cols:
                        st.subheader("Revenue vs Cost Analysis")
                        
                        current_rev_col = next((col for col in revenue_cols if 'current' in col.lower()), None)
                        current_cost_col = next((col for col in cost_sales_cols if 'current' in col.lower()), None)
                        
                        if current_rev_col and current_cost_col:
                            if has_company_col and len(selected_companies) > 1:
                                # Create a grouped bar chart for companies
                                comparison_df = filtered_df.groupby('Company').agg({
                                    current_rev_col: 'mean',
                                    current_cost_col: 'mean'
                                }).reset_index()
                                
                                comparison_df = pd.melt(
                                    comparison_df, 
                                    id_vars=['Company'], 
                                    value_vars=[current_rev_col, current_cost_col],
                                    var_name='Metric', 
                                    value_name='Value'
                                )
                                
                                # Replace column names for better display
                                comparison_df['Metric'] = comparison_df['Metric'].replace({
                                    current_rev_col: 'Revenue',
                                    current_cost_col: 'Cost of Sales'
                                })
                                
                                fig = px.bar(
                                    comparison_df,
                                    x='Company',
                                    y='Value',
                                    color='Metric',
                                    barmode='group',
                                    title="Average Revenue vs Cost of Sales by Company",
                                    color_discrete_map={
                                        'Revenue': 'rgb(46, 134, 193)',
                                        'Cost of Sales': 'rgb(231, 76, 60)'
                                    }
                                )
                                
                                fig.update_layout(height=500)
                                st.plotly_chart(fig, use_container_width=True, key=get_unique_key("revenue_cost_comp"))
                                
                                # Add explanation for Revenue vs Cost comparison
                                add_plot_description(
                                    title="Revenue vs Cost of Sales Comparison",
                                    description="This grouped bar chart compares the average revenue (blue) and cost of sales (red) for each selected company.",
                                    insights=[
                                        "Companies with higher bars for both metrics have larger operations overall",
                                        "The gap between the revenue and cost bars represents the gross profit",
                                        "Wider gaps indicate better profit margins and operational efficiency",
                                        "Companies with similar revenue but lower costs are more efficient",
                                        "This comparison helps identify which companies generate more value from their sales"
                                    ]
                                )
                                
                                # Calculate and display profit margin
                                st.subheader("Profit Margin Analysis")
                                margin_df = filtered_df.groupby('Company').agg({
                                    current_rev_col: 'mean',
                                    current_cost_col: 'mean'
                                }).reset_index()
                                
                                margin_df['Gross Profit'] = margin_df[current_rev_col] - margin_df[current_cost_col]
                                margin_df['Margin %'] = (margin_df['Gross Profit'] / margin_df[current_rev_col] * 100).round(2)
                                
                                fig = px.bar(
                                    margin_df,
                                    x='Company',
                                    y='Margin %',
                                    color='Company',
                                    title="Gross Profit Margin % by Company",
                                    text='Margin %'
                                )
                                
                                fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                                fig.update_layout(height=500, uniformtext_minsize=8, uniformtext_mode='hide')
                                
                                st.plotly_chart(fig, use_container_width=True, key=get_unique_key("margin_analysis"))
                                
                                # Add explanation for Profit Margin Analysis
                                add_plot_description(
                                    title="Gross Profit Margin Analysis",
                                    description="This bar chart shows the gross profit margin percentage for each company, calculated as (Revenue - Cost of Sales) / Revenue × 100.",
                                    insights=[
                                        "Higher percentages indicate better efficiency in converting sales into profit",
                                        "Industry leaders often maintain higher margins than competitors",
                                        "Margins below industry averages may signal pricing or cost management issues",
                                        "Companies with similar business models should have comparable margins",
                                        "Margins are often more important than absolute revenue for long-term sustainability"
                                    ]
                                )
                            else:
                                # For single company/dataset
                                if date_cols:
                                    # Time-based stacked analysis
                                    date_col = date_cols[0]
                                    
                                    # Prepare data for stacked and grouped bar chart
                                    fig = go.Figure()
                                    
                                    # Revenue bars
                                    fig.add_trace(go.Bar(
                                        x=filtered_df[date_col],
                                        y=filtered_df[current_rev_col],
                                        name='Revenue',
                                        marker_color='rgb(46, 134, 193)'
                                    ))
                                    
                                    # Cost of Sales bars
                                    fig.add_trace(go.Bar(
                                        x=filtered_df[date_col],
                                        y=filtered_df[current_cost_col],
                                        name='Cost of Sales',
                                        marker_color='rgb(231, 76, 60)'
                                    ))
                                    
                                    # Calculate and add gross profit
                                    filtered_df['Gross_Profit_Calc'] = filtered_df[current_rev_col] - filtered_df[current_cost_col]
                                    
                                    fig.add_trace(go.Bar(
                                        x=filtered_df[date_col],
                                        y=filtered_df['Gross_Profit_Calc'],
                                        name='Gross Profit',
                                        marker_color='rgb(39, 174, 96)'
                                    ))
                                    
                                    # Update layout
                                    fig.update_layout(
                                        title="Revenue, Cost, and Profit Analysis Over Time",
                                        xaxis_title=date_col,
                                        yaxis_title="Amount",
                                        barmode='group',
                                        height=500
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True, key=get_unique_key("revenue_cost_time"))
                                    
                                    # Add explanation for Revenue/Cost/Profit over time
                                    add_plot_description(
                                        title="Revenue, Cost, and Profit Analysis Over Time",
                                        description="This grouped bar chart shows revenue (blue), cost of sales (red), and gross profit (green) for each time period.",
                                        insights=[
                                            "Track how revenue and costs change over time and whether they move in tandem",
                                            "The green bars (gross profit) should ideally grow over time for a healthy business",
                                            "Periods where costs rise faster than revenue indicate margin pressure",
                                            "Look for seasonal patterns that may affect the business cycle",
                                            "Consistent growth in all three metrics suggests a scaling business"
                                        ]
                                    )
                    
                    # 2. YoY Analysis (Heatmap)
                    if yoy_cols and has_company_col and len(selected_companies) > 1 and date_cols:
                        st.subheader("Year-over-Year Growth Analysis")
                        
                        # Select important YoY metrics
                        important_yoy = [col for col in yoy_cols if any(metric in col.lower() for metric in 
                                                                      ['revenue', 'gross_profit', 'operating_profit', 'profit_for_period', 'earnings_per_share'])]
                        
                        if important_yoy and date_cols:
                            date_col = date_cols[0]
                            
                            # Create a heatmap for YoY metrics by company and time
                            for yoy_metric in important_yoy:
                                # Skip if mostly null
                                if filtered_df[yoy_metric].isna().mean() > 0.7:
                                    continue
                                
                                # Get readable metric name
                                metric_name = yoy_metric.replace('YoY_Change_Pct_', '').replace('_', ' ').title()
                                
                                # Pivot data for heatmap
                                try:
                                    # Format datetime if needed to get just year-quarter or similar
                                    if pd.api.types.is_datetime64_any_dtype(filtered_df[date_col]):
                                        filtered_df['period_label'] = filtered_df[date_col].dt.strftime('%Y-%m')
                                    else:
                                        filtered_df['period_label'] = filtered_df[date_col]
                                    
                                    pivot_df = filtered_df.pivot_table(
                                        values=yoy_metric,
                                        index='Company',
                                        columns='period_label',
                                        aggfunc='mean'
                                    )
                                    
                                    # Create heatmap
                                    fig = px.imshow(
                                        pivot_df,
                                        text_auto='.1f',
                                        color_continuous_scale='RdYlGn',  # Red for negative, Green for positive
                                        aspect="auto",
                                        title=f"YoY % Change: {metric_name}",
                                        labels=dict(x="Period", y="Company", color="% Change")
                                    )
                                    
                                    fig.update_layout(height=400)
                                    st.plotly_chart(fig, use_container_width=True, key=get_unique_key(f"yoy_heatmap_{metric_name}"))
                                    
                                    # Add explanation for YoY Growth heatmap
                                    add_plot_description(
                                        title=f"Year-over-Year Growth: {metric_name}",
                                        description=f"This heatmap shows the percentage change in {metric_name.lower()} compared to the same period in the previous year. Green indicates growth, red indicates decline.",
                                        insights=[
                                            "Green cells represent positive growth; darker green means stronger growth",
                                            "Red cells represent decline; darker red means steeper decline",
                                            "Look for patterns across time periods (columns) to identify growth trends",
                                            "Compare companies (rows) to see which are consistently outperforming others",
                                            "The numbers show the exact percentage change year-over-year"
                                        ]
                                    )
                                except Exception as e:
                                    st.info(f"Could not create heatmap for {metric_name}: {str(e)}")
                    
                    # 3. Profit Breakdown (Stacked Bar)
                    profit_breakdown_cols = [col for col in filtered_df.columns if any(x in col.lower() for x in 
                                                                                     ['operating_profit', 'tax_expense', 'profit_for_period'])]
                    
                    if len(profit_breakdown_cols) >= 2 and 'current' in ''.join(profit_breakdown_cols).lower():
                        st.subheader("Profit Breakdown Analysis")
                        
                        current_op_col = next((col for col in filtered_df.columns if 'operating_profit' in col.lower() and 'current' in col.lower()), None)
                        current_tax_col = next((col for col in filtered_df.columns if 'tax_expense' in col.lower() and 'current' in col.lower()), None)
                        current_net_col = next((col for col in filtered_df.columns if 'profit_for_period' in col.lower() and 'current' in col.lower()), None)
                        
                        if has_company_col and len(selected_companies) > 1:
                            # Create a stacked bar for companies
                            breakdown_df = filtered_df.groupby('Company').agg({
                                col: 'mean' for col in [c for c in [current_op_col, current_tax_col, current_net_col] if c is not None]
                            }).reset_index()
                            
                            # Melt the dataframe for stacked bar
                            cols_to_melt = [c for c in [current_op_col, current_tax_col, current_net_col] if c is not None]
                            
                            if cols_to_melt:
                                melted_df = pd.melt(
                                    breakdown_df,
                                    id_vars=['Company'],
                                    value_vars=cols_to_melt,
                                    var_name='Component',
                                    value_name='Value'
                                )
                                
                                # Replace column names for better display
                                component_names = {
                                    current_op_col: 'Operating Profit',
                                    current_tax_col: 'Tax Expense',
                                    current_net_col: 'Net Profit'
                                }
                                
                                melted_df['Component'] = melted_df['Component'].replace({
                                    col: name for col, name in component_names.items() if col is not None
                                })
                                
                                fig = px.bar(
                                    melted_df,
                                    x='Company',
                                    y='Value',
                                    color='Component',
                                    title="Profit Components Breakdown by Company",
                                    barmode='stack'
                                )
                                
                                fig.update_layout(height=500)
                                st.plotly_chart(fig, use_container_width=True, key=get_unique_key("profit_breakdown"))
                                
                                # Add explanation for profit breakdown
                                add_plot_description(
                                    title="Profit Components Breakdown",
                                    description="This stacked bar chart shows how different profit components (operating profit, tax expense, net profit) contribute to the overall financial performance of each company.",
                                    insights=[
                                        "The total height of each bar represents the company's financial performance",
                                        "The proportion of each color shows the relative size of each profit component",
                                        "Companies with larger operating profit segments are more efficient at their core business",
                                        "Tax expense (if shown) indicates the impact of taxation on profitability",
                                        "Compare the ratio of net profit to operating profit across companies to assess efficiency"
                                    ]
                                )
                        elif date_cols:
                            # Time-based analysis for single company/dataset
                            date_col = date_cols[0]
                            
                            # Prepare data for visualization
                            profit_components = []
                            if current_op_col: profit_components.append((current_op_col, 'Operating Profit'))
                            if current_tax_col: profit_components.append((current_tax_col, 'Tax Expense'))
                            if current_net_col: profit_components.append((current_net_col, 'Net Profit'))
                            
                            if profit_components:
                                # For area chart
                                fig = go.Figure()
                                
                                for col, name in profit_components:
                                    fig.add_trace(go.Scatter(
                                        x=filtered_df[date_col],
                                        y=filtered_df[col],
                                        mode='lines',
                                        name=name,
                                        stackgroup='one'
                                    ))
                                
                                # Update layout
                                fig.update_layout(
                                    title="Profit Components Over Time",
                                    xaxis_title=date_col,
                                    yaxis_title="Amount",
                                    height=500
                                )
                                
                                st.plotly_chart(fig, use_container_width=True, key=get_unique_key("profit_time"))
                                
                                # Add explanation for profit components over time
                                add_plot_description(
                                    title="Profit Components Over Time",
                                    description="This stacked area chart shows how different profit components evolve over time, with the total height representing the combined value.",
                                    insights=[
                                        "The changing height of the entire area shows overall profit performance trends",
                                        "The thickness of each layer shows the contribution of each profit component",
                                        "Growing areas indicate improving financial performance over time",
                                        "Look for consistent proportions between components for stable business operations",
                                        "Sudden changes in any component may indicate significant business events"
                                    ]
                                )
                    
                    # If we still have companies to compare but no specific financial metrics found
                    if has_company_col and len(selected_companies) > 1 and not revenue_cols and not profit_cols:
                        # Create a bar chart comparing metrics across companies (original code)
                        for metric_name in selected_metrics:
                            # Skip if data is mostly null
                            if filtered_df[metric_name].isna().mean() > 0.5:
                                st.info(f"Insufficient data for {metric_name}")
                                continue
                            
                            # Create a summary dataframe
                            summary_df = filtered_df.groupby('Company')[metric_name].mean().reset_index()
                            
                            fig = px.bar(
                                summary_df,
                                x='Company',
                                y=metric_name,
                                color='Company',
                                title=f"Average {metric_name} by Company"
                            )
                            
                            st.plotly_chart(fig, use_container_width=True, key=get_unique_key(f"bar_comp_{metric_name}"))
                            
                            # Add explanation for metric comparison
                            metric_friendly_name = metric_name.replace('_', ' ').title()
                            add_plot_description(
                                title=f"Average {metric_friendly_name} Comparison",
                                description=f"This bar chart compares the average {metric_friendly_name.lower()} across different companies.",
                                insights=[
                                    f"Taller bars indicate higher average {metric_friendly_name.lower()} values",
                                    "Compare the relative performance of each company for this metric",
                                    f"Consider what a high or low value for {metric_friendly_name.lower()} means in your industry context",
                                    "The average smooths out time-based fluctuations to show overall performance"
                                ]
                            )
                        
                        # Create a radar chart for performance comparison if we have enough metrics
                        if len(selected_metrics) >= 3:
                            st.subheader("Performance Radar Chart")
                            
                            # Prepare data for radar chart - use means of each metric
                            radar_data = []
                            
                            for company in selected_companies:
                                company_data = filtered_df[filtered_df['Company'] == company]
                                values = []
                                
                                for metric in selected_metrics:
                                    values.append(company_data[metric].mean())
                                
                                radar_data.append({
                                    'company': company,
                                    'metrics': selected_metrics,
                                    'values': values
                                })
                            
                            # Normalize values for radar chart
                            max_values = []
                            for i in range(len(selected_metrics)):
                                max_val = max([data['values'][i] for data in radar_data])
                                max_values.append(max_val if max_val > 0 else 1)
                            
                            for data in radar_data:
                                data['normalized_values'] = [val/max_val for val, max_val in zip(data['values'], max_values)]
                            
                            # Create radar chart
                            fig = go.Figure()
                            
                            for data in radar_data:
                                fig.add_trace(go.Scatterpolar(
                                    r=data['normalized_values'],
                                    theta=data['metrics'],
                                    fill='toself',
                                    name=data['company']
                                ))
                            
                            fig.update_layout(
                                polar=dict(
                                    radialaxis=dict(
                                        visible=True,
                                        range=[0, 1]
                                    )
                                ),
                                title="Relative Performance Comparison",
                                showlegend=True
                            )
                            
                            st.plotly_chart(fig, use_container_width=True, key=get_unique_key("radar_chart"))
                            st.caption("Note: Values are normalized for comparison. 1.0 represents the highest value among the compared entities.")
                            
                            # Add explanation for radar chart
                            add_plot_description(
                                title="Performance Radar Chart",
                                description="This radar chart provides a multi-dimensional view of performance across all selected metrics. Values are normalized so that the best performer in each metric reaches the outer edge (1.0).",
                                insights=[
                                    "Larger shapes indicate better overall performance across multiple metrics",
                                    "The shape reveals strengths and weaknesses across different metrics",
                                    "A well-rounded shape suggests balanced performance across all metrics",
                                    "Overlapping areas show where companies have similar performance",
                                    "Points reaching the outer edge (1.0) represent the best performer for that metric"
                                ]
                            )
                    elif not has_company_col or len(selected_companies) <= 1:
                        # Create histograms for single dataset (original code)
                        for metric_name in selected_metrics:
                            # Skip if data is mostly null
                            if filtered_df[metric_name].isna().mean() > 0.5:
                                st.info(f"Insufficient data for {metric_name}")
                                continue
                            
                            fig = px.histogram(
                                filtered_df,
                                x=metric_name,
                                title=f"Distribution of {metric_name}"
                            )
                            
                            st.plotly_chart(fig, use_container_width=True, key=get_unique_key(f"hist_{metric_name}"))
                            
                            # Add explanation for histogram
                            metric_friendly_name = metric_name.replace('_', ' ').title()
                            add_plot_description(
                                title=f"Distribution of {metric_friendly_name}",
                                description=f"This histogram shows the frequency distribution of {metric_friendly_name.lower()} values across all data points.",
                                insights=[
                                    "Taller bars indicate more frequent occurrence of those values",
                                    "The spread of the histogram shows the range and variability of the data",
                                    "A bell-shaped distribution suggests normal variation around an average",
                                    "Multiple peaks may indicate distinct groups or scenarios in the data",
                                    "Outliers appear as isolated bars far from the main distribution"
                                ]
                            )
                    else:
                        # Create histograms for single dataset
                        for metric_name in selected_metrics:
                            # Skip if data is mostly null
                            if filtered_df[metric_name].isna().mean() > 0.5:
                                st.info(f"Insufficient data for {metric_name}")
                                continue
                            
                            fig = px.histogram(
                                filtered_df,
                                x=metric_name,
                                title=f"Distribution of {metric_name}"
                            )
                            
                            st.plotly_chart(fig, use_container_width=True, key=get_unique_key(f"hist2_{metric_name}"))
                            
                            # Add explanation for histogram
                            metric_friendly_name = metric_name.replace('_', ' ').title()
                            add_plot_description(
                                title=f"Distribution of {metric_friendly_name}",
                                description=f"This histogram shows the frequency distribution of {metric_friendly_name.lower()} values across all data points.",
                                insights=[
                                    "Taller bars indicate more frequent occurrence of those values",
                                    "The spread of the histogram shows the range and variability of the data",
                                    "A bell-shaped distribution suggests normal variation around an average",
                                    "Multiple peaks may indicate distinct groups or scenarios in the data",
                                    "Outliers appear as isolated bars far from the main distribution"
                                ]
                            )
                
                with viz_tab3:
                    st.subheader("Financial Performance Summary")
                    
                    # Advanced financial summary
                    # Identify key financial metrics
                    revenue_cols = [col for col in filtered_df.columns if 'revenue' in col.lower()]
                    cost_sales_cols = [col for col in filtered_df.columns if 'cost_of_sales' in col.lower()]
                    gross_profit_cols = [col for col in filtered_df.columns if 'gross_profit' in col.lower() and not 'margin' in col.lower()]
                    margin_cols = [col for col in filtered_df.columns if 'margin' in col.lower() or 'gross_profit_margin_pct' in col.lower()]
                    operating_profit_cols = [col for col in filtered_df.columns if 'operating_profit' in col.lower()]
                    profit_period_cols = [col for col in filtered_df.columns if 'profit_for_period' in col.lower()]
                    eps_cols = [col for col in filtered_df.columns if 'earnings_per_share' in col.lower()]
                    yoy_cols = [col for col in filtered_df.columns if 'yoy_change_pct' in col.lower()]
                    
                    # Create a comprehensive financial summary table
                    if has_company_col and len(selected_companies) > 1:
                        # Multi-company financial metrics summary
                        st.subheader("Key Financial Metrics by Company")
                        
                        # Prepare summary table structure
                        summary_metrics = []
                        
                        # Current period metrics
                        current_metrics = {}
                        for prefix in ['Current_', '']:  # Try with prefix first, then without
                            if not current_metrics.get('revenue'):
                                current_rev_col = next((col for col in revenue_cols if prefix.lower() in col.lower()), None)
                                if current_rev_col:
                                    current_metrics['revenue'] = current_rev_col
                            
                            if not current_metrics.get('gross_profit'):
                                current_gp_col = next((col for col in gross_profit_cols if prefix.lower() in col.lower()), None)
                                if current_gp_col:
                                    current_metrics['gross_profit'] = current_gp_col
                            
                            if not current_metrics.get('gross_margin'):
                                current_margin_col = next((col for col in margin_cols if prefix.lower() in col.lower()), None)
                                if current_margin_col:
                                    current_metrics['gross_margin'] = current_margin_col
                            
                            if not current_metrics.get('operating_profit'):
                                current_op_col = next((col for col in operating_profit_cols if prefix.lower() in col.lower()), None)
                                if current_op_col:
                                    current_metrics['operating_profit'] = current_op_col
                            
                            if not current_metrics.get('net_profit'):
                                current_np_col = next((col for col in profit_period_cols if prefix.lower() in col.lower()), None)
                                if current_np_col:
                                    current_metrics['net_profit'] = current_np_col
                            
                            if not current_metrics.get('eps'):
                                current_eps_col = next((col for col in eps_cols if prefix.lower() in col.lower()), None)
                                if current_eps_col:
                                    current_metrics['eps'] = current_eps_col
                        
                        # YoY metrics
                        yoy_metrics = {}
                        for metric in ['revenue', 'gross_profit', 'operating_profit', 'profit_for_period', 'earnings_per_share']:
                            yoy_col = next((col for col in yoy_cols if metric in col.lower()), None)
                            if yoy_col:
                                yoy_metrics[metric] = yoy_col
                        
                        # Build summary table
                        summary_data = []
                        
                        for company in selected_companies:
                            company_data = filtered_df[filtered_df['Company'] == company]
                            row = {'Company': company}
                            
                            # Add current metrics
                            for metric_key, col_name in current_metrics.items():
                                if col_name in company_data.columns:
                                    row[f"{metric_key.replace('_', ' ').title()}"] = company_data[col_name].mean()
                            
                            # Add YoY metrics
                            for metric_key, col_name in yoy_metrics.items():
                                if col_name in company_data.columns:
                                    row[f"{metric_key.replace('_', ' ').title()} YoY %"] = company_data[col_name].mean()
                            
                            summary_data.append(row)
                        
                        if summary_data:
                            summary_df = pd.DataFrame(summary_data)
                            
                            # Format the dataframe for display
                            display_df = summary_df.copy()
                            
                            # Format numeric columns
                            for col in display_df.columns:
                                if col != 'Company':
                                    if 'YoY' in col:
                                        # Format as percentage with 2 decimal places
                                        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A")
                                    elif 'Margin' in col:
                                        # Format as percentage with 2 decimal places
                                        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A")
                                    elif 'EPS' in col:
                                        # Format with 2 decimal places
                                        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")
                                    else:
                                        # Format with thousand separators
                                        display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "N/A")
                            
                            # Display the styled table
                            st.dataframe(display_df, use_container_width=True)
                            
                            # Add explanation for financial summary table
                            add_plot_description(
                                title="Financial Metrics Summary Table",
                                description="This table provides a comprehensive view of key financial metrics for each company, including current period values and year-over-year changes.",
                                insights=[
                                    "Compare absolute values to understand the relative scale of each company",
                                    "Year-over-Year (YoY) percentages show growth rates compared to the previous year",
                                    "Look for companies with both strong absolute numbers and positive growth rates",
                                    "Higher margin percentages indicate better operational efficiency",
                                    "This summary helps identify overall financial leaders across multiple metrics"
                                ]
                            )
                            
                            # Create a downloadable Excel file with the summary
                            if st.button("Generate Financial Summary Report"):
                                # Create a temporary Excel file
                                output = io.BytesIO()
                                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                    summary_df.to_excel(writer, sheet_name='Financial Summary', index=False)
                                    
                                    # Get the xlsxwriter workbook and worksheet objects
                                    workbook = writer.book
                                    worksheet = writer.sheets['Financial Summary']
                                    
                                    # Add formats
                                    header_format = workbook.add_format({
                                        'bold': True, 
                                        'text_wrap': True, 
                                        'valign': 'top', 
                                        'fg_color': '#D7E4BC', 
                                        'border': 1
                                    })
                                    
                                    number_format = workbook.add_format({'num_format': '#,##0'})
                                    percent_format = workbook.add_format({'num_format': '0.00%'})
                                    
                                    # Write the column headers with the header format
                                    for col_num, value in enumerate(summary_df.columns.values):
                                        worksheet.write(0, col_num, value, header_format)
                                    
                                    # Set column formats
                                    for col_num, col_name in enumerate(summary_df.columns):
                                        if col_name != 'Company':
                                            if 'YoY' in col_name or 'Margin' in col_name:
                                                worksheet.set_column(col_num, col_num, 15, percent_format)
                                            else:
                                                worksheet.set_column(col_num, col_num, 15, number_format)
                                        else:
                                            worksheet.set_column(col_num, col_num, 20)
                                
                                # Download button
                                st.download_button(
                                    label="📥 Download Excel Report",
                                    data=output.getvalue(),
                                    file_name="financial_summary_report.xlsx",
                                    mime="application/vnd.ms-excel"
                                )
                        
                        # Add correlation analysis
                        if len(current_metrics) > 1:
                            st.subheader("Correlation Between Key Metrics")
                            
                            # Select only financial columns for correlation
                            financial_cols = [col for metric, col in current_metrics.items()]
                            
                            if len(financial_cols) > 1:
                                corr_df = filtered_df[financial_cols].corr()
                                
                                # Rename columns for better display
                                col_mapping = {col: key.replace('_', ' ').title() for key, col in current_metrics.items()}
                                corr_df = corr_df.rename(columns=col_mapping, index=col_mapping)
                                
                                fig = px.imshow(
                                    corr_df,
                                    color_continuous_scale='RdBu_r',
                                    labels=dict(color="Correlation"),
                                    text_auto=True,
                                    title="Correlation Between Financial Metrics"
                                )
                                
                                fig.update_layout(height=500)
                                st.plotly_chart(fig, use_container_width=True, key=get_unique_key("corr_heatmap"))
                                
                                # Add explanation for correlation heatmap
                                add_plot_description(
                                    title="Correlation Between Financial Metrics",
                                    description="This heatmap shows how different financial metrics correlate with each other. Values range from -1 (perfect negative correlation) to +1 (perfect positive correlation).",
                                    insights=[
                                        "Blue cells indicate positive correlation - metrics that tend to move together",
                                        "Red cells indicate negative correlation - metrics that tend to move in opposite directions",
                                        "Darker colors show stronger relationships between metrics",
                                        "Values close to 0 (light colors) suggest little or no relationship between metrics",
                                        "The diagonal always shows perfect correlation (1.0) as each metric correlates perfectly with itself"
                                    ]
                                )
                    else:
                        # Single company/dataset summary
                        if revenue_cols or gross_profit_cols or operating_profit_cols:
                            # Financial metrics table
                            st.subheader("Financial Metrics Overview")
                            
                            metrics_to_display = {}
                            
                            # Get metrics columns
                            for prefix in ['Current_', '']:  # Try with prefix first, then without
                                if revenue_cols:
                                    rev_col = next((col for col in revenue_cols if prefix.lower() in col.lower()), None)
                                    if rev_col:
                                        metrics_to_display['Revenue'] = rev_col
                                
                                if cost_sales_cols:
                                    cost_col = next((col for col in cost_sales_cols if prefix.lower() in col.lower()), None)
                                    if cost_col:
                                        metrics_to_display['Cost of Sales'] = cost_col
                                
                                if gross_profit_cols:
                                    gp_col = next((col for col in gross_profit_cols if prefix.lower() in col.lower()), None)
                                    if gp_col:
                                        metrics_to_display['Gross Profit'] = gp_col
                                
                                if margin_cols:
                                    margin_col = next((col for col in margin_cols if prefix.lower() in col.lower()), None)
                                    if margin_col:
                                        metrics_to_display['Gross Margin %'] = margin_col
                                
                                if operating_profit_cols:
                                    op_col = next((col for col in operating_profit_cols if prefix.lower() in col.lower()), None)
                                    if op_col:
                                        metrics_to_display['Operating Profit'] = op_col
                                
                                if profit_period_cols:
                                    np_col = next((col for col in profit_period_cols if prefix.lower() in col.lower()), None)
                                    if np_col:
                                        metrics_to_display['Net Profit'] = np_col
                                
                                if eps_cols:
                                    eps_col = next((col for col in eps_cols if prefix.lower() in col.lower()), None)
                                    if eps_col:
                                        metrics_to_display['EPS'] = eps_col
                            
                            if metrics_to_display:
                                # Create a summary table
                                metrics_df = pd.DataFrame({
                                    'Metric': list(metrics_to_display.keys()),
                                    'Mean': [filtered_df[col].mean() for col in metrics_to_display.values()],
                                    'Min': [filtered_df[col].min() for col in metrics_to_display.values()],
                                    'Max': [filtered_df[col].max() for col in metrics_to_display.values()],
                                    'Std Dev': [filtered_df[col].std() for col in metrics_to_display.values()]
                                })
                                
                                # Format the table
                                display_metrics = metrics_df.copy()
                                
                                for col in ['Mean', 'Min', 'Max', 'Std Dev']:
                                    # Format differently based on metric type
                                    for i, metric in enumerate(display_metrics['Metric']):
                                        if 'Margin' in metric or '%' in metric:
                                            display_metrics.loc[i, col] = f"{display_metrics.loc[i, col]:.2f}%"
                                        elif 'EPS' in metric:
                                            display_metrics.loc[i, col] = f"{display_metrics.loc[i, col]:.2f}"
                                        else:
                                            display_metrics.loc[i, col] = f"{display_metrics.loc[i, col]:,.0f}"
                                
                                st.dataframe(display_metrics, use_container_width=True)
                                
                                # Add explanation for metrics overview
                                add_plot_description(
                                    title="Financial Metrics Overview",
                                    description="This table provides summary statistics for key financial metrics across all time periods, including the mean (average), minimum, maximum, and standard deviation.",
                                    insights=[
                                        "The mean shows the central tendency of each metric over time",
                                        "Min and Max values reveal the range and extremes of financial performance",
                                        "Standard deviation (Std Dev) indicates volatility - higher values show more variability",
                                        "Compare metrics to understand the overall financial structure of the business",
                                        "Look for metrics with high variability as they may indicate areas of financial uncertainty"
                                    ]
                                )
                        
                        # Create a standard summary of the whole dataset for other metrics
                        if selected_metrics:
                            other_metrics = [m for m in selected_metrics if m not in 
                                          list(metrics_to_display.values()) if 'metrics_to_display' in locals()]
                            
                            if other_metrics:
                                st.subheader("Other Metrics Summary")
                                summary_df = filtered_df[other_metrics].describe()
                                st.dataframe(summary_df.T)
                                
                                # Add explanation for other metrics summary
                                add_plot_description(
                                    title="Other Metrics Summary Statistics",
                                    description="This table provides comprehensive statistical summaries for all additional selected metrics, including count, mean, standard deviation, minimum, quartiles, and maximum.",
                                    insights=[
                                        "The count shows how many non-null values exist for each metric",
                                        "Quartiles (25%, 50%, 75%) help understand the distribution of values",
                                        "Compare means and medians (50%) to understand if distributions are skewed",
                                        "The standard deviation indicates how spread out the values are",
                                        "Min and max values show the full range of the data"
                                    ]
                                )
                    
                    # If we have YoY metrics, create a special YoY summary section
                    if yoy_cols:
                        st.subheader("Year-over-Year Performance")
                        
                        # Select important YoY metrics
                        important_yoy = [col for col in yoy_cols if any(metric in col.lower() for metric in 
                                                                     ['revenue', 'gross_profit', 'operating_profit', 'profit_for_period', 'earnings_per_share'])]
                        
                        if important_yoy:
                            # For each important YoY metric, create a summary
                            yoy_summary = []
                            
                            for company in selected_companies if has_company_col else ['Dataset']:
                                company_data = filtered_df[filtered_df['Company'] == company] if has_company_col else filtered_df
                                
                                row = {'Entity': company}
                                
                                for yoy_col in important_yoy:
                                    if yoy_col in company_data.columns and not company_data[yoy_col].isna().all():
                                        # Extract metric name for display
                                        metric_name = yoy_col.replace('YoY_Change_Pct_', '').replace('_', ' ').title()
                                        
                                        # Calculate average YoY change
                                        avg_yoy = company_data[yoy_col].mean()
                                        latest_yoy = company_data[yoy_col].iloc[-1] if len(company_data) > 0 else None
                                        
                                        row[f"{metric_name} Avg YoY %"] = avg_yoy
                                        row[f"{metric_name} Latest YoY %"] = latest_yoy
                                
                                yoy_summary.append(row)
                            
                            if yoy_summary:
                                yoy_df = pd.DataFrame(yoy_summary)
                                
                                # Format for display
                                display_yoy = yoy_df.copy()
                                
                                for col in display_yoy.columns:
                                    if col != 'Entity' and 'YoY' in col:
                                        display_yoy[col] = display_yoy[col].apply(
                                            lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A"
                                        )
                                
                                st.dataframe(display_yoy, use_container_width=True)
                                
                                # Add explanation for YoY performance summary
                                add_plot_description(
                                    title="Year-over-Year Performance Summary",
                                    description="This table shows the average and latest year-over-year percentage changes for key financial metrics across entities.",
                                    insights=[
                                        "Positive percentages indicate growth compared to the same period in the previous year",
                                        "Negative percentages show decline compared to the previous year",
                                        "Compare average YoY with latest YoY to see if performance is improving or deteriorating",
                                        "Look for consistent positive growth across multiple metrics as a sign of strong performance",
                                        "Different growth rates across entities help identify market leaders and laggards"
                                    ]
                                )
                                
                                # Visually highlight the YoY performance
                                cols_to_plot = [col for col in yoy_df.columns if 'Avg YoY' in col]
                                
                                if cols_to_plot and has_company_col and len(selected_companies) > 1:
                                    # Create a bar chart for YoY performance comparison
                                    plot_df = pd.melt(
                                        yoy_df, 
                                        id_vars=['Entity'],
                                        value_vars=cols_to_plot,
                                        var_name='Metric',
                                        value_name='YoY %'
                                    )
                                    
                                    # Clean up metric names for display
                                    plot_df['Metric'] = plot_df['Metric'].apply(lambda x: x.replace(' Avg YoY %', ''))
                                    
                                    fig = px.bar(
                                        plot_df,
                                        x='Metric',
                                        y='YoY %',
                                        color='Entity',
                                        barmode='group',
                                        title="Average Year-over-Year Growth by Metric",
                                        labels={'YoY %': 'Average YoY Growth (%)'}
                                    )
                                    
                                    # Add a reference line at y=0
                                    fig.add_shape(
                                        type="line",
                                        x0=-0.5,
                                        y0=0,
                                        x1=len(cols_to_plot) - 0.5,
                                        y1=0,
                                        line=dict(color="red", width=1.5, dash="dash")
                                    )
                                    
                                    # Format y-axis as percentage
                                    fig.update_layout(
                                        yaxis=dict(tickformat='.1f'),
                                        height=500
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True, key=get_unique_key("yoy_bar_chart"))
                                    
                                    # Add explanation for YoY performance chart
                                    add_plot_description(
                                        title="Year-over-Year Growth Comparison",
                                        description="This grouped bar chart compares the average year-over-year growth rates for key metrics across different entities.",
                                        insights=[
                                            "Bars above the red dashed line (0%) indicate positive growth",
                                            "Bars below the line indicate negative growth (decline)",
                                            "Compare different colored bars within each metric to see which entities outperform others",
                                            "Look for entities that consistently show positive growth across all metrics",
                                            "The height of each bar shows the percentage growth rate - taller bars mean faster growth"
                                        ]
                                    )
                    
                    # Correlation matrix (original code)
                    if len(selected_metrics) > 1:
                        st.subheader("Correlation Matrix")
                        
                        corr_df = filtered_df[selected_metrics].corr()
                        
                        fig = px.imshow(
                            corr_df,
                            color_continuous_scale='RdBu_r',
                            labels=dict(color="Correlation"),
                            title="Correlation Between Metrics"
                        )
                        
                        st.plotly_chart(fig, use_container_width=True, key=get_unique_key("full_corr_matrix"))
                        
                        # Add explanation for full correlation matrix
                        add_plot_description(
                            title="Correlation Matrix For All Selected Metrics",
                            description="This heatmap shows the correlation coefficients between all selected metrics, revealing how they move in relation to each other.",
                            insights=[
                                "Blue squares indicate positive correlation (metrics increase or decrease together)",
                                "Red squares indicate negative correlation (when one metric increases, the other decreases)",
                                "Darker colors represent stronger relationships between metrics",
                                "Light-colored squares (values near 0) show metrics that have little relationship",
                                "Look for unexpected relationships that might provide business insights"
                            ]
                        )
                
                # Download option
                col1, col2 = st.columns([4, 1])
                with col2:
                    csv = filtered_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Data",
                        data=csv,
                        file_name="filtered_data.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

# Implement chat page
elif st.session_state.page == "Chat":
    # CHAT PAGE
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Configure Gemini API with the new client approach
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        st.error("GEMINI_API_KEY not found in environment variables")

    st.markdown("<div class='main-header'>Financial Data Analysis Chat</div>", unsafe_allow_html=True)
    st.markdown("""
    Ask questions about the financial metrics data and get detailed business insights from Gemini AI.
    """)
    
    # Show data preview
    with st.expander("Sample Questions", expanded=False):
        sample_questions = [
            "How does EPS correlate with net profit across quarters?",
            "Based on recent trends, what areas should Dipped company focus on to improve profitability?",
            "Which quarter had the most significant increase in net profit for Richarde Pieris Exports?",
            "What is the revenue growth trend over the last 4 quarters for a Dipped company?",
        ]
        for question in sample_questions:
            st.markdown(f"• {question}")

    # Function to query Gemini directly with the entire dataset
    def query_gemini_direct(question, df):
        try:
            # Convert dataframe to CSV string for context - including all rows
            csv_string = df.to_csv(index=False)
            
            # Create a comprehensive prompt with the data context and question
            prompt = f"""
You are a financial analyst and data expert specialized in analyzing business metrics. 
Please analyze the following CSV data and answer the question with precise, detailed insights:

### DATA:
```
{csv_string}
```

### QUESTION: 
{question}

### INSTRUCTIONS:
- Analyze the data precisely and quantitatively to answer the question.
- This is financial report data. Focus on quarterly values across companies.
- Avoid excessive explanation—focus on extracting the required figures and insights.
- Perform any necessary calculations (e.g., growth rates, margins, averages, comparisons) to ensure accurate conclusions.
- Use a clear structure: include headings, bullet points, and numbers to support your analysis.
- Only include relevant insights, patterns, or anomalies that directly help answer the question.
- Keep the response **concise and focused**—do not make it too long.
- Conclude with any concise, actionable recommendations if applicable."""

            # Generate the response with configured parameters
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    max_output_tokens=2048,  # Control max token length
                    temperature=0.2,         # Lower temperature for more precise analysis
                    top_p=0.95,              # Default top_p for balanced selection
                    top_k=40                 # Slightly higher top_k for better quality
                )
            )
            
            # Clean up any HTML artifacts from the response
            cleaned_response = response.text
            cleaned_response = re.sub(r"</?div[^>]*>", "", cleaned_response)
            cleaned_response = re.sub(r"`{0,3}<\/?div[^`]*>`{0,3}", "", cleaned_response)
            cleaned_response = cleaned_response.replace("</div>", "").replace("<div>", "")
            print("---- RAW RESPONSE ----")
            print(response.text)
            print("---- CLEANED RESPONSE ----")
            print(cleaned_response)
            return cleaned_response
        except Exception as e:
            return f"Error querying Gemini: {str(e)}"

    # Main content - chat interface
    st.markdown("### Chat")

    # Initialize the messages list if it's empty
    if len(st.session_state.messages) == 0:
        st.session_state.messages = [{
            "role": "assistant",
            "content": f"I've loaded the financial metrics data with {st.session_state.df.shape[0]} rows and {st.session_state.df.shape[1]} columns. How can I help you analyze it?"
        }]

    # Display chat messages
    for message in st.session_state.messages:
        avatar_url = "https://api.dicebear.com/7.x/bottts/svg?seed=data-assistant" if message["role"] == "assistant" else "https://api.dicebear.com/7.x/personas/svg?seed=user"
        safe_content = html.escape(message["content"]) if message["role"] == "assistant" else message["content"]
        # Display in chat message container
        with st.container():
            if message["role"] == "assistant":
                st.markdown(message["content"], unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="chat-message user">
                    <img class="avatar" src="{avatar_url}">
                    <div class="content">{message['content']}</div>
                </div>
                """, unsafe_allow_html=True)

    # Function to process new messages
    def process_user_message(user_input):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        try:
            with st.spinner('Analyzing your financial data...'):
                # Direct Gemini approach with full dataset
                response = query_gemini_direct(user_input, st.session_state.df)
                
                # Add option to use streaming for faster responses on large outputs
                use_streaming = False  # Set to True to enable streaming
                
                if use_streaming:
                    # For streaming responses (placeholder - would need different UI implementation)
                    placeholder = st.empty()
                    full_response = ""
                    
                    # This would need to be implemented differently since we changed the API call
                    # Would need to use client.models.generate_content_stream instead
                    # Left as a placeholder for future implementation
                    
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    # Regular non-streaming response
                    st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            error_message = f"I encountered an error while analyzing your data: {str(e)}"
            st.session_state.messages.append({"role": "assistant", "content": error_message})

    # Chat input
    user_input = st.chat_input("Ask a question about the financial data...")
    
    if user_input:
        process_user_message(user_input)
        st.rerun()

    # Clear chat button
    if st.sidebar.button("Clear Chat History"):
        st.session_state.messages = [{
            "role": "assistant",
            "content": f"I've loaded the financial metrics data with {st.session_state.df.shape[0]} rows and {st.session_state.df.shape[1]} columns. How can I help you analyze it?"
        }]
        st.rerun()

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("Powered by Google Gemini")
