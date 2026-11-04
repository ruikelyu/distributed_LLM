# RQ1 Figure 5 spatial water: controlled interpretation review memo (v1.0.0)

**Status: interpretation confirmed by the authors; reserved for later coordinated migration into the manuscript.**

## 1. Review scope and evidence

This memo only interprets the validated data `05_results/v1.0.0/result/manuscript_figures/figure5_spatial_water_data.csv` and its marker `05_results/v1.0.0/result/manuscript_figures/figure5_spatial_water.validated.done.json`. Statistics are aggregated directly from provincial allocation shares; the PyPSA solver is not run, Figure 5 is not changed, and the manuscript text is not modified.

## 2. Within-architecture descriptive summary

| Architecture | National onsite water (million m³/yr) | Largest provincial allocation | Top-7 provincial allocation share | High-or-above share | Extremely High share |
|---|---:|---|---:|---:|---:|
| PF | 0.466 | Guangdong (13.5%) | 57.0% | 31.4% | 19.3% |
| LDC aggregate | 3.121 | Hebei (14.8%) | 62.8% | 51.1% | 26.1% |

Shares here are provincial spatial-allocation shares of each architecture's own national onsite water total: PF uses the 2030 REFERENCE manufacturing-electricity spatial scenario and LDC uses the 2025 in-service intelligent-computing capacity proxy. PF and LDC use different registered WUE scenarios and different spatial inputs, so differences in national totals or shares cannot be interpreted as a net effect of deployment architecture.

## 3. Top-7 provincial spatial allocation

| Architecture | Rank | Province | Onsite water (m³/yr) | Within-architecture share | Aqueduct baseline category |
|---|---:|---|---:|---:|---|
| PF | 1 | Guangdong | 62,668 | 13.5% | Low (<10%) |
| PF | 2 | Zhejiang | 56,470 | 12.1% | Medium - High (20-40%) |
| PF | 3 | Jiangsu | 43,593 | 9.4% | Medium - High (20-40%) |
| PF | 4 | Shandong | 41,614 | 8.9% | Extremely High (>80%) |
| PF | 5 | Sichuan | 27,734 | 6.0% | Medium - High (20-40%) |
| PF | 6 | Hubei | 16,704 | 3.6% | Low - Medium (10-20%) |
| PF | 7 | Fujian | 16,672 | 3.6% | Medium - High (20-40%) |
| LDC_AGGREGATE | 1 | Hebei | 461,841 | 14.8% | Extremely High (>80%) |
| LDC_AGGREGATE | 2 | Shanghai | 322,879 | 10.3% | High (40-80%) |
| LDC_AGGREGATE | 3 | Zhejiang | 277,033 | 8.9% | Medium - High (20-40%) |
| LDC_AGGREGATE | 4 | Guizhou | 257,842 | 8.3% | Low - Medium (10-20%) |
| LDC_AGGREGATE | 5 | Inner Mongolia | 239,611 | 7.7% | High (40-80%) |
| LDC_AGGREGATE | 6 | Guangdong | 231,508 | 7.4% | Low (<10%) |
| LDC_AGGREGATE | 7 | Ningxia | 167,651 | 5.4% | High (40-80%) |

The two Top-7 sets share 2 provinces: Guangdong, Zhejiang. This only shows that the two registered spatial inputs produce different provincial distributions. Both are referred to as Top-7 provincial spatial allocation; the cumulative share is not a concentration of physical data centers or plant sites.

## 4. Water-stress category composition

| Architecture | Aqueduct baseline category | Provinces | Allocated onsite water (m³/yr) | Within-architecture share |
|---|---|---:|---:|---:|
| PF | Low (<10%) | 3 | 77,168 | 16.6% |
| PF | Low - Medium (10-20%) | 7 | 70,305 | 15.1% |
| PF | Medium - High (20-40%) | 9 | 171,848 | 36.9% |
| PF | High (40-80%) | 6 | 56,384 | 12.1% |
| PF | Extremely High (>80%) | 6 | 90,108 | 19.3% |
| LDC_AGGREGATE | Low (<10%) | 3 | 275,988 | 8.8% |
| LDC_AGGREGATE | Low - Medium (10-20%) | 7 | 540,781 | 17.3% |
| LDC_AGGREGATE | Medium - High (20-40%) | 9 | 708,351 | 22.7% |
| LDC_AGGREGATE | High (40-80%) | 6 | 779,625 | 25.0% |
| LDC_AGGREGATE | Extremely High (>80%) | 6 | 815,802 | 26.1% |

These category totals answer 'what share of each architecture's proxy allocation falls in a given provincial background category'; water volume is not multiplied by the stress score, and this does not constitute m³ world-equivalent, a formal LCIA, or a local water-resource impact.

## 5. Author-confirmed Results wording pending migration

In the Figure 5 spatial screen of the v1.0.0 main scenario, PF's 0.466 million m³/year of onsite cooling and humidification water is allocated by the 2030 REFERENCE manufacturing-electricity spatial scenario; the top 7 provinces account for 57.0%, and provinces in the Aqueduct baseline High or Extremely High categories account for 31.4%. LDC aggregate's 3.121 million m³/year is allocated by the 2025 in-service intelligent-computing capacity proxy; the top 7 provinces account for 62.8%, and High or Extremely High category provinces account for 51.1%. The two Top-7 sets share 2 provinces (Guangdong, Zhejiang). These shares only describe the overlay of two registered provincial spatial allocations on the same provincial water-stress background; they do not represent actual facility siting, physical site concentration, a causal architecture effect, or a formal water-scarcity impact.

## 6. Required accompanying claim boundaries

1. `results_describe_two_registered_provincial_spatial_allocations_not_observed_facility_siting`
2. `top7_share_is_registered_spatial_allocation_not_physical_site_concentration`
3. `stress_composition_is_the_share_of_allocated_site_water_in_province_categories_not_a_scarcity_weighted_impact`
4. `site_water_quantity_and_stress_score_are_never_multiplied`
5. `PF_and_LDC_national_water_totals_use_different_registered_WUE_scenarios_and_their_difference_is_not_an_architecture_effect`
6. `cross_architecture_distribution_differences_are_descriptive_input_based_differences_not_causal_architecture_effects`
7. `Aqueduct40_baseline_is_a_1979_2019_prioritization_screen_not_real_time_or_site_validated_stress`
8. `industrial_gross_withdrawal_is_a_within_province_aggregation_weight_not_a_data_center_water_inventory`
9. `no_m3_world_equivalent_formal_LCIA_or_local_water_impact_is_reported`
10. `LDC_AGGREGATE_is_a_logical_equal_service_portfolio_not_one_physical_site`
11. `2030_BAU_water_stress_is_excluded_and_reserved_for_RQ3_sensitivity`
12. `author_approved_wording_is_reserved_for_later_coordinated_manuscript_migration`

## 7. Author decision gate

This confirmation only authorizes these values, names, and boundaries for later coordinated manuscript migration; this script still does not modify the manuscript, and the Figure 5 data and figure status are unchanged.
