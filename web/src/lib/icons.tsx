// Cleo — hand-rolled 16x16 icon set, 1.5px stroke, currentColor.
// Adapted from the canonical design (design-ref icons.jsx). No icon library.

import type { CSSProperties, ReactNode } from 'react';

export interface IconProps {
  size?: number;
  strokeWidth?: number;
  style?: CSSProperties;
  className?: string;
}

const make =
  (path: ReactNode) =>
  ({ size = 14, strokeWidth = 1.5, style, className }: IconProps) => (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      className={className}
      aria-hidden="true"
    >
      {path}
    </svg>
  );

export const Icons = {
  // Nav
  Spec: make(
    <>
      <path d="M3.5 2.5h6L12.5 5.5v8a1 1 0 0 1-1 1h-8a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Z" />
      <path d="M9 2.5v3.5h3.5" />
      <path d="M5 9h6M5 11.5h4" />
    </>
  ),
  Inbox: make(
    <>
      <path d="M2 9.5 4 3h8l2 6.5" />
      <path d="M2 9.5V13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V9.5H10.5l-1 1.5h-3l-1-1.5H2Z" />
    </>
  ),
  Layers: make(
    <>
      <path d="M8 2 2 5l6 3 6-3-6-3Z" />
      <path d="m2 8 6 3 6-3" />
      <path d="m2 11 6 3 6-3" />
    </>
  ),
  Chart: make(
    <>
      <path d="M2 14V2" />
      <path d="M2 14h12" />
      <path d="M5 11V8" />
      <path d="M8 11V5" />
      <path d="M11 11V7" />
    </>
  ),
  Ledger: make(
    <>
      <rect x="2.5" y="2.5" width="11" height="11" rx="1.5" />
      <path d="M2.5 6h11M5 2.5v11" />
      <path d="M7 8.5h4M7 10.5h3" />
    </>
  ),
  Sparkle: make(
    <path d="M8 2v3.5M8 10.5V14M2 8h3.5M10.5 8H14M3.8 3.8l2.5 2.5M9.7 9.7l2.5 2.5M3.8 12.2l2.5-2.5M9.7 6.3l2.5-2.5" />
  ),
  Shield: make(
    <>
      <path d="M8 2 3 4v4.5C3 11 5 13 8 14c3-1 5-3 5-5.5V4L8 2Z" />
      <path d="m5.5 8 1.7 1.6L10.5 6.5" />
    </>
  ),
  // Utility
  Search: make(
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="m13.5 13.5-3.2-3.2" />
    </>
  ),
  Plus: make(<path d="M8 3v10M3 8h10" />),
  X: make(<path d="m3.5 3.5 9 9M12.5 3.5l-9 9" />),
  Check: make(<path d="m3.5 8.5 3 3 6-7" />),
  Chev: make(<path d="m4 6 4 4 4-4" />),
  ChevR: make(<path d="m6 4 4 4-4 4" />),
  External: make(
    <>
      <path d="M9 3h4v4" />
      <path d="M13 3 7 9" />
      <path d="M13 9v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h3" />
    </>
  ),
  Play: make(<path d="M5 3.5v9l7-4.5-7-4.5Z" />),
  History: make(
    <>
      <path d="M3 8a5 5 0 1 0 1.5-3.5L3 6" />
      <path d="M3 3v3h3" />
      <path d="M8 5.5V8l1.8 1.2" />
    </>
  ),
  Refresh: make(
    <>
      <path d="M3 8a5 5 0 1 1 1.5 3.5" />
      <path d="M2 11.5h3v-3" />
    </>
  ),
  Bolt: make(<path d="M8.5 2 4 9h3.5L7 14l4.5-7H8l.5-5Z" />),
  Quote: make(
    <>
      <path d="M3 7c0-2 1.5-3.5 3.5-3.5M3 7v3a2 2 0 0 0 2 2h.5a2 2 0 0 0 2-2V8a1 1 0 0 0-1-1H3Z" />
      <path d="M9 7c0-2 1.5-3.5 3.5-3.5M9 7v3a2 2 0 0 0 2 2h.5a2 2 0 0 0 2-2V8a1 1 0 0 0-1-1H9Z" />
    </>
  ),
  Link: make(
    <>
      <path d="M9 4.5h2A2.5 2.5 0 0 1 13.5 7v0A2.5 2.5 0 0 1 11 9.5H9" />
      <path d="M7 11.5H5A2.5 2.5 0 0 1 2.5 9v0A2.5 2.5 0 0 1 5 6.5h2" />
      <path d="M5.5 8h5" />
    </>
  ),
  ArrowUp: make(<path d="M8 13V3M8 3l-3 3M8 3l3 3" />),
  ArrowDown: make(<path d="M8 3v10M8 13l-3-3M8 13l3-3" />),
  Eye: make(
    <>
      <path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z" />
      <circle cx="8" cy="8" r="1.8" />
    </>
  ),
  Settings: make(
    <>
      <circle cx="8" cy="8" r="2" />
      <path d="M8 1.5v1.5M8 13v1.5M2.5 8H1M15 8h-1.5M3.6 3.6 4.6 4.6M11.4 11.4 12.4 12.4M3.6 12.4 4.6 11.4M11.4 4.6 12.4 3.6" />
    </>
  ),
  Send: make(
    <>
      <path d="m2.5 8 11-5.5L11 13l-3-4-5.5-1Z" />
      <path d="M8 9 11 6" />
    </>
  ),
  Brain: make(
    <>
      <path d="M5 3.5a2 2 0 0 0-2 2v1a2 2 0 0 0-1 1.7v0a2 2 0 0 0 1 1.7v.6a2 2 0 0 0 2 2h.5V3.5H5Z" />
      <path d="M11 3.5a2 2 0 0 1 2 2v1a2 2 0 0 1 1 1.7v0a2 2 0 0 1-1 1.7v.6a2 2 0 0 1-2 2h-.5V3.5h.5Z" />
      <path d="M5.5 6.5h2M8.5 9h2M5.5 9.5h2" />
    </>
  ),
};
