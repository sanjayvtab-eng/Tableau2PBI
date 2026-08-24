import { FormEvent, useState } from 'react';
import { DatabaseZap, LockKeyhole, ShieldCheck } from 'lucide-react';
import { login } from '../services/api';

export default function Login({ onAuthenticated }: {onAuthenticated: () => void}) {
  const [username, setUsername] = useState('balamuraleee@gmail.com');
  const [password, setPassword] = useState('12345');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('');
    try { await login(username, password); sessionStorage.setItem('t2pbi_authenticated', 'true'); onAuthenticated(); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="loginShell">
    <div className="loginBrandPanel">
      <div className="loginBrand"><DatabaseZap size={38}/><div><b>TABLEAU2PBI</b><span>Enterprise Migration Workbench</span></div></div>
      <h1>Convert Tableau logic into a governed Power BI solution.</h1>
      <p>Inventory files, recover source lineage, validate joins and datatypes, generate M and DAX, review the semantic model, and export safely.</p>
      <div className="loginFeature"><ShieldCheck/> Safe Openable Mode is enabled by default.</div>
    </div>
    <form className="loginCard" onSubmit={submit}>
      <div className="loginIcon"><LockKeyhole/></div><h2>Secure workspace login</h2><p className="muted">Demo credentials are prefilled for local testing.</p>
      <label>Username<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username"/></label>
      <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password"/></label>
      {error && <div className="error">{error}</div>}
      <button className="primary loginButton" disabled={busy}>{busy ? 'Signing in...' : 'Sign in to Workbench'}</button>
      <div className="demoWarning">Demo authentication only. Replace with Microsoft Entra ID, OAuth, or enterprise SSO before production deployment.</div>
    </form>
  </div>;
}
