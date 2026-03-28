# bilingual-book 📖

Turn any English book or article into a bilingual English-Chinese edition — one paragraph English, one paragraph Chinese — ready to import into reading apps like WeChat Read (微信读书).

## Two Ways to Use

### 1. As a Claude Code Skill (Recommended)

Claude does the translation directly — no API key needed. Just install the skill and tell Claude what to convert.

**Install:**
```bash
# Clone into your Claude Code skills directory
git clone https://github.com/yangdehua/bilingual-book.git ~/.claude/skills/bilingual-book
```

**Use:**
```
# In Claude Code, just say:
> 把这本书做成双语对照版 /path/to/book.epub
> Make this article bilingual https://example.com/article
> /bilingual-book
```

Claude will:
1. Extract content from your EPUB/URL/PDF
2. Translate everything using parallel agents (Claude itself is the translator)
3. Generate EPUB or PDF with full TOC navigation

**How it works internally:**
- `SKILL.md` — Instructions that tell Claude how to do the conversion
- `generate.py` — Script Claude calls to produce the final EPUB/PDF
- Translation is done by Claude's own agents in parallel (~400 lines per agent)
- No external API calls, no extra cost beyond your Claude Code subscription

### 2. As a Standalone CLI Tool

For automation or use outside Claude Code. Calls Anthropic/OpenAI API for translation.

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...  # or OPENAI_API_KEY

python bilingual_book.py book.epub                     # → bilingual EPUB
python bilingual_book.py book.epub --format pdf        # → bilingual PDF
python bilingual_book.py https://example.com/article   # URL → EPUB
python bilingual_book.py book.epub --provider openai   # Use GPT-4o
```

## Output Format

Each paragraph appears as:

> **English original text here.**
>
> <span style="color:gray">中文翻译在这里。</span>

Key quotes highlighted in color. Full chapter navigation / bookmarks.

## Output Examples

| Format | Features | Best for |
|--------|----------|----------|
| EPUB | TOC navigation, reflowable text | WeChat Read, Apple Books, Kindle |
| PDF | Bookmarks, fixed layout, CJK fonts | Print, desktop reading |

## Architecture

```
bilingual-book/
├── SKILL.md             # Claude Code skill (instructions for Claude)
├── generate.py          # EPUB/PDF generator (called by skill or standalone)
├── bilingual_book.py    # Standalone CLI tool (with API translation)
├── requirements.txt     # Python dependencies
└── README.md
```

**Skill mode** (Claude Code):
```
User input → Claude extracts text → Claude agents translate in parallel
           → generate.py produces EPUB/PDF
```

**CLI mode** (standalone):
```
User input → bilingual_book.py extracts text → API translates in batches
           → bilingual_book.py produces EPUB/PDF
```

## Requirements

- Python 3.8+
- `pandoc` (for EPUB extraction): `brew install pandoc` / `apt install pandoc`
- `pip install ebooklib` (for EPUB output)
- `pip install reportlab` (for PDF output)
- For CLI mode: `pip install anthropic` or `pip install openai`

## Cost Estimate (CLI mode only)

| Size | Paragraphs | Anthropic Sonnet | OpenAI GPT-4o |
|------|-----------|-----------------|---------------|
| Article | ~50 | ~$0.10 | ~$0.15 |
| Short book | ~500 | ~$1.00 | ~$1.50 |
| Full book | ~1500 | ~$3.00 | ~$4.50 |

Skill mode: included in your Claude Code subscription.

## License

MIT
