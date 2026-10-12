# barbs-erse implementation plan

Revision: 12 October 2026. Status: implementation draft. This revision supersedes the previous implementation plan. A release is not considered complete until the source, HACS, hassfest, and real Home Assistant acceptance gates below have been verified.

## 1. Confirmed scope

- Product and eventual repository name: **barbs-erse**.
- Home Assistant integration domain and Python directory: **barbs_erse**.
- Installation through HACS as a custom integration.
- All authored repository content in English: documentation, filenames, code, comments, tests, UI labels, errors, notifications, examples and release notes.
- Clear, short entity names and an automatically named device. No profile-name question during setup.
- One cumulative imported-energy sensor in kWh per configured installation.
- **Single-rate electricity only.** No time-of-use selector, off-peak controls or two/three-rate prices.
- **All comparison prices exclude VAT.** No VAT selector or inclusive-VAT mode.
- One billing anchor date and a positive billing-period length in days. Consecutive fixed-length cycles; no monthly day reset and no editable end date.
- Daily ERSE ZIP refresh at a configurable local time.
- A compact dashboard card showing up to ten best offers, daily standing charge, kWh price, last successful refresh and new-offer count.
- Preserve the original requirement for Home Assistant savings notifications and relevant market/eligibility filters.

Source column names and official supplier/offer names must remain exact for interoperability and identity. Portuguese text received from ERSE is external data, not an authored UI translation. Do not translate an official offer name into an invented name. Document source fields in English while quoting exact CSV keys where necessary.

## 2. Changes from the existing repository

The inspected checkout is `/home/tiago/repos/ha-erse`, with domain `erse_energy` and origin `git@github.com:tibarbosa/ha-erse.git`. It already contains an initial integration. The implementation must adapt that code rather than assume an empty repository.

| Existing behavior | Required behavior | Reason |
|---|---|---|
| Portuguese UI and documentation | English throughout authored content | A consistent project language |
| User-supplied profile name | Automatic device name | Less setup friction |
| Start/end date controls | Anchor date + consecutive N-day cycles | Match the requested billing model |
| Single/two/three-rate selector | Single-rate behavior only | Avoid exposing unsupported functionality |
| VAT basis selector | VAT-exclusive inputs and calculations | One consistent comparison basis |
| Provisional offer preview | Compact ranked Top 10 with price pairs | Fast dashboard consultation |
| Catalog timestamp only | Separate last successful refresh and new-offer count | Show data freshness and actual additions |
| `erse_energy` domain | `barbs_erse` domain | Match the new product identity |
| SVG in root brand folder | Packaged PNG branding in integration directory | Meet current HA/HACS packaging requirements |

Do not silently convert an existing inclusive-VAT profile into exclusive-VAT prices. Require price re-entry when migrating such a profile. An old arbitrary start/end range also requires choosing an anchor and duration; do not guess its intended recurrence.

## 3. Naming and setup

Use `barbs-erse` as the integration title and default device name. The config-entry title is automatic. For multiple entries, derive a readable suffix from the chosen energy sensor's friendly name; never prompt for a custom name. Use immutable registry/config-entry identifiers for unique IDs, not display names.

Use Home Assistant entity naming (`has_entity_name=True`) so labels are short on the device page and have a device prefix elsewhere. Users remain free to rename entities through HA.

| Entity label | Proposed default entity ID | Purpose |
|---|---|---|
| Energy price | `number.barbs_erse_energy_price` | Current contract EUR/kWh, excluding VAT |
| Standing charge | `number.barbs_erse_standing_charge` | Current contract EUR/day, excluding VAT |
| Contracted power | `select.barbs_erse_contracted_power` | kVA, including 4.6 and 5.75 |
| Billing start | `date.barbs_erse_billing_start` | Anchor date; the only editable date |
| Billing days | `number.barbs_erse_billing_days` | Positive integer cycle length |
| Update time | `time.barbs_erse_update_time` | Daily local refresh time |
| Refresh offers | `button.barbs_erse_refresh_offers` | Manual refresh |
| Energy used | `sensor.barbs_erse_energy_used` | Imported kWh in the current cycle |
| Current cost | `sensor.barbs_erse_current_cost` | Cost incurred to the displayed cutoff |
| Best offers | `sensor.barbs_erse_best_offers` | Number of displayed offers, compact list in attributes |
| Potential savings | `sensor.barbs_erse_potential_savings` | Savings over the ranking reference period |
| Last update | `sensor.barbs_erse_last_update` | Last successful catalog refresh timestamp |
| New offers | `sensor.barbs_erse_new_offers` | Additions compared with the previous successful refresh |

Entity IDs are defaults, not hardcoded references: HA may suffix them or users may rename them. The dashboard editor must use an entity selector and derive its companion data from the selected Best offers entity.

Setup fields:

1. **Energy sensor** — select and validate an imported-energy cumulative sensor in kWh.
2. **Contracted power**, **Energy price**, **Standing charge** — help text says “All prices exclude VAT.”
3. **Billing start**, **Billing days** — example: 2026-10-08 and 30 days.
4. **Update time** — suggested default 03:15 in HA's configured timezone.

Put advanced eligibility and notification options in the options flow. Mainland Portugal is the documented scope; no region selector suggesting unsupported regions. No name, tariff-type, VAT-basis or end-date questions.

## 4. Billing-cycle semantics

Let `A` be the anchor local calendar date and `N` the configured positive integer number of days. For a date `T >= A`:

```text
cycle_index = floor((T - A).days / N)
cycle_start = A + cycle_index * N days
cycle_end_exclusive = cycle_start + N days
```

Use half-open intervals internally. Render the last included date as `cycle_end_exclusive - 1 day`.

Example: anchor **8 October 2026**, duration **30 days**:

- Cycle 1: 8 October–6 November.
- Cycle 2: 7 November–6 December.
- Cycle 3: 7 December–5 January.

The start day intentionally moves across calendar months. Do not restart on the eighth of every month. Local civil days retain their meaning across daylight-saving changes; do not calculate cycle boundaries using multiples of 86,400 seconds.

If the anchor is in the future, show “Billing has not started” instead of a negative cycle. Changing the anchor or length recomputes the active cycle and notification baseline. Derived cycle dates can appear in read-only attributes/card text; there is no separate date-range feature.

**Current cost:** consume actual measured energy from the cycle start to a stated data cutoff. Count standing charges through the same cutoff under a documented daily accrual convention: at local midnight, accrue the completed civil day's standing charge. Use precise history/current readings for the live portion where available; if only hourly statistics are available, report the last complete-hour cutoff. Do not charge a full N days against only a few days of measured energy.

**Ranking reference:** prefer the most recent complete N-day cycle with full coverage. If unavailable, use the elapsed part of the active cycle with a clear “Partial period” label and the same energy/days for every offer. With no usable consumption, show an empty ranking and “Not enough consumption data”; do not invent a consumption profile or sort solely by kWh price. No manual start/end selection is needed for either view.

Historical current-contract prices need effective dates recorded internally when changed. Preserve actual cost history; for switching comparisons, apply today's contract prices and today's candidate prices to the same reference consumption.

## 5. ERSE ingestion — single-rate only

Fetch `https://simuladorprecos.erse.pt/config/Settings.json` and follow `csvPath` on each refresh. The server supplies the full ZIP; single-rate filtering happens locally after download, not via an imaginary filtered endpoint.

Read only the necessary CSV entries in memory:

- `CondComerciais.csv`: identity, eligibility, validity, terms, supplier/offer links, mandatory service costs and indexation markers.
- `Precos_ELEGN.csv`: join keys, power, counting option, standing charge and single-rate energy price.

Keep electric price rows with `Contagem=1`, required electric terms present, and a matching eligible electricity condition. Exclude gas-only rows, dual-fuel bundles, and two/three-rate variants from the normalized catalog. In price rows, `TF` is the intended daily standing charge and `TV|TVFV|TVP` the single-rate energy term; verify units and VAT-exclusive basis against official examples before enabling monetary claims.

Normalize authored model fields to English: `supplier_code`, `offer_id`, `supplier_name`, `offer_name`, `power_kva`, `standing_charge`, `energy_price`, `valid_from`, `valid_until`, `indexed`, `terms_url`, and eligibility fields. Maintain exact source keys only in the parser/source documentation.

Join using `(COM, COD_Proposta)`. A normalized single-rate variant is identified by `(COM, COD_Proposta, power_kva, "1")`. Do not discard meaningful duplicates before separating gas and electricity components. Exclude ambiguous conflicting electric variants with a diagnostic.

Resolve supplier display names through a reviewed code-to-name mapping with provenance. The ZIP has no dedicated supplier-name table. If unknown, display its source code; never guess from a shortened offer title. Preserve offer names in details to distinguish two offers from one supplier.

Download limits, ZIP entry checks, BOM handling, decimal commas, missing-price checks, validity and atomic cache replacement remain required. Network or structural failures preserve the last valid catalog. Recompute validity locally even when the file hash is unchanged.

## 6. Cost and ranking policy

Every comparison is in EUR **excluding VAT**:

```text
base_cost = reference_kwh * energy_price
          + reference_days * standing_charge
savings = current_contract_base_cost - candidate_base_cost
```

Use Decimal arithmetic. Display the full published precision needed for unit prices, rather than rounding prices to cents before multiplying.

Rank by combined cost for the same contracted power and consumption reference, not by energy price alone. Display the concise price pair requested while retaining ranking inputs and total costs in details. Return up to ten eligible offers, without padding. Multiple offers from one supplier are permitted; details identify each offer. A later optional supplier-deduplication filter must not silently change “ten offers” into “ten suppliers.”

This scope is energy + standing charge, excluding VAT and other taxes. To keep savings meaningful, default to offers without unresolved mandatory services or conditional costs. Where known mandatory charges apply, either calculate them explicitly on both sides or exclude the offer from savings claims. Do not subtract discounts already included in published prices. Treat non-cash promotions separately.

Keep filters for regulated/free market, indexed/non-indexed and commercial eligibility. Single-rate is enforced, never a selectable filter. Indexation is independent of regulated/free market. Indexed offers, if enabled, use ERSE's published estimate and carry an “Indexed estimate” badge; do not claim an actual or guaranteed future price. Savings notifications for estimated indexed offers require an explicit option. Do not add an OMIE feed to this release.

## 7. New offers and successful updates

Maintain a persistent set of single-rate offer-variant identities from each successful refresh. A “new offer” is an identity present now and absent from the immediately preceding successful snapshot.

For each device, count additions at its selected power, then apply that device's eligibility filters. The count covers all eligible additions, **not just additions entering the Top 10**. Store each addition's identity so the count can be audited.

- First successful download: establish baseline, `new_offers=0`.
- Same identity with a changed price: not new; potentially a savings event.
- Reordered Top 10: not new.
- Removed offer: not new.
- Reappearance after absence in the previous snapshot: new again, per the requested comparison rule.
- Successful unchanged response, including a validated HTTP 304: advance last-success time and set new count to zero.
- Failed update: keep last-success timestamp and last successful delta unchanged; show stale/error state separately.
- Restart: restore snapshots and delta; no false “everything is new.”
- Changed power/filters: rebuild the baseline for that configuration and reset the counter; do not call user configuration changes ERSE additions.

Write the new catalog, previous/current identity sets, successful timestamp and delta atomically. Guard manual/scheduled refreshes with a lock so one download cannot become another simultaneous download's false baseline.

Distinguish “Last update” (successful fetch/validation) from “Catalog version” (source content). A recent check of unchanged data is not a new publication by ERSE.

## 8. Dashboard experience

Deliver a dedicated **barbs-erse Offers** card with a visual editor and a native Markdown fallback. Register the card with Home Assistant's card picker and load its resource through a supported, tested mechanism packaged with the integration. All frontend runtime assets stay inside `custom_components/barbs_erse/`; no separate HACS frontend repository or external card dependency is required.

User flow: **Edit dashboard → Add card → barbs-erse Offers → select Best offers entity → Save**. Editing an existing dashboard remains a deliberate user action. Do not inject cards into dashboards automatically.

The custom card must expose a stub configuration and visual editor, handle renamed entities, and render supplier-provided text safely as text rather than raw HTML. If auto resource registration is unavailable for a YAML-managed dashboard, provide the exact resource path and a manual fallback in the English README. Verify registration, unloading, cache-busting and updates in a real HA frontend before calling this flow complete.

Illustrative layout; the companies and prices below are fictional:

```text
barbs-erse · Best offers
4.6 kVA · Single rate · Excluding VAT

Company A: €0.3500/day / €0.1600/kWh
Company B: €0.4200/day / €0.1580/kWh
Company C: €0.3000/day / €0.1750/kWh
... up to 10 eligible offers

Last update: 12 Oct 2026, 03:15
New offers: 3

Ranking: 300 kWh over 30 days
[Refresh]                         [Offer details]
```

For this example, costs are A €58.50, B €60.00 and C €61.50. A ranks first even though B has a lower kWh price. Unit prices are the main content; total cost, offer identity, savings and conditions are available in details. The card displays update time in HA's local timezone. Also handle loading, no matching offers, insufficient consumption and stale data without hiding the last successful timestamp.

The Best offers sensor contains a maximum of ten compact records plus `last_successful_update`, `new_offer_count`, reference consumption/days, power, status and summary metadata. This makes the card self-contained and avoids guessing related entity IDs. The full catalog must not be copied into entity attributes or Recorder history.

## 9. Savings notifications

Emit `barbs_erse_cheaper_offer` for newly eligible or materially improved offers whose comparable cost is lower than the current contract. Provide an English blueprint with a user-selected notification action, supporting mobile and persistent notifications.

Persist deduplication across restarts; changes in position alone do not notify. Group multiple candidates into one message. Separate notification policy from the New offers counter: a price reduction can trigger a savings alert without increasing new-offer count.

Default threshold: any positive saving; configurable minimum EUR and percentage. When both thresholds are set, require both. Use the same ranking reference and display base-cost/excluding-VAT scope. Suppress alerts for failed/stale data or insufficient consumption. The first successful setup establishes a baseline; offer an optional initial summary.

## 10. Branding and HACS-ready repository

Generate an original, simple electricity/comparison icon, not an ERSE official logo. Supply transparent PNG assets readable on light and dark backgrounds, with a maintained vector source if useful. Proposed assets: square 256×256 `icon.png` and 512×512 `icon@2x.png`, plus dark variants if contrast requires them.

Package them at `custom_components/barbs_erse/brand/`. An SVG alone in a root-level folder does not satisfy the delivery. Inspect actual PNG rendering and check current HACS/HA validation requirements during implementation. Local branding is supported by HA 2026.3+; set the actual minimum HA version to the version proven by testing, not merely the branding minimum.

Target tree:

```text
barbs-erse/
  custom_components/barbs_erse/
    __init__.py
    manifest.json
    const.py
    config_flow.py
    coordinator.py
    entity.py
    sensor.py
    number.py
    select.py
    date.py
    time.py
    button.py
    diagnostics.py
    strings.json
    translations/en.json
    erse_client.py
    parser.py
    models.py
    billing.py
    consumption.py
    pricing.py
    notifications.py
    storage.py
    frontend/barbs-erse-offers.js
    brand/icon.png
    brand/icon@2x.png
  docs/IMPLEMENTATION_PLAN.md
  docs/ERSE_DATA.md
  docs/MIGRATION.md
  examples/offers-card.yaml
  examples/dashboard.yaml
  blueprints/automation/cheaper_offer.yaml
  tests/
  .github/workflows/ci.yaml
  .github/workflows/validate.yaml
  hacs.json
  pyproject.toml
  README.md
  CHANGELOG.md
  LICENSE
```

Release requirements:

- Exactly one integration domain in `custom_components`.
- Real version, `config_flow`, Recorder dependency, appropriate integration/iot type, codeowner, documentation and issue URLs in the manifest.
- `hacs.json` with actual minimum supported HA version and valid metadata.
- English installation, setup, billing, card, notification, troubleshooting and migration documentation.
- Actual runnable card, notification event producer and blueprint; no example advertising an unimplemented capability.
- Existing license preserved unless intentionally changed.
- Lint, unit/integration tests, frontend checks, HACS validation and hassfest in CI.
- Release artifacts matching HACS download behavior; if using the default-branch directory distribution, document it and avoid an unnecessary custom ZIP process.
- No placeholder URLs or pending translations in the release deliverable.

The current GitHub URL is known; a future URL such as `tibarbosa/barbs-erse` is not yet verified. Renaming the local/product domain does not rename GitHub. During implementation, either retain the existing remote URL with the new product name or explicitly rename/create the repository and update real links. Do not claim push-readiness with nonexistent issue/documentation URLs. Publishing or pushing is a separate action from preparing the files.

## 11. Migration approach

Changing an HA integration domain is not a normal options migration. Preserve the existing implementation while preparing the replacement and document a controlled transition:

1. Export or record current prices, energy entity and refresh preferences.
2. Remove/disable the old integration entry before activating the replacement to avoid duplicate scheduled updates and notifications.
3. Install the new `barbs_erse` component and add it with the simplified flow.
4. Re-enter VAT-exclusive prices, billing anchor and duration.
5. Update dashboard/automation entity references; remove obsolete old entities and component files after confirming operation.

An automatic migration may be implemented only if it is validated against HA's registries and domain constraints. Do not promise preservation of old entity IDs across a domain rename. For new installations, no migration steps are necessary.

## 12. Implementation phases and acceptance criteria

| Phase | Deliverable | Acceptance |
|---|---|---|
| 1 | English naming, new domain, migration instructions | No authored Portuguese UI/docs; no name, tariff or VAT selector |
| 2 | N-day cycle engine and consumption adapter | Correct rolling cycles across months, leap days and DST; future anchor and missing history handled |
| 3 | Single-rate catalog, snapshots and delta | Only single-rate electrical variants; first/repeated/failed/restarted updates produce correct new counts |
| 4 | Comparable costs, filters and savings | Common power/reference period, VAT-exclusive costs; official sample validation; no false conditional savings |
| 5 | Card, entities and notifications | Addable from card picker; price pairs, update time and additions visible; notifications deduplicated |
| 6 | PNG branding and release package | Fresh install and upgrade via HACS; frontend icon visible; CI passes; actual repository links valid |

Specific tests: price-vs-standing-charge ranking tradeoffs; duplicate/gas rows; expired/missing-condition offers; empty prices; no eligible offers; catalog unchanged/304; new ID versus changed price; baseline after configuration changes; refresh races; offline cache; energy-meter resets; hourly cutoff; anchor in future; duration validation; cycle boundaries across short months and DST; card renamed-entity behavior; integration reload and restart; blueprint event delivery.

Completion means installing from the target GitHub repository through HACS in a clean supported HA instance, configuring without a name question, adding the card through the UI, and observing both successful scheduled refresh and a controlled notification test. Passing static checks alone is not evidence of end-to-end readiness.

## References

- [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/)
- [HA integration structure and domain naming](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [HA local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/)
- [HA entity naming](https://developers.home-assistant.io/docs/core/entity/)
- [ERSE Settings.json](https://simuladorprecos.erse.pt/config/Settings.json)
