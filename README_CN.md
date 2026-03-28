# bilingual-book 📖 英文书一键变双语对照

把任何英文书或文章，转成英汉双语对照版——每段英文下面跟一段中文翻译，可以直接导入微信读书。

## 解决什么问题

想读英文原版书提升英语，但生词太多读不下去；纯看翻译版又学不到东西。

这个工具一行命令搞定：读英文卡住了瞄一眼中文，不卡就继续。

## 两种用法

### 方式一：Claude Code Skill（推荐）

Claude 自己就是翻译器，不需要额外 API Key，不需要额外花钱。

**安装：**
```bash
git clone https://github.com/yangdehua/bilingual-book.git ~/.claude/skills/bilingual-book
```

**使用：**
```
# 在 Claude Code 里直接说：
> 把这本书做成双语对照版 /path/to/book.epub
> 这篇文章做成双语 https://example.com/article
```

Claude 会自动：提取内容 → 多个 agent 并行翻译 → 生成带目录的 EPUB/PDF。

### 方式二：命令行工具

独立运行，调 Claude API 或 OpenAI API 翻译。

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python bilingual_book.py book.epub                     # → 双语 EPUB
python bilingual_book.py book.epub --format pdf        # → 双语 PDF
python bilingual_book.py https://example.com/article   # 网页 → EPUB
python bilingual_book.py book.epub --provider openai   # 用 GPT-4o 翻译
```

## 效果

每段内容呈现为：

> **English original text here.**
>
> 中文翻译在这里。

重点语句用颜色高亮。EPUB 有完整目录导航，PDF 有书签。

## 支持的输入输出

| 输入 | 输出 | 适合场景 |
|------|------|---------|
| EPUB 文件 | EPUB | 导入微信读书、Apple Books |
| 网页链接 | EPUB | 技术博客、长文阅读 |
| PDF 文件 | PDF | 带书签导航，适合桌面阅读 |
| 纯文本 | EPUB/PDF | 任意文本内容 |

## 翻译成本（仅命令行模式）

| 篇幅 | 段落数 | Anthropic Sonnet | OpenAI GPT-4o |
|------|--------|-----------------|---------------|
| 一篇文章 | ~50 | ~¥0.7 | ~¥1 |
| 短书 | ~500 | ~¥7 | ~¥10 |
| 整本书 | ~1500 | ~¥20 | ~¥30 |

Skill 模式：包含在 Claude Code 订阅内，不额外收费。

## 安装依赖

```bash
# EPUB 提取
brew install pandoc          # macOS
sudo apt install pandoc      # Linux

# Python 依赖
pip install ebooklib         # EPUB 生成
pip install reportlab        # PDF 生成
pip install anthropic        # 命令行模式翻译（二选一）
pip install openai           # 命令行模式翻译（二选一）
```

## 项目结构

```
bilingual-book/
├── SKILL.md             # Claude Code skill 指令文件
├── generate.py          # EPUB/PDF 生成器（skill 和 CLI 共用）
├── bilingual_book.py    # 独立命令行工具
├── requirements.txt
└── README.md
```

## 许可证

MIT
