import { MigrationProject, Relationship, SourceMapping } from '../types/project';

function normalizeApiBaseUrl(value: string | undefined): string {
  const raw = (value || 'http://127.0.0.1:8000').trim().replace(/\/$/, '');
  if (!raw) return 'http://127.0.0.1:8000';
  if (/^https?:\/\//i.test(raw)) return raw;
  return `https://${raw}`;
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export function makeAbsoluteApiUrl(url: string): string {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_BASE_URL}${url.startsWith('/') ? url : `/${url}`}`;
}

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = body.detail || JSON.stringify(body);
    } catch {
      message = await response.text();
    }
    throw new Error(message || response.statusText);
  }
  return response.json();
}

async function assertTableauBackend(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Backend health check failed with HTTP ${response.status}`);
    }
    const health = await response.json();
    if (!String(health.application || '').includes('TABLEAU2PBI')) {
      throw new Error('Port 8000 is not running the TABLEAU2PBI backend. Stop the old backend and restart this application backend.');
    }
    const backendVersion = String(health.version || '0.0.0');
    const majorVersion = Number.parseInt(backendVersion.split('.')[0] || '0', 10);
    if (!Number.isFinite(majorVersion) || majorVersion < 11) {
      throw new Error(
        `Port 8000 is running an incompatible TABLEAU2PBI backend version (${backendVersion}). ` +
        'Stop the older backend and start the backend included with this V11 package.'
      );
    }
  } catch (error) {
    throw new Error(`Cannot connect to TABLEAU2PBI backend at ${API_BASE_URL}. Start backend first using start_tableau2pbi.ps1. Details: ${(error as Error).message}`);
  }
}

export async function uploadProject(files: File[]): Promise<MigrationProject> {
  await assertTableauBackend();
  const form = new FormData();
  files.forEach(file => form.append('files', file, file.name));
  const response = await fetch(`${API_BASE_URL}/api/projects/upload`, { method: 'POST', body: form });
  return asJson<MigrationProject>(response);
}

export async function loadDemo(): Promise<MigrationProject> {
  await assertTableauBackend();
  const response = await fetch(`${API_BASE_URL}/api/projects/demo`, { method: 'POST' });
  return asJson<MigrationProject>(response);
}

export async function saveSourceMappings(projectId: string, mappings: SourceMapping[]): Promise<MigrationProject> {
  await assertTableauBackend();
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/source-mappings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(mappings)
  });
  return asJson<MigrationProject>(response);
}

export async function saveRelationships(projectId: string, relationships: Relationship[]): Promise<MigrationProject> {
  await assertTableauBackend();
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/relationships`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(relationships)
  });
  return asJson<MigrationProject>(response);
}

export async function exportProject(projectId: string): Promise<{download_url: string; absolute_download_url?: string; export_path: string; health_status: string}> {
  await assertTableauBackend();
  const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/export`, { method: 'POST' });
  const result = await asJson<{download_url: string; absolute_download_url?: string; export_path: string; health_status: string}>(response);
  return { ...result, absolute_download_url: result.absolute_download_url || makeAbsoluteApiUrl(result.download_url) };
}

export async function downloadExportPackage(downloadUrl: string, filename: string): Promise<void> {
  const absoluteUrl = makeAbsoluteApiUrl(downloadUrl);
  const response = await fetch(absoluteUrl);
  if (!response.ok) {
    throw new Error(`Download failed with HTTP ${response.status}: ${await response.text()}`);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
}

export async function login(username: string, password: string): Promise<{authenticated: boolean}> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({username, password})});
  return asJson(response);
}
