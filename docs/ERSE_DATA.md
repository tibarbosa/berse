# ERSE data contract — single-rate electricity

Inspection date: 12 October 2026. This document describes the observed source snapshot and the single-rate implementation behavior. CSV units, supplier-code names, and all eligibility legends remain subject to validation against official offer documents and simulator results before a production savings claim is treated as authoritative.

## Source and files

Discover the current download URL through the `csvPath` property of [Settings.json](https://simuladorprecos.erse.pt/config/Settings.json). Do not hardcode a snapshot URL in the integration.

Observed snapshot: [20261008 113816 CSV.zip](https://simuladorprecos.erse.pt/Admin/csvs/20261008%20113816%20CSV.zip).

SHA-256: `f3ecd1245ea255f32be8309850f30925f35992d7463eb7d6b161f9a841ba5ca8`.

| ZIP entry | Rows excluding header | Columns | Uncompressed bytes | Purpose |
|---|---:|---:|---:|---|
| `csv\CondComerciais.csv` | 910 | 66 | 1,950,719 | Offer identity, conditions, validity, eligibility and links |
| `csv\Precos_ELEGN.csv` | 17,121 | 12 | 1,003,248 | Electricity and gas price variants |

Files use UTF-8 with BOM, semicolon delimiters, decimal commas and `dd/mm/yyyy` dates. Some cells are empty or whitespace-only. Preserve identifiers as text and parse monetary values with Decimal. Empty prices are not zero.

The ZIP is downloaded in full. The normalized runtime catalog retains only the data needed for single-rate electricity. There is no known server-side single-rate ZIP endpoint.

## Relationships

```text
CondComerciais (COM, COD_Proposta)
                  |
                  | one offer condition to multiple price variants
                  v
Precos_ELEGN (COM, COD_Proposta, Pot_Cont, Contagem)
                  |
                  | electric terms present; Contagem == "1"
                  v
Single-rate electricity variant
```

`(COM, COD_Proposta)` is unique across the 910 observed condition rows. Join on both keys. For a normalized single-rate electric variant, use supplier code, proposal code and power; include the counting code in persistent identity for explicit provenance.

Before separating energy components, 204 groups of price rows have matching dimensional keys but different contents. Some contain gas terms in one row and electric terms in another. Do not remove these by blindly keeping the first occurrence.

Across all electricity counting options, 16,235 rows have both `TF` and `TV|TVFV|TVP` populated, with no duplicate `(COM, COD_Proposta, Pot_Cont, Contagem)` keys after that filter. This is not the number of eligible single-rate offers.

The snapshot also contains 40 price rows without matching conditions, four for each of `CURBEI`, `CURDIA`, `CURSON`, `CURDUR`, `CURLIS`, `CURLUS`, `CURMED`, `CURPAX`, `CURSET`, `CURTAG`. These observed orphans are gas rows and must not enter an electricity ranking.

## Implemented conservative policy

The parser reads the exact filenames and source keys shown below. It preserves official offer names, joins on `(COM, COD_Proposta)`, keeps counting option `1`, and groups price components before distinguishing electricity from gas. Conflicting electric rows are excluded with a diagnostic; gas-only rows and unmatched conditions do not enter the catalog. A parser-version change bypasses the saved ETag once so the cached catalog is rebuilt using the new interpretation.

Only `Segmento=Dom` is included. `Ndom` is excluded, and `Tod` is not assumed to mean a domestic offer until the source legend has been reviewed. Offers with missing/invalid validity dates are excluded. `Data ini` and `Data fim` are checked against the current local date whenever rankings are recalculated, including after an unchanged source response.

`FiltroPrecosIndex_ELE` is interpreted only for explicit scalar yes/no values. Any non-empty unknown marker is treated as indexed and is excluded by default. The additional-service flag follows the same rule and is treated as conditional unless it is explicitly false. A blank annual service cost paired with `FiltroServicosAdic=N` means no additional service cost; a blank cost with `S` or an unknown flag remains unresolved. A conditional offer is only compared when the user enables that filter and the source explicitly reports zero annual service cost. Offers with unresolved service costs, positive mandatory annual service costs, or `ConsIni_ELE`/`ConsFim_ELE` limits are excluded from savings comparisons until those costs and units can be represented safely. The original condition strings remain in offer details.

The repository's `supplier_names.json` is empty because no reviewed, provenance-backed supplier code mapping is available yet. The integration therefore displays the exact source code as the supplier label. `TUR` is classified as the regulated reference based on the observed source example; other source codes are classified as free-market offers. The source does not provide a dedicated market column, so this mapping must be rechecked against current ERSE documentation.

Source settings are fetched on every catalog refresh and `csvPath` is followed dynamically. The full ZIP is size-limited and validated before parsing. Catalog and identity snapshots, successful timestamp, ETag and addition delta are written together only after validation; failures retain the last valid catalog and last successful delta. Refreshes share a lock, and a just-completed refresh is coalesced across entries.

## Required price fields

| Exact source key | English normalized meaning | Treatment |
|---|---|---|
| `COM` | Supplier code | Join key and supplier mapping |
| `COD_Proposta` | Offer ID | Join key and identity |
| `Pot_Cont` | Contracted power | Parse as kVA; compare with selected power |
| `Contagem` | Counting option | Accept only `1` for single rate |
| `TF` | Standing charge | Expected EUR/day; verify source units and VAT-exclusive basis |
| `TV\|TVFV\|TVP` | Energy price | For counting option 1, expected EUR/kWh; verify source basis |

Ignore `TVV|TVC` and `TVVz` for this release. Exclude gas-only rows using component presence rather than assuming `Pot_Cont` alone proves an electric row. `Escalao`, `ORD`, `TFGN` and `TVGN` do not feed the single-rate calculation.

## Required condition fields

| Purpose | Exact source keys |
|---|---|
| Identity and presentation | `COM`, `COD_Proposta`, `NomeProposta`, `TxTModalidade` |
| Supply and segment | `Fornecimento`, `Segmento` |
| Counting and consumption eligibility | `TipoContagem`, `ConsIni_ELE`, `ConsFim_ELE` |
| Validity | `Data ini`, `Data fim`, `DuracaoContrato` |
| Indexation | `FiltroPrecosIndex_ELE`, `TxTAtualizaPrecos`, `TxTERSE` |
| Contract conditions | `FiltroContratacao`, `Filtrofaturacao`, `FiltroPagamento`, `FiltroAtendimento`, `FiltroFidelização` |
| Other eligibility | `FiltroRenovavel_ELE`, `FiltroRestrições`, `FiltroServicosAdic`, `FiltroTarifaSocial`, `FiltroReembolsos`, `FiltroNovosClientes` |
| Service costs | `CustoServicos_s/IVA (€/ano)`, `CustoServicos_c/IVA (€/ano)` |
| Reimbursements | `ReembFixo (€/ano)`, `ReembTF_ELE (%)`, `ReembTW_ELE (%)`, `ReembW_ELE (€/kWh)` |
| New-customer benefits | `DescontNovoCliente_c/IVA (€/ano)`, `Desc. TF_ELE (%) - Novo Cliente`, `Desc. TW_ELE (%) - Novo Cliente`, `Desc. W_ELE (€/kWh) - Novo Cliente` |
| Explanations | `TxTOferta`, `TxTERSE`, `TxTContratação`, `TxTFatura`, `TxTPagamento`, `TxTFidelização`, `TxTRestricoesAdic`, `Detalhe restrições`, `DetalheOutrosDesc/benefi`, `TxTServicoAdic`, `TxToutrosServicoAdic`, `TxTReembolsos` |
| Source links | `LinkCOM`, `LinkOfertaCom`, `LinkFichaPadrao`, `LinkCondicoesGerais` |

Retain only the condition data needed for eligibility, cost integrity and offer details. Contact and gas-specific fields are not needed for the requested quick comparison.

Observed `Fornecimento` values: ELE (414), DUAL (361), GN (135). For this scope, include ELE only. Observed segments include Dom, Ndom and Tod; validate their semantics and select domestic-compatible offers. There are 76 condition rows marked indexed across all segments/supplies, not 76 eligible single-rate offers.

`TipoContagem` values such as `123` describe supported counting options. They are not a counting option numbered 123. Price rows remain authoritative for whether a particular single-rate power variant exists.

Some filters are S/N, others are positional strings such as `111` or `100`. Do not invent meanings for bit positions. Confirm the legend before using them for automatic eligibility; retain human-readable conditions for inspection.

## Real source example

Condition key: `COM=TUR`, `COD_Proposta=TUR`. The observed condition is an electricity regulated-price reference valid from 1 October to 31 December 2026.

Matching single-rate price row:

```text
Pot_Cont=4,6
Contagem=1
TF=0,2499
TV|TVFV|TVP=0,1711
```

Assuming EUR/day and EUR/kWh excluding VAT, 300 kWh and 30 days produce:

```text
300 * 0.1711 + 30 * 0.2499 = EUR 58.827
Displayed base cost: EUR 58.83
```

This verifies the join and arithmetic, not the complete commercial/fiscal interpretation. Before release, reconcile representative source values with official offer documents and simulator results. No VAT is added by barbs-erse.

The official [ERSE electricity simulator](https://simuladorprecos.erse.pt/eletricidade/) labels contract inputs as EUR/kWh for energy and EUR/day for contracted power, and instructs consumers to enter those prices without VAT. That confirms the simulator's user-input units and VAT basis. It does not, by itself, prove that every `TF`/`TV|TVFV|TVP` CSV value is a direct one-to-one match for those inputs or that all included charges are represented. The example above remains a parser/arithmetic check until it is reconciled against a current official offer document and simulator result.

`TUR` is the regulated reference observed in this snapshot. There is no independent market column. Document this mapping; do not equate “not indexed” with “regulated.” There is also no dedicated supplier-name table; use a maintained, sourced English-code-to-official-name mapping with source-code fallback.

## New-offer identity

Use `(COM, COD_Proposta, normalized_power_kva, "1")`. Compare the current and previous successful normalized snapshots. Price changes do not change identity. Offer validity and configured eligibility determine whether a newly added variant counts for a specific device. Initial import establishes a baseline of zero additions.

A ZIP can contain expired rows. Download recency does not make them eligible. Missing validity dates require an explicit, validated policy rather than an assumption of unlimited validity.

## Validation gates

Before declaring the comparison ready:

- Confirm units and VAT-exclusive interpretation of electric TF/TV.
- Confirm which discounts and network charges are already embedded; avoid double counting.
- Validate consumption-limit units and annualization separately from the configured N-day billing cycle.
- Exclude unresolved mandatory services/conditional benefits from confirmed savings.
- Label index-linked prices as ERSE estimates when enabled; the ZIP is not an OMIE time series.
- Reject structural corruption atomically and keep the last valid catalog.
- Record source URL, download time, hash, parser version and row provenance for diagnostics.

The current runtime exposes unit prices without rounding them before multiplication and does not subtract discounts or add VAT. The integration records the first configured contract prices, then records each entity-driven price change with an effective timestamp. It uses Recorder state history when coverage is complete and falls back to continuous hourly statistics, stopping at the last complete-hour boundary. Current-cycle energy is split at recorded price changes using cumulative meter history (linear interpolation between surrounding readings where a change falls between readings). If only hourly statistics are available and a price changed within an hour, current cost is left unavailable because that interval total cannot be split reliably. Standing charges accrue at local midnight for each completed civil day, using the price effective at that day's start. Before the first recorded price change, the first configured price is used for the earlier part of the cycle.

## Notification event

`barbs_erse_cheaper_offer` groups candidates in one event. Event data includes `reference_kwh`, `reference_days`, `price_basis: excluding VAT`, and a `candidates` list. Each candidate includes source identity, supplier/offer names, contracted power, unit prices, comparable base costs, savings, indexation status and terms URL. The included automation blueprint accepts a user-selected notification action. Position changes alone do not change identity; the baseline and prior unit prices are stored between restarts.

The integration's authored documentation and labels are English. Exact source headers and original official commercial names remain unchanged because translating them would break parsing or misidentify offers.
