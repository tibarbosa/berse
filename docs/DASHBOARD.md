# berse dashboard card

The bundled `custom:berse-offers` card needs no other custom cards or build tools. All interface text is English. Supplier-provided names and conditions retain their original language.

## Add it to Home Assistant

1. Install and configure berse, then reload the browser to load its registered resource.
2. Edit a dashboard, select **Add card → berse Offers** and choose the integration's **Best offers** sensor.
3. Save. Alternatively paste [offers-card.yaml](../examples/offers-card.yaml) into a manual card. Adjust the entity ID if renamed.

A complete dashboard is in [dashboard.yaml](../examples/dashboard.yaml). For dashboards that manage resources in YAML, register:

```yaml
lovelace:
  resources:
    - url: /berse/berse-offers.js?v=0.4.0
      type: module
```

## Compare the same period

Every offer uses `kWh × energy price + days × standing charge`. The dashed reference comes from the offer record's `current_cost`, calculated over that exact same period. The measured current-cycle cost sensor may cover a different period and is not used as the chart reference.

Bars start at zero and share one scale. Green means cheaper, grey means equal cost at displayed cent precision, and red means more expensive. Text badges explain the difference without relying on color.

The sensor retains up to fifteen cheapest eligible offers, even if all cost more. The card initially shows the best three. The footer combines a **Show** selector (3, 6, 9, 12 or 15 offers) with **Show all 15 offers** / **Show top 3**. Both controls stay synchronized. Fewer available offers shorten the choices and button count; with three or fewer, expansion controls are hidden. The selected count and expanded offer details survive sensor updates while the card remains mounted. Reloading the dashboard or changing the selected sensor returns to the best three. All fifteen offers share one cost scale, which stays fixed when expanding or collapsing. In Sections dashboards, leave the card height at **Auto** to allow it to expand.

Total costs, savings and consumption use two decimal places; energy prices and daily standing charges use four decimal places; sorting retains the original precision.

Essential conditions appear as English labels below each offer. Expand **Offer details** for grouped eligibility, contract, billing and payment, precise unit rates, price-update notes, additional services, validity and links. **Offer factsheet** and **General conditions** use separate source URLs. Missing important data is shown as **Not provided**; no commitment or payment requirements are inferred from missing fields. Portuguese supplier descriptions remain available under **Original ERSE information**. New-customer and promotion flags describe source conditions, not a confirmation that your household qualifies. The integration does not apply additional promotional refunds or social-tariff discounts to the displayed comparison.

Supplier names and logos are discovered daily from ERSE using a fictional reference profile, without submitting your consumption or current rates. Images are cached locally in Home Assistant and checked weekly for changes. Failed discovery preserves previous metadata; bundled logos and initials provide fallbacks. New suppliers appear normally and use initials until matching metadata becomes available. Turn **Show supplier logos** off in the visual card editor or set `show_supplier_logos: false`. Logo sources and refresh instructions are in the frontend suppliers directory.

Manual mode uses your configured kWh for the full billing period. It never invents measured energy history. Example: 100 kWh over 30 days at EUR 0.20/kWh plus EUR 0.40/day gives a current-contract estimate of EUR 32.00.

## Preview and customize

From the repository root, run `python3 -m http.server 8090`, then open `http://localhost:8090/examples/preview.html`. This uses the real card with explicitly fictional data, including cheaper, equal and more-expensive offers. It also demonstrates an all-more-expensive case, fifteen-offer expansion and a shorter result list. No HA account is needed for the preview.

Optional card configuration:

```yaml
type: custom:berse-offers
entity: sensor.berse_best_offers
title: Your best offers
show_supplier_logos: true
```

The card follows Home Assistant theme variables, supports narrow dashboard columns, escapes supplier text through DOM text nodes, and accepts only HTTPS supplier links. Stale, missing-history, unavailable and empty-result states have explicit messages. The refresh button uses the sensor's registered companion entity rather than guessing its ID.
