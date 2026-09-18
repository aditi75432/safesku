# SaferProducts.gov data source

SafeSKU uses the public SaferProducts.gov `IncidentDetails` OData service as a secondary product-safety evidence source.

## Authentication

The CPSC developer documentation requires an application key and specifies that it is sent as the username in HTTP Basic Authentication with no password.

Store the key locally in `.env`:

```env
SAFERPRODUCTS_API_KEY=...
```

Never commit the key.

## Fields used by SafeSKU

The live service exposes scalar fields used for:

- incident date and publication date
- incident description and location
- product brand, model, description, category, UPC, serial number
- manufacturer
- retailer

OData navigation/deferred properties are ignored unless explicitly modeled later.

## Temporal rule

For historical pre-recall analysis, an incident is eligible only when:

```text
incident_date < recall_date
```

Publication date is retained separately. This allows the experiment to distinguish when an event occurred from when the report became publicly available.

## Probe-first workflow

Run:

```powershell
python scripts\probe_saferproducts.py
```

The probe requests two one-record pages (`$skip=0` and `$skip=1`) and prints only schema/field summaries. This verifies that OData paging parameters advance through the dataset before bulk ingestion is implemented.
