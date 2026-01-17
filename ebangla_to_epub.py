#!/usr/bin/env python3
"""
eBangla Library to EPUB Converter

This script converts books from ebanglalibrary.com to EPUB format.
It scrapes the book metadata and chapter content from the website and
generates a properly formatted EPUB file.

Usage:
    python ebangla_to_epub.py <book_url>

Example:
    python ebangla_to_epub.py "https://www.ebanglalibrary.com/books/আগামী-রাত্রির-উপাখ্যান/"
"""

import sys
import re
import argparse
from urllib.parse import urljoin, urlparse
import os
import requests
from bs4 import BeautifulSoup
from ebooklib import epub


def sanitize_filename(filename):
    """Remove or replace characters that are invalid in filenames."""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Limit length
    return filename[:200]


def extract_book_metadata(soup, url):
    """Extract book metadata from the main book page."""
    metadata = {
        'title': '',
        'subtitle': '',
        'editors': '',
        'acknowledgments': '',
        'intro_html': '',
        'cover_image_url': '',
        'url': url
    }
    
    # Try to find the metadata container
    # The ID might be dynamic, so we'll look for the pattern
    tab_content = soup.find('div', id=re.compile(r'ld-tab-content-\d+'))
    
    if tab_content:
        # Store the full HTML content for the intro chapter
        metadata['intro_html'] = str(tab_content)
        
        # Extract all text and parse it
        text_content = tab_content.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # First non-empty line is usually the title
        if lines:
            metadata['title'] = lines[0]
        
        # Look for subtitle, editors, and acknowledgments
        for i, line in enumerate(lines):
            if i == 1 and line:  # Second line is often subtitle
                metadata['subtitle'] = line
            if 'সম্পাদনা' in line or 'সঙ্কলন' in line:
                metadata['editors'] = line
            if 'কৃতজ্ঞতা' in line:
                metadata['acknowledgments'] = line
    
    # Fallback: try to get title from h1 or page title
    if not metadata['title']:
        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text(strip=True)
        else:
            metadata['title'] = soup.title.string if soup.title else 'Unknown Book'
    
    # Extract cover image URL
    cover_img = soup.find('img', class_='entry-image')
    if cover_img:
        # Try data-src first (lazy loaded), then src
        metadata['cover_image_url'] = cover_img.get('data-src') or cover_img.get('src') or ''
    
    return metadata


def extract_chapter_links(soup, base_url):
    """Extract all chapter links from the book page."""
    chapters = []
    
    # Find the container with chapter links
    post_container = soup.find('div', id=re.compile(r'learndash_post_\d+'))
    
    if post_container:
        # Find all links that are lesson/chapter links
        links = post_container.find_all('a', class_=re.compile(r'ld-item-name'))
        
        for link in links:
            chapter_title = link.get_text(strip=True)
            chapter_url = link.get('href')
            
            if chapter_url and chapter_title:
                # Make sure URL is absolute
                chapter_url = urljoin(base_url, chapter_url)
                chapters.append({
                    'title': chapter_title,
                    'url': chapter_url
                })
    
    return chapters


def extract_chapter_content(url):
    """Extract content from a chapter page."""
    print(f"  Fetching chapter: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
    except requests.RequestException as e:
        print(f"  Error fetching chapter: {e}")
        return None
    
    soup = BeautifulSoup(response.text, 'lxml')
    
    # Find the content container
    content_div = soup.find('div', class_='entry-content')
    
    if not content_div:
        # Try alternative selectors
        content_div = soup.find('div', class_=re.compile(r'ld-tab-content.*entry-content'))
    
    if content_div:
        # Get the HTML content, preserving formatting
        return str(content_div)
    
    return None


def download_cover_image(url):
    """Download cover image and return image data and extension."""
    if not url:
        return None, None
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Determine image extension from URL or content-type
        if '.jpg' in url or '.jpeg' in url:
            ext = 'jpg'
        elif '.png' in url:
            ext = 'png'
        elif '.webp' in url:
            ext = 'jpg'  # Convert webp to jpg for better compatibility
        else:
            ext = 'jpg'  # Default
        
        return response.content, ext
    except requests.RequestException as e:
        print(f"  Warning: Could not download cover image: {e}")
        return None, None


def create_epub(metadata, chapters, output_filename):
    """Create an EPUB file from the book metadata and chapters."""
    book = epub.EpubBook()
    
    # Set metadata
    book.set_identifier(metadata['url'])
    book.set_title(metadata['title'])
    book.set_language('bn')  # Bengali language code
    
    if metadata['editors']:
        book.add_author(metadata['editors'])
    
    # Download and add cover image
    if metadata['cover_image_url']:
        print("  Downloading cover image...")
        cover_data, cover_ext = download_cover_image(metadata['cover_image_url'])
        if cover_data:
            book.set_cover(f'cover.{cover_ext}', cover_data)
            print("  ✓ Cover image added")
    
    # Create intro page with full book content from the intro section
    if metadata['intro_html']:
        # Use the full HTML content from the intro section
        intro_content = f"""
        <html>
        <head><title>{metadata['title']}</title></head>
        <body>
            {metadata['intro_html']}
            <hr/>
            <p style="text-align: center; font-size: 0.9em; margin-top: 2em;">
                <em>This EPUB was created using <a href="https://github.com/hackerslash/ebanglalibrary_to_epub">eBangla Library to EPUB Converter</a></em>
            </p>
        </body>
        </html>
        """
    else:
        # Fallback to basic metadata if intro_html is not available
        intro_content = f"""
        <html>
        <head><title>{metadata['title']}</title></head>
        <body>
            <h1>{metadata['title']}</h1>
            {f'<h2>{metadata["subtitle"]}</h2>' if metadata['subtitle'] else ''}
            {f'<p>{metadata["editors"]}</p>' if metadata['editors'] else ''}
            {f'<p>{metadata["acknowledgments"]}</p>' if metadata['acknowledgments'] else ''}
            <hr/>
            <p style="text-align: center; font-size: 0.9em; margin-top: 2em;">
                <em>This EPUB was created using <a href="https://github.com/hackerslash/ebanglalibrary_to_epub">eBangla Library to EPUB Converter</a></em>
            </p>
        </body>
        </html>
        """
    
    intro_chapter = epub.EpubHtml(title='Book Information',
                                   file_name='intro.xhtml',
                                   lang='bn')
    intro_chapter.content = intro_content
    book.add_item(intro_chapter)
    
    # Add chapters
    epub_chapters = [intro_chapter]
    
    for i, chapter in enumerate(chapters):
        print(f"Processing chapter {i+1}/{len(chapters)}: {chapter['title']}")
        
        content = extract_chapter_content(chapter['url'])
        
        if content:
            # Create EPUB chapter
            chapter_file = f'chapter_{i+1}.xhtml'
            epub_chapter = epub.EpubHtml(title=chapter['title'],
                                         file_name=chapter_file,
                                         lang='bn')
            
            # Wrap content in proper HTML structure
            epub_chapter.content = f"""
            <html>
            <head><title>{chapter['title']}</title></head>
            <body>
                <h1>{chapter['title']}</h1>
                {content}
            </body>
            </html>
            """
            
            book.add_item(epub_chapter)
            epub_chapters.append(epub_chapter)
        else:
            print(f"  Warning: Could not extract content for chapter: {chapter['title']}")
    
    # Define Table of Contents
    book.toc = tuple(epub_chapters)
    
    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Define CSS style
    style = '''
    body {
        font-family: 'Noto Sans Bengali', 'Kalpurush', sans-serif;
        line-height: 1.6;
        margin: 2em;
    }
    h1 {
        text-align: center;
        margin-bottom: 1em;
    }
    p {
        text-align: justify;
        margin-bottom: 0.5em;
    }
    '''
    nav_css = epub.EpubItem(uid="style_nav",
                            file_name="style/nav.css",
                            media_type="text/css",
                            content=style)
    book.add_item(nav_css)
    
    # Create spine
    book.spine = ['nav'] + epub_chapters
    
    # Write EPUB file
    epub.write_epub(output_filename, book, {})
    print(f"\n✓ EPUB created successfully: {output_filename}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert eBangla Library books to EPUB format'
    )
    parser.add_argument('url', help='URL of the book on ebanglalibrary.com')
    parser.add_argument('-o', '--output', help='Output filename (optional)')
    
    args = parser.parse_args()
    
    book_url = args.url
    
    # Validate URL
    parsed_url = urlparse(book_url)
    if 'ebanglalibrary.com' not in parsed_url.netloc:
        print("Error: URL must be from ebanglalibrary.com")
        sys.exit(1)
    
    print(f"Fetching book page: {book_url}")
    
    try:
        response = requests.get(book_url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
    except requests.RequestException as e:
        print(f"Error fetching book page: {e}")
        sys.exit(1)
    
    soup = BeautifulSoup(response.text, 'lxml')
    
    # Extract metadata
    print("Extracting book metadata...")
    metadata = extract_book_metadata(soup, book_url)
    print(f"  Title: {metadata['title']}")
    if metadata['subtitle']:
        print(f"  Subtitle: {metadata['subtitle']}")
    if metadata['editors']:
        print(f"  Editors: {metadata['editors']}")
    
    # Extract chapter links
    print("\nExtracting chapter links...")
    chapters = extract_chapter_links(soup, book_url)
    print(f"  Found {len(chapters)} chapters")
    
    if not chapters:
        print("Error: No chapters found on the page")
        sys.exit(1)
    
    # Determine output filename
    if args.output:
        output_filename = args.output
    else:
        safe_title = sanitize_filename(metadata['title'])
        output_filename = f"{safe_title}.epub"
    
    # Create EPUB
    print(f"\nCreating EPUB file...")
    create_epub(metadata, chapters, output_filename)


if __name__ == '__main__':
    main()
