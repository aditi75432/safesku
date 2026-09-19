# SafeSKU Data Bundle

The SafeSKU data bundle is the normal onboarding path for local demos and research workspaces.
It turns several raw research artifacts into one portable `.zip` file with a manifest and per-file SHA-256 checksums.

## Why the bundle exists

A product user should not need to understand SafeSKU's internal artifact tree.
The normal workflow is:

```text
research artifacts
      ↓
SafeSKU Bundle Builder
      ↓
one ZIP
      ↓
SafeSKU Data Workspace
      ↓
validate → register → ingest → search → analyze
```

The API still supports individual uploads under the Advanced section for debugging and custom integrations.

## Build a bundle

First inspect what SafeSKU can find:

```powershell
python scripts\inspect_safesku_artifacts.py data
```

When the discovered files are unambiguous, build the bundle. The builder uses the same schema detection as the SafeSKU API and refuses to guess when multiple plausible files exist:

```powershell
python scriptsuild_safesku_bundle.py --root data --output dataundles\safesku-research-bundle.zip
```

For large repositories, explicit paths are safer than filename-based discovery:

```powershell
python scriptsuild_safesku_bundle.py `
  --file cpsc "PATH_TO_CPSC_ARTIFACT" `
  --file saferproducts "PATH_TO_SAFERPRODUCTS_ARTIFACT" `
  --file amazon_products "PATH_TO_AMAZON_PRODUCTS_ARTIFACT" `
  --file linkage "PATH_TO_LINKAGE_ARTIFACT" `
  --output dataundles\safesku-research-bundle.zip
```

Amazon review text is optional. Do not add it until the artifact is a real review-level dataset that SafeSKU can ingest.

## Bundle contract

A bundle contains:

```text
manifest.json
 datasets/
   cpsc/...
   saferproducts/...
   amazon_products/...
   amazon_reviews/...
   linkage/...
```

`manifest.json` records the SafeSKU bundle format, workspace metadata, source type, member path, byte count and SHA-256 for every dataset.
The importer rejects path traversal, unsupported source types, missing members, checksum mismatches and byte-count mismatches.

## What SafeSKU does after upload

1. Stores the ZIP in the local runtime workspace.
2. Reads and validates `manifest.json`.
3. Extracts only declared dataset members into a temporary directory.
4. Verifies every member checksum before registering it.
5. Registers each dataset using the existing streamed ingestion path.
6. Starts ingestion in the background.
7. Shows dataset counts and readiness in the workspace.
8. Makes the resulting evidence searchable and available to the investigation workflow.

The source records remain authoritative. The bundle is only a transport and workspace packaging format.
