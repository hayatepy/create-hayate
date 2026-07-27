# Vendored admin runtime

This directory records the immutable upstream sources copied into
`src/hayate_admin` and `src/hayate_htmx`. They are included because
Pywrangler cannot install VCS records into its portable Workers lock while
preserving the generator's offline, zero-network behavior.

The snapshots are unmodified. Their MIT licenses are preserved in this
directory. Do not update a commit without regenerating the snapshots and
running the generated direct, SQLite, browser, and workerd/D1 gates.
