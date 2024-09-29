# CV Parser and Downloader

A Python-based project for downloading CVs from an Excel sheet and extracting educational history using a Language Model (LLM) via the Ollama API. This tool automates the process of fetching CVs, parsing relevant educational information, and compiling the results into a structured CSV file.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Ollama Integration](#ollama-integration)
  - [What is Ollama?](#what-is-ollama)
  - [Setting up Ollama](#setting-up-ollama)
  - [How This Project Uses Ollama](#how-this-project-uses-ollama)
- [Usage](#usage)
  - [Downloading CVs](#downloading-cvs)
  - [Parsing CVs](#parsing-cvs)
- [Configuration](#configuration)
- [Logging](#logging)
- [License](#license)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)

## Features

- **CV Downloading**: Automatically download CVs from URLs listed in an Excel file.
- **Batch Processing**: Supports downloading multiple CVs concurrently for efficiency.
- **PDF Parsing**: Extracts text from downloaded PDF CVs.
- **Educational History Extraction**: Utilizes a Language Model to identify and extract educational qualifications.
- **CSV Compilation**: Aggregates the extracted data into a structured CSV file for easy analysis.
- **Logging**: Comprehensive logging for monitoring and troubleshooting.

## Prerequisites

- **Python 3.7 or higher**
- **Ollama API Service**: Ensure the Ollama API is running and accessible at `http://localhost:11434/api/generate`.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/cv-parser-downloader.git
   cd cv-parser-downloader
   ```

2. **Create a Virtual Environment (Optional but Recommended)**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

Here’s the **Ollama Integration** section for your `README.md`:

---

## Ollama Integration

### What is Ollama?

**Ollama** is a local-first platform that allows you to run large language models (LLMs) directly on your machine without relying on cloud services. It supports models such as **LLaMA**, **Mistral**, and others for tasks like text generation and language understanding.

Ollama operates a server at `http://localhost:11434`, allowing you to send requests via a REST API to interact with these models. This makes it a perfect solution for applications needing real-time processing while maintaining privacy and low latency.

For more information, visit the [Ollama GitHub documentation](https://github.com/ollama/ollama).

### Setting Up Ollama

1. **Install Ollama**: Follow the instructions on the [Ollama GitHub page](https://github.com/ollama/ollama) to install the server on your local machine.
2. **Run Ollama**: Start the service by running:
   ```bash
   ollama run llama3.2
   ```
   This will start the Ollama server, accessible at `http://localhost:11434`.

### How This Project Uses Ollama

In this project, Ollama is used to process text extracted from CV PDFs. Specifically, the system identifies educational institutions (for Bachelor's, Master's, and PhD degrees) mentioned in the CVs by interacting with the Ollama API.

Here’s how the process works:
- The project extracts the text surrounding the term "education" from the PDFs.
- This extracted text is sent as a prompt to the Ollama API, where a model (such as **LLaMA 3**) analyzes it.
- The API returns a structured JSON response containing the universities associated with each degree.
- This information is then parsed and compiled into a CSV file.

Example of an API request:
```bash
curl http://localhost:11434/api/generate \
    -d '{ "model": "llama3", "prompt": "Extract the universities for Bachelor’s, Master’s, and PhD from the following text: ..." }'
```

The response will be a JSON object containing the extracted educational data.

--- 

You can add this section to your `README.md` under the Ollama Integration heading.

## Usage

The project consists of two main scripts:

1. **cv_downloader.py**: Downloads CVs from an Excel file.
2. **cv_parser.py**: Parses downloaded CVs to extract educational history.

### Downloading CVs

1. **Prepare the Excel File**

   - Ensure your Excel file (`JobPlacements.xlsx` by default) has a sheet named `AP Subset`.
   - The sheet should contain a column named `Website/Linkedin/CV` with URLs pointing directly to PDF CVs.

2. **Run the Downloader Script**

   ```bash
   python cv_downloader.py
   ```

   **Parameters:**

   - `EXCEL_FILE`: Path to the Excel file containing CV URLs.
   - `SHEET_NAME`: Name of the sheet within the Excel file.
   - `COLUMN_NAME`: Column name containing the CV URLs.
   - `OUTPUT_DIR`: Directory where downloaded PDFs will be saved.
   - `ZIP_FILENAME`: Name of the ZIP file to archive downloaded PDFs.
   - `ROW_RANGE`: Tuple indicating the range of rows to process (start, end).
   - `MAX_THREADS`: Number of concurrent threads for downloading.

   **Default Configuration:**

   These parameters are set within the `cv_downloader.py` script. Modify them as needed before running the script.

### Parsing CVs

1. **Ensure Downloaded CVs are Available**

   Make sure the `cvs` directory (or your specified `OUTPUT_DIR`) contains the downloaded PDF files.

2. **Run the Parser Script**

   ```bash
   python cv_parser.py <input_directory> <output_csv>
   ```

   **Arguments:**

   - `<input_directory>`: Path to the directory containing PDF files (e.g., `cvs`).
   - `<output_csv>`: Path where the resulting CSV file will be saved (e.g., `education_history.csv`).

   **Example:**

   ```bash
   python cv_parser.py cvs education_history.csv
   ```

   **Functionality:**

   - Extracts text from each PDF.
   - Identifies context around the word "education".
   - Sends the context to the Ollama API to extract universities for Bachelor's, Master's, and PhD degrees.
   - Compiles the results into a CSV file with columns: `File Name`, `Bachelors`, `Masters`, `PhD`.

## Configuration

### cv_downloader.py

Modify the following variables as needed:

- `EXCEL_FILE`: Path to your Excel file containing CV URLs.
- `SHEET_NAME`: Name of the sheet in the Excel file.
- `COLUMN_NAME`: Column containing the CV URLs.
- `OUTPUT_DIR`: Directory to save downloaded PDFs.
- `ZIP_FILENAME`: Name for the ZIP archive of PDFs.
- `TIMEOUT`: Timeout for HTTP requests (in seconds).
- `ROW_RANGE`: Tuple specifying the range of rows to process.
- `MAX_THREADS`: Maximum number of concurrent download threads.

### cv_parser.py

The parser script accepts command-line arguments:

- `input_directory`: Directory containing the PDF files.
- `output_csv`: Path to save the output CSV file.

Example:

```bash
python cv_parser.py cvs output/education_history.csv
```

## Logging

Both scripts implement logging to provide real-time feedback and error tracking.
Adjust the logging level in the scripts if needed.

## License

This project is licensed under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

1. Fork the repository.
2. Create your feature branch: `git checkout -b feature/YourFeature`.
3. Commit your changes: `git commit -m 'Add some feature'`.
4. Push to the branch: `git push origin feature/YourFeature`.
5. Open a pull request.

## Acknowledgements

- [pdfplumber](https://github.com/jsvine/pdfplumber) for PDF text extraction.
- [Pandas](https://pandas.pydata.org/) for data manipulation.
- [TQDM](https://github.com/tqdm/tqdm) for progress bars.
- [Ollama](https://ollama.com/) for the Language Model API.
