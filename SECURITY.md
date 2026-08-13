# Security and privacy

Please do not open a public issue for a suspected credential, private key, or
personal-data exposure. Report it privately to mail@nepaliarchives.org with
the affected path or commit and enough detail to reproduce the finding.

The current public source tree intentionally documents the archive workflow, DAG,
capability tiers, validation rules, and agent task boundaries. It does not
publish:

- API keys, credentials, or private keys;
- concrete agent vendors, model identifiers, or account arrangements;
- operator usernames, key paths, workstation paths, or authenticated remotes;
- executable third-party scripts or reader comments inside captured HTML.

Provider/model bindings, credentials, local paths, and deployment notes stay in
ignored local files. If a secret is ever committed, revoke or rotate it first;
removing a later revision does not remove it from Git history or existing
clones.

Earlier revisions may retain superseded operational metadata. This
forward-looking policy does not claim that ordinary commits erase history.
