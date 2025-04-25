import os
import pandas as pd
import requests
from datetime import datetime, timedelta
import re

# Configuration
CSV_FILE = "../results/quarterly_reports_consolidated.csv"  # Your consolidated CSV file
OUTPUT_DIR = "../quarterly_pdfs"  # Directory to save PDFs
YEARS_TO_FETCH = 5  # Number of years back from today to fetch reports

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_date(date_str):
    """Parse date from various formats used in the CSV"""
    # Try different date formats
    date_formats = [
        # Format in your example: "09 Feb 202511:19 PM"
        r"(\d{2}) (\w{3}) (\d{4})(\d{2}):(\d{2}) ([AP]M)",
        # Other potential formats
        r"(\d{2}) (\w{3}) (\d{4}) (\d{2}):(\d{2}) ([AP]M)",
        r"(\d{2})-(\w{3})-(\d{4})",
        r"(\d{2})/(\d{2})/(\d{4})"
    ]
    
    for pattern in date_formats:
        match = re.match(pattern, date_str)
        if match:
            # Extract components based on the pattern
            if pattern == date_formats[0]:  # "09 Feb 202511:19 PM"
                day, month_str, year, hour, minute, am_pm = match.groups()
                # Fix potential issue where year and hour are merged
                if len(year) > 4:
                    year = year[:4]
                    hour = year[4:]
            elif pattern == date_formats[1]:  # "09 Feb 2025 11:19 PM"
                day, month_str, year, hour, minute, am_pm = match.groups()
            elif pattern in [date_formats[2], date_formats[3]]:  # "DD-MMM-YYYY" or "DD/MM/YYYY"
                if pattern == date_formats[2]:
                    day, month_str, year = match.groups()
                else:
                    day, month, year = match.groups()
                    # Convert numeric month to month name
                    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    month_str = months[int(month) - 1]
            
            # Convert month name to number
            months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, 
                      "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
            
            if month_str in months:
                month = months[month_str]
                return datetime(int(year), month, int(day))
    
    print(f"Warning: Could not parse date: {date_str}")
    return None

def sanitize_filename(filename):
    """Sanitize filename to remove invalid characters"""
    # Replace invalid characters with underscores
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def download_pdf(url, output_path):
    """Download PDF from URL and save to file"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                file.write(response.content)
            print(f"✅ Downloaded: {output_path}")
            return True
        else:
            print(f"❌ Failed to download {url}. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")
        return False

def main():
    # Calculate cutoff date (5 years ago from today)
    today = datetime.now()
    cutoff_date = today - timedelta(days=365 * YEARS_TO_FETCH)
    
    print(f"Downloading all reports from {cutoff_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    
    try:
        # Load the CSV file
        df = pd.read_csv(CSV_FILE)
        print(f"Loaded {len(df)} reports from {CSV_FILE}")
        
        # Track statistics
        stats = {
            "total": len(df),
            "within_date_range": 0,
            "download_success": 0,
            "download_failed": 0
        }
        
        # Process each report
        for index, row in df.iterrows():
            company_symbol = row["company_symbol"]
            report_text = row["report_text"]
            pdf_url = row["pdf_url"]
            date_str = row["date_uploaded"]
            
            # Parse date
            report_date = parse_date(date_str)
            
            # Check if it's within the date range (if we have a valid date)
            if not report_date or report_date >= cutoff_date:
                stats["within_date_range"] += 1
                
                # Create filename with company symbol and report text
                filename = f"{company_symbol}_{sanitize_filename(report_text)}.pdf"
                output_path = os.path.join(OUTPUT_DIR, filename)
                
                # Download PDF
                if download_pdf(pdf_url, output_path):
                    stats["download_success"] += 1
                else:
                    stats["download_failed"] += 1
        
        # Print summary
        print("\nDownload Summary:")
        print(f"Total reports in CSV: {stats['total']}")
        print(f"Reports within date range (or date unknown): {stats['within_date_range']}")
        print(f"Successfully downloaded: {stats['download_success']}")
        print(f"Failed to download: {stats['download_failed']}")
        print(f"\nPDFs saved to: {os.path.abspath(OUTPUT_DIR)}")
        
    except Exception as e:
        print(f"Error processing CSV file: {e}")

if __name__ == "__main__":
    main()