# eBangla Library to EPUB Converter

A Python script that converts books from [eBangla Library](https://www.ebanglalibrary.com/) to EPUB format for offline reading.

## Features

- Extracts book metadata (title, subtitle, editors, acknowledgments)
- Scrapes all chapter content from the book
- Generates a properly formatted EPUB file
- Preserves Bengali text and formatting
- Includes table of contents

## Requirements

- Python 3.7 or higher
- Internet connection to fetch book content

## Installation

1. Clone or download this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the script with a book URL from eBangla Library:

```bash
python ebangla_to_epub.py "https://www.ebanglalibrary.com/books/[book-url]"
```

### Example

```bash
python ebangla_to_epub.py "https://www.ebanglalibrary.com/books/%e0%a6%86%e0%a6%97%e0%a6%be%e0%a6%ae%e0%a7%80-%e0%a6%b0%e0%a6%be%e0%a6%a4%e0%a7%8d%e0%a6%b0%e0%a6%bf%e0%a6%b0-%e0%a6%89%e0%a6%aa%e0%a6%be%e0%a6%96%e0%a7%8d%e0%a6%af%e0%a6%be%e0%a6%a8/"
```

### Custom Output Filename

You can specify a custom output filename using the `-o` or `--output` option:

```bash
python ebangla_to_epub.py "https://www.ebanglalibrary.com/books/[book-url]" -o my_book.epub
```

## Output

The script will:
1. Fetch the book page and extract metadata
2. Find all chapter links
3. Download each chapter's content
4. Generate an EPUB file with the book title as the filename (or your specified filename)

The EPUB file can be opened in any e-reader application that supports the EPUB format, such as:
- Calibre (Desktop)
- Apple Books (macOS/iOS)
- Google Play Books (Android)
- Adobe Digital Editions
- And many more

## How It Works

1. **Metadata Extraction**: The script scrapes the book's main page to extract the title, subtitle, editors, and acknowledgments from the `#ld-tab-content-*` element.

2. **Chapter Discovery**: It finds all chapter links under the `#learndash_post_*` container.

3. **Content Scraping**: For each chapter, it fetches the page and extracts the content from the `.entry-content` div.

4. **EPUB Generation**: Using the `ebooklib` library, it creates a properly formatted EPUB file with:
   - Book metadata
   - Table of contents
   - An intro page with book information
   - All chapters with preserved formatting

## Notes

- The script is designed specifically for the eBangla Library website structure
- Please respect the website's terms of service and copyright
- Use this tool for personal, educational purposes only
- The script includes error handling for network issues and missing content

## Troubleshooting

**No chapters found**: Make sure you're using the correct book URL (not a chapter URL)

**Network errors**: Check your internet connection and try again

**Missing content**: Some chapters might not be publicly available or might have a different structure

## License

This script is provided as-is for educational purposes.
