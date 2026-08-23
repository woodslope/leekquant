import { copyFile, mkdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const assets = join(root, 'assets');
const vendor = join(assets, 'vendor');

await mkdir(vendor, { recursive: true });

const copies = [
  ['react/umd/react.production.min.js', 'react.production.min.js'],
  ['react-dom/umd/react-dom.production.min.js', 'react-dom.production.min.js'],
  ['@babel/standalone/babel.min.js', 'babel.min.js']
];

for (const [source, target] of copies) {
  await copyFile(join(root, 'node_modules', source), join(vendor, target));
}

const tailwind = join(root, 'node_modules', '.bin', 'tailwindcss');
const result = spawnSync(tailwind, [
  '-i', join(root, 'src', 'styles.css'),
  '-o', join(assets, 'app.css'),
  '--content', join(root, 'index.html'),
  '--minify'
], { stdio: 'inherit' });

if (result.status !== 0) process.exit(result.status || 1);
