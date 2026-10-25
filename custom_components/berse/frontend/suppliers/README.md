# Supplier logos

These supplier marks are copied without modification from the public ERSE simulator. They identify the corresponding suppliers; their trademarks belong to their respective owners and are not covered by the project MIT license. See `sources.json` for the original URLs and retrieval date.

Home Assistant serves the packaged images locally at `/berse/suppliers/`. The card loads only local bundled or cached image paths, keeps the image aspect ratio, and falls back to initials if an image is unavailable. Unknown suppliers also use initials.

To refresh the collection, retrieve supplier names and `Logotipo` URLs from the ERSE simulator results with a fictional reference profile. Match `CodOferta` against `COD_Proposta` and `COM` in the catalog; do not guess supplier identities from offer-name prefixes. Download only PNG/JPEG marks from ERSE, inspect the format and size, and update `sources.json`, `supplier_names.json` and `supplier_logos.json`. Additional suppliers can be added when a verified mark is available.

The integration also discovers supplier names and logos automatically from ERSE. Downloaded images are stored in `.storage/berse_supplier_logos`, exposed at `/berse/supplier-cache/`, and named by their content hash. Metadata discovery is daily; existing image contents are checked weekly. The bundled collection remains an offline fallback.
