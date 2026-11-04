# Modelling assumptions and data

This document lists the assumptions behind the results in the paper: the value or range used, the basis or source,
and the file where it is set. It complements [paper_map.md](paper_map.md), which traces each figure, table and number to its
output file, and [DATA_SOURCES.md](../DATA_SOURCES.md), which lists third-party data and licences.

Paths are relative to the repository root. Bold values are those used in the core scenario. Parameter IDs (for
example `E05`, `SRV01`, `L02`) refer to rows of the evidence tables `02_data/china_enterprise_ai_cost_parameters.csv`
and `02_data/distributed_ai_facility_parameters.csv`, which give the source title, URL and evidence quality for each value.

Contents: [AI service demand](#ai-service-demand) · [Physical model](#physical-model) ·
[Water, floor space and land](#water-floor-space-and-land) · [Enterprise payments](#enterprise-payments) ·
[Sensitivity ranges](#sensitivity-ranges) · [Evidence files](#evidence-files)

## AI service demand

A "service unit" (`2024_baseline_reference_workload_unit`) is one 2024 reference compute-hour. In the legacy templates this is one L20-equivalent GPU-hour. It is divided by eta_IT = 3.0, so 0.3333 reference h per unit (`02_data/processed/compute_efficiency/common_it_effective_efficiency_scenarios.csv`).

### Task classes and scope

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Six task classes, all scoped `K_choice` (can run at the factory or in a pool) | office, agent, vision, maintenance, scheduling, simulation | Author-approved scope (`author_approved_scope_not_empirically_validated`); evidence grades range from B-/C (vision) to C-/D (scheduling, simulation) | `02_data/manufacturing_ai_task_core_scope_v0.1.csv` |
| Excluded `K_edge` parts (must stay on site) | Raw camera frames and closed-loop vision; PLC/MPC and second-level control; safety interlocks; logic that must keep running during network outages; operational twins coupled to equipment | Same file, `excluded_k_edge_component` | same |
| Excluded `K_pool` parts (beyond what a factory node can handle) | Large shared models; high-concurrency multi-agent search; tightly coupled multiphysics; foundation-model or time-series pretraining | Same file, `excluded_k_pool_component`. The ledger script enforces K_choice only | same; `08_code/prepare_effective_service_data.py` |

### Annual demand (China, 31 industries C13–C43, year 2030)

| Assumption | Value (low / base / high) | Basis and source | File |
|---|---|---|---|
| Formula actually implemented | Q_2030 = (2023 AI-using firms) × (2023 per-adopter reference h/day by task) × G_k | The script rebuilds a 2023 baseline from a legacy 2030 table (`legacy_task_2030 / [(adopting_firms_2030/ai_using_firms_2023) × legacy_per_adopter_growth]`) and multiplies it by the task growth G_k. No national TWh calibration is applied | `08_code/prepare_effective_service_data.py`; lineage in `02_data/processed/effective_service/lineage.json` |
| Activity driver B (firm counts) | 460,054 above-size manufacturing firms in 2023, of which 96,311 used AI | Fifth Economic Census, Table 4-9; China Statistical Yearbook 2024, Table 13-2 | `02_data/china_manufacturing_ai_31sector_proxy_parameters.csv`; employees, assets and revenue in `02_data/china_manufacturing_sector_baseline.csv` (Census Tables 3-2 and 3-3) |
| A_any in 2023 (observed) | 20.93% national, weighted by firm count; industries range from 11.4% (C20) to 36.6% (C16) | Economic Census, as above | `02_data/china_manufacturing_ai_31sector_proxy_parameters.csv` |
| Adoption anchor | "over 30%" (0.30) for above-size manufacturers | MIIT, 22 Jul 2026 (no base year stated); a 21 Apr 2026 digitalchina.gov.cn commentary dates it to 2025. Context only; not a model input | `02_data/future_manufacturing_ai_workload_model.csv`, row F003 |
| A_any in 2030 | Target 0.480046. Industry odds = odds_2023 × (odds(target)/odds(0.2093))^speed, with speed 0.80–1.15 by template. This gives 46.76% weighted by firm count (range 25.9%–67.2%) | Scenario target (`national_adoption_target_2030`); industry paths use odds-ratio diffusion | `08_code/core/adoption.py`; `config/defaults.yaml` (`national_adoption_target_2030`); `template_diffusion_speed` in the proxy CSV |
| Per-adopter task intensity in 2023 (bundles θ·W·f·λ·S) | C36 template: office 2.5, agent 1.5, vision 0.667, maintenance 1.0, scheduling 1.0, simulation 1.6 h/day per adopter. Other industries apply multipliers of 0.4–1.2 per task (e.g. C13 office ×0.75) | `conditional_screening_scenario`. Back-cast from assumed 2030 per-adopter templates. 13 industries have direct templates; 18 use proxy or auto-calibrated templates, with 4 documented fallbacks; four industries (C29, C30, C33, C35; 21% of demand) use internally calibrated intensities | `02_data/interim/effective_service/legacy_manufacturing_ai_task_hardware_demo_task_results.csv`; `.../legacy_manufacturing_ai_31sector_bottomup_weights.csv`; `02_data/raw/curated/effective_service_template_fallbacks.csv` |
| Task growth G_k, 2023→2030 (total service) | office 12/20/40; agent 75/130/260; vision 70/120/240; maintenance 52/90/180; scheduling 145/250/500; simulation 128/220/440 | `externally_bounded_correlation_adjusted_joint_scenario`. These are joint scenario values that shrink the full A·W·f·λ·C·S product to account for correlated factors. Examples: the base product for agents is 5×2×1.1×1.5×4×2.5 = 165, shrunk to 130. Supporting evidence: Gartner 2026, Applied Compute agent benchmark, Deloitte 2025 survey, IEA *Energy and AI*. These are assumed scenario values: the products (24/165/151/110/319/290) are scaled down by 0.76–0.83 so that the reference-system energy is consistent with the external 14 TWh anchor. The task-level adoption assumptions are not constrained by the any-AI adoption path. The growth factors are derived from 2024–26 task-level adoption but applied to the 2023 baseline | `02_data/raw/curated/effective_service_task_growth_scenarios.csv` |
| Low/high scaling | High = 2.00× base for every task. Low = 0.577–0.600× by task (0.581× in total) | Ratios of the G_k values above | same |
| Resulting demand | 55.51 / 95.54 / 191.09 million units/day. Shares in the base case: simulation 36.1%, scheduling 25.1%. Largest industries: C39 10.40, C34 10.29, C38 10.11 (32.2% together) | Matches the demand scenarios and task shares in Fig. 2 of the paper | `02_data/processed/effective_service/manufacturing_ai_effective_service_2030.csv` |
| Prototype factory parameters (illustrate W, f, λ, S) | 800 employees, 200 connected machines, W = 0.25 (0.10–0.50), 1,000 events/day, 6 tasks per user per day, 8 calls per agent task, 33.24 L20-h/day in 2030 | Scenario assumptions with case anchors (MIIT Suzhou case and others). Used only for hourly shapes, not for the ledger totals | `02_data/future_manufacturing_ai_workload_model.csv` |
| External scale check (not an input) | Reference energy 8.12 / 13.98 / 27.97 TWh/yr, against external 8 / 14 / 28 TWh; 30 of 31 industries fall inside the 0.75–1.25 band | `role: optional_external_scale_comparison_not_model_input`. The central 14 TWh is 400 × 50% × 7%. The 400 TWh is from CAICT 2025 (all computing centres, central 2030 case). The 50% AI share and 7% manufacturing share are assumptions derived in this study; 7% = 4% (CAICT Nov. 2025, share of compute use) grown at IDC rates. Because the growth factors were scaled with this anchor in view, it is context, not an independent check. The reference system (1.25 kW, PUE 1.20, 65% utilization) differs from the model, whose AI facility energy is 12.11 TWh | `05_results/effective_service_bottom_up_recalculation.md`; `02_data/processed/effective_service/external_energy_allocation_31sectors.csv` |

### Hourly arrivals and flexibility

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Daily arrival shapes (24 h, repeated identically on all 7 days) | Office and agent follow the prototype hourly curve. Office: 76% of arrivals in 08–18 h, peak/mean 2.18. Agent: 62%. Vision follows the industry's mean clock-hour production load. Maintenance = 0.75 × production shape + 0.25. Scheduling: base level 0.2, with peaks at 05–07, 13–15 and 21–23 h. Simulation: 1.0 at 22–05 h, 0.1 otherwise | Assumed shapes, with no observational data; no weekday/weekend difference | `08_code/core/data.py` (`task_shapes`, `parse_office_agent_shapes`); `02_data/future_manufacturing_ai_workload_model.csv` |
| Rigid / intraday / batch shares, central case | office 0.70/0.25/0.05; agent 0.55/0.35/0.10; vision 0.75/0.20/0.05; maintenance 0.35/0.50/0.15; scheduling 0.25/0.55/0.20; simulation 0.10/0.20/0.70 | `recommended_structured_prior`: assumed from the nature of each task, with a written rationale; no observational data | `02_data/manufacturing_ai_task_flexibility_mapping.csv` |
| Deadlines | Intraday: 4 h (office, agent, vision) or 12 h (others). Batch: 72 h (central) | Assumed | same |
| Sensitivity cases | `no_shift` (rigid = 1); `conservative` (e.g. office 0.85/0.14/0.01, batch deadline 24 h); `flexible` (e.g. simulation 0.05/0.15/0.80) | same | same; `config/defaults.yaml` (`flexibility_scenario: central`) |

### Foundation-model and strict-LLM attribution (scenario attributions, not observations)

| Task | FM share (low / base / high) | Strict LLM (low / base / high) | Basis |
|---|---|---|---|
| office | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | Defined as LLM + RAG (arXiv 2005.11401) |
| agent | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | Multi-turn LLM with tools (Applied Compute benchmark) |
| vision | 0.50 / 0.75 / 1.00 | 0.10 / 0.20 / 0.30 | Few-shot VLM anomaly detection (PromptAD, CVPR 2024) |
| maintenance | 0.25 / 0.50 / 0.75 | 0.20 / 0.40 / 0.60 | Time-series foundation models (arXiv 2402.03885; 2411.02718) |
| scheduling | 0.15 / 0.35 / 0.60 | 0.10 / 0.25 / 0.45 | MIIT 2025 policy document; no production telemetry |
| simulation | 0.10 / 0.25 / 0.40 | 0.05 / 0.15 / 0.30 | LLM agent calling simulators via MCP (arXiv 2601.11650) |
| **Weighted by service** | **34.7% / 49.7% / 66.0%** | **27.6% / 37.7% / 50.9%** | All rows have status `exploratory_parameter`; evidence grades range from B+ to C-/D+ |

Files: `02_data/manufacturing_foundation_model_task_attribution_parameters_v0.1.csv`, `08_code/build_c36_unified_ai_task_ledger.py`, `08_code/build_national_unified_ai_task_ledger.py`. Results: `05_results/v1.0.0/result/national_local_cloud_cost_v1/ledger/task_attribution_summary.csv` (evidence status `scenario_attribution_not_observed_national_mean`).

### United States (21 NAICS-3 industries, 311–339)

| Assumption | Value (low / base / high) | Basis and source | File |
|---|---|---|---|
| Formula | service = driver × adoption × workload units per active driver per day × service per workload unit × applicability | Built bottom-up; China is not scaled to the US | `08_code/build_us_manufacturing_ai_demand.py`; `config/demand_cases/us_manufacturing_ai_demand_v0.1.yaml` (internal version v0.3.0) |
| Drivers | Office and agent: employment. Vision and scheduling: establishments. Maintenance: establishments × MECS electricity per establishment index (NAICS 337 suppressed, so index = 1). Simulation: BERD domestic R&D employment (313–316 split by employment) | 2022 Economic Census EC2200SIZEEMPEST; EIA MECS 2022; NSF BERD 2023 | `02_data/raw/curated/us_manufacturing_activity_naics3_2022.csv`, `us_manufacturing_mecs_2022.csv`, `us_manufacturing_berd_2023.csv` |
| 2030 adoption by task (current anchor → low / base / high) | office 0.198 → 0.198 / 0.254 / 0.337; agent 0.128 → 0.128 / 0.168 / 0.232; vision 0.023 → 0.023 / 0.028 / 0.040; maintenance and scheduling 0.080 → 0.080 / 0.096 / 0.132; simulation 0.083 → 0.083 / 0.107 / 0.147 | Anchors from BTOS 2025–26 and MOPS 2021. Illustrative 4-year log-odds diffusion at 0 / 0.05–0.08 / 0.14–0.18 per year, with caps of 0.40–0.70 | `02_data/processed/us_demand/us_task_driver_parameters_v0.1.csv`; `02_data/raw/curated/us_business_ai_functions_btos_2026.csv`, `us_manufacturing_ai_adoption_mops_2021.csv` |
| Workload units per active driver per day | Base: office 10, agent 28 (4 × 7), vision 35 (5 × 7), maintenance 20, scheduling 70 (10 × 7), simulation 40 (4 × 10). Low ≈ 0.7×, high ≈ 1.45× | Scenario | YAML config |
| Service units per workload unit | office 0.0474, agent 0.3148, vision 6.620, maintenance 4.755, scheduling 12.31, simulation 0.847 | Transferred from the China per-unit intensity | YAML config |
| Result | 29.47 / 51.30 / 103.08 million units/day (0.574× / 1× / 2.009×). Reference energy 6.909 TWh in the base case | Check against China (ratio 0.45–0.55) only; not used for calibration | `02_data/processed/us_demand/us_manufacturing_ai_effective_service_2030.csv`; `05_results/v1.0.0/result/us_demand/findings.md` |

## Physical model


### Architectures and representative groups

| Assumption | Value (low / base / high) | Basis and source | File |
|---|---|---|---|
| Architectures | PF (fixed origin shares at each node), SHG (all group service at one host), MSG (joint time–site routing of all 6 task classes), LDC (single logical pool, no production load) | Authors' design. Ownership, network and governance costs are excluded (`include_incremental_private_network_cost: false`) | `config/deployment_core.yaml`, `config/scenarios/group_multisite_core_v1.yaml` |
| MSG-no-routing control | Same nodes, loads, deadlines and prices as MSG. Each rigid task-hour and each flexible-job total is fixed to node share ω_n = represented site count / F_group | Paired control; effect = MSG-no-routing minus MSG | `config/scenarios/group_multisite_core_v1.yaml` (`mechanism_controls`) |
| Representative groups | 1 equivalent group per industry (31 industries, C13–C43), assumed to be a known AI adopter | Concentration ratios (CR_N/N), annual reports. Evidence grades A–D | `02_data/china_manufacturing_representative_group_parameters.md` §3 |
| Group output share s_group | Industry-specific base values, 0.005 (C41, C43) to 0.100 (C25); C36 = 0.055 / 0.085 / 0.130 | C36: CAAM 2024, top 10 groups = 84.9% of sales, so CR10/10 | same |
| Sites per group F_group | Base 4 (C18, C40, C41) to 40 (C13); C36 = 9 | Counts of plants or bases from annual reports, or analogues | same; C36 from `02_data/manufacturing_production_load_calibration.csv` (`load_site_count` 9) |
| Routing/AI-node cap | `max_modeled_routing_nodes: 5`. Nodes = min(F_group, 5), and sites are assigned to nodes with near-equal integer weights (C36: 2,2,2,2,1) | Keeps the model tractable | `config/scenarios/group_multisite_core_v1.yaml`; `08_code/run_group_architecture_core.py` (`balanced_factory_weights`) |
| SHG host choice | The modeled node with the median weekly peak load (C36: R4) | Code rule | `08_code/run_group_architecture_core.py` (`host_index`) |
| National scaling | Industry total = group result × adopter share / s_group. Task origin is split equally across the group's sites | Equal-share proxy | `08_code/core/representative_group.py`; `config/defaults.yaml` (`adopter_conditioning`) |
| Electrical boundary | Each AI node uses only its own host-site load, with no aggregation across meters. The same provincial hourly price applies at every site | — | `config/scenarios/group_multisite_core_v1.yaml` |

### Compute

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Reference GPU server group | 2× NVIDIA L20 48 GB (Lenovo WR5220 G3), 2U. Capacity G_GPU = 2 reference accelerator-h/h | Lenovo public configuration (L01–L03); L20 275 W (HPE QuickSpecs, L07) | `config/defaults.yaml` (`server`); `02_data/china_enterprise_ai_cost_parameters.csv` |
| GPU power | 1.50 kW max, 0.36 kW online idle, 0.02 kW cold standby. The 1.50 kW maximum is the upper end of the registered range (1.05 / 1.25 / 1.50 kW, SRV01). It was chosen because distributed server rooms typically run less efficiently. A typical 2×L20 server (2×275 W GPU TDP, 2×270 W CPUs, plus fans and memory) draws about 1.3–1.4 kW. For a like-for-like comparison, the same value is used for all architectures, including LDC | IDs SRV01/SRV03/SRV06 in `02_data/distributed_ai_facility_parameters.csv` | `config/defaults.yaml` |
| GPU cost | CNY 150,000; Y = 5 yr; ρ = 8%; O&M 5%/yr; facility capex 20%. Annual cost = CNY 52,582 | Assumed value within observed price ranges (L02); the cited product page gives the configuration only. Life 4/5/6/7 yr evidence (Alibaba, QingCloud, Tencent) | `config/defaults.yaml` |
| CPU server | 2×32-core, 256 GB. 1.0 CPU-server-h/h; 0.78 / 0.28 / 0.02 kW; CNY 60,000 / 90,000 / 118,000 | Power: assumed engineering values. Cost: base is an engineering midpoint; the low end (CNY 60,000) is a 2025 public procurement price for a matched 2×32-core, 256 GB server including installation and five-year support, and the high end (CNY 118,000) is a 2025 China CDC procurement award for a 768 GB server (`02_data/raw/curated/china_cpu_server_cloud_capacity_evidence_v1.csv`, row CNCPU001). The evidence file holds no record for the low end; its nearest low-price observation is CNY 58,700 for a 64 GB server (row CNCPU002) | `config/compute_hardware/cpu_gpu_routing_v1.yaml` (`cpu_server`) |
| CPU share q_k (`practice_routed`) | Maintenance 0.5, scheduling 0.8, simulation 0.5, others 0. Alternatives: `gpu_only` (all 0); `cpu_heavy` 0.75/1.0/0.75 | Structural scenario, not observed shares | same |
| CPU time multiplier m_k | Maintenance 2.0, scheduling 1.0, simulation 1.0 (sensitivity 0.5/1/2/4) | Proxy pending benchmarks | same |
| Routing file used | v1 for the physical model; v2 differs only in cloud-product billing | Code docstring | `config/defaults.yaml` (`routing_config`); `08_code/run_group_architecture_core.py` |
| Service unit / throughput | 1 service unit = 1.0 reference (2024 L20) accelerator-h. Reference compute per unit = 1/η = 0.667 / **0.333** / 0.2 | Author-confirmed scenarios | `02_data/raw/curated/common_it_effective_efficiency_scenarios.csv`, `02_data/processed/compute_efficiency/...` |
| Common IT efficiency η (2030 vs 2024) | 1.5 / **3.0** / 5.0, applied to all architectures and to both CPU and GPU | Assumed scenario, a combined judgment on hardware, model and software gains; 1.5× and 5× bound the range. Excludes PUE, utilization and margin | same |
| Planning margin r_plan | **0.15** on mean demand. Sensitivity 0 / 0.15 / 0.30 / 0.50. N+k spare = 0 | Engineering assumption covering demand uncertainty, operating buffer and reliability; not calibrated to availability. Binding in all HFD, MSD and LDC runs (paper eq. 1i) | `config/defaults.yaml`; `config/sensitivity/national_oat_extended_screen_v1.yaml`; `config/sensitivity/parameter_bounds_design_v1.csv` (PHY07) |
| Integrality | PF: integer N_inst. SHG, MSG, LDC: continuous. Online groups are always continuous | — | `config/scenarios/group_multisite_core_v1.yaml` (`integer_boundary`); `config/defaults.yaml` (`server_groups_integer: false`) |
| Minimum online servers | `minimum_online_servers: 1` (GPU only), enforced in `core/model.py` (used by LDC). There is no such constraint in the PF/SHG/MSG group solver | — | `config/defaults.yaml`; `08_code/core/model.py`; `08_code/run_group_architecture_core.py` |

### Facility power

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Factory multiplier m_fac (PF/SHG/MSG) | **1.30**, constant over time. Sensitivity 1.20 / 1.60 | Engineering estimate (ID PUE04 in `02_data/distributed_ai_facility_parameters.csv`): 1 + 0.25 cooling + 0.04 power delivery + 0.01 other. Measured small-room annual PUEs are 1.5–2.1 (LBNL) | `config/defaults.yaml`; `config/compute_hardware/cpu_gpu_routing_v1.yaml`; `config/sensitivity/national_oat_extended_screen_v1.yaml` |
| LDC PUE proxy | **1.22** (GPU and CPU) | Annual PUE of an advanced large facility. Rounded from Tencent's 2023 owned-data-center PUE (1.246) and leading-cloud values (about 1.20) (ID PUE05); China's 2023 average is 1.48 (CAC) | `config/sensitivity/national_cloud_center_v1.yaml` |

### Production loads

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Industry week (EWELD) | One complete Monday–Sunday week (168 h, days with ≥80 valid readings, values ≥0) per industry. Chosen by minimum RMSE of the median daily shape against a 24-h template (author-compiled source input `02_data/processed/core/manufacturing_31sector_base_load_profiles.csv`; see `DATA_SOURCES.md`), then rescaled to the industry mean MW | EWELD (Liu et al. 2023, CC BY 4.0) | `08_code/prepare_eweld_representative_weeks.py`; `02_data/processed/core/manufacturing_31sector_real_weeks.lineage.json` |
| Proxies (no direct sample) | C16 → ISIC 22, C25 → ISIC 17, C37 → ISIC 25, C42 → ISIC 22 (same-archetype proxies). The other 27 use their direct ISIC division | Archetype crosswalk | `02_data/manufacturing_load_curve_source_crosswalk.csv`; lineage JSON |
| Node weeks | Distinct EWELD users of the source ISIC division, taken in user-ID order, each with its best-fit (min-RMSE) week. Aligned by weekday and hour, not by calendar week | — | `08_code/run_group_architecture_core.py` (`select_factory_weeks`) |
| C36 week screens | Monday/Tue–Fri mean ≥ 0.75; weekday daily-mean CV ≤ 0.35; weekly peak/mean ≤ 3.0 | Data-quality screen | `config/scenarios/group_multisite_core_v1.yaml` |
| C36 magnitude | 26,704,000 vehicles / 0.849 × 0.085 = 2.67 M vehicles. 2.97 MWh/vehicle × (2,340 / 5,398 GWh electricity share) = 1.287 MWh/vehicle. Group = 3.44 TWh/yr = 392.9 MW mean = 43.7 MW per site × 9 sites. Five measured profiles cover nine sites. The group represents an average top-10 vehicle manufacturer (s_group = 84.9%/10, CAAM 2024) with nine production sites (assumed). Energy intensity follows one OEM's reported value (Mercedes-Benz, 2.97 MWh/vehicle) and its electricity share | CAAM 2024 sales; Mercedes-Benz Sustainability Report 2023 | `02_data/manufacturing_production_load_calibration.csv`; `08_code/core/production_load.py` |
| Other 30 industries | Site mean = industry mean load × s_group / F_group. **Note:** this differs from the bottom-up C36 rule. Applied to C36, it would give 260.8 MW per site instead of 43.7 MW. A larger production load leaves more headroom, so results for the other 30 industries depend on this choice. A single rule for all industries is left for future work | 2030 industry electricity from the authors' REFERENCE energy scenario | `08_code/core/production_load.py` (legacy mode); `02_data/processed/core/manufacturing_31sector_base_load_profiles.csv`; `02_data/external/d_energy.csv` |

### Grid capacity

| Assumption | Value | Basis | File |
|---|---|---|---|
| K0 and ΔK | K0 = optimized no-AI net peak, with zero headroom credit. ΔK = [max(L+P_fac) − K0]+ | Unobserved existing headroom H0 is kept, not consumed | `config/defaults.yaml` (`grid_capacity_upgrade_boundary`); `08_code/core/model.py` |
| Grid expansion limit / penalty | None / 0 in the core | Used only in structural sensitivities | `config/defaults.yaml` |
| Site distribution (paper Fig. 3) | Shares are over AI-hosting sites: all factories under PFD (7,586), host factories under HFD (888), and AI-hosting nodes under MSD (4,231). "No additional capacity" means exactly 0 MW; counting values below 10⁻⁶ MW (solver tolerance) as zero gives 22.9% instead of 22.2% for MSD | Weighted node table | `08_code/build_node_interconnection_distribution.py` |

### Prices and tariffs

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Tariff class | Guangdong two-part industrial/commercial tariff, 1–10(20) kV, Pearl River Delta | Guangdong Power Grid agency-purchase price notice, April 2026. Applied to all sites and architectures, including the pooled large data center, for comparability; at ≥220 kV the rates would be 26.1 CNY/kW-month and 0.0732 CNY/kWh. The tariff affects costs and scheduling incentives, not how additional capacity is measured | `02_data/china_enterprise_ai_cost_parameters.csv` (E01–E11) |
| Maximum-demand charge | 36.1 CNY/kW-month (26.1 for ≥220 kV), i.e. 433,200 CNY/MW-yr | Same notice (E05) | `config/defaults.yaml` |
| Hourly energy price | Guangdong provincial average-node day-ahead price, 2026-05-28 to 06-03, 15-min prices averaged to hours. The cyclic week is reordered to start on Monday 06-01 (Mon–Wed 06-01 to 06-03, then Thu–Sun 05-28 to 05-31) so each weekday's prices meet the same weekday's load. Third-party data, not redistributed | Not in the public repository; see `DATA_SOURCES.md` | `08_code/core/data.py` (`read_core_grid_energy_prices`) |
| Volumetric adders | 0.0147 line loss + 0.1260 T&D + 0.0859 system operation + 0.02766875 funds = 0.25427 CNY/kWh | E08–E11 | `config/defaults.yaml` |
| Flat-tariff alternative | 0.65856875 CNY/kWh (flat-period price, 1–10 kV two-part). Implemented as `flat_tariff` mode; used only for the QLoRA energy term in the payment comparison (about CNY 0.019 bn). No core sensitivity config activates it | E01 | `config/defaults.yaml`; `08_code/core/data.py` |

### LDC counterfactual

| Assumption | Value | File |
|---|---|---|
| Sizing | Demand of all 31 industries pooled at one logical node: L = 0, K0 = 0, continuous capacity. Same flexible jobs and deadlines, same Guangdong prices and demand charge, r_plan 0.15, N+k 0, no PV or battery | `config/sensitivity/national_cloud_center_v1.yaml`; `08_code/run_national_cloud_center.py` |

### Horizon and solver

| Assumption | Value | File |
|---|---|---|
| Horizon | 168 h, cyclic. σ = 365 / 7 = 52.14 | `config/defaults.yaml` (`horizon_hours`, `annualization_days`) |
| Solver | Gurobi 13.0.2 (`environment.yml`), MIPGap 0.001, 5 threads; Linopy 0.7.0, PyPSA 1.2.2 | `config/defaults.yaml`; `environment.yml`; `README.md` |

### PV/battery extension (not in core results)

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Roof area | US MECS 2022 enclosed floorspace per establishment, mapped to industries (e.g. C13: 5,636 m²) | EIA MECS Tables 7.6/7.9/9.1; Namin et al. 2023 method | `02_data/processed/core/china_manufacturing_industry_rooftop_parameters.csv`; `02_data/raw/curated/china_manufacturing_to_us_mecs_rooftop_crosswalk.csv` |
| u_roof / η_mod / γ | 0.90 / 0.22 kW/m² / 0.80, i.e. 158 W per m² of roof | Assumptions | `config/defaults.yaml` (`factory`) |
| PV case | Existing rooftop PV at the area limit with c_PV = 0. The capex alternative is 2.8 CNY/W over 25 yr. Profile: typical day, case `steel` | — | `config/runs/all_industries_der_sensitivity.yaml`; `04_cases/two_user_pv_battery_typical_day.csv` |
| Battery | 2 h duration; round-trip 0.96 (√ per leg). Energy 99.19 EUR/kWh (773.7 CNY), life 22.5 yr. Inverter 60.30 EUR/kW (470.3 CNY), life 10 yr, FOM 0.25%/yr. 7.8 CNY/EUR | Danish Energy Agency catalogue; UCSB China template; NEA reports | `02_data/raw/curated/battery_cost_parameters_2025.csv`; `config/defaults.yaml` |


### Battery peak-shaving alternative (post-processing)

| Assumption | Value | Basis and source | File |
|---|---|---|---|
| Placement | One behind-the-meter battery per AI host site: each factory (PF), the host (SHG), each node (MSG); it shaves only that site's peak | — | `08_code/analyze_bess_peak_shaving.py` |
| Sizing | Excess e_{n,t} = max(0, L_{n,t} + p_{n,t} − K_n) on the core schedules. Power P_n = max_t e_{n,t}; energy E_n = max_d Σ_{t∈d} e_{n,t} / η_dis (largest daily excess, recharged once per day within existing capacity) | Assumption; schedules are not re-optimized with storage, so sizes are an upper bound | same |
| Round-trip efficiency | 0.90 (√ per leg) | Assumption for AC-side commercial and industrial systems | same |
| Cost | c_P P_n + c_E E_n, with price(h) = c_E + c_P / h fitted to 2-h and 4-h prices: system 496 CNY/kW + 405 CNY/kWh; EPC 491 CNY/kW + 760 CNY/kWh | CNESA average winning bids, Sep. 2026, for utility-scale projects (excluding framework procurement and user-side projects), used for behind-the-meter batteries | `02_data/raw/curated/cnesa_bess_bid_prices_2026_09.csv` |
| Grid-connection benchmark | 220-kV substation and lines of the Taihang computing center phase 2 (Datong): 3 × 150 MVA transformers (two in service, 300 MVA), lines of 10.4 km and 35.3 km, planned investment CNY 231.96 million. Scaled linearly to 1,488 MW: 231.96 × 1,488 / 300 = CNY 1.15 billion, assuming 1 MVA ≈ 1 MW; excludes upstream network reinforcement | Datong Ecology and Environment Bureau, approval 同环函(服务)辐〔2025〕14号, 7 May 2025 | — |
| Check | Hourly simulation tests whether each site can recharge its daily energy; sites that cannot are counted, not resized | — | `R/bess_peak_shaving/bess_peak_shaving_sites.csv` (`daily_recharge_feasible`) |

Water, floor-space, land and payment results are computed after the optimization and do not enter the objective.

## Water, floor space and land

| Assumption | Value (low / base / high if any) | Basis and source | File |
|---|---|---|---|
| Factory-site (PF) water-use intensity | 0 / **0.05** / 0.329 L/kWh-IT | An assumed value for small sites (about 50 kW IT or less) cooled by air or direct expansion, with air-cooled heat rejection. It is not an observed average. Anchors: Alibaba air-cooled WUE (FY2025) and Huawei FM2000. The range comes from WAT01. | `02_data/processed/resource_footprint/small_china_us_water_baseline_comparison.csv`; `config/sensitivity/parameter_bounds_design_v1.csv` |
| Large-data-center (LDC) water-use intensity | 0.06 / **0.335** / 1.8 L/kWh-IT | Unweighted mean of Alibaba's mostly air-cooled 0.329 (ESG FY2025) and Microsoft Americas 0.340 (FY2025), rounded. It is not a national observation for China. The range comes from WAT02. | same files |
| What is counted | On-site cooling and humidification water per kWh of IT electricity | Withdrawal and consumption are not separated. Water = IT energy × WUE, where IT energy = facility power / m^fac. | `config/scenarios/rq1_resource_footprint_summary_v1.yaml` (claim_boundaries); `config/scenarios/figure5_rq1_spatial_water_v1.yaml` |
| Provincial allocation, PF | Each industry's provincial shares of manufacturing **electricity** in 2030 (31 industries × 31 provinces; 133 rows are zero) | Authors' 2030 REFERENCE energy scenario. The allocation is frozen and has no alternative weighting. | `02_data/external/d_energy.csv` → `02_data/processed/resource_footprint/province_industry_ai_allocation.csv` (+ `.lineage.json`) |
| Provincial allocation, LDC | Shares of in-use intelligent computing capacity (FP16) in June 2025, e.g., Hebei 0.148, Shanghai 0.1035, Zhejiang 0.0888 | CAICT *Comprehensive Compute Index Blue Book (2025)*, Fig. 7. Shares were digitized from treemap areas and calibrated to the stated 14.8% for Hebei. They describe capacity, not provider traffic. | `02_data/processed/resource_footprint/china_province_cloud_ai_capacity_share_caict2025.csv` |
| Water-stress context | Aqueduct 4.0 baseline water stress (`bws`), averaged within each province with industrial gross-withdrawal weights (`Ind`), categories 0–4 | WRI Aqueduct 4.0 country rankings (release Y2023M07D05, province_baseline sheet, 1979–2019 baseline), verified on 2026-09-13. Shown next to water volumes but never multiplied by them. The 2030 BAU case is reserved for sensitivity analysis. | `config/scenarios/aqueduct40_province_water_stress_v1.yaml`; `02_data/processed/resource_footprint/china_province_aqueduct40_baseline_water_stress.csv` |
| Core water results | PF 465,812 m³/yr; LDC 3,120,547 m³/yr. Share in High or Extremely High stress provinces: PF 31.4%, LDC 51.1% | Matches the paper (0.47 vs 3.12 million m³, 85% lower). | `05_results/v1.0.0/result/rq1_resource_footprint/rq1_resource_footprint_summary.csv`; `05_results/v1.0.0/result/rq1_spatial_water_interpretation/*.csv` |
| PF rack layout | 2U server groups in 42U racks, so a full rack holds 21 groups | Reference 2U server with two NVIDIA L20 GPUs | `config/scenarios/rq1_resource_footprint_audit_v1.yaml` (`rack_usable_height_u`, `server_height_u`); `08_code/audit_rq1_resource_footprint.py` |
| PF floor scenarios (rack fill φ, non-compute rack share ν, floor area per rack β) | compact 0.75 / 0.10 / 5 m²; **central 0.60 / 0.10 / 9 m²**; spacious 0.50 / 0.20 / 14 m² | The central case is used; compact and spacious cases are registered but not reported. Floor area per rack follows GB 50174-2017 §4.2.2: main-room area of 2.0–4.0 m² per rack, plus auxiliary and support areas of 1.5–2.5 times the main room. This gives 5 / 9 / 14 m² per rack (2.0 × 2.5, 3.0 × 3.0, 4.0 × 3.5). Rack fill and non-compute rack share are assumed. | `config/scenarios/rq1_resource_footprint_audit_v1.yaml` |
| PF floor result | 916,849 m² (central case) | About 121 m² per site across 7,586 scaled factory sites, computed from `core_scenarios.csv` (sum of physical_factory_count × industry_equivalent_multiplier) | `05_results/.../rq1_resource_footprint_summary.csv`; `05_results/v1.0.0/result/group_architecture_core/national/core_scenarios.csv` |
| LDC floor and site intensity | GFA 1,100 m²/MW-IT; site area 313 m²/MW-IT; greenfield case (new_build = 1, new_land = 1) | The file labels these a "screening_project_proxy", with evidence IDs CN_GFA_SAMPLE_RANGE and CN_CU_JJJ_NORTH. Existing-capacity and campus-expansion variants are also registered (land = 0). 1,100 m²/MW-IT is rounded from two projects: (127,000 + 100,000 m²) / (93.72 + 115 MW) = 1,088 (China Telecom Wuhu phase 1; China Unicom Tianjin Wuqing, whose floor area is a lower bound). Wuhu alone gives 1,353. The site area of 313 m²/MW-IT is Unicom Wuqing (54 mu / 115 MW). | `02_data/raw/curated/resource_footprint_space_scenarios.csv` |
| LDC results | Floor 1,341,327 m²; land 381,668 m² (K^IT ≈ 1,219 MW-IT ≈ 1,488 MW / 1.22) | Matches the paper (1.34 and 0.38 million m²) | `05_results/.../rq1_resource_footprint_summary.csv` |
| PF off-site land | 0, only under the existing-site case SMALL_FACTORY_REUSE | New building area at PF sites is not quantified | `02_data/raw/curated/resource_footprint_space_scenarios.csv`; `config/scenarios/rq1_resource_footprint_summary_v1.yaml` |

## Enterprise payments

### China: factory-site deployment (local)

| Assumption | Value (low / base / high if any) | Basis and source | File |
|---|---|---|---|
| GPU server group | CNY 127,500 / **150,000** / 258,060 | Public price range for the Lenovo WR5220 G3 with 2× L20 48 GB (2026). Base is near the low end of the range. | `02_data/china_enterprise_ai_cost_parameters.csv` (L02); `config/defaults.yaml` (server) |
| CPU server group (2×32 physical cores, ≥256 GB, complete delivery) | CNY 60,000 / **90,000** / 118,000 | Low: 2025 public procurement (256 GB, installation and 5-year support). High: 2025 China CDC 768 GB server. Base: engineering midpoint. | `config/compute_hardware/cpu_gpu_routing_v1.yaml` (cpu_server) |
| Server power (GPU / CPU) | Full load 1.50 / 0.78 kW; idle 0.36 / 0.28 kW; standby 0.02 kW | Parameter IDs SRV01/03/06 | `config/defaults.yaml`; `config/compute_hardware/cpu_gpu_routing_v1.yaml` |
| Annualization | Y = 5 yr (4 / 7), ρ = 8% (6% / 12%), O&M 5%/yr (2% / 8%), facility CAPEX 20% (10% / 35%), planning margin 15% | Capital recovery factor (8%, 5 yr) = 0.2505, so annual cost = (1.2 × CRF + 0.05) × CAPEX | `config/defaults.yaml`; `02_data/china_enterprise_ai_cost_parameters.csv` (L13–L15, U01) |
| Electricity | Maximum-demand charge CNY 36.1 (26.1) /kW-month. Hourly energy price = Guangdong day-ahead price for 2026-05-28 to 06-03 plus 0.25427 CNY/kWh of adders (line loss 0.0147, transmission and distribution 0.1260, system operation 0.0859, government funds 0.02767) | Guangdong Power Grid agency-purchase notice, April 2026 (E05, E08–E11). Hourly prices are not redistributed. | `config/defaults.yaml` (energy); `02_data/china_enterprise_ai_cost_parameters.csv` |
| Lifecycle: QLoRA | 8 / **24** / 80 L20 GPU-hours per 15.36 M training tokens (FT006, from the Guanaco-33B configuration); 15% training reserve; fully shiftable | QLoRA paper and Guanaco model card | `02_data/enterprise_llm_lifecycle_parameters.csv`; `config/demand_cases/c36_local_cloud_core_v2.yaml` |
| Lifecycle: RAG storage | 6 bytes per corpus token × 2 copies. Bundled NVMe 3.84 / **7.68** / 15.36 TB per server (ST006). Incremental storage CAPEX 0 / **0** / 30,000 CNY per server (ST007) | Lenovo configuration. Incremental storage cost is 0 in the core case because bundled storage is sufficient. | same files |
| PF local total | CNY 55.43 bn/yr = servers 46.07 + energy 9.10 + demand charges 0.24 + QLoRA energy 0.019. SHG 55.16, MSG 54.92 | Matches "about CNY 55 bn" and the stated <1% spread across architectures | `05_results/v1.0.0/result/national_local_cloud_cost_v1/cost/{comparison,local_cost_components}.csv` |

### China: cloud procurement

| Assumption | Value (low / base / high if any) | Basis and source | File |
|---|---|---|---|
| Providers and text models | Alibaba Cloud qwen3.7-max-2026-06-08: CNY 12 in / 1.2 cached / 36 out per M tokens. DeepSeek V4-Pro: USD 0.435 / 0.003625 / 0.87 per M tokens, FX 6.7719 (2026-07-24). Both accessed 2026-08-11; DeepSeek has since raised its prices, so all prices are an Aug. 2026 snapshot | List prices with no discounts, batch or caching (cache_hit_rate = 0) | `02_data/processed/api_token_cost/api_token_prices_v1_1.csv`; `config/defaults.yaml` (formal_allowed_providers) |
| Bundles | 2 providers × 2 agent archetypes (standard_agent with runtime 0; managed_agents with CNY 0.5/session-hour). MCP: 5 s per tool call × CNY 0.000156/s | Four provider-and-archetype bundles | `config/demand_cases/c36_local_cloud_core_v2.yaml` |
| Managed-service prices | Knowledge-base runtime 0.03 CNY/KB-h; embedding 0.5 and rerank 0.5 CNY/M tokens; VLM 0.15 / 1.5 CNY/M tokens; QLoRA training 0.05 CNY/1k tokens; QLoRA inference 0.6 / 4.8 CNY/M tokens | "official_public_price_anchors", record IDs CLD003–CLD029 | `config/demand_cases/c36_local_cloud_core_v2.yaml` |
| Share of each task class delivered as a managed service (base) | office and agent 1.0; vision 0.75; maintenance 0.50; scheduling 0.35; simulation 0.25 (low/high cases also registered) | Aligned to the foundation-model attribution table | same file |
| Residual GPU capacity | Alibaba ecs.gn8is-2x.8xlarge (2× L20): CNY 182,668.20 / **210,068.43** / 237,468.66 per year, i.e., the public price of 12 × 15,222.35 plus 0%, 15% or 30% for enterprise delivery | Price source is an Alibaba developer-community article, not the official price page. The surcharges are scenarios, not quotes. | `02_data/china_enterprise_ai_cost_parameters.csv` (C17, C19) |
| Residual CPU capacity | ECS c8i.8xlarge (32 vCPU, 64 GiB, 0.25 of a local server): CNY 24,422.76 / **28,086.17** / 31,749.59 per year, from the one-year prepaid price (12 × CNY 2,035.23/month, 35% below the monthly list price of 3,131.13) plus 0%, 15% or 30%. PAI-EAS (maintenance tasks): CNY 67,837.44 flat, with no surcharge | Surcharges apply only to reserved CPU/GPU capacity, not to token APIs | `config/compute_hardware/cpu_gpu_routing_v2.yaml` |
| Cloud totals (base price case) | CNY 95.13 to 100.72 bn/yr (low price case 85.5–91.1; high 104.8–110.4). Residual capacity is about 91 bn (GPU 31.7, ECS 42.1, EAS 17.1); managed services about 4 bn | Matches "CNY 95–101 bn" | `05_results/.../national_local_cloud_cost_v1/cost/{comparison,cloud_cost_components}.csv` |

### United States (21 NAICS-3 industries, post-processing only)

| Assumption | Value (low / base / high if any) | Basis and source | File |
|---|---|---|---|
| CPU server (64 physical cores, ≥256 GB, 3-year complete delivery) | USD 32,550 / **34,100** / 37,200 | Engineered proxy (Exxact platform + storage + 5–20% delivery allowance), pending an OEM quote | `02_data/processed/cost_benchmark/us_core_cost_parameters_v1.csv`; `config/cost_cases/us_heterogeneous_cpu_v1.yaml` |
| GPU server (2× L20) | USD 44,400 / **46,500** / 50,800 | Bill-of-materials proxy plus 5/10/20% integration allowance; no observed complete-server quote | same |
| Industrial electricity | USD 0.0612 / **0.0813** / 0.2153 per kWh, flat | EIA Electric Power Annual, final 2024 U.S. industrial average. Low and high are state values (Texas is the low). | same |
| Annualization and facility | 8%, 5 yr, 20% facility CAPEX, 5% O&M, m^fac 1.30 (shared with China) | — | `config/cost_cases/us_heterogeneous_cpu_v1.yaml`; `08_code/analyze_us_industry_heterogeneous_hardware.py` |
| Cloud capacity | GPU: 2× AWS g6e.4xlarge (L40S), 1-yr all-upfront, USD 30,948 / yr (high 33,160). CPU: AWS c7i.8xlarge, USD 7,723 / yr. No delivery surcharge | AWS price list, us-east-1 | `us_core_cost_parameters_v1.csv` |
| API providers | OpenAI gpt-5.6-terra USD 2.75 / 16.5; Anthropic claude-sonnet-5 3.3 / 16.5; Google gemini-3.6-flash 1.5 / 7.5 (per M input / output tokens) | U.S.-region prices: OpenAI and Anthropic include a 10% U.S.-residency premium, Google uses its regional endpoint | `02_data/processed/cost_benchmark/us_api_token_prices_v1.csv` |
| Not modeled | Hourly optimization, production-load coupling and maximum-demand charges (the Dominion GS-4 tariff is marked blocked); cloud RAG, agent runtime and QLoRA; storage | Stated in the findings and parameter status | `05_results/v1.0.0/result/cost_benchmark/heterogeneous_hardware_v1/us_naics3/findings.md` |
| U.S. totals (base case) | Local USD 15.88 bn (CPU low/high: 15.44 / 16.75). Cloud 18.71 (Google) / 19.10 (OpenAI) / 19.14 (Anthropic), of which CPU capacity is 15.83 | Matches "about USD 16 and 19 bn" | `.../us_naics3/us_national_comparison.csv` |

## Sensitivity ranges

**Known limitations of this release.** Only the no-shift sensitivity (PHY03) is used in the paper. The hardware sensitivities HW01 and HW02 are not supported: the CPU-time multiplier factor is not read by the group solver, and the large-data-center run does not apply the routing or CPU-server overrides. Cloud residual capacity is always sized on base-case demand, so non-base payment cases are not supported.

The bounds below are registered in `config/sensitivity/parameter_bounds_design_v1.csv`, with basis and range decision in `parameter_range_provenance_v1.csv`. The paper reports no one-at-a-time sensitivity results. The only ranges it reports come from the demand scenarios (PHY01, about 0.6× and 2.0× base, used to scale payments) and from the spread across cloud provider bundles.

| Factor | Base | Low / High | Used in reported ranges |
|---|---|---|---|
| PHY01 demand case | base | low / high | **Yes** |
| PHY02 IT efficiency η | 3.0 | 1.5 / 5.0 | No |
| PHY04 / PHY05 / PHY06 / PHY07: GPU max power, idle power, m^fac, planning margin | 1.5 kW / 0.36 kW / 1.3 / 0.15 | 1.05–1.5 / 0.28–0.5 / 1.2–1.6 / 0–0.50 | No |
| PHY11 maximum-demand charge (CNY/kW-month) | 36.1 | 26.1 / 36.1 | No |
| COST01 China GPU server (CNY) | 150,000 | 127,500 / 258,060 | No |
| COST02 lifetime (yr) | 5 | 4 / 7 | No |
| COST03 O&M; COST04 facility CAPEX | 0.05; 0.20 | 0.02–0.08; 0.10–0.35 | No |
| COST05A China CPU server (CNY) | 90,000 | 60,000 / 118,000 | No (computed, not reported) |
| COST05B cloud delivery multiplier | 1.15 | 1.0 / 1.3 | No (computed: 85–110 bn) |
| COST06 / CPU01 U.S. GPU / CPU server (USD) | 46,500 / 34,100 | 44,400–50,800 / 32,550–37,200 | No |
| COST07 U.S. electricity (USD/kWh) | 0.0813 | 0.0612 / 0.2153 | No |
| COST08 U.S. cloud GPU (USD/yr) | 30,948 | 30,948 / 33,160 | No |
| HW01 CPU/GPU routing; HW03 cloud CPU capacity relative to local | practice_routed; 0.25 | gpu_only / cpu_heavy; 0.125 / 0.5 | No |
| WAT01 / WAT02 WUE (L/kWh-IT) | 0.05 / 0.335 | 0–0.329 / 0.06–1.8 | No |
| LAND01 / LAND02 reuse / new-build fraction | 1 / 1 | 0 / 1 | No |
| COST05, LAND03 (GFA 1,100), LAND04 (site 313), WAT04 | — | not defined | No |

## Evidence files

The parameter tables above cite the following author-compiled evidence notes and registers. Most are written in
Chinese. They record the sources, extraction steps and reasoning behind the values; the model does not read them.

| File | Contents |
|---|---|
| `02_data/china_manufacturing_ai_evidence_update.md` | Observed AI adoption by Chinese manufacturers (economic census, statistical yearbook, government statements) used for A_any |
| `02_data/china_manufacturing_ai_effective_service_bottom_up_report.md` | Derivation of the 2023→2030 task growth factors G_k and the low/high scenarios |
| `02_data/manufacturing_ai_task_compute_stack_evidence.csv` | Evidence for the task scope: which parts of each task class can run at a factory or in a pool |
| `02_data/distributed_ai_facility_parameters.csv`, `02_data/china_enterprise_ai_cost_parameters.csv` | Parameter registers (IDs such as `SRV01`, `PUE04`, `E05`, `L02`) with source titles, URLs and evidence quality |
| `02_data/cloud_ai_delivery_billing_evidence_v0.1.csv` | Cloud price records `CLD001`–`CLD030` with snapshot dates and source URLs |
| `02_data/china_us_hyperscale_cloud_physical_parameters_report.md` | Large-data-center floor area, site area and water-use evidence |
| `02_data/china_manufacturing_ai_water_cooling_noise_space_report.md` | Factory server-room cooling, water and space evidence |
| `08_code/prepare_resource_footprint_province_allocation.py` | Builds the provincial allocation used for per-factory water (run outside the workflow; diagnostics in `02_data/processed/resource_footprint/province_industry_ai_allocation_diagnostics.csv`) |
| `08_code/archive/run_manufacturing_ai_31sector_topdown.mjs`, `08_code/archive/run_manufacturing_ai_task_hardware_demo.mjs` | Historical generators of the per-industry weights and per-task templates in `02_data/interim/effective_service/` (kept for provenance; they depend on tools not included here and are not part of the workflow) |
