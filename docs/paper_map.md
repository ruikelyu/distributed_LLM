# Where each result in the paper comes from

Paths are relative to the repository root. `R` = `05_results/v1.0.0/result`, `S` = `05_results/sensitivity/v1.0.0`.
All files below are rebuilt by `python 08_code/reproduce_paper_results.py`, except the optimization outputs marked
*(solver)*, which are rebuilt by `snakemake paper --forceall`.

## Paper

Five pages, grid-interconnection focus. The paper names the four deployment
architectures PFD, HFD, MSD and LDC. The data files use the earlier labels, mapped once here and not repeated below.

| Paper | Data files | Meaning |
|---|---|---|
| PFD, per-factory deployment | `PF` (`factory_distributed`) | each factory hosts its own servers |
| HFD, host-factory deployment | `SHG` (`group_single_host`) | one host factory per corporate group |
| MSD, multi-site deployment | `MSG` (`group_multisite`) | up to five host factories with routing |
| LDC, large-data-center deployment | `LDC_AGGREGATE` (and `LDC_EMPIRICAL_REFERENCE` for Epoch records) | new large data centers serving the same demand |

Capacity values are national sums of `industry_equivalent_sum_incremental_grid_peak_mw` unless another column is named.
Where the paper rounds a value, the file value is shown to the precision needed to check it.

### Figures

| Paper item | Value in paper | Source file (column) | Script |
|---|---|---|---|
| Fig. 1, Deployment architectures | schematic, no data | `R/manuscript_figures/gm_architectures.pdf` (schematic, built from the architecture settings in `config/scenarios/group_multisite_core_v1.yaml`) | `08_code/build_gm_figures.py` |
| Fig. 2, Manufacturing AI service demand in China, 2030 | (a) low, base and high demand by task class; (b) eight largest industries in the base case | `R/manuscript_figures/figure1_manufacturing_ai_demand_data.csv` (`value` by `panel`, `category`, `series`), `R/manuscript_figures/figure1_manufacturing_ai_demand.pdf` | `08_code/build_figure1_manufacturing_ai_demand.py` |
| Fig. 3, Distribution of factory sites by additional capacity | PFD, HFD and MSD site shares by capacity bin; 69 Epoch AI records in gray | PFD, HFD and MSD shares in `R/manuscript_figures/figure3_grid_capacity_data.csv` (`value` where `panel = node_scale_distribution`) and `R/node_interconnection_distribution/node_interconnection_histogram.csv` (`node_proportion`); Epoch records in `R/node_interconnection_distribution/node_interconnection_distribution.csv` (`architecture = LDC_EMPIRICAL_REFERENCE`, `capacity_case = peak_facility_multiplier_1p20`, `incremental_interconnection_capacity_mw`); plotted as `R/manuscript_figures/gm_site_distribution.pdf` | plot `08_code/build_gm_figures.py`; data `08_code/build_node_interconnection_distribution.py` and `08_code/build_figure3_rq1_grid_capacity.py` (config `config/scenarios/figure3_rq1_grid_capacity_v2.yaml`) |
| Fig. 4, Non-coincident peaks in the vehicle-manufacturing group (C36) | (a, b) host factory R4 under HFD, one representative week; (c) additional capacity at the five MSD nodes before and after routing; (d) normalized node loads | `R/group_architecture_core/C36/hourly.csv` (`base_load_mw`, AI load by `factory_id`, `architecture`), `msg_no_routing_hourly.csv` *(solver)*; figure file `R/manuscript_figures/figure3_load_coordination.pdf` | `08_code/build_figure3_load_coordination_redesign.py` |

### Tables

| Paper item | Value in paper | Source file (column) | Script |
|---|---|---|---|
| Table I, Deployment architectures as model instances | nodes, production load, routing; facility multiplier 1.30 (PFD, HFD, MSD) and 1.22 (LDC) | `config/scenarios/group_multisite_core_v1.yaml` (`max_modeled_routing_nodes: 5`), `config/defaults.yaml` (`marginal_facility_multiplier: 1.30`), `config/sensitivity/national_cloud_center_v1.yaml` (1.22) | `08_code/run_group_architecture_core.py`, `08_code/run_national_cloud_center.py` |
| Table II, Capacity, reduction vs. LDC | LDC 1,488; PFD 556; HFD 576; MSD 30 MW; reductions 63%, 61%, 98% | `S/national_grid_capacity_comparison.csv` (`architecture_national_incremental_grid_expansion_mw`, `ldc_aggregate_incremental_grid_expansion_mw`, `capacity_difference_vs_ldc_aggregate_fraction`); same values in `R/manuscript_figures/figure3_grid_capacity_data.csv` (`panel = aggregate_capacity`). Files give 1,487.65 / 555.65 / 575.78 / 30.16 MW and 0.9797, 0.6265, 0.6130 | `08_code/summarize_national_grid_capacity_comparison.py` |
| Table II, Battery (MWh) | 1,080 / 1,583 / 46 (PFD, HFD, MSD) | `R/bess_peak_shaving/bess_peak_shaving_national.csv` (`energy_mwh`); files give 1,079.9 / 1,583.0 / 46.5. Battery power (`power_mw`) equals the capacity above | `08_code/analyze_bess_peak_shaving.py` |
| Table II, Battery cost (CNY bn) | 0.71--1.09 / 0.93--1.49 / 0.03--0.05 | same file (`cost_system_bn_cny` to `cost_epc_bn_cny`); files give 0.713--1.094, 0.927--1.486, 0.034--0.050 | same |

### Headline numbers

Introduction and abstract

| Paper item | Value in paper | Source file (column) | Script |
|---|---|---|---|
| Additional capacity, LDC vs. factory sites vs. MSD | 1,488 MW; 556--576 MW; 30 MW | as Table II | as Table II |
| Reduction in the abstract | about 60%, and 98% with routing | as Table II (0.613 to 0.626; 0.980) | as Table II |
| Sites below 1 MW | most individual sites | `R/node_interconnection_distribution/node_interconnection_histogram.csv` (`node_proportion` for bins up to 1 MW) | `08_code/build_node_interconnection_distribution.py` |

Case study

| Paper item | Value in paper | Source file (column) | Script |
|---|---|---|---|
| 2030 demand, three scenarios | 55.5 / 95.5 / 191.1 million units/day (text rounds the base case to 96) | `R/manuscript_figures/figure1_manufacturing_ai_demand_data.csv` (`value`, `panel = a`, summed over `series`); also `R/national_local_cloud_cost_v1/ledger/service_reconciliation.csv` (`effective_service_units_day` by `parameter_case`) | `08_code/build_figure1_manufacturing_ai_demand.py`, `08_code/build_national_unified_ai_task_ledger.py` |
| Eight largest industries (Fig. 2b) | C39, C34, C38, C26, C35, C30, C36, C33 | same Fig. 2 data (`value`, `panel = b`); base case 10.40, 10.29, 10.11, 7.13, 6.24, 6.15, 5.59, 4.48 million units/day | same |
| AI facility electricity | about 12 TWh/yr | `R/group_architecture_core/national/core_scenarios.csv` (sum of `industry_equivalent_annual_ai_facility_energy_twh` over rows with `architecture = PF`, `base_load_case = actual_load`; 12.11 TWh; SHG and MSG give 12.11 as well) | `08_code/run_group_architecture_core.py` *(solver)* |
| Share of 2030 manufacturing electricity | about 0.25% of 4,799 TWh | `02_data/processed/core/manufacturing_31sector_base_load_profiles.csv` (sum of `baseline_load_mw` over the 24 hours of the 31 industries for one `temporal_scenario`, times 365 days, divided by 10^6 = 4,799.4 TWh; the three scenarios give the same total); 12.11 / 4,799.4 = 0.252% | derived in the text |
| Task shares, base demand | R&D simulation and production scheduling together 61% (36.1% and 25.1%) | `R/manuscript_figures/figure1_manufacturing_ai_demand_data.csv` (`panel = a`, `series = simulation`, `scheduling`) | `08_code/build_figure1_manufacturing_ai_demand.py` |
| Flexibility shares and deadlines | firm shares 10% (simulation), 25% (scheduling), 70--75% (office, visual review); delays 4--12 h and 72 h | `02_data/manufacturing_ai_task_flexibility_mapping.csv` (`rho_rigid`, `intraday_deadline_h`, `batch_deadline_h`, rows with `scenario = central`) | none, input file |
| Firm share overall | about one third | demand-weighted mean of `rho_rigid` (central) using the base-case task shares above; gives 0.32 | derived in the text |
| Server and tariff inputs | L20 server 1.50 kW full load, 0.36 kW idle; 15% margin; threefold compute reduction; 36.1 CNY/(kW month) | `config/defaults.yaml` (`maximum_wall_power_kw`, `online_idle_wall_power_kw`, `installed_reserve_fraction`, `maximum_demand_rmb_per_kw_month`); efficiency `it_efficiency_3p0` in `02_data/processed/compute_efficiency/common_it_effective_efficiency_scenarios.csv` | none, input files |

Grid-interconnection requirements

| Paper item | Value in paper | Source file (column) | Script |
|---|---|---|---|
| PFD sites below 0.1 MW | 68% | `R/manuscript_figures/figure3_grid_capacity_data.csv` (`value`, `series = PF`, `category_id = positive_below_0p1_mw`; 0.684) | `08_code/build_figure3_rq1_grid_capacity.py` |
| HFD sites between 0.1 and 1 MW | 58% | same (`series = SHG`, `category_id = 0p1_to_1_mw`; 0.580) | same |
| MSD sites below 0.1 MW | more than 99% | same (`series = MSG`, `exact_zero` 0.222 plus `positive_below_0p1_mw` 0.769 = 0.991) | same |
| MSD sites with no additional capacity | 22% | same (`series = MSG`, `category_id = exact_zero`; 0.222) | same |
| Epoch AI records | 69 sites; 21 to 1,135 MW; median 182 MW | `R/node_interconnection_distribution/node_interconnection_distribution.csv` (`incremental_interconnection_capacity_mw`, `architecture = LDC_EMPIRICAL_REFERENCE`, `capacity_case = peak_facility_multiplier_1p20`; 69 rows, min 20.8, median 182.4, max 1,135.2); snapshot `02_data/processed/node_interconnection/epoch_ai_current_it_power_2026-09-10.csv` | `08_code/build_node_interconnection_distribution.py` |

Mechanisms of capacity reduction

| Paper item | Value in paper | Source file (column) | Script |
|---|---|---|---|
| HFD without production load at the host | 1,585 MW | `R/rq2_mechanisms/rq2_mechanism_effects.csv` (`control_incremental_grid_capacity_mw`, row `observation_level = national_sum`, `control_case = SHG_ZERO_PRODUCTION_LOAD`; 1,585.2) | `08_code/summarize_rq2_mechanisms.py` |
| HFD with production load, and reduction | 576 MW, 64% | same row (`mechanism_enabled_incremental_grid_capacity_mw` 575.8; `effect_fraction_of_control` 0.637) | same |
| HFD without task shifting, standalone | 2,372 MW | derived from `S/national_oat_group_architecture/result/PHY03__no_shift/core_scenarios.csv` (1,343.29, `industry_equivalent_sum_incremental_grid_peak_mw`) plus `.../PHY03__no_shift/shg_load_alignment.csv` (1,028.22, sum of `industry_equivalent_avoided_incremental_grid_peak_mw`); 1,343.29 + 1,028.22 = 2,371.5 | `08_code/summarize_rq2_mechanisms.py` *(solver)* |
| HFD without task shifting, co-located, and reduction | 1,343 MW, 43% | same no-shift `core_scenarios.csv` (1,343.29); 1,028.22 / 2,371.5 = 0.434 | same |
| MSD without routing | 562 MW | `R/group_architecture_core/national/msg_coordination_value.csv` (`industry_equivalent_msg_no_routing_sum_incremental_grid_peak_mw`, 561.94); also `R/rq2_mechanisms/rq2_mechanism_effects.csv` (`control_incremental_grid_capacity_mw`, row `MSG_NO_ROUTING`) | `08_code/run_group_architecture_core.py` *(solver)* |
| MSD with routing, and reduction | 30 MW, 95% | same file (`industry_equivalent_msg_coordinated_sum_incremental_grid_peak_mw` 30.16; `effect_fraction_of_control` 0.946 in `rq2_mechanism_effects.csv`) | same |

Possible infrastructure reductions

| Paper item | Value in paper | Source file (column) | Script |
|---|---|---|---|
| Per-factory sites that cannot fully shave the peak | 1.6% | `R/bess_peak_shaving/bess_peak_shaving_national.csv` (`sites_daily_recharge_infeasible` / `sites_weighted` for `PF`; 124.96 / 7,586.10 = 1.65%) | `08_code/analyze_bess_peak_shaving.py` |
| Battery cost for MSD | CNY 0.05 bn or less | same file (`cost_epc_bn_cny`, `MSG`; 0.050); battery prices from `02_data/raw/curated/cnesa_bess_bid_prices_2026_09.csv` | same |
| Datong 220-kV substation and lines | CNY 0.23 bn for 300 MVA | `docs/assumptions.md` (grid-connection benchmark; planned investment CNY 231.96 million) | none, external source |
| Datong cost scaled to 1,488 MW | CNY 1.2 bn | derived in the text: 231.96 million x 1,488 / 300 = CNY 1,150.5 million, assuming 1 MVA = 1 MW | derived in the text |
| Battery cost vs. connection cost | reduction over 95% | derived in the text: 1 - 0.05 / 1.15 = 0.96 | derived in the text |
| On-site water, PFD | 0.47 million m3/yr | `R/rq1_resource_footprint/rq1_resource_footprint_summary.csv` (`value`, `metric_id = onsite_cooling_humidification_water`, `architecture = PF`; 465,812 m3) | `08_code/build_rq1_resource_footprint_summary.py` |
| Water reduction vs. LDC | about 85% | same file (`architecture = LDC_AGGREGATE`; 3,120,547 m3; 1 - 465,812 / 3,120,547 = 0.851) | same |
| Water-use intensities | 0.05 and about 0.33 L/kWh of IT energy | `docs/assumptions.md` (water-use intensity rows; 0.05 and 0.335 central, Alibaba 0.329) | `config/scenarios/rq1_resource_footprint_summary_v1.yaml` |
| Floor area, PFD | 0.92 million m2, about 120 m2 per site | same summary file (`metric_id = total_facility_floor_requirement`, `architecture = PF`; 916,849 m2); per site 916,849 / 7,586.1 sites (`sites_weighted` in `bess_peak_shaving_national.csv`) = 121 m2 | same |
| Floor area and land conversion, LDC | 1.34 and 0.38 million m2 | same summary file (`total_facility_floor_requirement` 1,341,327 m2; `offsite_land_conversion` 381,668 m2; `architecture = LDC_AGGREGATE`) | same |
| Enterprise payments, factory sites | about CNY 55 bn/yr | `R/national_local_cloud_cost_v1/cost/comparison.csv` (`annual_100pct_local_cost_rmb`, `parameter_case = base`; PF 55.43, SHG 55.16, MSG 54.92 bn) | `08_code/run_national_local_vs_cloud_cost_v1.py` |
| Enterprise payments, cloud procurement | CNY 95--101 bn/yr | same file (`annual_100pct_cloud_cost_rmb`, `parameter_case = base`, `cloud_price_case = base`; 95.13 to 100.72 bn across the four provider bundles) | same |

### Optimization outputs *(solver)*

| Run | Output |
|---|---|
| PFD, HFD, MSD and MSD-no-routing for 31 industries (HFD also with zero production load) | `R/group_architecture_core/<industry>/` and national totals in `R/group_architecture_core/national/` |
| New large data centers (LDC counterfactual) | `S/national_cloud_center_v1/summary.csv` (`incremental_grid_expansion_mw` 1,487.65) |
| HFD without task shifting, actual and zero production load (paired run for the 2,372 and 1,343 MW values) | `S/national_oat_group_architecture/result/PHY03__no_shift/` |
