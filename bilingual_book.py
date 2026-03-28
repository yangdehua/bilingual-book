#!/usr/bin/env python3
"""
bilingual-book: Convert English books/articles into bilingual English-Chinese editions.

Supports EPUB, URL, PDF, and plain text as input.
Outputs EPUB (for reading apps) or PDF (with bookmarks).

Usage:
    python bilingual_book.py input.epub              # EPUB → bilingual EPUB
    python bilingual_book.py input.epub --format pdf  # EPUB → bilingual PDF
    python bilingual_book.py https://example.com/article  # URL → bilingual EPUB
    python bilingual_book.py input.txt               # Text → bilingual EPUB
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_from_epub(filepath):
    """Extract plain text from EPUB using pandoc."""
    result = subprocess.run(
        ['pandoc', filepath, '-t', 'plain', '--wrap=none'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error: pandoc failed - {result.stderr}", file=sys.stderr)
        print("Install pandoc: brew install pandoc / apt install pandoc", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def extract_from_url(url):
    """Extract article text from URL using trafilatura or fallback."""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_comments=False,
                                   include_tables=True, favor_precision=True)
        if text:
            return text
    except ImportError:
        pass

    # Fallback: use requests + basic HTML stripping
    try:
        import requests
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
                self.skip = False
                self.skip_tags = {'script', 'style', 'nav', 'footer', 'header'}

            def handle_starttag(self, tag, attrs):
                if tag in self.skip_tags:
                    self.skip = True

            def handle_endtag(self, tag):
                if tag in self.skip_tags:
                    self.skip = False
                if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'br', 'div'):
                    self.text.append('\n')

            def handle_data(self, data):
                if not self.skip:
                    self.text.append(data)

        resp = requests.get(url, timeout=30,
                           headers={'User-Agent': 'Mozilla/5.0 bilingual-book/1.0'})
        parser = TextExtractor()
        parser.feed(resp.text)
        return ''.join(parser.text)
    except ImportError:
        print("Error: install requests or trafilatura for URL support", file=sys.stderr)
        print("  pip install trafilatura   # recommended", file=sys.stderr)
        print("  pip install requests      # minimal", file=sys.stderr)
        sys.exit(1)


def extract_from_pdf(filepath):
    """Extract text from PDF."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return '\n\n'.join(text_parts)
    except ImportError:
        # Fallback to pdftotext
        result = subprocess.run(['pdftotext', '-layout', filepath, '-'],
                               capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        print("Error: install pdfplumber for PDF support", file=sys.stderr)
        print("  pip install pdfplumber", file=sys.stderr)
        sys.exit(1)


def extract_text(source):
    """Extract text from any supported source."""
    if source.startswith('http://') or source.startswith('https://'):
        print(f"Fetching URL: {source}")
        return extract_from_url(source)

    path = Path(source)
    if not path.exists():
        print(f"Error: file not found: {source}", file=sys.stderr)
        sys.exit(1)

    suffix = path.suffix.lower()
    if suffix == '.epub':
        print(f"Extracting EPUB: {source}")
        return extract_from_epub(source)
    elif suffix == '.pdf':
        print(f"Extracting PDF: {source}")
        return extract_from_pdf(source)
    elif suffix in ('.txt', '.md', '.text'):
        print(f"Reading text: {source}")
        return path.read_text(encoding='utf-8')
    else:
        print(f"Trying as plain text: {source}")
        return path.read_text(encoding='utf-8')


def classify_line(line):
    """Classify a line into content type."""
    stripped = line.strip()
    if not stripped or stripped == '[]':
        return None, None

    # Part headers
    if re.match(r'^Part [IVX]+[:\s]', stripped):
        return 'part', stripped

    # Question lines
    if stripped.startswith('Q:') or stripped.startswith('Q '):
        return 'question', stripped

    # Chapter/section headers (short lines, title case, no period at end)
    if (len(stripped) < 80 and not stripped.endswith('.')
            and not stripped.endswith(',') and not stripped.endswith('"')
            and stripped[0].isupper()
            and not any(c in stripped for c in ['。', '，'])):
        words = stripped.split()
        if len(words) <= 10:
            # Check if it looks like a title (most words capitalized)
            caps = sum(1 for w in words if w[0].isupper() or w in
                      ('a', 'an', 'the', 'of', 'in', 'on', 'at', 'to', 'for',
                       'and', 'but', 'or', 'nor', 'is', 'was', 'like'))
            if caps >= len(words) * 0.6:
                return 'chapter', stripped

    # Short punchy lines (potential highlights)
    if len(stripped) < 120 and stripped.endswith('.'):
        sentences = stripped.split('. ')
        if len(sentences) <= 2:
            return 'highlight', stripped

    return 'text', stripped


def parse_content(text):
    """Parse extracted text into structured content tuples (without translation)."""
    lines = text.split('\n')
    content = []

    for line in lines:
        ctype, ctext = classify_line(line)
        if ctype and ctext:
            content.append((ctype, ctext))

    return content


def translate_with_anthropic(content, api_key=None, batch_size=20):
    """Translate content using Anthropic API."""
    try:
        import anthropic
    except ImportError:
        print("Error: install anthropic SDK for translation", file=sys.stderr)
        print("  pip install anthropic", file=sys.stderr)
        sys.exit(1)

    if not api_key:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    translated = []

    # Process in batches
    total = len(content)
    for i in range(0, total, batch_size):
        batch = content[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        print(f"  Translating batch {batch_num}/{total_batches}...")

        # Build prompt
        lines_json = json.dumps(
            [{"type": t, "en": en} for t, en in batch],
            ensure_ascii=False
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{
                "role": "user",
                "content": f"""Translate each English text to natural, fluent Chinese. Return a JSON array with the same structure, adding a "cn" field.

Rules:
- Translate naturally, not word-for-word
- Keep the "type" and "en" fields unchanged
- Add a "cn" field with the Chinese translation
- For "part" and "chapter" types, translate the title
- Return ONLY the JSON array, no other text

Input:
{lines_json}"""
            }]
        )

        # Parse response
        resp_text = message.content[0].text.strip()
        # Extract JSON from response
        if resp_text.startswith('['):
            json_text = resp_text
        else:
            match = re.search(r'\[.*\]', resp_text, re.DOTALL)
            if match:
                json_text = match.group()
            else:
                print(f"  Warning: failed to parse batch {batch_num}, using originals")
                for t, en in batch:
                    translated.append((t, en, en))
                continue

        try:
            results = json.loads(json_text)
            for item in results:
                translated.append((item['type'], item['en'], item.get('cn', item['en'])))
        except json.JSONDecodeError:
            print(f"  Warning: JSON parse error in batch {batch_num}, using originals")
            for t, en in batch:
                translated.append((t, en, en))

    return translated


def translate_with_openai(content, api_key=None, batch_size=20):
    """Translate content using OpenAI API."""
    try:
        import openai
    except ImportError:
        print("Error: install openai SDK for translation", file=sys.stderr)
        print("  pip install openai", file=sys.stderr)
        sys.exit(1)

    if not api_key:
        api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Error: set OPENAI_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    client = openai.OpenAI(api_key=api_key)
    translated = []

    total = len(content)
    for i in range(0, total, batch_size):
        batch = content[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        print(f"  Translating batch {batch_num}/{total_batches}...")

        lines_json = json.dumps(
            [{"type": t, "en": en} for t, en in batch],
            ensure_ascii=False
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": f"""Translate each English text to natural, fluent Chinese. Return a JSON array with the same structure, adding a "cn" field.

Rules:
- Translate naturally, not word-for-word
- Keep the "type" and "en" fields unchanged
- Add a "cn" field with the Chinese translation
- Return ONLY the JSON array, no other text

Input:
{lines_json}"""
            }],
            max_tokens=8000
        )

        resp_text = response.choices[0].message.content.strip()
        if resp_text.startswith('```'):
            resp_text = re.sub(r'^```\w*\n?', '', resp_text)
            resp_text = re.sub(r'\n?```$', '', resp_text)

        try:
            results = json.loads(resp_text)
            for item in results:
                translated.append((item['type'], item['en'], item.get('cn', item['en'])))
        except json.JSONDecodeError:
            print(f"  Warning: JSON parse error in batch {batch_num}")
            for t, en in batch:
                translated.append((t, en, en))

    return translated


def h(text):
    """HTML escape."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def generate_epub(content, output_path, title="Bilingual Book", author=""):
    """Generate bilingual EPUB."""
    from ebooklib import epub

    CSS = '''
body { font-family: "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei",
       "Hiragino Sans GB", "WenQuanYi Micro Hei", sans-serif;
       line-height: 1.8; color: #1a1a1a; padding: 0 0.5em; }
.en { font-size: 1em; color: #1a1a1a; margin-bottom: 0.15em; }
.cn { font-size: 0.92em; color: #666; margin-bottom: 1.2em; }
.highlight .en { font-weight: bold; color: #CC4422; margin-left: 0.5em; }
.highlight .cn { color: #996633; font-weight: bold; margin-left: 0.5em; }
.question .en { font-style: italic; color: #555; }
.question .cn { color: #888; }
h1 { text-align: center; color: #B8860B; font-size: 1.5em; margin-top: 2em; }
h1.cn { font-size: 1.1em; color: #666; font-weight: normal; margin-top: 0.2em; margin-bottom: 1.5em; }
h2 { color: #CC4422; font-size: 1.2em; margin-top: 1.5em; margin-bottom: 0.1em; }
h2.cn { font-size: 0.95em; color: #666; font-weight: normal; margin-top: 0; margin-bottom: 0.8em; }
'''

    book = epub.EpubBook()
    book.set_identifier(f'bilingual-{hash(title) & 0xFFFFFF:06x}')
    book.set_title(f'{title} (英汉双语)')
    book.set_language('en')
    if author:
        book.add_author(author)
    book.add_metadata('DC', 'description', 'Bilingual English-Chinese Edition')

    css_item = epub.EpubItem(uid='style', file_name='style/default.css',
                             media_type='text/css', content=CSS.encode('utf-8'))
    book.add_item(css_item)

    spine = ['nav']
    toc = []
    current_part_label = ''
    current_part_chapters = []
    chapter_idx = 0

    # Title page
    title_html = f'''<html><body style="text-align:center; padding-top: 25%;">
    <h1 style="font-size:1.8em; color:#1a1a1a;">{h(title)}</h1>
    <p style="color:#999; margin-top:1em;">{h(author)}</p>
    <p style="color:#aaa; margin-top:2em;">英汉双语对照版<br/>Bilingual Edition</p>
    </body></html>'''
    title_ch = epub.EpubHtml(title='Title', file_name='title.xhtml', lang='en')
    title_ch.content = title_html.encode('utf-8')
    book.add_item(title_ch)
    spine.append(title_ch)

    current_file = None
    current_html = ''

    def flush():
        nonlocal current_file, current_html
        if current_file and current_html:
            current_file.content = (
                f'<html><head><link rel="stylesheet" href="style/default.css"/></head>'
                f'<body>{current_html}</body></html>'
            ).encode('utf-8')
            book.add_item(current_file)
            spine.append(current_file)
        current_html = ''
        current_file = None

    for item in content:
        t, en, cn = item[0], h(item[1]), h(item[2])

        if t == 'part':
            flush()
            if current_part_label and current_part_chapters:
                toc.append((epub.Section(current_part_label), current_part_chapters[:]))
            current_part_label = f'{item[1]} / {item[2]}'
            current_part_chapters = []
            chapter_idx += 1
            current_file = epub.EpubHtml(title=current_part_label,
                                         file_name=f'ch_{chapter_idx:03d}.xhtml', lang='en')
            current_file.add_item(css_item)
            current_html = f'<h1>{en}</h1><h1 class="cn">{cn}</h1>'

        elif t == 'chapter':
            flush()
            chapter_idx += 1
            ch_title = f'{item[1]} / {item[2]}'
            current_file = epub.EpubHtml(title=ch_title,
                                         file_name=f'ch_{chapter_idx:03d}.xhtml', lang='en')
            current_file.add_item(css_item)
            current_part_chapters.append(current_file)
            current_html = f'<h2>{en}</h2><h2 class="cn">{cn}</h2>'

        elif t == 'highlight':
            current_html += f'<div class="highlight"><p class="en">{en}</p><p class="cn">{cn}</p></div>'
        elif t == 'question':
            current_html += f'<div class="question"><p class="en">{en}</p><p class="cn">{cn}</p></div>'
        elif t == 'text':
            current_html += f'<p class="en">{en}</p><p class="cn">{cn}</p>'

    flush()
    if current_part_label and current_part_chapters:
        toc.append((epub.Section(current_part_label), current_part_chapters[:]))
    elif current_part_chapters:
        toc.extend(current_part_chapters)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_path, book, {})
    print(f"\nEPUB generated: {output_path}")
    print(f"  Chapters: {chapter_idx}")


def generate_pdf(content, output_path, title="Bilingual Book", author=""):
    """Generate bilingual PDF with bookmarks."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Find Chinese font
    font_paths = [
        '/Library/Fonts/Microsoft/Microsoft Yahei.ttf',
        '/Library/Fonts/Microsoft/SimHei.ttf',
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    ]
    cn_font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('CNFont', fp))
                cn_font = 'CNFont'
                break
            except Exception:
                continue

    if not cn_font:
        print("Warning: no Chinese font found, using Helvetica", file=sys.stderr)
        cn_font = 'Helvetica'

    class Bookmark(Flowable):
        def __init__(self, bm_title, level=0):
            Flowable.__init__(self)
            self.bm_title = bm_title
            self.level = level
            self.width = 0
            self.height = 0
        def draw(self):
            key = f'bm_{id(self)}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(self.bm_title, key, level=self.level)

    EN_COLOR = HexColor('#1A1A1A')
    CN_COLOR = HexColor('#666666')
    ACCENT = HexColor('#CC4422')

    styles = {
        'part': ParagraphStyle('P', fontName='Helvetica-Bold', fontSize=22,
                               textColor=HexColor('#B8860B'), spaceAfter=8*mm,
                               spaceBefore=15*mm, alignment=1),
        'part_cn': ParagraphStyle('PC', fontName=cn_font, fontSize=16,
                                  textColor=CN_COLOR, spaceAfter=12*mm, alignment=1),
        'chapter': ParagraphStyle('C', fontName='Helvetica-Bold', fontSize=16,
                                  textColor=ACCENT, spaceBefore=10*mm, spaceAfter=2*mm),
        'chapter_cn': ParagraphStyle('CC', fontName=cn_font, fontSize=13,
                                     textColor=CN_COLOR, spaceAfter=6*mm),
        'en': ParagraphStyle('E', fontName='Helvetica', fontSize=11,
                             textColor=EN_COLOR, leading=16, spaceAfter=1.5*mm),
        'cn': ParagraphStyle('CN', fontName=cn_font, fontSize=10,
                             textColor=CN_COLOR, leading=15, spaceAfter=5*mm),
        'highlight': ParagraphStyle('H', fontName='Helvetica-Bold', fontSize=12,
                                    textColor=ACCENT, leading=18, spaceAfter=1.5*mm,
                                    leftIndent=5*mm, rightIndent=5*mm),
        'highlight_cn': ParagraphStyle('HC', fontName=cn_font, fontSize=11,
                                       textColor=HexColor('#996633'), leading=16,
                                       spaceAfter=6*mm, leftIndent=5*mm, rightIndent=5*mm),
        'question': ParagraphStyle('Q', fontName='Helvetica-BoldOblique', fontSize=11,
                                   textColor=HexColor('#555555'), leading=16, spaceAfter=1.5*mm),
        'question_cn': ParagraphStyle('QC', fontName=cn_font, fontSize=10,
                                      textColor=HexColor('#888888'), leading=15, spaceAfter=5*mm),
    }

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                           leftMargin=20*mm, rightMargin=20*mm,
                           topMargin=20*mm, bottomMargin=20*mm,
                           title=title, author=author)
    story = []

    # Title page
    story.append(Spacer(1, 40*mm))
    ts = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=28,
                        textColor=EN_COLOR, alignment=1, leading=36)
    story.append(Paragraph(h(title), ts))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(h(author),
                           ParagraphStyle('A', fontName='Helvetica', fontSize=12,
                                         textColor=CN_COLOR, alignment=1)))
    story.append(Spacer(1, 15*mm))
    story.append(Paragraph('Bilingual Edition',
                           ParagraphStyle('Ed', fontName='Helvetica', fontSize=11,
                                         textColor=HexColor('#999'), alignment=1)))
    story.append(PageBreak())

    for item in content:
        t = item[0]
        en = h(item[1])
        cn = h(item[2])

        if t == 'part':
            story.append(PageBreak())
            story.append(Bookmark(f'{item[1]} / {item[2]}', level=0))
            story.append(Spacer(1, 20*mm))
            story.append(Paragraph(en, styles['part']))
            story.append(Paragraph(cn, styles['part_cn']))
        elif t == 'chapter':
            story.append(Bookmark(f'{item[1]} / {item[2]}', level=1))
            story.append(Paragraph(en, styles['chapter']))
            story.append(Paragraph(cn, styles['chapter_cn']))
        elif t == 'highlight':
            story.append(Paragraph(en, styles['highlight']))
            story.append(Paragraph(cn, styles['highlight_cn']))
        elif t == 'question':
            story.append(Paragraph(en, styles['question']))
            story.append(Paragraph(cn, styles['question_cn']))
        else:
            story.append(Paragraph(en, styles['en']))
            story.append(Paragraph(cn, styles['cn']))

    doc.build(story)
    print(f"\nPDF generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert English content into bilingual English-Chinese editions.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
  %(prog)s book.epub                          # EPUB → bilingual EPUB
  %(prog)s book.epub -f pdf                   # EPUB → bilingual PDF
  %(prog)s https://example.com/article        # URL → bilingual EPUB
  %(prog)s article.txt -o bilingual.epub      # Text → bilingual EPUB
  %(prog)s book.epub --provider openai        # Use OpenAI for translation
'''
    )
    parser.add_argument('source', help='Input file (EPUB/PDF/TXT) or URL')
    parser.add_argument('-f', '--format', choices=['epub', 'pdf'], default='epub',
                       help='Output format (default: epub)')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('-t', '--title', help='Book title (auto-detected if not set)')
    parser.add_argument('-a', '--author', default='', help='Author name')
    parser.add_argument('--provider', choices=['anthropic', 'openai'], default='anthropic',
                       help='Translation API provider (default: anthropic)')
    parser.add_argument('--batch-size', type=int, default=20,
                       help='Paragraphs per API call (default: 20)')
    parser.add_argument('--api-key', help='API key (or use env var)')

    args = parser.parse_args()

    # Extract text
    text = extract_text(args.source)
    if not text or len(text.strip()) < 50:
        print("Error: no content extracted", file=sys.stderr)
        sys.exit(1)

    lines = [l for l in text.split('\n') if l.strip()]
    print(f"Extracted {len(lines)} lines of content")

    # Auto-detect title
    title = args.title
    if not title:
        for line in lines[:10]:
            stripped = line.strip()
            if len(stripped) > 3 and len(stripped) < 100:
                title = stripped
                break
        if not title:
            if args.source.startswith('http'):
                title = 'Article'
            else:
                title = Path(args.source).stem

    # Parse content structure
    print("Parsing content structure...")
    content = parse_content(text)
    print(f"Found {len(content)} paragraphs")

    # Translate
    print(f"Translating with {args.provider}...")
    if args.provider == 'anthropic':
        translated = translate_with_anthropic(content, args.api_key, args.batch_size)
    else:
        translated = translate_with_openai(content, args.api_key, args.batch_size)

    print(f"Translated {len(translated)} entries")

    # Determine output path
    output = args.output
    if not output:
        if args.source.startswith('http'):
            base = re.sub(r'[^\w]', '_', title)[:50]
        else:
            base = Path(args.source).stem
        output = f'{base}_bilingual.{args.format}'

    # Generate output
    if args.format == 'epub':
        generate_epub(translated, output, title, args.author)
    else:
        generate_pdf(translated, output, title, args.author)

    size = os.path.getsize(output)
    print(f"  Size: {size / 1024:.0f} KB")
    print(f"  Entries: {len(translated)}")


if __name__ == '__main__':
    main()
