# Private Memory

Private Memory is a local file-indexing and chat application for finding information in personal files. It extracts text and descriptions from files, stores them in a local SQLite database, and uses a local Ollama vision model to answer questions.

The application is intended to keep file processing and chat on the user's machine.

## Features

- Watches `~/Desktop/TestMemoryFolder` for new files.
- Indexes PNG, JPG, JPEG, PDF, TXT, Markdown (`.md`), and Word (`.docx`) files.
- Uses RapidOCR for text extraction from images and scanned PDF pages.
- Uses PyMuPDF to extract text from normal PDF pages.
- Reads UTF-8 text and Markdown files directly, and extracts paragraphs and table cells from DOCX files.
- Uses the local `qwen2.5vl:3b` Ollama vision model for image descriptions.
- Stores file paths, types, summaries, and modification timestamps in SQLite.
- Provides a Streamlit chat interface for searching indexed memories.
- Attaches the most relevant image or PDF to chat responses when possible.

## Project structure

| File | Purpose |
|---|---|
| `indexer.py` | Scans and watches the memory folder and writes summaries to the SQLite database. |
| `app.py` | Runs the Streamlit chat interface and queries the local Ollama model. |
| `memory.db` | SQLite database containing indexed file information. |
| `requirements.txt` | Python dependencies. |

## Requirements

- Windows
- Python 3
- Ollama
- The Ollama `qwen2.5vl:3b` model

Install Ollama separately, start the Ollama service, and download the required model:

```powershell
ollama pull qwen2.5vl:3b
```

## Installation

From the project directory, create and activate a virtual environment:

```powershell
py -m venv myvenv
.\myvenv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, allow scripts for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Usage

1. Create the memory folder if it does not already exist:

   ```text
   C:\Users\<username>\Desktop\TestMemoryFolder
   ```

2. Start the indexer:

   ```powershell
   .\myvenv\Scripts\python.exe .\indexer.py
   ```

   The indexer recursively processes existing files in the folder and continues watching for new files. Keep this terminal running.

3. In a second terminal, start the chat application with the project environment:

   ```powershell
   .\myvenv\Scripts\python.exe -m streamlit run .\app.py
   ```

4. Open the Streamlit address displayed in the terminal, normally `http://localhost:8501`.

## How it works

### Indexing images

For `.png`, `.jpg`, and `.jpeg` files, the indexer:

1. Runs RapidOCR.
2. Uses the OCR text directly when enough text is detected.
3. Otherwise, resizes the image to at most 768 pixels per side.
4. Sends the resized image and a descriptive prompt to Ollama.
5. Stores OCR text and the vision-model description together.

Temporary resized and extracted images are deleted after processing.

### Indexing PDFs

For `.pdf` files, the indexer uses PyMuPDF:

1. Extracts embedded text from each page.
2. Renders pages without extractable text as 120-DPI images.
3. Runs OCR on those rendered pages.
4. Combines all page content into one summary.

### Indexing text and Word documents

- `.txt` and `.md` files are read as UTF-8 text. UTF-8 byte-order marks are supported; undecodable bytes are replaced.
- `.docx` files are read with `python-docx`. Paragraphs and table-cell text are stored in the indexed summary.
- Legacy `.doc` files are not supported.

### Searching with the chat interface

The Streamlit application:

1. Loads all indexed records from `memory.db`.
2. Builds a context containing file names, IDs, and summaries.
3. Sends the context and recent chat messages to the Ollama model.
4. Parses the model's `MATCH_ID` marker.
5. Displays the answer and, when applicable, the matching image or a PDF download button.

## Database

The SQLite database is created in the project directory as `memory.db`.

The `personal_files` table contains:

| Column | Description |
|---|---|
| `id` | Auto-incrementing unique record ID. |
| `file_path` | Absolute path to the source file. |
| `file_type` | Lowercase file extension. |
| `summary` | OCR text and/or AI-generated description. |
| `timestamp` | Source file modification time. |

The indexer does not reprocess a file when a record with the same absolute path already exists.

## Privacy

File extraction and database storage happen locally. The application requires a local Ollama installation and model, but it does not require sending file content to a hosted API.

The model, local files, OCR output, and database should still be treated as sensitive data on the computer where they are stored.

## Stopping the application

- Stop the indexer with `Ctrl+C` in its terminal.
- Stop Streamlit with `Ctrl+C` in its terminal.

## Troubleshooting

### Ollama model is missing

Download the model explicitly:

```powershell
ollama pull qwen2.5vl:3b
```

### The database is empty

Run `python indexer.py` before starting the chat interface, and place supported files inside `Desktop\TestMemoryFolder`.

### A file was modified after it was indexed

The current indexer identifies files only by `file_path`, not by modification time. Remove the matching row from `memory.db` or delete and recreate `memory.db` if all records need to be rebuilt.

### No text or description appears

- Confirm that the file is `.png`, `.jpg`, `.jpeg`, `.pdf`, `.txt`, `.md`, or `.docx`.
- Confirm that the file can be opened by PyMuPDF or Pillow.
- Check Ollama is running.
- Read the error printed by `indexer.py`.
