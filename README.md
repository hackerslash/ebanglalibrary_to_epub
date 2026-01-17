# eBangla Library to EPUB/PDF Converter

I wanted to read some books from [eBangla Library](https://www.ebanglalibrary.com/) on my Kindle, so I created this script to convert them to EPUB and PDF formats. This takes a book URL from eBangla Library and converts it to EPUB or PDF format.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

**Convert to EPUB:**
```bash
python ebangla_to_epub.py "https://www.ebanglalibrary.com/books/[book-url]"
```

**Custom output filename:**
```bash
python ebangla_to_epub.py -o mybook.epub "https://www.ebanglalibrary.com/books/[book-url]"
```

## What it does

- Downloads book cover, intro content, and all chapters
- Creates a properly formatted EPUB
- Preserves Bengali text and formatting
- Names the file using the book title

## Note

Please respect the website's terms of service and use this for personal reading only.
