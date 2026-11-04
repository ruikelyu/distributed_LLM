# RQ1 spatial-water audit

- Status: `READY_FOR_SPATIAL_REBUILD`
- Model version: `v1.0.0`
- Execution: solver-free audit; no Figure 5 or manuscript authorization

## Component disposition

| Component | Ready | Disposition | Reason |
|---|---:|---|---|
| PF_province_water_allocation | true | `REBUILD_POSTPROCESS_NO_SOLVE` | allocate the approved PF national water total with the frozen 31-industry REFERENCE electricity-share scenario |
| LDC_province_water_allocation | true | `REBUILD_POSTPROCESS_NO_SOLVE_USING_OWN_APPROVED_WATER_TOTAL` | allocate LDC's own approved water total with the frozen 2025 CAICT capacity proxy; do not reuse PF IT energy |
| national_water_total | true | `PRESERVE_APPROVED_TOTALS` | uniform architecture-specific WUE means spatial allocation changes distribution, not the approved national total |
| formal_water_scarcity_LCIA_application | true | `NOT_APPLICABLE_BY_APPROVED_DESIGN` | the approved design does not multiply site water by a characterization factor or report world-equivalent impact |
| province_water_stress_context_and_Figure5 | true | `USE_SEPARATE_BASELINE_CONTEXT_PANEL` | use the checksum-frozen WRI province baseline, industrial-demand-weighted score only as a prioritization context separate from site-water quantities |

## Decisive findings

- PF allocation closes across 31 industries and 31 provinces and its upstream source hash matches the registered lineage.
- The LDC input is usable only as a frozen 2025 in-use intelligent-compute capacity proxy, not provider traffic or a 2030 siting forecast.
- PF and LDC must retain their own approved national on-site cooling and humidification water totals; the superseded script incorrectly applies PF IT energy to LDC.
- The official WRI Aqueduct 4.0 rankings archive is checksum-frozen, and the industrial-demand-weighted baseline water-stress rows reproduce for all 31 provinces with lineage.
- The approved design retains the registered site-water WUE values and presents province water stress separately. It does not multiply the two, report m3 world-eq, or claim a formal LCIA water-scarcity impact.
- The superseded script also hard-codes v1.0.0 paths and a 1.30 multiplier and labels the metric as withdrawal, outside the current water boundary.

## Next admissible action

Build the YAML-versioned PF-versus-LDC Figure 5 postprocessor using each architecture's approved national site-water total and the Aqueduct baseline score as a separate context field or panel. Keep 2030 BAU for RQ3 sensitivity only. No optimization rerun is required unless location-specific WUE or another power-affecting cooling assumption is introduced.
