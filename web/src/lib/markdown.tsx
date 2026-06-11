// Cleo — tiny markdown renderer for agent-written briefs.
// Headings, lists, code fences, blockquotes, hr, bold/italic/code/links.
// Builds React elements directly (no innerHTML), no external dependency.

import type { ReactNode } from 'react';

export function Markdown({ text }: { text: string }) {
  return <div className="md">{renderBlocks(text)}</div>;
}

function renderBlocks(src: string): ReactNode[] {
  const lines = src.replace(/\r\n/g, '\n').split('\n');
  const out: ReactNode[] = [];
  let i = 0;
  let key = 0;

  const isBlockStart = (line: string) =>
    /^(#{1,4})\s/.test(line) ||
    line.startsWith('```') ||
    /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+[.)]\s+/.test(line) ||
    /^>\s?/.test(line);

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }

    // fenced code
    if (line.startsWith('```')) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        buf.push(lines[i]);
        i++;
      }
      i++; // closing fence
      out.push(
        <pre key={key++}>
          <code>{buf.join('\n')}</code>
        </pre>
      );
      continue;
    }

    // headings
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const content = inline(h[2]);
      const level = h[1].length;
      if (level === 1) out.push(<h1 key={key++}>{content}</h1>);
      else if (level === 2) out.push(<h2 key={key++}>{content}</h2>);
      else if (level === 3) out.push(<h3 key={key++}>{content}</h3>);
      else out.push(<h4 key={key++}>{content}</h4>);
      i++;
      continue;
    }

    // horizontal rule
    if (/^(-{3,}|_{3,}|\*{3,})\s*$/.test(line.trim())) {
      out.push(<hr key={key++} />);
      i++;
      continue;
    }

    // unordered list
    if (/^\s*[-*+]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(
          <li key={items.length}>
            {inline(lines[i].replace(/^\s*[-*+]\s+/, ''))}
          </li>
        );
        i++;
      }
      out.push(<ul key={key++}>{items}</ul>);
      continue;
    }

    // ordered list
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(
          <li key={items.length}>
            {inline(lines[i].replace(/^\s*\d+[.)]\s+/, ''))}
          </li>
        );
        i++;
      }
      out.push(<ol key={key++}>{items}</ol>);
      continue;
    }

    // blockquote
    if (/^>\s?/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s?/, ''));
        i++;
      }
      out.push(<blockquote key={key++}>{inline(buf.join(' '))}</blockquote>);
      continue;
    }

    // paragraph — gather until blank line or block start
    const buf: string[] = [line];
    i++;
    while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) {
      buf.push(lines[i]);
      i++;
    }
    out.push(<p key={key++}>{inline(buf.join(' '))}</p>);
  }
  return out;
}

const INLINE_RE =
  /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\n]+\*)|(\[([^\]]+)\]\(([^)\s]+)\))/g;

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let k = 0;
  const re = new RegExp(INLINE_RE.source, 'g');
  let m = re.exec(text);
  while (m) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1]) out.push(<code key={k++}>{m[1].slice(1, -1)}</code>);
    else if (m[2]) out.push(<strong key={k++}>{inline(m[2].slice(2, -2))}</strong>);
    else if (m[3]) out.push(<em key={k++}>{inline(m[3].slice(1, -1))}</em>);
    else if (m[4])
      out.push(
        <a key={k++} href={m[6]} target="_blank" rel="noreferrer">
          {m[5]}
        </a>
      );
    last = m.index + m[0].length;
    m = re.exec(text);
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
