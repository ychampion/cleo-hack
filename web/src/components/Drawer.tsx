// Cleo — right slide-over drawer (adapted from the design's primitives.jsx).

import { useEffect, type ReactNode } from 'react';
import { Icons } from '../lib/icons';

export function Drawer({
  open,
  onClose,
  width = 460,
  eyebrow,
  title,
  subtitle,
  children,
}: {
  open: boolean;
  onClose: () => void;
  width?: number;
  eyebrow?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <>
      <div className="d-mask" onClick={onClose} />
      <aside className="d-shell" style={{ width }} role="dialog" aria-modal="true">
        <header className="d-hd">
          <div className="d-titles">
            {eyebrow && <div className="d-eyebrow">{eyebrow}</div>}
            {title && <h3>{title}</h3>}
            {subtitle && <p className="d-sub">{subtitle}</p>}
          </div>
          <button className="icon-btn" onClick={onClose} title="Close">
            <Icons.X size={13} />
          </button>
        </header>
        <div className="d-bd">{children}</div>
      </aside>
    </>
  );
}
