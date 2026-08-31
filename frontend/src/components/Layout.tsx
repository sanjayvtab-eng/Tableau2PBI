import { ReactNode, useState, useEffect, useRef } from 'react';
import { 
  DatabaseZap, ShieldCheck, ArrowUp, ArrowRight, LogOut, Search, HelpCircle, Bell, User,
  ChevronDown, Menu
} from 'lucide-react';

type Props = { children: ReactNode; active: string; onNav: (tab: string) => void; hasProject: boolean; onLogout: () => void };

const navGroups = {
  discover: ['Upload Models', '360 Summary', 'File Processing Tree', 'TDE Source Recovery', 'Source Overview'],
  prepare: ['Source Mapping', 'Preview & Types', 'Relationships'],
  convert: ['Calculations', 'M Query', 'Final Tables', 'Visual Plan']
};

const orderedStages = [
  'Landing',
  'Upload',
  'Upload Models',
  '360 Summary',
  'File Processing Tree',
  'TDE Source Recovery',
  'Source Overview',
  'Source Mapping',
  'Preview & Types',
  'Relationships',
  'Calculations',
  'M Query',
  'Final Tables',
  'Visual Plan',
  'Validation',
  'Export'
];

export default function Layout({ children, active, onNav, hasProject, onLogout }: Props) {
  const [projectsMenuOpen, setProjectsMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setProjectsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleNav = (tab: string) => {
    onNav(tab);
    setProjectsMenuOpen(false);
    setMobileMenuOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const currentIdx = orderedStages.indexOf(active);
  const nextStage = currentIdx >= 0 && currentIdx < orderedStages.length - 1 ? orderedStages[currentIdx + 1] : null;
  const canGoNext = nextStage && (hasProject || ['Upload', 'Upload Models'].includes(nextStage));

  const TopNavLinks = () => (
    <>
      <button className={active === 'Landing' ? 'active' : ''} onClick={() => handleNav('Landing')}>Dashboard</button>
      <button className={active === 'Upload' ? 'active' : ''} onClick={() => handleNav('Upload')}>New Migration</button>
      
      <div className="dropdownContainer" ref={menuRef} style={{ display: 'flex', alignItems: 'center' }}>
        <button 
          className={['Upload Models', '360 Summary', 'File Processing Tree', 'TDE Source Recovery', 'Source Overview', 'Source Mapping', 'Preview & Types', 'Relationships', 'Calculations', 'M Query', 'Final Tables', 'Visual Plan'].includes(active) ? 'active' : ''}
          onClick={() => setProjectsMenuOpen(!projectsMenuOpen)}
          disabled={!hasProject}
        >
          Projects <ChevronDown size={14}/>
        </button>
        {projectsMenuOpen && hasProject && (
          <div className="megaMenu">
            <div className="megaMenuColumn">
              <h4>DISCOVER</h4>
              {navGroups.discover.map(tab => (
                <a key={tab} onClick={() => handleNav(tab)} className={active === tab ? 'active' : ''}>{tab}</a>
              ))}
            </div>
            <div className="megaMenuColumn">
              <h4>PREPARE</h4>
              {navGroups.prepare.map(tab => (
                <a key={tab} onClick={() => handleNav(tab)} className={active === tab ? 'active' : ''}>{tab}</a>
              ))}
            </div>
            <div className="megaMenuColumn">
              <h4>CONVERT</h4>
              {navGroups.convert.map(tab => (
                <a key={tab} onClick={() => handleNav(tab)} className={active === tab ? 'active' : ''}>{tab}</a>
              ))}
            </div>
          </div>
        )}
      </div>

      <button className={active === 'Validation' ? 'active' : ''} onClick={() => handleNav('Validation')} disabled={!hasProject}>Validation</button>
      <button className={active === 'Export' ? 'active' : ''} onClick={() => handleNav('Export')} disabled={!hasProject}>Exports</button>
    </>
  );

  return (
    <div className="appShell topNavShell">
      <header className="globalHeader">
        <div className="headerBrand">
          <DatabaseZap size={24}/>
          <div>
            <b>TABLEAU2PBI</b>
            <span>Migration Workbench</span>
          </div>
        </div>

        <nav className="desktopNav">
          <TopNavLinks />
        </nav>

        <div className="headerActions">
          <div className="safeModePill"><ShieldCheck size={14}/> Safe Mode</div>
          <button className="iconBtn" title="Search"><Search size={18}/></button>
          <button className="iconBtn" title="Help"><HelpCircle size={18}/></button>
          <button className="iconBtn" title="Notifications"><Bell size={18}/></button>
          <button className="iconBtn" title="User Profile"><User size={18}/></button>
          <button className="iconBtn signoutBtn" onClick={onLogout} title="Sign Out"><LogOut size={18}/></button>
          <button className="mobileMenuToggle" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
            <Menu size={20}/>
          </button>
        </div>
      </header>

      {mobileMenuOpen && (
        <div className="mobileNavOverlay">
          <TopNavLinks />
        </div>
      )}

      <main className="mainPanel">
        <div id="pageTop"/>
        <div className="pageContentWrapper">
          {children}
          
          {nextStage && (
            <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid #E2E8F0', paddingTop: '24px' }}>
              <button 
                className="primary" 
                disabled={!canGoNext} 
                onClick={() => handleNav(nextStage)}
                style={{ padding: '12px 24px', fontSize: '15px' }}
              >
                Proceed to {nextStage} <ArrowRight size={18}/>
              </button>
            </div>
          )}
        </div>
        <button className="goTop" onClick={() => document.getElementById('pageTop')?.scrollIntoView({behavior:'smooth'})}>
          <ArrowUp size={18}/> Top
        </button>
      </main>
    </div>
  );
}
