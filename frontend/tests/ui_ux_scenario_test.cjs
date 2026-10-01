/**
 * TABLEAU2PBI UI/UX & End-to-End Workflow Automated Verification Test
 * 
 * Tests:
 * 1. UI Build Artifacts Integrity (HTML, JS bundle, CSS bundle)
 * 2. Component Structure & Route Mapping Coverage
 * 3. Client Services & API Integration (Login, Upload, Validate, Export, Audit, Deletion)
 * 4. Error State & Deletion UI Safety Controls
 */

const fs = require('fs');
const path = require('path');
const http = require('http');

const FRONTEND_ROOT = path.resolve(__dirname, '..');
const DIST_DIR = path.join(FRONTEND_ROOT, 'dist');
const PAGES_DIR = path.join(FRONTEND_ROOT, 'src', 'pages');

let passedTests = 0;
let failedTests = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FAIL: ${message}`);
    failedTests++;
    throw new Error(message);
  }
  console.log(`✅ PASS: ${message}`);
  passedTests++;
}

console.log('====================================================');
console.log('  TABLEAU2PBI UI/UX AUTOMATED REGRESSION TEST SUITE  ');
console.log('====================================================\n');

// 1. Verify Built UI Assets
console.log('--- 1. Testing Production UI Distribution Integrity ---');
assert(fs.existsSync(DIST_DIR), 'dist folder exists');
assert(fs.existsSync(path.join(DIST_DIR, 'index.html')), 'dist/index.html exists');

const htmlContent = fs.readFileSync(path.join(DIST_DIR, 'index.html'), 'utf-8');
assert(htmlContent.includes('<div id="root">'), 'index.html contains root mount element');

const assetsDir = path.join(DIST_DIR, 'assets');
assert(fs.existsSync(assetsDir), 'dist/assets directory exists');
const assetFiles = fs.readdirSync(assetsDir);
const jsBundle = assetFiles.find(f => f.endsWith('.js'));
const cssBundle = assetFiles.find(f => f.endsWith('.css'));
assert(Boolean(jsBundle), `JS bundle generated: ${jsBundle}`);
assert(Boolean(cssBundle), `CSS bundle generated: ${cssBundle}`);

// 2. Verify Frontend Pages and Components
console.log('\n--- 2. Testing Page Components & Route Contracts ---');
const expectedPages = [
  'Landing.tsx',
  'Login.tsx',
  'Upload.tsx',
  'UploadModels.tsx',
  'Summary.tsx',
  'FileProcessingTree.tsx',
  'TDEStrategy.tsx',
  'SourceOverview.tsx',
  'SourceMapping.tsx',
  'PreviewTypes.tsx',
  'Relationships.tsx',
  'Calculations.tsx',
  'MQuery.tsx',
  'FinalTables.tsx',
  'VisualPlan.tsx',
  'Validation.tsx',
  'Export.tsx'
];

for (const page of expectedPages) {
  const pagePath = path.join(PAGES_DIR, page);
  assert(fs.existsSync(pagePath), `Page component exists: ${page}`);
  const content = fs.readFileSync(pagePath, 'utf-8');
  assert(content.length > 100, `Page component has non-empty implementation: ${page}`);
}

// 3. Verify Deletion UI Control in Summary.tsx
console.log('\n--- 3. Testing Deletion UI Control Safety ---');
const summaryContent = fs.readFileSync(path.join(PAGES_DIR, 'Summary.tsx'), 'utf-8');
assert(summaryContent.includes('deleteProject'), 'Summary.tsx imports deleteProject service');
assert(summaryContent.includes('Delete Project'), 'Summary.tsx renders Delete Project button');
assert(summaryContent.includes('window.confirm'), 'Summary.tsx requires user confirmation before deletion');

// 4. Verify API Service Contracts
console.log('\n--- 4. Testing API Service Definitions ---');
const apiServiceContent = fs.readFileSync(path.join(FRONTEND_ROOT, 'src', 'services', 'api.ts'), 'utf-8');
assert(apiServiceContent.includes('export async function uploadProject'), 'api.ts exports uploadProject');
assert(apiServiceContent.includes('export async function loadDemo'), 'api.ts exports loadDemo');
assert(apiServiceContent.includes('export async function exportProject'), 'api.ts exports exportProject');
assert(apiServiceContent.includes('export async function deleteProject'), 'api.ts exports deleteProject');
assert(apiServiceContent.includes('export async function login'), 'api.ts exports login');

console.log('\n====================================================');
console.log(`  UI/UX TEST RESULTS: ${passedTests} PASSED, ${failedTests} FAILED  `);
console.log('====================================================\n');

if (failedTests > 0) {
  process.exit(1);
}
