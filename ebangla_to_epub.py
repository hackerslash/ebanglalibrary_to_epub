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
from io import BytesIO
from PIL import Image


def sanitize_filename(filename):
    """Remove or replace characters that are invalid in filenames."""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
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
        'url': url,
        'filename_title': ''
    }
    if soup.title and soup.title.string:
        metadata['filename_title'] = soup.title.string.strip()
    tab_content = soup.find('div', id=re.compile(r'ld-tab-content-\d+'))
    if tab_content:
        tab_content_copy = BeautifulSoup(str(tab_content), 'lxml')
        for button in tab_content_copy.find_all('button', class_='simplefavorite-button'):
            button.decompose()
        for unwanted in tab_content_copy.find_all(['script', 'style']):
            unwanted.decompose()
        intro_html_raw = str(tab_content_copy.find('div', id=re.compile(r'ld-tab-content-\d+')))
        metadata['intro_html'] = clean_html_for_epub(intro_html_raw)
        text_content = tab_content.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        if lines:
            metadata['title'] = lines[0]
        for i, line in enumerate(lines):
            if i == 1 and line:
                metadata['subtitle'] = line
            if 'সম্পাদনা' in line or 'সঙ্কলন' in line:
                metadata['editors'] = line
            if 'কৃতজ্ঞতা' in line:
                metadata['acknowledgments'] = line
    if not metadata['title']:
        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text(strip=True)
        else:
            metadata['title'] = soup.title.string if soup.title else 'Unknown Book'
    cover_img = soup.find('img', class_='entry-image')
    if cover_img:
        metadata['cover_image_url'] = cover_img.get('data-src') or cover_img.get('src') or ''
    return metadata


def clean_html_for_epub(html):
    """Clean HTML to make it XHTML-compliant for EPUB."""
    html = re.sub(r'<br\s*>', '<br/>', html)
    html = re.sub(r'<hr\s*>', '<hr/>', html)
    html = re.sub(r'<img([^>]*[^/])>', r'<img\1/>', html)
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup.find_all(['script', 'style', 'ins', 'button']):
        tag.decompose()
    for nav_tag in soup.find_all('nav'):
        if nav_tag.get('id') == 'ftwp-contents':
            continue
        nav_tag.decompose()
    google_selectors = [
        {'class_': re.compile(r'google-anno.*')},
        {'class_': re.compile(r'google-auto-placed')},
        {'class_': re.compile(r'adsbygoogle')},
    ]
    for selector in google_selectors:
        for tag in soup.find_all(**selector):
            tag.decompose()
    for tag in soup.find_all(class_=re.compile(r'simplefavorite-button')):
        tag.decompose()
    lms_classes = [
        'ld-course-status',
        'ld-course-progress',
        'ld-tabs-navigation',
        'ld-expand-button',
        'ld-status-icon',
    ]
    for cls in lms_classes:
        for tag in soup.find_all(class_=cls):
            tag.decompose()
    for tag in soup.find_all(attrs={'aria-labelledby': True}):
        del tag['aria-labelledby']
    for tag in soup.find_all(attrs={'aria-describedby': True}):
        del tag['aria-describedby']
    for tag in soup.find_all(attrs={'aria-controls': True}):
        del tag['aria-controls']
    for tag in soup.find_all(attrs={'aria-owns': True}):
        del tag['aria-owns']
    return str(soup)


def download_image(url):
    """Download an image and convert it to JPEG format.
    Returns tuple of (image_data, extension) or (None, None) on failure.
    """
    if not url:
        return None, None
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        if not response.content or len(response.content) < 100:
            return None, None
        img = Image.open(BytesIO(response.content))
        img.verify()
        img = Image.open(BytesIO(response.content))
        if img.mode in ('RGBA', 'LA'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                rgb_img.paste(img, mask=img.split()[-1])
            else:
                rgb_img.paste(img.convert('RGB'))
            img = rgb_img
        elif img.mode == 'P':
            if 'transparency' in img.info:
                img = img.convert('RGBA')
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1])
                img = rgb_img
            else:
                img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        output = BytesIO()
        img.save(output, format='JPEG', quality=90)
        jpeg_data = output.getvalue()
        output.close()
        return jpeg_data, 'jpg'
    except Exception as e:
        print(f"  Warning: Could not download image {url}: {e}")
        return None, None


def process_intro_images(html):
    """Extract and download all images from intro HTML.
    Returns:
        - Modified HTML with updated image references
        - List of tuples: (filename, image_data, media_type)
    """
    soup = BeautifulSoup(html, 'html.parser')
    images_to_embed = []
    img_counter = 0
    for img_tag in soup.find_all('img'):
        data_src = img_tag.get('data-src')
        data_lazy_src = img_tag.get('data-lazy-src')
        src = img_tag.get('src')
        img_url = None
        if data_src and data_src.startswith('http'):
            img_url = data_src
        elif data_lazy_src and data_lazy_src.startswith('http'):
            img_url = data_lazy_src
        elif src and src.startswith('http'):
            img_url = src
        if not img_url:
            img_tag.decompose()
            continue
        print(f"  Downloading intro image: {img_url[:80]}...")
        img_data, ext = download_image(img_url)
        if img_data:
            img_counter += 1
            img_filename = f'intro_image_{img_counter}.{ext}'
            images_to_embed.append((img_filename, img_data, 'image/jpeg'))
            img_tag['src'] = img_filename
            for attr in ['data-src', 'data-lazy-src', 'data-srcset', 'srcset',
                        'data-sizes', 'sizes', 'data-lazy-srcset', 'loading']:
                if img_tag.has_attr(attr):
                    del img_tag[attr]
            print(f"  ✓ Image embedded as {img_filename}")
        else:
            img_tag.decompose()
    for source_tag in soup.find_all('source'):
        source_tag.decompose()
    for picture_tag in soup.find_all('picture'):
        picture_tag.unwrap()
    return str(soup), images_to_embed


def extract_direct_content_chapters(soup):
    """Extract chapters directly from the page (new structure)."""
    chapters = []
    article = soup.find('article')
    if not article:
        return chapters
    headings = article.find_all('h2')
    has_chapter_headings = False
    for heading in headings:
        text = heading.get_text(strip=True)
        if 'অধ্যায়' in text or text.startswith('Chapter') or text.startswith('অধ্যায়'):
            has_chapter_headings = True
            break
    if not has_chapter_headings:
        return chapters
    for heading in headings:
        chapter_title = heading.get_text(strip=True)
        if not chapter_title or chapter_title in ['Book Information', 'সারাংশ', 'Reader Interactions']:
            continue
        content_parts = []
        current = heading.find_next_sibling()
        while current:
            if current.name == 'h2':
                break
            if current.name == 'p':
                content_parts.append(str(current))
            current = current.find_next_sibling()
        if content_parts:
            raw_content = '\n'.join(content_parts)
            cleaned_content = clean_html_for_epub(raw_content)
            chapters.append({
                'title': chapter_title,
                'content': cleaned_content,
                'type': 'direct'
            })
    return chapters


def extract_chapter_links(soup, base_url):
    chapters = []
    post_container = soup.find('div', id=re.compile(r'learndash_post_\d+'))
    if post_container:
        lesson_items = post_container.find_all('div', class_='ld-item-lesson-item')
        for lesson_item in lesson_items:
            is_expandable = 'ld-expandable' in lesson_item.get('class', [])
            lesson_link = lesson_item.find('a', class_='ld-item-name')
            if not is_expandable and lesson_link:
                lesson_url = lesson_link.get('href')
                lesson_title = lesson_link.get_text(strip=True)
                if lesson_url and lesson_title and '/lessons/' in lesson_url:
                    lesson_url = urljoin(base_url, lesson_url)
                    if not any(ch['url'] == lesson_url for ch in chapters):
                        chapters.append({
                            'title': lesson_title,
                            'url': lesson_url,
                            'type': 'link'
                        })
            elif is_expandable and lesson_link:
                lesson_url = lesson_link.get('href')
                title_div = lesson_link.find('div', class_='ld-item-title')
                lesson_title = title_div.get_text(strip=True) if title_div else lesson_link.get_text(strip=True)
                lesson_title = re.sub(r'\d+\s*Topics?$', '', lesson_title).strip()
                if lesson_url and lesson_title and '/lessons/' in lesson_url:
                    lesson_url = urljoin(base_url, lesson_url)
                    if not any(ch['url'] == lesson_url for ch in chapters):
                        chapters.append({
                            'title': lesson_title,
                            'url': lesson_url,
                            'type': 'link'
                        })
                topic_links = lesson_item.find_all('a', href=True)
                for link in topic_links:
                    chapter_url = link.get('href')
                    chapter_title = link.get_text(strip=True)
                    if chapter_url and chapter_title and '/topics/' in chapter_url:
                        chapter_url = urljoin(base_url, chapter_url)
                        if not any(ch['url'] == chapter_url for ch in chapters):
                            chapters.append({
                                'title': chapter_title,
                                'url': chapter_url,
                                'type': 'link'
                            })
        if not chapters:
            all_links = post_container.find_all('a', href=True)
            for link in all_links:
                chapter_url = link.get('href')
                chapter_title = link.get_text(strip=True)
                if chapter_url and chapter_title and ('/topics/' in chapter_url or '/lessons/' in chapter_url):
                    chapter_url = urljoin(base_url, chapter_url)
                    if not any(ch['url'] == chapter_url for ch in chapters):
                        chapters.append({
                            'title': chapter_title,
                            'url': chapter_url,
                            'type': 'link'
                        })
        if not chapters:
            links = post_container.find_all('a', class_=re.compile(r'ld-item-name'))
            for link in links:
                chapter_title = link.get_text(strip=True)
                chapter_url = link.get('href')
                if chapter_url and chapter_title:
                    chapter_url = urljoin(base_url, chapter_url)
                    chapters.append({
                        'title': chapter_title,
                        'url': chapter_url,
                        'type': 'link'
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
    toc_div = soup.find('div', id='ftwp-container-outer')
    content_div = soup.find('div', id='ftwp-postcontent')
    if toc_div and content_div:
        combined_html = str(toc_div) + str(content_div)
        return clean_html_for_epub(combined_html)
    if content_div:
        return clean_html_for_epub(str(content_div))
    content_div = soup.find('div', class_='ld-tab-content entry-content')
    if content_div:
        return clean_html_for_epub(str(content_div))
    content_div = soup.find('div', class_='entry-content')
    if content_div:
        return clean_html_for_epub(str(content_div))
    content_div = soup.find('div', class_=re.compile(r'ld-tab-content'))
    if content_div:
        return clean_html_for_epub(str(content_div))
    return None


def download_cover_image(url):
    """Download cover image, validate it, and convert to JPEG format."""
    if not url:
        return None, None
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        if not response.content or len(response.content) < 100:
            print(f"  Warning: Cover image appears to be empty or too small")
            return None, None
        try:
            img = Image.open(BytesIO(response.content))
            img.verify()
            img = Image.open(BytesIO(response.content))
            if img.mode in ('RGBA', 'LA'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    rgb_img.paste(img, mask=img.split()[-1])
                else:
                    rgb_img.paste(img.convert('RGB'))
                img = rgb_img
            elif img.mode == 'P':
                if 'transparency' in img.info:
                    img = img.convert('RGBA')
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1])
                    img = rgb_img
                else:
                    img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            output = BytesIO()
            img.save(output, format='JPEG', quality=95, optimize=True)
            jpeg_data = output.getvalue()
            output.close()
            test_img = Image.open(BytesIO(jpeg_data))
            test_img.load()
            test_img.close()
            if len(jpeg_data) < 100:
                print(f"  Warning: Converted JPEG appears to be too small")
                return None, None
            return jpeg_data, 'jpg'
        except Exception as img_error:
            print(f"  Warning: Could not process cover image: {img_error}")
            return None, None
    except requests.RequestException as e:
        print(f"  Warning: Could not download cover image: {e}")
        return None, None


def escape_xml(text):
    """Escape XML special characters."""
    if not text:
        return ''
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


def create_epub(metadata, chapters, output_filename):
    """Create an EPUB file from the book metadata and chapters."""
    book = epub.EpubBook()
    book.set_identifier(metadata['url'])
    book.set_title(metadata['title'])
    book.set_language('bn')
    if metadata['editors']:
        book.add_author(metadata['editors'])
    if metadata['cover_image_url']:
        print("  Downloading cover image...")
        cover_data, cover_ext = download_cover_image(metadata['cover_image_url'])
        if cover_data:
            book.set_cover(f'cover.{cover_ext}', cover_data)
            print("  ✓ Cover image added")
    intro_images = []
    if metadata['intro_html']:
        print("  Processing intro content images...")
        processed_intro_html, intro_images = process_intro_images(metadata['intro_html'])
        intro_content = f"""
        <html>
        <head><title>{metadata['title']}</title></head>
        <body>
            {processed_intro_html}
            <hr/>
            <p style="text-align: center; font-size: 0.9em; margin-top: 2em;">
                <em>This EPUB was created using <a href="https://github.com/hackerslash/ebanglalibrary_to_epub">eBangla Library to EPUB Converter</a></em>
            </p>
        </body>
        </html>
        """
    else:
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
    for img_filename, img_data, media_type in intro_images:
        img_item = epub.EpubItem(
            uid=img_filename.replace('.', '_'),
            file_name=img_filename,
            media_type=media_type,
            content=img_data
        )
        book.add_item(img_item)
    intro_chapter = epub.EpubHtml(title='Book Information',
                                   file_name='intro.xhtml',
                                   lang='bn')
    intro_chapter.content = intro_content
    book.add_item(intro_chapter)
    epub_chapters = [intro_chapter]
    for i, chapter in enumerate(chapters):
        print(f"Processing chapter {i+1}/{len(chapters)}: {chapter['title']}")
        if chapter.get('type') == 'direct':
            content = chapter.get('content', '')
        else:
            content = extract_chapter_content(chapter['url'])
        if content:
            chapter_file = f'chapter_{i+1}.xhtml'
            epub_chapter = epub.EpubHtml(title=chapter['title'],
                                         file_name=chapter_file,
                                         lang='bn')
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
    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
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
    book.spine = ['nav'] + epub_chapters
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
    print("Extracting book metadata...")
    metadata = extract_book_metadata(soup, book_url)
    print(f"  Title: {metadata['title']}")
    if metadata['subtitle']:
        print(f"  Subtitle: {metadata['subtitle']}")
    if metadata['editors']:
        print(f"  Editors: {metadata['editors']}")
    print("\nDetecting page structure...")
    chapters = extract_direct_content_chapters(soup)
    if chapters:
        print(f"  ✓ Detected new page structure (direct content)")
        print(f"  Found {len(chapters)} chapters")
    else:
        print(f"  Detected old page structure (topic links)")
        chapters = extract_chapter_links(soup, book_url)
        print(f"  Found {len(chapters)} chapters")
    if not chapters:
        print("Error: No chapters found on the page")
        sys.exit(1)
    if args.output:
        output_filename = args.output
    else:
        filename_title = metadata.get('filename_title') or metadata['title']
        safe_title = sanitize_filename(filename_title)
        output_filename = f"{safe_title}.epub"
    print(f"\nCreating EPUB file...")
    create_epub(metadata, chapters, output_filename)


if __name__ == '__main__':
    main()
