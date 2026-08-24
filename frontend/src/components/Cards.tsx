import { ReactNode } from 'react';

export function Card({ title, children, right }: {title?: string; children: ReactNode; right?: ReactNode}) {
  return <section className="card">{title && <div className="cardHeader"><h2>{title}</h2>{right}</div>}<div>{children}</div></section>;
}

export function Metric({ label, value }: {label: string; value: unknown}) {
  return <div className="metric"><span>{label}</span><b>{String(value ?? '-')}</b></div>;
}

export function Badge({ children, tone = 'neutral' }: {children: ReactNode; tone?: 'good' | 'warn' | 'bad' | 'neutral'}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
