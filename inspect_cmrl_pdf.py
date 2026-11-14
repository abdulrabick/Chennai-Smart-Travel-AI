from pathlib import Path
import pdfplumber

PROJECT_ROOT = Path(__file__).resolve().parent

PDF_FILES = [
    PROJECT_ROOT / "data" / "raw" / "cmrl_fare_table.pdf",
    PROJECT_ROOT / "data" / "raw" / "cmrl_discounted_fare_table.pdf"
]

for pdf_file in PDF_FILES:

    print("\n" + "=" * 60)
    print("PDF:", pdf_file.name)
    print("=" * 60)

    if not pdf_file.exists():
        print("ERROR: PDF file not found!")
        continue

    with pdfplumber.open(pdf_file) as pdf:

        print("Total pages:", len(pdf.pages))

        for page_number, page in enumerate(pdf.pages, start=1):

            print(f"\n--- PAGE {page_number} ---")

            text = page.extract_text()

            if text:
                print(text)
            else:
                print("No selectable text found on this page.")