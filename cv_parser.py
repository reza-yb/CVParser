import re
import requests
import json
import pdfplumber
import argparse
import csv
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define the API endpoint
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Define the headers
HEADERS = {
    "Content-Type": "application/json"
}


def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a PDF file using pdfplumber.

    :param pdf_path: Path to the PDF file.
    :return: Extracted text as a string or None if an error occurs.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except FileNotFoundError:
        logging.error(f"The file {pdf_path} was not found.")
    except Exception as e:
        logging.error(f"An error occurred while extracting text from {pdf_path}: {e}")
    return None


def extract_education_context(text, window_size=60):
    """
    Extracts up to 30 words before and after the first occurrence of 'education' in the text.

    :param text: The full text extracted from the PDF.
    :param window_size: Number of words before and after the word 'education' to extract.
    :return: A string with extracted context around the first occurrence of 'education'.
    """
    logging.debug("Extracting context around the word 'education'.")

    # Find the first occurrence of the word 'education' (case-insensitive) with a word boundary
    pattern = re.compile(r'education', re.IGNORECASE)
    match = pattern.search(text)  # Find the first match only

    if match:
        # Extract 30 words before and after the first match
        end = min(len(text), match.end() + window_size * 6)
        return text[match.start():end]

    logging.warning("No occurrence of 'education' found. processing the first sections of file only")
    return text[:window_size*6*3]  # Return first three sections


def extract_education_history(text, model="llama3.2", stream=False):
    """
    Sends the extracted text context to the LLM to extract universities for bachelor's, master's, and PhD.

    :param text: The extracted context around the word 'education'.
    :param model: The LLM model to use.
    :param stream: Whether to stream the response.
    :return: The JSON object with universities for bachelor's, master's, and PhD, or None if failed.
    """
    prompt = (
        "Extract the universities for bachelor's, master's, and PhD from the text. "
        "Return a JSON like: {\"bachelors\": \"uni name or null\", \"masters\": \"uni name or null\", \"phd\": \"uni name or null\"}.\n\n"
        f"Text: {text}\n\n"
        "Give only the JSON."
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream
    }

    try:
        response = requests.post(OLLAMA_API_URL, headers=HEADERS, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        generated_text = result.get("response") or result.get("generated_text") or ""

        try:
            education_history = json.loads(generated_text.strip())
            if isinstance(education_history, dict):
                for degree in ["bachelors", "masters", "phd"]:
                    if education_history.get(degree) == "null":
                        education_history[degree] = None
                return education_history
            else:
                raise ValueError("The extracted data is not a valid JSON object.")
        except (json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Failed to parse the response as JSON. LLM's Response: {generated_text}. Error: {e}")

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err} - {response.text}")
    except requests.exceptions.ConnectionError:
        logging.error("Failed to connect to the LLM. Is the service running?")
    except requests.exceptions.Timeout:
        logging.error("The request timed out.")
    except requests.exceptions.RequestException as err:
        logging.error(f"An error occurred: {err}")

    return None


def process_pdf_file(pdf_path):
    """
    Processes a single PDF file to extract relevant education text and send to the LLM.

    :param pdf_path: Path to the PDF file.
    :return: Education history as a dictionary or None if extraction fails.
    """
    logging.info(f"Processing file: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    if not text:
        logging.warning(f"No text extracted from {pdf_path}. Skipping.")
        return None

    education_context = extract_education_context(text)
    logging.debug(f"Education context:\n {education_context}")
    if not education_context:
        logging.warning(f"No relevant education context found in {pdf_path}.")
        return None

    education_history = extract_education_history(education_context)
    if education_history is None:
        logging.warning(f"Failed to extract education history from {pdf_path}.")
        return None

    logging.info(f"Extracted education history for {pdf_path}: {education_history}")
    return education_history


def main():
    """
    Main entry point for the script. Extracts education history from all PDFs in a directory
    and compiles results into a CSV.
    """
    parser = argparse.ArgumentParser(
        description="Extract education history from all PDFs in a directory using Ollama and compile results into a CSV."
    )
    parser.add_argument("input_directory", help="Path to the directory containing PDF files.")
    parser.add_argument("output_csv", help="Path to the output CSV file.")
    args = parser.parse_args()

    input_dir = Path(args.input_directory)
    output_csv = Path(args.output_csv)

    if not input_dir.is_dir():
        logging.error(f"The input path {input_dir} is not a directory or does not exist.")
        return

    # Find all PDF files in the directory
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        logging.info(f"No PDF files found in the directory {input_dir}.")
        return

    logging.info(f"Found {len(pdf_files)} PDF files in {input_dir}.")

    # Prepare data for CSV
    csv_data = []
    for pdf_file in pdf_files:
        education_history = process_pdf_file(pdf_file)
        if education_history:
            csv_data.append({
                "File Name": pdf_file.name,
                "Bachelors": education_history.get("bachelors", None),
                "Masters": education_history.get("masters", None),
                "PhD": education_history.get("phd", None)
            })

    # Write to CSV
    try:
        with open(output_csv, mode='w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["File Name", "Bachelors", "Masters", "PhD"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for row in csv_data:
                writer.writerow(row)
        logging.info(f"CSV file has been created at {output_csv}.")
    except Exception as e:
        logging.error(f"Failed to write to CSV file {output_csv}: {e}")


if __name__ == "__main__":
    main()
