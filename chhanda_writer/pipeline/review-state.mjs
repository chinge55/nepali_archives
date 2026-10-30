// Offline assessment freshness and catalogue matching; no classifications are inferred.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

function evidenceIsCurrent(work, evidence, digests) {
  if (!Array.isArray(evidence) || !evidence.length) return false;
  return evidence.every(entry => {
    if (!entry || typeof entry.file !== 'string' || !entry.locator || !entry.note) return false;
    const filename = path.resolve(work, entry.file);
    if (path.isAbsolute(entry.file) || !filename.startsWith(work + path.sep)) return false;
    try {
      if (fs.lstatSync(filename).isSymbolicLink() || !fs.realpathSync(filename).startsWith(fs.realpathSync(work) + path.sep)) return false;
      if (!digests.has(filename)) digests.set(filename, crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex'));
      return digests.get(filename) === entry.sha256;
    } catch { return false; }
  });
}

export function assessmentIsCurrent(work, metadata, textDigest, digests = new Map()) {
  const annotation = metadata.prosody;
  if (!annotation || !['reviewed', 'uncertain'].includes(annotation.status) || annotation.text_sha256 !== textDigest ||
      !/^\d{4}-\d{2}-\d{2}$/.test(annotation.reviewed || '') || !Number.isFinite(Date.parse(annotation.reviewed))) return false;
  if (evidenceIsCurrent(work, annotation.evidence, digests)) return true;
  // A source-limited assessment is still recorded. A newly available source reopens it.
  if (annotation.status !== 'uncertain' || !Array.isArray(annotation.evidence) || annotation.evidence.length ||
      typeof annotation.review_note !== 'string' || !annotation.review_note.trim()) return false;
  const source = metadata.source || {};
  const files = [source.html, source.pdf, metadata.formats?.pdf, ...(source.pdf_editions || []).map(e => e.file)];
  return !files.some(file => typeof file === 'string' && fs.existsSync(path.resolve(work, file)));
}

export function matchesCataloguePattern(actual, pattern, metre) {
  if (actual === pattern) return true;
  if (metre.kind === 'bahr') {
    // Handbook meters 10, 27, 29 and 37 admit an unscanned final short; 26 does not.
    return ['ramal_musamman_mahzuf', 'hazaj_musaddas_mahzuf', 'mutaqarib_musamman_mahzuf',
      'kamil_musamman_salim'].includes(metre.id) && actual === pattern + 'L';
  }
  return actual.length === pattern.length && actual.slice(0, -1) === pattern.slice(0, -1) &&
    actual.at(-1) === 'L' && pattern.at(-1) === 'G';
}
