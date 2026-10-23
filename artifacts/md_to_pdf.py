import html
import re
import sys

import pymupdf

SRC = "docs/PROJECT_REPORT_2PAGE.md"
OUT = "docs/ClearCut_Report_2pages.pdf"


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", text)


def convert(lines):
    out, table, stack = [], [], []

    def close_lists(depth=0):
        while len(stack) > depth:
            out.append(f"</{stack.pop()}>")

    def flush_table():
        if not table:
            return
        rows = [r for r in table if not re.fullmatch(r"\|?[\s:\-|]+\|?", r)]
        out.append("<table>")
        for index, row in enumerate(rows):
            tag = "th" if index == 0 else "td"
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
        out.append("</table>")
        table.clear()

    for line in lines:
        if line.startswith("|"):
            close_lists()
            table.append(line)
            continue
        flush_table()
        if not line.strip():
            continue
        if line.startswith("# "):
            close_lists()
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            close_lists()
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif re.match(r"^\s+- ", line):
            if len(stack) < 2:
                stack.append("ul")
                out.append("<ul>")
            out.append(f"<li>{inline(line.strip()[2:])}</li>")
        elif line.startswith("- "):
            close_lists(1)
            if not stack:
                stack.append("ul")
                out.append("<ul>")
            out.append(f"<li>{inline(line[2:])}</li>")
        elif re.match(r"^\d+\. ", line):
            if not stack or stack[0] != "ol":
                close_lists()
                stack.append("ol")
                out.append("<ol>")
            out.append(f"<li>{inline(re.sub(r'^\d+\. ', '', line))}</li>")
        else:
            close_lists()
            css = ' class="center"' if line.startswith("**Code:**") else ""
            out.append(f"<p{css}>{inline(line)}</p>")
    flush_table()
    close_lists()
    return "\n".join(out)


def render(body_html, size):
    css = f"""
    body {{ font-family: sans-serif; font-size: {size}pt; line-height: 1.18; }}
    h1 {{ font-size: {size + 5}pt; text-align: center; color: #1F3A5F; margin: 0 0 2pt 0; }}
    h2 {{ font-size: {size + 1.8}pt; color: #1F3A5F; margin: 7pt 0 2pt 0; border-bottom: 1px solid #1F3A5F; }}
    p {{ margin: 0 0 3pt 0; }}
    p.center {{ text-align: center; }}
    ul, ol {{ margin: 0 0 3pt 0; padding-left: 14pt; }}
    li {{ margin: 0 0 1.5pt 0; }}
    code {{ font-family: monospace; font-size: {size - 0.7}pt; }}
    table {{ width: 100%; border-collapse: collapse; margin: 2pt 0 5pt 0; }}
    th {{ background-color: #DCE6F1; text-align: left; border: 0.5pt solid #777; padding: 2pt 4pt; }}
    td {{ border: 0.5pt solid #777; padding: 2pt 4pt; }}
    """
    story = pymupdf.Story(html=body_html, user_css=css)
    page = pymupdf.paper_rect("a4")
    where = page + (48, 38, -48, -34)
    writer = pymupdf.DocumentWriter(OUT)
    more = 1
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return len(pymupdf.open(OUT))


markdown = open(SRC, encoding="utf-8").read().splitlines()
body = convert(markdown)
for size in (10.0, 9.5, 9.0, 8.7, 8.4, 8.0):
    pages = render(body, size)
    print(f"font {size}pt -> {pages} pages")
    if pages <= 2:
        break
print("saved", OUT)
