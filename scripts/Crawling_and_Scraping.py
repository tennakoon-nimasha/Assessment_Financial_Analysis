import os
import csv
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
API_KEY = "fc-4ff7aca975c84b53b1ff3151f5c26fc4"
COMPANY_URLS = [
    'https://www.cse.lk/pages/company-profile/company-profile.component.html?symbol=DIPD.N0000',
    'https://www.cse.lk/pages/company-profile/company-profile.component.html?symbol=REXP.N0000'
]

# Create directories for storing data
os.makedirs("../markdown", exist_ok=True)
os.makedirs("../html", exist_ok=True)

def get_company_name(url):
    """Extract company symbol and return full name"""
    symbol = url.split('symbol=')[1]
    if symbol == "DIPD.N0000":
        return "Dipped Products PLC", symbol
    elif symbol == "REXP.N0000":
        return "Richard Pieris Exports PLC", symbol
    else:
        return f"Unknown Company ({symbol})", symbol

def scrape_company_page(url):
    """Scrape company page and save HTML content to markdown file"""
    company_name, symbol = get_company_name(url)
    print(f"Scraping data for {company_name} ({symbol})...")
    
    # Create API request
    api_url = "https://api.firecrawl.dev/v1/scrape"
    payload = {
        "url": url,
        "formats": ["html"],
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Send request
    response = requests.post(api_url, json=payload, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: Failed to scrape {company_name}. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
    # Save response to markdown file
    markdown_file = f"markdown/{symbol}.md"
    with open(markdown_file, "w", encoding="utf-8") as file:
        file.write(response.text)
    
    print(f"✅ Data for {company_name} saved to {markdown_file}")
    return markdown_file

def extract_quarterly_reports(markdown_file):
    """Extract quarterly reports from markdown file"""
    company_name, symbol = get_company_name(f"https://www.cse.lk/pages/company-profile/company-profile.component.html?symbol={os.path.basename(markdown_file).split('.')[0]}")
    
    # Load markdown file
    with open(markdown_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Try to extract JSON structure that contains HTML
    try:
        data_old = json.loads(content)
        data = data_old.get("data", {})
        html_content = data.get("html", "")
    except json.JSONDecodeError:
        print(f"Failed to parse {markdown_file} as JSON. Please check the format.")
        return []
    
    # Save HTML content to .html file
    html_file = f"html/{symbol}.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # Parse HTML and extract quarterly reports
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Try to find the quarterly reports tab
    quarterly_tab = None
    
    # Look for tab with ID "21b" (common ID for quarterly reports tab)
    quarterly_tab = soup.find("div", id="21b")
    
    # If not found by ID, try to find by tab title
    if not quarterly_tab:
        # Look for tabs with "Quarterly Reports" text
        tabs = soup.find_all("li", class_="nav-item")
        for tab in tabs:
            if "Quarterly Reports" in tab.get_text():
                tab_id = tab.find("a").get("href", "").replace("#", "")
                quarterly_tab = soup.find("div", id=tab_id)
                break
    
    reports = []
    
    if quarterly_tab:
        # Look for table rows
        rows = quarterly_tab.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                try:
                    date_uploaded = cells[0].get_text(strip=True).split("\n")[0]
                    report_text = cells[1].get_text(strip=True)
                    
                    # Extract PDF link
                    pdf_link_tag = cells[1].find("a", href=True)
                    pdf_link = ""
                    if pdf_link_tag and ".pdf" in pdf_link_tag['href']:
                        pdf_link = pdf_link_tag['href']
                        # Make relative URLs absolute
                        if pdf_link.startswith("/"):
                            pdf_link = f"https://www.cse.lk{pdf_link}"
                    
                    # Only add if we have a PDF link
                    if pdf_link:
                        # Extract quarter and year information from report text
                        quarter_info = ""
                        year_info = ""
                        
                        # Attempt to parse date from report text (common formats)
                        for date_format in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]:
                            try:
                                # Look for date patterns in the report text
                                for word in report_text.split():
                                    try:
                                        date_obj = datetime.strptime(word, date_format)
                                        year_info = str(date_obj.year)
                                        
                                        # Determine quarter based on month
                                        month = date_obj.month
                                        if 1 <= month <= 3:
                                            quarter_info = "Q1"
                                        elif 4 <= month <= 6:
                                            quarter_info = "Q2"
                                        elif 7 <= month <= 9:
                                            quarter_info = "Q3"
                                        else:
                                            quarter_info = "Q4"
                                        
                                        break
                                    except ValueError:
                                        continue
                                if year_info:
                                    break
                            except ValueError:
                                continue
                        
                        reports.append({
                            "company_name": company_name,
                            "company_symbol": symbol,
                            "date_uploaded": date_uploaded,
                            "report_text": report_text,
                            "quarter": quarter_info,
                            "year": year_info,
                            "pdf_url": pdf_link
                        })
                except Exception as e:
                    print(f"Error processing row: {e}")
    else:
        print(f"Warning: Could not find quarterly reports tab in {markdown_file}")
    
    print(f"📄 Extracted {len(reports)} quarterly reports for {company_name}")
    return reports

def main():
    """Main function to scrape data and create consolidated CSV"""
    all_reports = []
    
    # Step 1: Scrape each company page
    markdown_files = []
    for url in COMPANY_URLS:
        markdown_file = scrape_company_page(url)
        if markdown_file:
            markdown_files.append(markdown_file)
    
    # Step 2: Extract quarterly reports from each markdown file
    for markdown_file in markdown_files:
        reports = extract_quarterly_reports(markdown_file)
        all_reports.extend(reports)
    
    # Step 3: Save consolidated reports to CSV
    if all_reports:
        csv_file_path = "../results/quarterly_reports_consolidated.csv"
        with open(csv_file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["company_name", "company_symbol", "date_uploaded", "report_text", "quarter", "year", "pdf_url"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_reports)
        
        print(f"\n✅ Consolidated {len(all_reports)} quarterly reports from {len(markdown_files)} companies to {csv_file_path}")
        
        # Print summary
        company_counts = {}
        for report in all_reports:
            company = report["company_name"]
            if company not in company_counts:
                company_counts[company] = 0
            company_counts[company] += 1
        
        print("\nSummary by company:")
        for company, count in company_counts.items():
            print(f"- {company}: {count} reports")
    else:
        print("No quarterly reports were found. Please check the extraction process.")

if __name__ == "__main__":
    main()