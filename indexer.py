import os
import time
import sqlite3
import tempfile
import pymupdf
from PIL import Image
from docx import Document
from rapidocr_onnxruntime import RapidOCR
import ollama
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | TEXT_EXTENSIONS | {".pdf", ".docx"}

# 1. Initialize built-in SQLite database
conn = sqlite3.connect("memory.db", check_same_thread=False)
conn.execute("""
    CREATE TABLE IF NOT EXISTS personal_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE,
        file_type TEXT,
        summary TEXT,
        timestamp REAL
    )
""")
conn.commit()

ocr_engine = RapidOCR()

def is_already_indexed(file_path):
    cur = conn.execute("SELECT 1 FROM personal_files WHERE file_path = ?", (file_path,))
    return cur.fetchone() is not None

def shrink_image(image_path, max_size=768):
    """Resizes images down so Ollama Vision processes them quickly on CPU."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((max_size, max_size))
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, "JPEG", quality=85)
    return tmp.name

def extract_ocr_text(image_path):
    """Fast CPU OCR for tickets, screenshots, and receipts."""
    result, _ = ocr_engine(image_path)
    if not result:
        return ""
    return " ".join([str(line[1]) for line in result if len(line) > 1])


def analyze_image(image_path):
    ocr_text = extract_ocr_text(image_path)
    # If OCR finds plenty of text (ticket/receipt), skip slow Vision AI
    if len(ocr_text.strip()) > 40:
        return f"Document/Ticket Text: {ocr_text}"

    small_img = shrink_image(image_path)
    try:
        prompt = (
            "In 2 short sentences, describe what is in this photo, dress type, color of dress, how many people, eyes, blurry, things in the picture and the exact facial expression"
            "or mood of any person (e.g., smiling, not smiling, angry, serious, sad)."
        )
        response = ollama.chat(
            model="qwen2.5vl:3b",
            messages=[{"role": "user", "content": prompt, "images": [small_img]}],
            options={"num_predict": 80}
        )
        return f"{ocr_text} {response['message']['content']}".strip()
    finally:
        if os.path.exists(small_img):
            os.remove(small_img)

def analyze_pdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    full_text = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            full_text.append(text)
        else:
            pix = page.get_pixmap(dpi=120)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            pix.save(tmp_path)
            try:
                full_text.append(extract_ocr_text(tmp_path))
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
    return "\n".join(full_text)

def analyze_text_file(file_path):
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as file:
        return file.read()

def analyze_docx(file_path):
    document = Document(file_path)
    content = [paragraph.text for paragraph in document.paragraphs]
    content.extend(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    return "\n".join(text for text in content if text.strip())

def index_file(file_path):
    abs_path = os.path.abspath(file_path)
    _, ext = os.path.splitext(abs_path)
    ext = ext.lower()

    if ext not in SUPPORTED_EXTENSIONS or is_already_indexed(abs_path):
        return

    print(f"Indexing: {os.path.basename(abs_path)}...")
    start = time.time()
    try:
        if ext in IMAGE_EXTENSIONS:
            content = analyze_image(abs_path)
        elif ext == ".pdf":
            content = analyze_pdf(abs_path)
        elif ext == ".docx":
            content = analyze_docx(abs_path)
        else:
            content = analyze_text_file(abs_path)

        if not content.strip():
            print(f"Skipped (no readable text/content): {os.path.basename(abs_path)}")
            return

        conn.execute(
            "INSERT OR REPLACE INTO personal_files (file_path, file_type, summary, timestamp) VALUES (?, ?, ?, ?)",
            (abs_path, ext, content, os.path.getmtime(abs_path))
        )
        conn.commit()
        print(f"Indexed in {time.time() - start:.1f}s: {os.path.basename(abs_path)}")
    except Exception as e:
        print(f"Error indexing {abs_path}: {e}")

class FolderWatcher(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            time.sleep(1)
            index_file(event.src_path)

if __name__ == "__main__":
    WATCH_FOLDER = os.path.expanduser("~/Desktop/TestMemoryFolder")
    os.makedirs(WATCH_FOLDER, exist_ok=True)

    for root, _, files in os.walk(WATCH_FOLDER):
        for f in files:
            index_file(os.path.join(root, f))

    print(f"Watching {WATCH_FOLDER} for new files...")
    observer = Observer()
    observer.schedule(FolderWatcher(), WATCH_FOLDER, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
