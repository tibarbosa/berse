# Migration to barbs-erse

`barbs_erse` is a new Home Assistant integration domain. It does not automatically convert an entry or preserve the old `erse_energy` entity IDs.

## Existing installations

1. Record the imported-energy entity, contracted power, current contract prices, refresh preferences, dashboard references, and automations.
2. Remove or disable the old `erse_energy` entry before enabling `barbs_erse`. This avoids duplicate catalog updates and notifications.
3. Install the new component and add **barbs-erse** from **Settings → Devices & services**.
4. Select the cumulative imported-energy sensor and re-enter the contract's current prices **excluding VAT**.
5. Choose the billing anchor and fixed cycle length. The old start and end dates do not indicate an intended recurring cycle, so they are not converted automatically.
6. Update dashboards and automations to use the new entity IDs. Remove obsolete entities after confirming the new integration is operating.

The first successful ERSE refresh establishes a zero-additions baseline. It does not report every catalog row as new.

## New installations

No migration is needed. Configure the integration with the current contract prices, billing anchor, and cycle length.
