import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import Layout from './components/Layout';
import Login from './pages/Login';
import FileProcessingTree from './pages/FileProcessingTree';
import Landing from './pages/Landing';
import Upload from './pages/Upload';
import UploadModels from './pages/UploadModels';
import Summary from './pages/Summary';
import SourceOverview from './pages/SourceOverview';
import SourceMapping from './pages/SourceMapping';
import PreviewTypes from './pages/PreviewTypes';
import Relationships from './pages/Relationships';
import Calculations from './pages/Calculations';
import MQuery from './pages/MQuery';
import FinalTables from './pages/FinalTables';
import VisualPlan from './pages/VisualPlan';
import Validation from './pages/Validation';
import TDEStrategy from './pages/TDEStrategy';
import ExportPage from './pages/Export';
import { MigrationProject } from './types/project';
import './styles.css';

function App() {
  const [authenticated, setAuthenticated] = useState(() => sessionStorage.getItem('t2pbi_authenticated') === 'true');
  const [active, setActive] = useState('Landing');
  const [project, setProject] = useState<MigrationProject>();
  const [ssoLoading, setSsoLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (token) {
      setSsoLoading(true);
      fetch('/api/auth/vtab-sso', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
      })
      .then(res => res.json())
      .then(data => {
        if (data.authenticated) {
          sessionStorage.setItem('t2pbi_authenticated', 'true');
          setAuthenticated(true);
          // Remove token from URL
          window.history.replaceState({}, document.title, window.location.pathname);
        } else {
          alert('SSO Failed: ' + data.detail);
        }
      })
      .catch(err => {
        console.error('SSO error:', err);
        alert('SSO Error: ' + err.message);
      })
      .finally(() => setSsoLoading(false));
    }
  }, []);

  const requireProject = (page: React.ReactNode) => project ? page : <Upload project={project} setProject={setProject} onLoaded={() => setActive('360 Summary')}/>;
  const content = (() => {
    switch(active) {
      case 'Landing': return <Landing onStart={() => setActive('Upload')}/>;
      case 'Upload': return <Upload project={project} setProject={setProject} onLoaded={() => setActive('Upload Models')}/>;
      case 'Upload Models': return <UploadModels project={project}/>;
      case '360 Summary': return requireProject(<Summary project={project!}/>);
      case 'File Processing Tree': return requireProject(<FileProcessingTree project={project!}/>);
      case 'TDE Source Recovery': return requireProject(<TDEStrategy project={project!} setProject={setProject}/>);
      case 'Source Overview': return requireProject(<SourceOverview project={project!}/>);
      case 'Source Mapping': return requireProject(<SourceMapping project={project!} setProject={setProject}/>);
      case 'Preview & Types': return requireProject(<PreviewTypes project={project!}/>);
      case 'Relationships': return requireProject(<Relationships project={project!} setProject={setProject}/>);
      case 'Calculations': return requireProject(<Calculations project={project!}/>);
      case 'M Query': return requireProject(<MQuery project={project!}/>);
      case 'Final Tables': return requireProject(<FinalTables project={project!}/>);
      case 'Visual Plan': return requireProject(<VisualPlan project={project!}/>);
      case 'Validation': return requireProject(<Validation project={project!}/>);
      case 'Export': return requireProject(<ExportPage project={project!}/>);
      default: return <Landing onStart={() => setActive('Upload')}/>;
    }
  })();
  if (ssoLoading) return <div style={{display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: 'white', fontFamily: 'system-ui'}}>Logging you in securely...</div>;
  if (!authenticated) return <Login onAuthenticated={() => setAuthenticated(true)}/>;
  return <Layout active={active} onNav={setActive} hasProject={!!project} onLogout={() => { sessionStorage.removeItem('t2pbi_authenticated'); setAuthenticated(false); }}>{content}</Layout>;
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
