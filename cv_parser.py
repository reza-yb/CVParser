import os
import re

import backoff
import pandas as pd
import requests
import json
import pdfplumber
import argparse
import logging
from pathlib import Path
from tqdm import tqdm
import openai
import concurrent.futures

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
HEADERS = {
    "Content-Type": "application/json"
}

openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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


def extract_education_context(text, api_choice, window_size=60):
    """
    Extracts up to 30 words before and after the first occurrence of 'education' in the text.

    :param text: The full text extracted from the PDF.
    :param window_size: Number of words before and after the word 'education' to extract.
    :return: A string with extracted context around the first occurrence of 'education'.
    """
    logging.debug("Extracting context around the word 'education'.")

    if api_choice == "ollama":
        # Find the first occurrence of the word 'education' (case-insensitive) with a word boundary
        pattern = re.compile(r'education', re.IGNORECASE)
        match = pattern.search(text)  # Find the first match only

        if match:
            # Extract 30 words before and after the first match
            end = min(len(text), match.end() + window_size * 6)
            return text[match.start():end]

        logging.warning("No occurrence of 'education' found. processing the first sections of file only")
        return text[:window_size * 6 * 3]  # Return first three sections
    else:
        return text[:window_size * 6 * 20]


def extract_education_history_ollama(text, model="llama3.2"):
    """
    Sends the extracted text context to the Ollama LLM to extract universities for bachelor's, master's, and PhD.

    :param text: The extracted context around the word 'education'.
    :param model: The LLM model to use.
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
        "stream": False
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

    except Exception as err:
        logging.error(f"An error occurred with Ollama API {err}", exc_info=True)

    return None

@backoff.on_exception(backoff.constant, openai.RateLimitError, max_tries=2, interval=30)
def completions_with_backoff(**kwargs):
    return openai_client.chat.completions.create(**kwargs)


def extract_education_history_openai(text, model="gpt-4o-mini"):
    """
    Sends the extracted text context to OpenAI API to extract universities for education trajectory and career trajectory.

    :param text: The extracted context around the word 'education'.
    :param model: The LLM model to use.
    :return: The JSON object with education_trajectory and career_trajectory, or None if failed.
    """
    try:
        prompt = """
        You are an assistant that extracts information from an unstructured CV and returns the needed info in JSON format.
        Extract the following from the given text:
        1. education_trajectory: List the degrees (B.A., M.A., Ph.D.) along with university names and graduation years in this format:
        "B.A., University Name, Year | M.A., University Name, Year | Ph.D., University Name, Year".
        2. career_trajectory: List the career trajectory (university, start year, end year, and position) in this format:
        "University Name, Start Year-End Year, Position | University Name, Start Year-End Year, Position". Beware phd candidate is not a career.
        Only return the JSON object with these two keys: education_trajectory and career_trajectory.
        """

        response = completions_with_backoff(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ]
                },
            ],
            temperature=1,
            max_tokens=350,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            response_format={
                "type": "json_object"
            }
        )

        generated_text = response.choices[0].message.content

        try:
            education_history = json.loads(generated_text)
            if isinstance(education_history, dict):
                return education_history
            else:
                raise ValueError("The extracted data is not a valid JSON object.")
        except (json.JSONDecodeError, ValueError) as e:
            logging.warning(f"Failed to parse the response as JSON. LLM's Response: {generated_text}. Error: {e}")
    except Exception as err:
        logging.error(f"An error occurred with OpenAI API: {err}", exc_info=True)

    return None


def extract_education_history(text, api_choice="openai", model="gpt-4o-mini"):
    """
    Sends the extracted text context to the chosen API (Ollama or OpenAI) to extract universities for bachelor's, master's, and PhD.

    :param text: The extracted context around the word 'education'.
    :param api_choice: The API to use ('ollama' or 'openai').
    :param model: The LLM model to use.
    :return: The JSON object with universities for bachelor's, master's, and PhD, or None if failed.
    """
    if api_choice == "ollama":
        return extract_education_history_ollama(text, model)
    elif api_choice == "openai":
        return extract_education_history_openai(text, model)
    else:
        logging.error(f"Invalid API choice: {api_choice}")
        return None


def process_pdf_file(pdf_path, api_choice="openai"):
    """
    Processes a single PDF file to extract relevant education text and send to the chosen LLM (Ollama or OpenAI).

    :param pdf_path: Path to the PDF file.
    :param api_choice: API choice, either 'ollama' or 'openai'.
    :return: Education history as a dictionary or None if extraction fails.
    """
    logging.info(f"Processing file: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    if not text:
        logging.warning(f"No text extracted from {pdf_path}. Skipping.")
        return None

    education_context = extract_education_context(text, api_choice)
    logging.debug(f"Education context:\n {education_context}")
    if not education_context:
        logging.warning(f"No relevant education context found in {pdf_path}.")
        return None

    education_history = extract_education_history(education_context, api_choice)
    if education_history is None:
        logging.warning(f"Failed to extract education history from {pdf_path}.")
        return None

    logging.info(f"Extracted education history for {pdf_path}: {education_history}")
    return education_history



def main():
    """
    Main entry point for the script. Extracts education history from all PDFs in a directory
    and compiles results into a CSV using multithreading.
    """
    parser = argparse.ArgumentParser(
        description="Extract education history from all PDFs in a directory using Ollama or OpenAI and compile results into a CSV."
    )
    parser.add_argument("input_directory", help="Path to the directory containing PDF files.")
    parser.add_argument("output_csv", help="Path to the output CSV file.")
    parser.add_argument("--api", choices=["ollama", "openai"], default="openai", help="Choose the API to use (ollama or openai).")
    args = parser.parse_args()

    input_dir = Path(args.input_directory)
    output_csv = Path(args.output_csv)

    if not input_dir.is_dir():
        logging.error(f"The input path {input_dir} is not a directory or does not exist.")
        return

    # Find all PDF files in the directory
    pdf_files = sorted(list(input_dir.glob("*.pdf")), key=lambda x: int(x.stem))
    if not pdf_files:
        logging.info(f"No PDF files found in the directory {input_dir}.")
        return

    logging.info(f"Found {len(pdf_files)} PDF files in {input_dir}.")

    # Prepare data for CSV
    csv_data = []

    def worker(pdf_file):
        education_history = process_pdf_file(pdf_file, api_choice=args.api)
        if education_history:
            if args.api == "openai":
                return {
                    "File Name": pdf_file.name,
                    "education_trajectory": education_history.get("education_trajectory", None),
                    "career_trajectory": education_history.get("career_trajectory", None)
                }
            elif args.api == "ollama":
                return {
                    "File Name": pdf_file.name,
                    "Bachelors": education_history.get("bachelors", None),
                    "Masters": education_history.get("masters", None),
                    "PhD": education_history.get("phd", None)
                }
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_pdf = {executor.submit(worker, pdf): pdf for pdf in pdf_files}

        for future in tqdm(concurrent.futures.as_completed(future_to_pdf), total=len(future_to_pdf), desc="Processing PDFs"):
            result = future.result()
            if result:
                csv_data.append(result)

    df = pd.DataFrame(csv_data)
    df['File Name'] = df['File Name'].str.replace('.pdf', '', regex=False).astype(int)
    df.set_index('File Name', inplace=True)
    df.index.name = "Row Number"
    df.sort_index(inplace=True)

    try:
        df.to_csv(output_csv)
        logging.info(f"CSV file has been created at {output_csv}.")
    except Exception as e:
        logging.error(f"Failed to write to CSV file {output_csv}: {e}")

if __name__ == "__main__":
    main()
