# berse

![berse logo](custom_components/berse/brand/icon.png)

berse compares the five lowest cost single-rate electricity offers for mainland Portugal in Home Assistant. It supports a cumulative energy sensor or an assumed kWh amount for a billing period.

All comparison prices exclude VAT. Estimates cover energy and the daily standing charge only.

## Data source

berse reads [ERSE's Settings.json](https://simuladorprecos.erse.pt/config/Settings.json), follows its current `csvPath`, and downloads the published offer data. The catalog refreshes daily at the configured time; you can also refresh it from Home Assistant.

## Install with HACS

1. In HACS, open **Integrations → ⋮ → Custom repositories**.
2. Add [`tibarbosa/berse`](https://github.com/tibarbosa/berse) as an **Integration**.
3. Install **berse** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**, search for **berse**, and add it.

Home Assistant displays the bundled logo after installation. HACS search icons for custom integrations depend on the HACS brand catalog; see [the upstream issue](https://github.com/hacs/integration/issues/5402).

## Configure

Choose a consumption source:

- **Cumulative energy sensor:** select an imported energy sensor in kWh with device class `energy` and state class `total` or `total_increasing`.
- **Manual consumption:** leave the sensor empty and enter the total kWh to assume for each billing period, such as **100** or **500**. This is the full period's usage, not usage per day.

Then set the contracted power, your current energy price in EUR/kWh, standing charge in EUR/day, billing start date, billing period length in days, and daily refresh time. Enter prices excluding VAT. Ranking compares each eligible offer using:

```text
consumption_kWh × energy_price + billing_days × standing_charge
```

Sensor mode ranks from the last complete period, or the active partial period when needed. Manual mode uses the configured kWh and full billing period immediately, without Recorder history. The measured **Energy used** and **Current cost** sensors remain unknown in manual mode; the offers card still estimates your current contract for the same assumed consumption.

Under **Configure → Current cost pricing**, choose **Current contract prices for the whole period** if the prices you entered apply to all measured usage in the billing cycle, including corrections to setup values. Choose **Prices recorded over time** for actual tariff changes; hourly history cannot resolve an energy price change within an hour, so Current cost remains unknown in that case. Changing this option preserves recorded price history and does not affect offer rankings.

Market, indexed offer, conditional eligibility, and notification preferences are available under the integration's **Configure** options.

## Dashboard card

In a storage-mode dashboard, select **Edit dashboard → Add card → berse Offers** and choose the **Best offers** sensor. The integration registers the card resource automatically. The card sorts and displays up to five offers, even when none saves money. Its shared cost scale marks your contract with a dashed line: green shows savings, grey shows equal cost, and red shows higher cost. Total costs, savings and consumption use two decimal places; energy prices and daily standing charges use four. Essential conditions appear below each offer. Expand **Offer details** for eligibility, contract duration, billing, precise unit rates, extra services, original ERSE information and supplier documents. Missing important data is marked **Not provided**. Non-indexed prices can still change under the supplier's terms.

Supplier names and logos update automatically from ERSE using a fictional profile; your consumption and contract prices are not submitted. Logos are cached and served locally by Home Assistant, with bundled logos and supplier initials as fallbacks. Discovery runs daily and cached images are checked weekly; new suppliers use initials until ERSE provides a matching logo. Disable **Show supplier logos** in the card editor, or set `show_supplier_logos: false` in YAML.

For a YAML-managed dashboard, add this resource:

```yaml
lovelace:
  resources:
    - url: /berse/berse-offers.js?v=0.3.0
      type: module
```

Then add the card:

```yaml
type: custom:berse-offers
entity: sensor.berse_best_offers
```

Use your actual Best offers entity ID if Home Assistant renamed it. See the [dashboard guide](docs/DASHBOARD.md), [complete YAML dashboard](examples/dashboard.yaml), [standalone card preview](examples/preview.html), or [Markdown fallback](examples/offers-markdown-card.yaml).
