# Financial Data Analysis Platform

A comprehensive solution for scraping, processing, and analyzing financial data from quarterly reports of Sri Lankan manufacturing companies.

## Overview

This project automates the collection and analysis of financial data from company quarterly reports, enabling comparative time series analysis across different entities. The platform consists of several components:

1. **Web Scraping**: Automates the collection of quarterly report links from company websites
2. **PDF Download**: Downloads financial report PDFs for specified companies
3. **Data Extraction**: Uses Gemini API to extract standardized financial metrics from PDFs
4. **Interactive Dashboard**: Visualizes the collected financial data with customizable views
5. **AI-Powered Chat**: Provides data analysis through conversational interface

## Requirements

- Python 3.8+
- Google Gemini API key
- FireCrawl API key (for web scraping)
- Required Python libraries (see installation)

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd financial-data-analysis
```

2. Create and activate a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your API keys:

```
GOOGLE_STUDIO_API_KEY=your_gemini_api_key
GEMINI_API_KEY=your_gemini_api_key
```

## Project Structure

```
financial-data-analysis/
├── Crawling_and_Scraping.py     # Web scraping component
├── Download_Reports.py          # PDF download component
├── Extraction_Financial_Data.py # Financial data extraction component
├── StreamlitUI.py               # Interactive dashboard and chat UI
├── quarterly_pdfs/              # Directory for downloaded PDFs
├── results/                     # Directory for processed data
│   └── financial_metrics.csv    # Consolidated financial metrics
└── markdown/                    # Directory for scraped content
└── html/                        # Directory for processed HTML
```

## Usage

The project workflow consists of four main steps:

### 1. Web Scraping

This script scrapes quarterly report links from company websites on the Colombo Stock Exchange.

```bash
python Crawling_and_Scraping.py
```

Currently configured for:
- Dipped Products PLC (DIPD.N0000)
- Richard Pieris Exports PLC (REXP.N0000)

To add more companies, update the `COMPANY_URLS` list in the script.

### 2. Download Reports

Downloads the PDF reports identified in the previous step.

```bash
python Download_Reports.py
```

The script is configured to download reports from the last 5 years, but this can be adjusted by changing the `YEARS_TO_FETCH` variable.

### 3. Extract Financial Data

Uses Google's Gemini API to extract standardized financial data from the PDFs.

```bash
python Extraction_Financial_Data.py
```

This script:
- Processes each PDF in the `quarterly_pdfs/` directory
- Extracts key financial metrics using Gemini's AI capabilities
- Consolidates the data into `results/financial_metrics.csv`

### 4. Interactive Dashboard

Launch the Streamlit dashboard to visualize and analyze the data:

```bash
streamlit run StreamlitUI.py
```

The dashboard offers:
- **Time Series Analysis**: Visualize metrics over time
- **Company Comparisons**: Compare performance across different companies
- **Summary Statistics**: View key financial indicators at a glance
- **AI-Powered Chat**: Ask natural language questions about the data

## Dashboard Features

### Analysis Dashboard

The dashboard provides several visualization tabs:

1. **Time Series**: Track financial metrics over time
   - Revenue & Profitability trends
   - Operating & Net Profit analysis
   - Earnings Per Share progression

2. **Comparisons**: Compare performance across companies
   - Revenue vs Cost Analysis
   - Year-over-Year growth heatmaps
   - Profit Breakdown Analysis

3. **Summary**: View aggregated financial performance data
   - Key Financial Metrics by Company
   - Correlation Between Metrics
   - Year-over-Year Performance Summary
