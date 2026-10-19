# Changelog

## 0.2.1

- Add a Current cost pricing option to apply current contract rates to the whole measured period when correcting setup prices, without deleting recorded price history.
- Keep hourly-statistics costs available after standing-charge-only or numerically unchanged price edits.
- Preserve the unknown cost guard for genuine energy price changes within an hour in recorded-price mode.
- Expose current-cost pricing mode, consumption source and failure notes in sensor attributes and diagnostics.

## 0.2.0

- Rename the integration and domain to berse; use a fresh setup.
- Show the five cheapest eligible offers, including offers without savings.
- Add manual consumption per billing period without an energy sensor.
- Add a cost-bar dashboard card with two-decimal values and a current-contract reference.
- Package the supplied berse logo and document the HACS search icon limitation.

## 0.1.2

- Treat blank ERSE service costs as zero when the source explicitly says no additional services are required.
- Rebuild cached catalogs after parser upgrades so updated eligibility rules take effect immediately.

## 0.1.1

- Fix Home Assistant setup form number selector validation.
- Fix ERSE catalog ZIP content negotiation.

## 0.1.0

- Introduce the `berse` Home Assistant integration domain and English setup flow.
- Add fixed-length billing cycles, single-rate offer parsing, comparison sensors, and persistent update snapshots.
- Add a dashboard offers card, a savings event, and an automation blueprint.
- Package local PNG branding and HACS metadata.
