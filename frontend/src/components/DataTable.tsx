type Props = { rows: Record<string, unknown>[]; empty?: string };

export default function DataTable({ rows, empty = 'No data available' }: Props) {
  if (!rows?.length) return <div className="empty">{empty}</div>;
  const cols = Array.from(rows.reduce((s, r) => { Object.keys(r).forEach(k => s.add(k)); return s; }, new Set<string>()));
  return <div className="tableWrap"><table><thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((r, idx) => <tr key={idx}>{cols.map(c => <td key={c}>{render(r[c])}</td>)}</tr>)}</tbody></table></div>;
}

function render(value: unknown) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return <pre className="inlineJson">{JSON.stringify(value, null, 2)}</pre>;
  return String(value);
}
