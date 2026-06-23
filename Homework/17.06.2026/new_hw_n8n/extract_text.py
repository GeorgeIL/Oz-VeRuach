import sys

import fitz  # PyMuPDF
from docx import Document


def extract_pdf(path):
    text = ""
    doc = fitz.open(path)
    for page in doc:
        text += page.get_text() + "\n"
    return text


def extract_docx(path):
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs])


def extract_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_file(path):
    if path.endswith(".pdf"):
        return extract_pdf(path)
    if path.endswith(".docx"):
        return extract_docx(path)
    if path.endswith(".txt"):
        return extract_txt(path)
    raise ValueError("Unsupported file type")


if __name__ == "__main__":
    file_path = sys.argv[1]
    print(extract_file(file_path))
