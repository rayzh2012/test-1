# Fangame Fetch Targets

This folder contains metadata-only target manifests for publicly distributed/free fangames and mirrors. Adding or updating a target via a pull request triggers the Fangame Fetch GitHub Action. The runner tries all listed public sources, follows download pages, rejects HTML/downloader stubs, requires a plausible archive header and minimum size, records SHA-256 and provenance, then produces both a full artifact and <=80MB Drive-friendly chunks.

Use only public, permission-compatible fangame distributions and mirrors. Do not add paid games, login-gated private shares, CAPTCHA bypasses, or access-control circumvention targets.
