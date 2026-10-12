# Changelog

## 0.1.2

- Treat blank ERSE service costs as zero when the source explicitly says no additional services are required.
- Rebuild cached catalogs after parser upgrades so updated eligibility rules take effect immediately.

## 0.1.1

- Fix Home Assistant setup form number selector validation.
- Fix ERSE catalog ZIP content negotiation.

## 0.1.0

- Introduce the `barbs_erse` Home Assistant integration domain and English setup flow.
- Add fixed-length billing cycles, single-rate offer parsing, comparison sensors, and persistent update snapshots.
- Add a dashboard offers card, a savings event, and an automation blueprint.
- Package local PNG branding and HACS metadata.
