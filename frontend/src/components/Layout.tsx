import { ReactNode } from 'react';
import { DatabaseZap, ShieldCheck, ArrowUp, LogOut } from 'lucide-react';

type Props = { children: ReactNode; active: string; onNav: (tab: string) => void; hasProject: boolean; onLogout: () => void };

const tabs = [
  'Landing', 'Upload', 'Upload Models', '360 Summary', 'File Processing Tree', 'TDE Source Recovery', 'Source Overview', 'Source Mapping', 'Preview & Types', 'Relationships',
  'Calculations', 'M Query', 'Final Tables', 'Visual Plan', 'Validation', 'Export'
];

export default function Layout({ children, active, onNav, hasProject, onLogout }: Props) {
  return <div className="appShell">
    <aside className="sideNav">
      <div className="brand"><DatabaseZap size={28}/><div><b>TABLEAU2PBI</b><span>Enterprise Workbench</span></div></div>
      <nav>{tabs.map(tab => <button key={tab} disabled={!hasProject && !['Landing','Upload','Upload Models'].includes(tab)} className={active === tab ? 'active' : ''} onClick={() => onNav(tab)}>{tab}</button>)}</nav>
      <div className="safe"><ShieldCheck size={18}/><span>Safe Openable Mode default</span></div>
      <button className="logoutButton" onClick={onLogout}><LogOut size={16}/> Sign out</button>
    </aside>
    <main className="mainPanel"><div id="pageTop"/>{children}<button className="goTop" onClick={() => document.getElementById('pageTop')?.scrollIntoView({behavior:'smooth'})}><ArrowUp size={18}/> Top</button></main>
  </div>;
}
