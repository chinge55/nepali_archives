#!/usr/bin/env node
// Offline review aid. Candidate scores never write or certify metadata.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { scan, splitPadas } from '../../assets/chhanda/engine.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const args = process.argv.slice(2);
let output, onlyUnreviewed = false;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--output' && args[i + 1]) output = args[++i];
  else if (args[i] === '--unreviewed') onlyUnreviewed = true;
  else throw new Error('Usage: suggest.mjs [--unreviewed] [--output FILE]');
}
const poetic = new Set(['kavita', 'balkavita', 'git', 'bhajan', 'gazal', 'mahakavya', 'khandakavya']);
const catalogue = JSON.parse(fs.readFileSync(path.join(root, 'assets/chhanda/catalogue.json'), 'utf8')).metres;
const definitions = catalogue.filter(m => m.pattern);
const directory = path.join(root, 'archives/authors');
const works = [];
const sourceDigests = new Map();
function evidenceIsCurrent(work, evidence) {
  if (!Array.isArray(evidence) || !evidence.length) return false;
  return evidence.every(entry => {
    if (!entry || typeof entry.file !== 'string') return false;
    const filename = path.resolve(work, entry.file);
    if (path.isAbsolute(entry.file) || !filename.startsWith(work + path.sep)) return false;
    try {
      if (fs.lstatSync(filename).isSymbolicLink() || !fs.realpathSync(filename).startsWith(fs.realpathSync(work) + path.sep)) return false;
      if (!sourceDigests.has(filename)) sourceDigests.set(filename, crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex'));
      return sourceDigests.get(filename) === entry.sha256;
    } catch { return false; }
  });
}
for (const author of fs.readdirSync(directory).sort()) {
  const authorDir = path.join(directory, author);
  if (!fs.statSync(authorDir).isDirectory()) continue;
  for (const slug of fs.readdirSync(authorDir).sort()) {
    const work = path.join(authorDir, slug), filename = path.join(work, 'metadata.json');
    if (!fs.existsSync(filename)) continue;
    const metadata = JSON.parse(fs.readFileSync(filename, 'utf8'));
    if (!poetic.has(metadata.genre?.[0])) continue;
    const text = fs.readFileSync(path.join(work, 'text.txt'), 'utf8');
    const digest = crypto.createHash('sha256').update(text).digest('hex');
    const reviewed = metadata.prosody?.status === 'reviewed' && metadata.prosody.text_sha256 === digest &&
      evidenceIsCurrent(work, metadata.prosody.evidence);
    if (onlyUnreviewed && reviewed) continue;
    // Section captions and colophons are not evidence against a poem's metre.
    const parts = splitPadas(text).filter(p => !/^\s*(?:वि|बि)\.?\s*सं\.?/u.test(p.text)).map(p => ({ ...p, ...scan(p.text) }));
    const substantial = parts.filter(p => p.syllables.length >= 8 && p.syllables.length <= 40);
    const candidates = definitions.map(m => {
      const matched = substantial.filter(p => !p.issues.length && (p.pattern === m.pattern ||
        p.pattern.length === m.pattern.length && p.pattern.slice(0, -1) === m.pattern.slice(0, -1) &&
        p.pattern.at(-1) === 'L' && m.pattern.at(-1) === 'G'));
      return { metre: m.id, exact_padas: matched.length, examined_padas: substantial.length,
        examples: matched.slice(0, 2).map(p => p.text.trim()) };
    }).filter(c => c.exact_padas).sort((a, b) => b.exact_padas - a.exact_padas || a.metre.localeCompare(b.metre));
    works.push({ work: path.relative(root, work).split(path.sep).join('/'), title: metadata.title,
      text_sha256: digest, reviewed, candidates: candidates.slice(0, 3),
      uncertain_padas: substantial.filter(p => p.issues.length).length,
      unexamined_parts: parts.length - substantial.length });
  }
}
const report = { version: 1, purpose: 'Candidate review queue; a missing match is not a free-verse classification.', works };
const json = JSON.stringify(report, null, 2) + '\n';
if (output) { fs.writeFileSync(output, json); console.log(`Prepared ${works.length} assessments; metadata was not changed.`); }
else process.stdout.write(json);
