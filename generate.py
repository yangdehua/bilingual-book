#!/usr/bin/env python3
"""
Generate bilingual EPUB or PDF from translated content tuples.

Used by the bilingual-book Claude Code skill. Each content file is a Python
file defining a list of (type, english, chinese) tuples.

Usage:
    python generate.py epub --content-files f1.py,f2.py --title "Title" --output out.epub
    python generate.py pdf  --content-files f1.py,f2.py --title "Title" --output out.pdf
"""

import argparse
import os
import sys


def load_content(file_list):
    """Load and merge content tuples from Python files."""
    all_content = []
    for fpath in file_list:
        fpath = fpath.strip()
        if not fpath or not os.path.exists(fpath):
            print(f"Warning: skipping {fpath}", file=sys.stderr)
            continue
        ns = {}
        code = open(fpath).read()
        try:
            exec(compile(code, fpath, 'exec'), ns)
        except SyntaxError as e:
            print(f"Error in {fpath} line {e.lineno}: {e.msg}", file=sys.stderr)
            sys.exit(1)
        # Find the list variable
        for k, v in ns.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], tuple):
                all_content.extend(v)
                print(f"  {fpath}: {len(v)} entries")
                break
    return all_content


def h(text):
    """HTML escape."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def generate_epub(content, output_path, title, author):
    """Generate bilingual EPUB with TOC."""
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
h1.cn { font-size: 1.1em; color: #666; font-weight: normal;
        margin-top: 0.2em; margin-bottom: 1.5em; }
h2 { color: #CC4422; font-size: 1.2em; margin-top: 1.5em; margin-bottom: 0.1em; }
h2.cn { font-size: 0.95em; color: #666; font-weight: normal;
        margin-top: 0; margin-bottom: 0.8em; }
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
    part_label = ''
    part_chapters = []
    ch_idx = 0
    cur_file = None
    cur_html = ''

    # Title page
    tp = epub.EpubHtml(title='Title', file_name='title.xhtml', lang='en')
    tp.content = (f'<html><body style="text-align:center; padding-top:25%;">'
                  f'<h1 style="font-size:1.8em; color:#1a1a1a;">{h(title)}</h1>'
                  f'<p style="color:#999; margin-top:1em;">{h(author)}</p>'
                  f'<p style="color:#aaa; margin-top:2em;">英汉双语对照版<br/>'
                  f'Bilingual Edition</p></body></html>').encode('utf-8')
    book.add_item(tp)
    spine.append(tp)

    def flush():
        nonlocal cur_file, cur_html
        if cur_file and cur_html:
            cur_file.content = (
                f'<html><head><link rel="stylesheet" href="style/default.css"/>'
                f'</head><body>{cur_html}</body></html>'
            ).encode('utf-8')
            book.add_item(cur_file)
            spine.append(cur_file)
        cur_html = ''
        cur_file = None

    for item in content:
        t, en_raw, cn_raw = item[0], item[1], item[2]
        en, cn = h(en_raw), h(cn_raw)

        if t == 'part':
            flush()
            if part_label and part_chapters:
                toc.append((epub.Section(part_label), part_chapters[:]))
            part_label = f'{en_raw} / {cn_raw}'
            part_chapters = []
            ch_idx += 1
            cur_file = epub.EpubHtml(title=part_label,
                                     file_name=f'ch_{ch_idx:03d}.xhtml', lang='en')
            cur_file.add_item(css_item)
            cur_html = f'<h1>{en}</h1><h1 class="cn">{cn}</h1>'

        elif t == 'chapter':
            flush()
            ch_idx += 1
            ch_title = f'{en_raw} / {cn_raw}'
            cur_file = epub.EpubHtml(title=ch_title,
                                     file_name=f'ch_{ch_idx:03d}.xhtml', lang='en')
            cur_file.add_item(css_item)
            part_chapters.append(cur_file)
            cur_html = f'<h2>{en}</h2><h2 class="cn">{cn}</h2>'

        elif t == 'highlight':
            cur_html += (f'<div class="highlight"><p class="en">{en}</p>'
                        f'<p class="cn">{cn}</p></div>')
        elif t == 'question':
            cur_html += (f'<div class="question"><p class="en">{en}</p>'
                        f'<p class="cn">{cn}</p></div>')
        else:
            cur_html += f'<p class="en">{en}</p><p class="cn">{cn}</p>'

    flush()
    if part_label and part_chapters:
        toc.append((epub.Section(part_label), part_chapters[:]))
    elif part_chapters:
        toc.extend(part_chapters)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine
    epub.write_epub(output_path, book, {})

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nEPUB: {output_path}")
    print(f"  Chapters: {ch_idx} | Entries: {len(content)} | Size: {size_kb:.0f} KB")


def generate_pdf(content, output_path, title, author):
    """Generate bilingual PDF with bookmarks."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    PageBreak, Flowable)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Find Chinese font
    cn_font = 'Helvetica'
    for fp in ['/Library/Fonts/Microsoft/Microsoft Yahei.ttf',
               '/Library/Fonts/Microsoft/SimHei.ttf',
               '/System/Library/Fonts/STHeiti Medium.ttc',
               '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
               '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('CNFont', fp))
                cn_font = 'CNFont'
                break
            except Exception:
                continue

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

    EC = HexColor('#1A1A1A')
    CC = HexColor('#666666')
    AC = HexColor('#CC4422')

    S = {
        'part': ParagraphStyle('P', fontName='Helvetica-Bold', fontSize=22,
                               textColor=HexColor('#B8860B'), spaceAfter=8*mm,
                               spaceBefore=15*mm, alignment=1),
        'part_cn': ParagraphStyle('PC', fontName=cn_font, fontSize=16,
                                  textColor=CC, spaceAfter=12*mm, alignment=1),
        'ch': ParagraphStyle('C', fontName='Helvetica-Bold', fontSize=16,
                             textColor=AC, spaceBefore=10*mm, spaceAfter=2*mm),
        'ch_cn': ParagraphStyle('CC', fontName=cn_font, fontSize=13,
                                textColor=CC, spaceAfter=6*mm),
        'en': ParagraphStyle('E', fontName='Helvetica', fontSize=11,
                             textColor=EC, leading=16, spaceAfter=1.5*mm),
        'cn': ParagraphStyle('CN', fontName=cn_font, fontSize=10,
                             textColor=CC, leading=15, spaceAfter=5*mm),
        'hl': ParagraphStyle('H', fontName='Helvetica-Bold', fontSize=12,
                             textColor=AC, leading=18, spaceAfter=1.5*mm,
                             leftIndent=5*mm, rightIndent=5*mm),
        'hl_cn': ParagraphStyle('HC', fontName=cn_font, fontSize=11,
                                textColor=HexColor('#996633'), leading=16,
                                spaceAfter=6*mm, leftIndent=5*mm, rightIndent=5*mm),
        'q': ParagraphStyle('Q', fontName='Helvetica-BoldOblique', fontSize=11,
                            textColor=HexColor('#555'), leading=16, spaceAfter=1.5*mm),
        'q_cn': ParagraphStyle('QC', fontName=cn_font, fontSize=10,
                               textColor=HexColor('#888'), leading=15, spaceAfter=5*mm),
    }

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                           leftMargin=20*mm, rightMargin=20*mm,
                           topMargin=20*mm, bottomMargin=20*mm,
                           title=title, author=author)
    story = []

    # Title page
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph(h(title),
                           ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=28,
                                         textColor=EC, alignment=1, leading=36)))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(h(author),
                           ParagraphStyle('A', fontName='Helvetica', fontSize=12,
                                         textColor=CC, alignment=1)))
    story.append(Spacer(1, 15*mm))
    story.append(Paragraph('Bilingual Edition',
                           ParagraphStyle('Ed', fontName='Helvetica', fontSize=11,
                                         textColor=HexColor('#999'), alignment=1)))
    story.append(PageBreak())

    for item in content:
        t = item[0]
        en, cn = h(item[1]), h(item[2])
        bm = f'{item[1]} / {item[2]}'

        if t == 'part':
            story.append(PageBreak())
            story.append(Bookmark(bm, 0))
            story.append(Spacer(1, 20*mm))
            story.append(Paragraph(en, S['part']))
            story.append(Paragraph(cn, S['part_cn']))
        elif t == 'chapter':
            story.append(Bookmark(bm, 1))
            story.append(Paragraph(en, S['ch']))
            story.append(Paragraph(cn, S['ch_cn']))
        elif t == 'highlight':
            story.append(Paragraph(en, S['hl']))
            story.append(Paragraph(cn, S['hl_cn']))
        elif t == 'question':
            story.append(Paragraph(en, S['q']))
            story.append(Paragraph(cn, S['q_cn']))
        else:
            story.append(Paragraph(en, S['en']))
            story.append(Paragraph(cn, S['cn']))

    doc.build(story)
    from pypdf import PdfReader
    pages = len(PdfReader(output_path).pages)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nPDF: {output_path}")
    print(f"  Pages: {pages} | Entries: {len(content)} | Size: {size_kb:.0f} KB")


def main():
    parser = argparse.ArgumentParser(description='Generate bilingual EPUB or PDF')
    parser.add_argument('format', choices=['epub', 'pdf'])
    parser.add_argument('--content-files', required=True,
                       help='Comma-separated list of Python content files')
    parser.add_argument('--title', default='Bilingual Book')
    parser.add_argument('--author', default='')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    files = args.content_files.split(',')
    print(f"Loading {len(files)} content file(s)...")
    content = load_content(files)
    if not content:
        print("Error: no content loaded", file=sys.stderr)
        sys.exit(1)
    print(f"Total: {len(content)} entries")

    if args.format == 'epub':
        generate_epub(content, args.output, args.title, args.author)
    else:
        generate_pdf(content, args.output, args.title, args.author)


if __name__ == '__main__':
    main()
