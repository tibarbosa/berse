# barbs-erse

Home Assistant integration for comparing single-rate electricity offers published by ERSE for mainland Portugal. It stores one current contract per installation, measures imported energy from a cumulative kWh sensor, and ranks eligible offers by energy plus daily standing charge.

All configured and published comparison prices are **excluding VAT**. The integration does not add VAT, other taxes, network charges, or promotions to its savings calculation. Read each supplier's official offer conditions before changing contract.

## Install with HACS

1. In HACS, add `tibarbosa/ha-erse` as a custom repository in the **Integration** category.
2. Install **barbs-erse** and restart Home Assistant.
3. Add the integration from **Settings → Devices & services → Add integration**.

The repository keeps its existing GitHub address, `tibarbosa/ha-erse`; the Home Assistant domain and product name are `barbs_erse` and `barbs-erse`.

The integration requires Home Assistant 2026.3 or newer. Its PNG brand assets are packaged locally with the integration.

## Configure

Choose an imported-energy sensor with device class `energy`, state class `total` or `total_increasing`, and unit `kWh`. Enter contracted power, your current energy price and standing charge, a billing anchor date, the fixed number of days in each cycle, and a local refresh time. Prices exclude VAT.

Billing periods are consecutive fixed-length cycles. For example, an 8 October anchor and 30 days gives 8 October–6 November, then 7 November–6 December. The start day does not reset monthly. A future anchor displays **Billing has not started**.

Energy and cost views recalculate every five minutes. The catalog follows the configured daily refresh time and retries an unsuccessful automatic fetch hourly; the Refresh offers button forces a new fetch. The current-cost sensor uses Recorder state history when coverage is complete and falls back to continuous hourly statistics, stopping at the last complete-hour boundary. It accrues standing charges for completed local civil days. Changes made through the integration's price number entities are stored with effective timestamps. Before the first recorded price change, the first configured price is used for the earlier part of the cycle. If only hourly statistics are available and a price changed within an hour, the integration leaves current cost unknown because that hour's energy cannot be split reliably.

Offer ranking uses the most recent complete billing period when Recorder coverage is available. Otherwise it uses the elapsed part of the active cycle and labels the result **Partial period**. With no usable consumption, the ranking is empty. There is no assumed household profile.

Advanced options control regulated/free market selection, indexed estimates, offers with conditional eligibility, and savings notification thresholds. A conditional offer is included only when the user enables it and ERSE explicitly reports zero annual service cost. Offers with missing service costs, positive mandatory service costs, or ERSE consumption-range values are excluded from savings comparisons until their costs and units can be represented safely. Indexed offers are estimates and are not a guaranteed future price.

## Offers card

In storage-mode dashboards, the integration registers its local card resource. Add it with **Edit dashboard → Add card → barbs-erse Offers**, choose the **Best offers** sensor, then save. The visual editor lets you select the sensor after entity renames. The card reads offer records and update metadata from that sensor; it does not assume companion entity IDs.

For YAML-managed dashboards, add the module resource to the dashboard's resource configuration:

```yaml
lovelace:
  resources:
    - url: /barbs_erse/barbs-erse-offers.js?v=0.1.0
      type: module
```

Then add the card:

```yaml
type: custom:barbs-erse-offers
entity: sensor.barbs_erse_best_offers
```

The entity ID above is the default. Select the actual entity ID if Home Assistant has suffixed or renamed it. A native Markdown fallback is in [examples/offers-markdown-card.yaml](examples/offers-markdown-card.yaml).

## Savings notifications

The integration fires `barbs_erse_cheaper_offer` after a successful catalog refresh when an offer is newly eligible or its comparable price improves and it has positive savings. The event groups matching candidates and reports costs and savings excluding VAT. The first successful catalog establishes a baseline; enable **Send an initial savings summary** if you want an initial event. Failed or stale updates and missing consumption do not emit savings events.

Import the automation blueprint from [blueprints/automation/cheaper_offer.yaml](blueprints/automation/cheaper_offer.yaml), then choose a notification action such as a mobile notification or persistent notification. Example event fields and a notification action are documented in [docs/ERSE_DATA.md](docs/ERSE_DATA.md).

## Entities

Each configured energy sensor creates one automatically named device with these entities:

| Entity | Purpose |
|---|---|
| Energy price | Current contract EUR/kWh, excluding VAT |
| Standing charge | Current contract EUR/day, excluding VAT |
| Contracted power | Contracted kVA |
| Billing start | Editable cycle anchor date |
| Billing days | Positive fixed cycle length |
| Update time | Daily local catalog refresh time |
| Refresh offers | Manual ERSE catalog refresh |
| Energy used | Imported kWh in the current cycle |
| Current cost | Recorded energy and accrued standing charge to the shown cutoff |
| Best offers | Count of the displayed offers, with up to ten compact records in attributes |
| Potential savings | Difference against the best comparable offer |
| Last update | Last successful fetch and validation |
| New offers | Eligible additions since the preceding successful ERSE snapshot |

Users can rename entities through Home Assistant. Names and entity IDs are never used as identity keys.

## Data and scope

The integration follows the `csvPath` in ERSE `Settings.json` and downloads the full ZIP. It normalizes single-rate electricity rows locally and stores only the compact catalog, not the full source tables in Recorder. Source data is external content: official supplier and offer names remain unchanged, while authored documentation and UI are English.

ERSE currently supplies no dedicated supplier-name table. Until a supplier code has a reviewed mapping with provenance, its source code is shown. Eligibility is deliberately conservative: the parser excludes non-domestic segments, missing or conflicting prices, missing validity dates, and offers with consumption-range values whose units have not been validated. The exact inclusion and field behavior is described in [docs/ERSE_DATA.md](docs/ERSE_DATA.md).

## Migration

The integration domain changed from `erse_energy` to `barbs_erse`, which Home Assistant treats as a different integration. Follow [docs/MIGRATION.md](docs/MIGRATION.md) before switching an existing installation. Prices must be re-entered excluding VAT; an old arbitrary date range is not converted into a recurring cycle.

## Development

The project uses Ruff, pytest, Home Assistant hassfest, HACS validation, and a JavaScript syntax check in GitHub Actions. Run local checks with:

```bash
python -m pip install -r requirements_test.txt ruff
python -m pytest
ruff check .
node --check custom_components/barbs_erse/frontend/barbs-erse-offers.js
```

The HACS release uses the default-branch directory distribution (`zip_release: false`). No frontend dependency or separate frontend repository is required.
