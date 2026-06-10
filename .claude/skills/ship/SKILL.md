---
name: ship
description: >-
  Verify → commit → push → confirm-live for this archive. Use whenever a change
  (works, pipeline, site, docs) is ready to land: runs the contribution checks,
  commits in the repo's style, pushes over SSH (origin is broken — see below),
  and verifies the CI deploy actually reached www.nepaliarchives.org.
---

# Ship a change (verify → commit → push → confirm live)

The repo is **source-only**: CI (`.github/workflows/deploy.yml`) rebuilds
`reader.html/epub`, `archives/index.json`, the font subset, `site/` and the search
index on every push. **Never commit those** (they're gitignored). A change is just
sources: `text.txt` / `metadata.json` / source files / `pipeline/*.py` / docs.

## 1. Verify

```bash
python3 pipeline/validate.py        # schema, slug/id, text sanity, rights gate — must pass
```
For site/pipeline changes also dry-run `python3 pipeline/build_site.py` (and see the
`verify-site-change` skill to eyeball rendering). Check `git status` is only the files
you intended — any `reader.*`/`index.json`/`*.woff2` showing up means gitignore broke.

## 2. Commit

Per logical batch (one book / one feature / one fix). Style: imperative summary line,
a body that explains *what and why* (counts, dedup decisions, gotchas hit), ending:

```
Co-Authored-By: Claude <model name> <noreply@anthropic.com>
```

**Commit or push only when the user asks.**

## 3. Push — SSH, never `origin`

`origin` is credential-less HTTPS: pushes fail, and its stale tracking ref makes
`git status` show a bogus `[ahead N]`. Ignore it. Push:

```bash
git push git@github.com:chinge55/nepali_archives.git main
```

(`~/.ssh/id_ed25519` is authenticated as repo owner `chinge55`.) To check what the
remote really has: `git ls-remote git@github.com:chinge55/nepali_archives.git main`.

## 4. Confirm the deploy (background poll)

Pages deploys take ~2–5 min. Poll for a **fresh** deploy, then health-sweep — run in
background and report when it resolves:

```bash
START=$(date -u +%s)
for i in $(seq 1 18); do
  lm=$(curl -sI https://www.nepaliarchives.org/ | grep -i '^last-modified:' | cut -d' ' -f2-)
  [ "$(date -u -d "$lm" +%s 2>/dev/null || echo 0)" -ge "$((START-150))" ] && { echo "fresh: $lm"; break; }
  sleep 20
done
for p in / /stats/ /pagefind/pagefind-entry.json <changed pages…>; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' https://www.nepaliarchives.org$p)  $p"
done
```

Tailor the sweep to the change (new work → its page + stats count; pipeline → an
affected artifact like a `reader.epub` or font). If CI fails, the site stays on the
last good deploy — fix and re-push. Docs-only changes still trigger a deploy but
nothing visible changes; skip the poll and say so.
