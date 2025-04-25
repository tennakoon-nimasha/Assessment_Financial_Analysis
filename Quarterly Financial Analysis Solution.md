**Quarterly Financial Analysis Solution**

**Approach and Methodology**

This solution provides an end-to-end pipeline for extracting, analyzing, and visualizing
financial data from quarterly reports of selected companies listed on the Colombo Stock
Exchange (CSE). The solution follows a modular architecture with four primary
components:

1. **Data Scraping** : Scraping the information from the relevant URLs.
2. **PDF Download** : Identifying and downloading the pdfs for the quarterly financial
    documents.
3. **Financial Data Extraction** : AI-powered extraction of structured financial metrics
4. **Interactive Dashboard** : Comprehensive visualization platform with AI query
    capabilities

**Technology Stack**

- **Web Scraping** : Firecrawl and Beautiful Soup
- **PDF Processing** : Google Gemini API for document understanding
- **Data Processing** : Pandas for structured data manipulation
- **Visualization** : Streamlit for application framework, Plotly for interactive charts
- **AI Components** : LangChain with Google Gemini LLM for natural language querying

**Assumptions**

1. **Report Structure** : While quarterly reports follow a general structure (Income
    Statement, Statement of Financial Position), there are variations in terminology and
    presentation between companies and over time.
2. **Data Consistency** : Financial reporting metrics like Revenue, Gross Profit, and Net
    Income are consistently reported across quarters, though naming conventions may
    vary.
3. **Group vs. Company Figures** : Group figures are prioritized over Company-only
    figures.
4. **Time Period** : Reports from the last 5 years from the current date were used for the
    analysis.


**Data Processing Pipeline**

**Step 1: Web Scraping (Crawling_and_Scraping.py)**

The scraping module targets the CSE website to identify and catalog quarterly reports for
the specified companies:

- Dipped Products PLC (DIPD.N0000)
- Richard Pieris Exports PLC (REXP.N0000)

**Implementation Details** :

- Uses FireCrawl API to access company profile pages with proper headers
- Identifies quarterly reports section and extracts report metadata
- Captures key information including upload date, report description, and PDF URL
- Outputs a consolidated CSV with all report details

**Step 2: PDF Download (Download_Reports.py)**

The download module systematically retrieves PDF reports for local processing:

**Implementation Details** :

- Parses various date formats found in the CSV using regex patterns
- Filters reports to focus on the past 5 years
- Creates sanitized filenames based on company symbol and report description
- Implements robust error handling for download failures

**Step 3: Financial Data Extraction (Extraction_Financial_Data.py)**

This critical module extracts structured financial metrics from unstructured PDF reports:

**Implementation Details** :

- Uses Google's Gemini API with a detailed extraction prompt
- Instructs the AI to identify and extract standardized financial metrics
- Validates extracted data, particularly date formats
- Maps financial periods to standard quarters (Q1-Q4)
- Consolidates all extracted metrics into a structured dataset


**Handling Data Inconsistencies** :

- Processes varying financial statement formats and terminology
- Normalizes metrics to common units for comparison
- Handles missing values with appropriate null representations
- Calculates derived metrics (e.g., margins, YoY changes) when not explicitly provided

**Extracted Financial Metrics** :

- Revenue/Turnover
- Cost of Sales
- Gross Profit
- Gross Profit Margin (%)
- Operating Profit
- Profit Before Tax
- Tax Expense
- Profit for the Period (Net Profit)
- Basic Earnings Per Share

**Step 4: Data Visualization (StreamlitUI.py)**

The dashboard component provides an interactive interface for exploring and analyzing the
financial data:

**Implementation Details** :

- Streamlit-based web application with responsive design
- Multi-tab interface for different analysis perspectives:
    o Time Series analysis of key metrics
    o Company Comparisons for benchmarking
    o Financial Summary with statistical insights
- Interactive filtering by company, time period, and metrics
- AI-powered chat assistant for natural language data querying


**Visualization Features** :

- Revenue and profit trend analysis with YoY comparisons
- Profit margin breakdown and analysis
- Company performance benchmarking
- Financial metric correlation analysis
- Performance heatmaps for quick pattern identification
- Downloadable summary reports

**Dataset Structure**

The solution produces a comprehensive financial dataset with the following structure:

**Company Information** :

- Company name
- Quarter and year
- Reporting period duration
- Period end dates (current and comparative)
- Audit status
- Currency unit
- Source information

**Financial Metrics (Current Period)** :

- Revenue
- Cost of Sales
- Gross Profit
- Gross Profit Margin (%)
- Operating Profit
- Profit Before Tax
- Tax Expense
- Profit for Period


- Earnings Per Share

**Financial Metrics (Comparative Period)** :

- Same metrics as current period, for the previous year's corresponding period

**Year-over-Year Changes** :

- Percentage changes for all key metrics

**Limitations and Challenges**

1. **PDF Extraction Accuracy** : Financial data extraction from PDFs is challenging due to
    varying formats, tables, and layouts across reports. The solution uses advanced AI
    capabilities but still requires validation for edge cases.
2. **Report Availability** : The availability and consistency of quarterly reports varied
    between companies and across time periods.
3. **Terminology Variations** : Financial statement line items use different terminology
    across companies and reporting periods, requiring robust mapping strategies.
4. **Unit Consistency** : Reports sometimes use different units (thousands vs. millions)
    or currencies, requiring normalization for accurate comparison.
5. **Gemini API Limitations** : The AI extraction process has rate limits and token
    constraints that impact processing speed for large report batches.

**LLM-Driven Query System**

The dashboard incorporates an AI-powered chat assistant that enables natural language
querying of the financial data:

**Implementation Details** :

- Uses the Google Gemini API to create the chat interface
- Provides conversational interface with suggested queries

The query system demonstrates practical capabilities while maintaining realistic context
window limitations. The LLM processes and responds to questions within the context of the
loaded financial dataset, providing both textual analysis and generating appropriate
visualizations.

**Conclusion**


This solution delivers a comprehensive pipeline for extracting, processing, and analyzing
financial data from quarterly reports. The interactive dashboard and AI-powered query
system provide powerful tools for financial analysis and decision-making. The standardized
dataset enables direct comparison of financial performance across companies and time
periods, offering valuable insights into the financial health and trends of the selected CSE-
listed companies.


