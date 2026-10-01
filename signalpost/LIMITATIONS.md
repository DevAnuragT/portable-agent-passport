# Known limitations

- The default fixture is offline and synthetic; it is not an official Builderr
  evaluation corpus.
- The bulk adapter loads local BRREG CSV/CSV.GZ identity snapshots; it does not
  download or refresh those snapshots itself.
- Refresh history is represented in prior JSONL output and typed change events;
  there is no SQLite or remote durable store.
- Website enrichment is static-only. It does not run JavaScript or a browser.
- Jobs and activity are extracted from verified page links/JSON-LD, not from
  restricted third-party platforms.
- The bundled 100-input smoke report checks contract correctness and linkage;
  it is not a coverage score and must not be described as an official result.
