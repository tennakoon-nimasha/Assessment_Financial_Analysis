import os
import json
import time
import pandas as pd
import httpx
from tqdm import tqdm
import re
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configuration
PDF_DIR = "../quarterly_pdfs"  # Directory containing downloaded PDFs
OUTPUT_CSV = "../results/financial_metrics.csv"  # Output CSV file
GOOGLE_API_KEY = os.getenv("GOOGLE_STUDIO_API_KEY")  # Replace with your actual Gemini API key

# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

# Create prompt for Gemini API
EXTRACTION_PROMPT = """
Task:
Extract standardized financial data from quarterly/interim reports of different Sri Lankan manufacturing companies for comparative time series analysis.

Objective:
Create a uniform dataset capturing consistently reported financial metrics across different companies to enable direct comparison and visualization of performance trends.

Instructions:
1. First, carefully examine the document to identify:
   - Company name (extract the exact legal entity name)
   - Report type (e.g., "Interim Report", "Quarterly Report")
   - Reporting period information

2. EXACT DATE EXTRACTION (CRITICAL):
   - Find the EXACT reporting period end date as written in the document (typically on cover page, header or in statement titles)
   - Report this date in ISO format (YYYY-MM-DD)
   - Example: Convert "30th June 2020" to "2020-06-30"
   - If only month and year are given (e.g., "June 2020"), use the last day of that month ("2020-06-30")
   - Similarly extract the comparative period end date (previous year's corresponding period)

3. PERIOD DETERMINATION:
   - Specifically identify if the report covers 3 months, 6 months, 9 months, or 12 months
   - This information is usually found in report titles or column headers (e.g., "Three months ended 30th June 2020")

4. ALWAYS prioritize extracting Group/Consolidated figures (not Company-only figures) for standardized comparison.

5. Extract these core financial metrics that appear consistently:
   - Revenue/Turnover (labeled as "Revenue from contracts with customers" or similar)
   - Cost of Sales
   - Gross Profit
   - Gross Profit Margin (%) [calculate if not provided: Gross Profit ÷ Revenue × 100]
   - Operating Profit/Profit from Operations
   - Profit Before Tax
   - Tax Expense
   - Profit for the Period (Net Profit)
   - Basic Earnings Per Share

6. For each metric:
   - Record the exact numeric value with original precision
   - Note the unit of measurement (e.g., Rs. '000)
   - Record both current period and corresponding period of previous year values
   - Calculate year-over-year percentage change if not provided

7. Source information:
   - Specify exactly which statement was used (e.g., "Consolidated Statement of Profit or Loss")
   - List the exact page number(s) where data was extracted from
   - Indicate if the figures are audited or unaudited (usually stated in the report)

Output Format:
Provide the extracted data in a simplified JSON format with the following schema:

{
  "company_info": {
    "name": "Company Name",
    "report_type": "Quarterly/Interim Report"
  },
  "reporting_period": {
    "duration": "3 months/9 months",
    "end_date": "YYYY-MM-DD",  // Ensure ISO format YYYY-MM-DD
    "comparative_end_date": "YYYY-MM-DD",  // Ensure ISO format YYYY-MM-DD
    "audit_status": "Audited/Unaudited"
  },
  "financial_metrics": {
    "currency_unit": "Rs. '000",
    "current_period": {
      "revenue": 0,
      "cost_of_sales": 0,
      "gross_profit": 0,
      "gross_profit_margin_pct": 0.0,
      "operating_profit": 0,
      "profit_before_tax": 0,
      "tax_expense": 0,
      "profit_for_period": 0,
      "earnings_per_share": 0.0
    },
    "comparative_period": {
      "revenue": 0,
      "cost_of_sales": 0,
      "gross_profit": 0,
      "gross_profit_margin_pct": 0.0,
      "operating_profit": 0,
      "profit_before_tax": 0,
      "tax_expense": 0,
      "profit_for_period": 0,
      "earnings_per_share": 0.0
    },
    "yoy_change_pct": {
      "revenue": 0.0,
      "cost_of_sales": 0.0,
      "gross_profit": 0.0,
      "operating_profit": 0.0,
      "profit_before_tax": 0.0,
      "tax_expense": 0.0,
      "profit_for_period": 0.0,
      "earnings_per_share": 0.0
    }
  },
  "source_information": {
    "statement_used": "Consolidated Income Statement/Statement of Profit or Loss",
    "page_numbers": [0]
  }
}

IMPORTANT NOTES ON DATE EXTRACTION:
- Quarter end dates typically follow standard patterns:
  * Q1: March 31, YYYY (for calendar year companies)
  * Q2: June 30, YYYY
  * Q3: September 30, YYYY
  * Q4: December 31, YYYY
- When date appears with ordinal suffixes (e.g., "30th June 2020"), convert to ISO format
- Pay special attention to the main financial statements and their headers which often contain the exact reporting period dates
- For Sri Lankan companies, please convert any dates to ISO format YYYY-MM-DD
- Make sure both current period and comparative period dates are in the same format

Note: If a specific field is not reported by a company, represent it as null rather than 0.
"""

def extract_financial_data_from_pdf(pdf_path):
    """Extract financial data from PDF using Gemini API"""
    try:
        print(f"Uploading file: {pdf_path}")
        
        # Upload the PDF using the Gemini File API
        file_part = genai.upload_file(pdf_path)
        
        # Get a model instance with the appropriate configuration
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.0,  # Use a low temperature for factual extraction
                "top_p": 0.95,
                "top_k": 0,
                "max_output_tokens": 4096,  # Increase token limit for detailed extraction
            }
        )
        
        # Call Gemini API with the uploaded file and prompt
        response = model.generate_content(
            [file_part, EXTRACTION_PROMPT],
            stream=False
        )
        
        # Get the response text
        if hasattr(response, 'text'):
            result_text = response.text
        else:
            result_text = str(response)
        
        # Extract JSON from text (handling potential extra text)
        try:
            # Find JSON object by looking for patterns
            json_match = re.search(r'(\{[\s\S]*\})', result_text)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            else:
                print(f"No JSON found in response. Response preview: {result_text[:200]}...")
                return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print(f"Raw response text: {result_text[:200]}...")
            return None
            
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

def validate_date_format(date_str):
    """Validate that the date is in YYYY-MM-DD format"""
    if not date_str:
        return False
    
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    return bool(re.match(pattern, date_str))

def determine_quarter(date_str):
    """Determine quarter based on date in YYYY-MM-DD format"""
    if not date_str or not validate_date_format(date_str):
        return "Unknown"
        
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        month = date_obj.month
        year = date_obj.year
        
        if 1 <= month <= 3:
            quarter = "Q1"
        elif 4 <= month <= 6:
            quarter = "Q2"
        elif 7 <= month <= 9:
            quarter = "Q3"
        else:
            quarter = "Q4"
            
        return f"{quarter} {year}"
    except:
        return "Unknown"

def process_pdfs():
    """Process all PDFs and compile results"""
    if not os.path.exists(PDF_DIR):
        print(f"Error: PDF directory '{PDF_DIR}' not found.")
        return
    
    # List all PDF files
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in '{PDF_DIR}'.")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process.")
    
    # Initialize results list
    results = []
    
    # Process each PDF
    for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        
        print(f"\nProcessing: {pdf_file}")
        
        try:
            # Extract data using Gemini API
            data = extract_financial_data_from_pdf(pdf_path)
            
            if data:
                # Extract company information
                company_info = data.get("company_info", {})
                company_name = company_info.get("name", "Unknown")
                report_type = company_info.get("report_type", "Unknown")
                
                # Extract reporting period information
                reporting_period = data.get("reporting_period", {})
                duration = reporting_period.get("duration", "Unknown")
                end_date = reporting_period.get("end_date", "")
                comparative_end_date = reporting_period.get("comparative_end_date", "")
                audit_status = reporting_period.get("audit_status", "Unknown")
                
                # Validate date formats
                if not validate_date_format(end_date):
                    print(f"⚠️ Warning: Current period date '{end_date}' is not in YYYY-MM-DD format")
                
                if not validate_date_format(comparative_end_date):
                    print(f"⚠️ Warning: Comparative period date '{comparative_end_date}' is not in YYYY-MM-DD format")
                
                # Determine quarter based on date
                quarter_year = determine_quarter(end_date)
                
                # Extract financial metrics
                financial_metrics = data.get("financial_metrics", {})
                currency_unit = financial_metrics.get("currency_unit", "Rs. '000")
                
                # Get current period metrics
                current_period = financial_metrics.get("current_period", {})
                
                # Get comparative period metrics
                comparative_period = financial_metrics.get("comparative_period", {})
                
                # Get YoY change percentages
                yoy_change_pct = financial_metrics.get("yoy_change_pct", {})
                
                # Get source information
                source_info = data.get("source_information", {})
                statement_used = source_info.get("statement_used", "Unknown")
                page_numbers = source_info.get("page_numbers", [])
                if isinstance(page_numbers, list):
                    page_numbers_str = ", ".join(map(str, page_numbers))
                else:
                    page_numbers_str = str(page_numbers)
                
                # Create result record
                result = {
                    "Company": company_name,
                    "Quarter_Year": quarter_year,
                    "Duration": duration,
                    "Period_End_Date": end_date,
                    "Comparative_Period_End_Date": comparative_end_date,
                    "Audit_Status": audit_status,
                    "Currency_Unit": currency_unit,
                    "Report_Type": report_type,
                    "Statement_Used": statement_used,
                    "Page_Numbers": page_numbers_str,
                    "PDF_Filename": pdf_file
                }
                
                # Add current period metrics with prefix
                for key, value in current_period.items():
                    result[f"Current_{key}"] = value
                
                # Add comparative period metrics with prefix
                for key, value in comparative_period.items():
                    result[f"Comparative_{key}"] = value
                
                # Add YoY change percentages with prefix
                for key, value in yoy_change_pct.items():
                    result[f"YoY_Change_Pct_{key}"] = value
                
                results.append(result)
                print(f"✅ Successfully extracted data. Period end date: {end_date}")
            else:
                print(f"❌ Failed to extract data from {pdf_file}")
            
            # Add delay to avoid API rate limits
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error processing {pdf_file}: {e}")
    
    # Create DataFrame
    if results:
        df = pd.DataFrame(results)
        
        # Save to CSV
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\nFinished processing {len(results)} PDFs.")
        print(f"Results saved to {OUTPUT_CSV}")
        
        # Print summary of extracted dates
        print("\nDate Extraction Summary:")
        for i, result in enumerate(results):
            company = result.get("Company", "Unknown")
            end_date = result.get("Period_End_Date", "Unknown")
            quarter = result.get("Quarter_Year", "Unknown")
            print(f"{i+1}. {company}: {end_date} ({quarter})")
    else:
        print("No data was extracted from PDFs.")

if __name__ == "__main__":
    # Check if API key is set
    if not GOOGLE_API_KEY:
        print("Error: Please set your Google API key in the .env file.")
    else:
        process_pdfs()