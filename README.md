# bilingual-book 📖

Turn any English book or article into a bilingual English-Chinese edition — one paragraph English, one paragraph Chinese — ready to import into reading apps like WeChat Read (微信读书).

## What it does

```
English EPUB/URL/PDF  →  Bilingual EPUB or PDF
                          with paragraph-by-paragraph translation
```

**Input:** EPUB, URL, PDF, or plain text
**Output:** EPUB (for reading apps) or PDF (with bookmarks & navigation)
**Translation:** Anthropic Claude or OpenAI GPT-4o

## Quick Start

```bash
pip install -r requirements.txt

# EPUB → bilingual EPUB (ready for WeChat Read)
python bilingual_book.py book.epub

# Web article → bilingual EPUB
python bilingual_book.py https://example.com/great-article

# EPUB → bilingual PDF with bookmarks
python bilingual_book.py book.epub --format pdf

# Use OpenAI instead of Anthropic
python bilingual_book.py book.epub --provider openai
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install pandoc (for EPUB extraction):
```bash
# macOS
brew install pandoc

# Ubuntu/Debian
sudo apt install pandoc
```

3. Set your API key:
```bash
# Anthropic (default)
export ANTHROPIC_API_KEY=sk-ant-...

# Or OpenAI
export OPENAI_API_KEY=sk-...
```

## Examples

### Book → WeChat Read

```bash
python bilingual_book.py "The_Book_of_Elon.epub"
# Output: The_Book_of_Elon_bilingual.epub
# Import to WeChat Read → enjoy bilingual reading
```

### Blog post → EPUB

```bash
python bilingual_book.py https://www.anthropic.com/engineering/some-article
# Output: some_article_bilingual.epub
```

### With custom title & author

```bash
python bilingual_book.py book.epub \
  --title "The Book of Elon" \
  --author "Eric Jorgenson" \
  --format pdf
```

## Output Format

Each paragraph appears as:

> **English original text here.**
>
> <span style="color: gray">中文翻译在这里。</span>

Key quotes are highlighted in color. Chapters and parts have proper navigation/bookmarks.

## How it works

1. **Extract** — Pulls text from EPUB (pandoc), URL (trafilatura), or PDF (pdfplumber)
2. **Classify** — Identifies parts, chapters, highlights, questions, and regular text
3. **Translate** — Sends batches to Claude/GPT-4o for natural Chinese translation
4. **Generate** — Creates EPUB with TOC or PDF with bookmarks

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-f`, `--format` | Output format: `epub` or `pdf` | `epub` |
| `-o`, `--output` | Output file path | auto-generated |
| `-t`, `--title` | Book title | auto-detected |
| `-a`, `--author` | Author name | — |
| `--provider` | `anthropic` or `openai` | `anthropic` |
| `--batch-size` | Paragraphs per API call | `20` |
| `--api-key` | API key (or use env var) | — |

## Cost Estimate

Translation cost depends on book length:

| Book size | ~Paragraphs | Anthropic (Sonnet) | OpenAI (GPT-4o) |
|-----------|------------|-------------------|-----------------|
| Article | 50 | ~$0.10 | ~$0.15 |
| Short book | 500 | ~$1.00 | ~$1.50 |
| Full book | 1500 | ~$3.00 | ~$4.50 |

## Requirements

- Python 3.8+
- pandoc (for EPUB input)
- Anthropic or OpenAI API key

## License

MIT
