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
    - url: /berse/berse-offers.js?v=0.2.1
      type: module
```

## Compare the same period

Every offer uses `kWh × energy price + days × standing charge`. The dashed reference comes from the offer record's `current_cost`, calculated over that exact same period. The measured current-cycle cost sensor may cover a different period and is not used as the chart reference.

Bars start at zero and share one scale. Green means cheaper, grey means equal cost at displayed cent precision, and red means more expensive. Text badges explain the difference without relying on color. The five cheapest eligible offers stay visible even if all cost more. Costs and consumption use two decimal places; sorting retains the original precision. Expand **Offer details** for validity, eligibility and supplier links.

Manual mode uses your configured kWh for the full billing period. It never invents measured energy history. Example: 100 kWh over 30 days at EUR 0.20/kWh plus EUR 0.40/day gives a current-contract estimate of EUR 32.00.

## Preview and customize

From the repository root, run `python3 -m http.server 8090`, then open `http://localhost:8090/examples/preview.html`. This uses the real card with explicitly fictional data, including cheaper, equal and more-expensive offers. It also demonstrates an all-more-expensive case. No HA account is needed for the preview.

Optional card configuration:

```yaml
type: custom:berse-offers
entity: sensor.berse_best_offers
title: Your 5 best offers
```

The card follows Home Assistant theme variables, supports narrow dashboard columns, escapes supplier text through DOM text nodes, and accepts only HTTPS supplier links. Stale, missing-history, unavailable and empty-result states have explicit messages. The refresh button uses the sensor's registered companion entity rather than guessing its ID.
