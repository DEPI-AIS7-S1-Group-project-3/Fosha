import React from 'react';

/** Renders the small Markdown subset the assistant writes (**bold**, "- " bullets, blank-line
    paragraphs) as React elements, so replies never show raw asterisks. No HTML is injected. */
function inline(text: string, keyPrefix: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
      : <React.Fragment key={`${keyPrefix}-${i}`}>{part.replace(/(^|\s)_([^_]+)_(?=\s|$)/g, '$1$2')}</React.Fragment>
  );
}

export const ReplyText: React.FC<{ text: string }> = ({ text }) => {
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      const items = bullets;
      blocks.push(<ul key={`ul-${blocks.length}`}>{items.map((b, i) => <li key={i}>{inline(b, `li-${i}`)}</li>)}</ul>);
      bullets = [];
    }
  };
  text.split('\n').forEach((raw) => {
    const line = raw.trim();
    const bullet = line.match(/^[-*•]\s+(.*)/);
    if (bullet) { bullets.push(bullet[1]); return; }
    flush();
    if (line) blocks.push(<p key={`p-${blocks.length}`}>{inline(line, `p-${blocks.length}`)}</p>);
  });
  flush();
  return <div className="text">{blocks}</div>;
};
