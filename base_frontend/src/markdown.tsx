import { Fragment, type ReactNode } from "react";

const BOLD_MARKER = "**";
const BOLD_PATTERN = /\*\*/g;

export function fixUnclosedBold(text: string): string {
  if (!text) return text;
  const matches = text.match(BOLD_PATTERN);
  if (!matches || matches.length % 2 === 0) return text;
  const lastIndex = text.lastIndexOf(BOLD_MARKER);
  return text.slice(0, lastIndex) + text.slice(lastIndex + BOLD_MARKER.length);
}

export function parseInlineMarkdown(text: string): ReactNode {
  if (!text) return null;
  const safe = fixUnclosedBold(text);
  const segments = safe.split(BOLD_MARKER);
  if (segments.length === 1) return segments[0];
  return segments.map((segment, idx) =>
    idx % 2 === 1 ? (
      <strong key={idx}>{segment}</strong>
    ) : (
      <Fragment key={idx}>{segment}</Fragment>
    ),
  );
}
