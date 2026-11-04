# Data sources and licences

The author-compiled tables and model results in this repository are released under CC BY 4.0
([LICENSE-DATA](LICENSE-DATA)). Third-party data keep their original licences, listed below. Files marked
*modified* were filtered, aggregated, or rescaled by the authors.

## Third-party data included in the repository

| Source | Licence | Files | How it is used |
|---|---|---|---|
| **EWELD** industrial and commercial load dataset. G. Liu et al., *Scientific Data* 10, 2023, [doi:10.1038/s41597-023-02503-6](https://doi.org/10.1038/s41597-023-02503-6); data [doi:10.6084/m9.figshare.21893808.v3](https://doi.org/10.6084/m9.figshare.21893808.v3) | CC BY 4.0 | `02_data/processed/core/manufacturing_31sector_real_weeks.csv` (+ `.lineage.json`) | Weekly production-load shapes. Each industry uses one continuous measured week from one anonymized EWELD user, normalized and rescaled to the industry's load magnitude. The lineage file records the user ID and dates. |
| **WRI Aqueduct 4.0** country rankings. World Resources Institute, 2023, [doi:10.46830/writn.23.00061](https://doi.org/10.46830/writn.23.00061) | CC BY 4.0 | province extract in `02_data/processed/resource_footprint/` (*modified*) | Baseline water-stress categories of Chinese provinces, used for the water-stress shares |
| **CNESA** (China Energy Storage Alliance), monthly energy-storage bid-price report, September 2026, [cnesa.org](https://www.cnesa.org/information/detail/?column_id=58&id=8668) | Published statistics; four published average bid prices are reproduced, see source for terms | `02_data/raw/curated/cnesa_bess_bid_prices_2026_09.csv` | Battery system and EPC cost per unit of power and energy in the battery alternative (Table II) |
| **Epoch AI**, AI Data Centers database, snapshot 2026-09-10, [epoch.ai/data/ai-data-centers](https://epoch.ai/data/ai-data-centers) | CC BY 4.0 | `02_data/processed/node_interconnection/epoch_ai_current_it_power_2026-09-10.csv` (*modified*) | Size distribution of reported AI data centers (Fig. 3) |
| **Danish Energy Agency** technology data catalogue for energy storage, via PyPSA [technology-data](https://github.com/PyPSA/technology-data) | Danish Energy Agency technology catalogue, publicly available; see source for terms | `02_data/raw/curated/battery_cost_parameters_2025.csv` (6 rows; lifetime, O&M, efficiency) | Battery parameters for the PV/storage extension. The two investment values are author-reviewed figures (UCSB China power-system template, NEA reports), as noted in the file. |

## Third-party data downloaded by script

| Source | Licence | Destination | Obtain with |
|---|---|---|---|
| EWELD (full archive, 258 MB) | CC BY 4.0 | `02_data/raw_load_profiles/eweld/EWELD.zip` | `python 08_code/fetch_external_data.py` (MD5-checked) |

## Not included

| Data | Reason | Effect |
|---|---|---|
| Hourly Guangdong day-ahead electricity prices, 28 May – 3 June 2026: province-average day-ahead nodal price (series `44_PMT_AVG_NODE`, 15-min, averaged to hours), Guangdong Power Exchange Center (广东电力交易中心) | Third-party data without redistribution permission | Needed only to re-solve the optimization; see the README for substitutes. The hourly price column was removed from the saved LDC hourly output. |
| Epoch AI original snapshot (`data_centers.csv`, `data_center_timelines.csv`, 2026-09-10) | Third-party original; only the processed extract is published | Download `data_centers.csv` and `data_center_timelines.csv` from [epoch.ai/data/ai-data-centers](https://epoch.ai/data/ai-data-centers) into `02_data/raw/epoch_ai/ai_data_centers/2026-09-10/` to rebuild the extract and rerun the interconnection node distribution step. Without them `reproduce_paper_results.py` skips that step and keeps the shipped outputs. The live dataset has changed since the snapshot |
| WRI Aqueduct 4.0 country rankings (`aqueduct-4-0-country-rankings.zip`) | Third-party original; only the province extract is published | Download from [doi:10.46830/writn.23.00061](https://doi.org/10.46830/writn.23.00061) to `02_data/raw/resource_footprint/water_stress_sources/aqueduct40/aqueduct-4-0-country-rankings.zip` (checked against the SHA-256 in `config/scenarios/aqueduct40_province_water_stress_v1.yaml`) to rebuild the extract and rerun the spatial water audit. Without it the script skips that step and keeps the shipped outputs |
| U.S. federal statistics extracts (`02_data/raw/curated/us_*.csv`) | Used only for U.S. results, which are not in the paper | The U.S. demand step is skipped by `reproduce_paper_results.py` and its shipped outputs are kept. To rerun it, obtain `us_manufacturing_activity_naics3_2022.csv`, `us_manufacturing_mecs_2022.csv` and `us_manufacturing_berd_2023.csv` (extracts of the 2022 Economic Census, EIA MECS 2022 and NSF BERD 2023) and place them in `02_data/raw/curated/` |
| Chinese province boundary files | Provider terms do not allow redistribution | Used only for a map that is not part of the paper. The water table is computed without them (`build_figure5_rq1_spatial_water.py --data-only`). |

## Author-compiled data

Everything else under `02_data/` was compiled by the authors from public sources cited in each file. This includes
task-class parameters, adoption and service-intensity assumptions, the provincial and industry energy baseline
(`02_data/external/d_energy.csv`: REFERENCE scenario of the authors' China energy-system model, 2020–2060 by province and industry), server and cloud price observations with
source URLs and access dates, facility water, floor-space and land parameters, and the CAICT 2025 provincial
computing-capacity shares digitized from the published report. The 24-hour industry templates `02_data/processed/core/manufacturing_31sector_base_load_profiles.csv` (+ `.lineage.json`) are author-compiled: their magnitudes equal the 2030 industry electricity in `d_energy.csv`, and their shapes come from an earlier equal-electricity national screen that is no longer available. They are a source input, used only to choose each industry's EWELD week. The regulated tariff components follow the Guangdong
Power Grid agency power-purchase price notice for April 2026.
