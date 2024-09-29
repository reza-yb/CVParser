import os
import pandas as pd
import requests
from urllib.parse import urlparse
from tqdm import tqdm
import zipfile
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

EXCEL_FILE = 'JobPlacements.xlsx'  # Path to your Excel file
SHEET_NAME = 'AP Subset'  # Name of the sheet containing links
COLUMN_NAME = 'Website/Linkedin/CV'  # Column with the URLs
OUTPUT_DIR = 'cvs'  # Directory to save downloaded PDFs
ZIP_FILENAME = 'cvs.zip'  # Name of the output ZIP file
TIMEOUT = 10  # Timeout for HTTP requests
ROW_RANGE = (0, 6000)  # Rows to be processed (start, end)
LOG_FILE = 'job_placement_download.log'  # Log file path
MAX_THREADS = 10  # Maximum number of concurrent threads

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Create output directory if it doesn't exist
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    logging.info(f"Created directory: {OUTPUT_DIR}")

# Read the Excel file
try:
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, usecols=[COLUMN_NAME])
    logging.info(f"Successfully read Excel file: {EXCEL_FILE}")
except Exception as e:
    logging.error(f"Error reading Excel file: {e}")
    exit(1)

# Select the specified range of links
try:
    selected_rows = df.iloc[ROW_RANGE[0]:ROW_RANGE[1]].dropna(subset=[COLUMN_NAME])
    links = selected_rows[COLUMN_NAME].tolist()
    row_numbers = selected_rows.index.tolist()  # Get actual Excel row numbers
    logging.info(f"Selected links from rows {ROW_RANGE[0]} to {ROW_RANGE[1]}")
except Exception as e:
    logging.error(f"Error selecting links from the Excel sheet: {e}")
    exit(1)


def is_pdf_url(url):
    parsed = urlparse(url)
    return parsed.path.lower().endswith('.pdf')


def download_pdf(url, save_path, row_num):
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        logging.info(f"Successfully downloaded PDF from for row {row_num}: {url}")
        return True
    except Exception as e:
        logging.error(f"Error downloading {url} (row {row_num}): {e}")
        return False


def modify_dropbox_link(link):
    """
    Modify Dropbox link for direct download.
    """
    if "dropbox.com" in link:
        if "dl=0" in link:
            return link.replace("dl=0", "dl=1")
        else:
            return f"{link}&dl=1"
    return link


def process_link(link, row_num):
    # Modify link if it's a Dropbox link
    pdf_url = modify_dropbox_link(link)

    if not is_pdf_url(pdf_url):
        logging.warning(f"Link at row {row_num} is not directly pointing to a PDF: {pdf_url}")
        return False

    filename = f"{row_num}.pdf"  # Use the actual Excel row number for the filename
    save_path = os.path.join(OUTPUT_DIR, filename)
    return download_pdf(pdf_url, save_path, row_num)


# Process links with ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures = {executor.submit(process_link, link, row_num+2): (link, row_num+2) for link, row_num in
               zip(links, row_numbers)}

    for future in tqdm(as_completed(futures), total=len(futures), desc="Processing links"):
        link, row_num = futures[future]
        try:
            success = future.result()
            if not success:
                logging.warning(f"Failed to download PDF for row {row_num} from {link}")
        except Exception as e:
            logging.error(f"Error in processing link {link} (row {row_num}): {e}")

# Create ZIP archive
try:
    with zipfile.ZipFile(ZIP_FILENAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = file  # To avoid including the folder structure
                zipf.write(file_path, arcname)
    logging.info(f"All PDFs have been downloaded and zipped into {ZIP_FILENAME}")
except Exception as e:
    logging.error(f"Error creating ZIP file {ZIP_FILENAME}: {e}")
