# RQ1 grid infrastructure: controlled interpretation review (v1.0.0)

**Status: approved by the authors for the figure and later manuscript migration; the current manuscript is not yet synchronized.**

## 1. Evidence scope

National totals come from `05_results/sensitivity/v1.0.0/national_grid_capacity_comparison.csv`; node scale comes from `05_results/v1.0.0/result/node_interconnection_distribution/node_interconnection_distribution.csv` and its common bins. The former compares national incremental interconnection capacity under the same effective AI service; the latter compares the capacity scale of weighted modeled deployment nodes with internationally published facility/campus records. The two answer different questions, and the external facility distribution must not be treated as an equal-service LDC node configuration.

## 2. National incremental interconnection capacity

| Architecture | Architecture capacity (MW) | LDC aggregate capacity (MW) | Difference vs. LDC (MW) | Ratio vs. LDC |
|---|---:|---:|---:|---:|
| PF | 555.7 | 1487.7 | 932.0 | 62.6% |
| SHG | 575.8 | 1487.7 | 911.9 | 61.3% |
| MSG | 30.2 | 1487.7 | 1457.5 | 98.0% |

All three distributed scenarios provide the same effective AI service as the LDC aggregate counterfactual. The LDC value is a logical portfolio of new capacity, not one physical data center or interconnection point.

## 3. Node-scale distribution

| Distribution | 0 MW | (0,0.1) MW | [0.1,1) MW | [1,10) MW | [10,100) MW | [100,1000) MW | [1000,10000) MW |
|---|---:|---:|---:|---:|---:|---:|---:|
| PF | 0.0% | 68.4% | 31.6% | 0.0% | 0.0% | 0.0% | 0.0% |
| SHG | 0.0% | 20.0% | 58.0% | 22.0% | 0.0% | 0.0% | 0.0% |
| MSG | 22.2% | 76.9% | 0.9% | 0.0% | 0.0% | 0.0% | 0.0% |
| LDC_EMPIRICAL_REFERENCE | 0.0% | 0.0% | 0.0% | 0.0% | 27.5% | 69.6% | 2.9% |

PF, SHG, and MSG shares use registered representative-node weights, not an observed sample of national factory interconnection points. The Epoch primary reference contains 69 internationally published AI facility or campus records, converted with a peak facility power / current IT power factor of 1.20; these records are not independent grid interconnection points, nor a China-specific or equal-service LDC configuration.

## 4. Author-approved Results wording for migration

Under the v1.0.0 main scenario and the same effective-AI-service boundary, the national incremental interconnection capacity required by PF, SHG, and MSG is 555.7, 575.8, and 30.2 MW, respectively, all below the LDC aggregate counterfactual's 1487.7 MW; the corresponding differences are 932.0 MW (62.6%), 911.9 MW (61.3%), and 1457.5 MW (98.0%). Beyond the national total, the deployment architecture also changes the node scale at which capacity appears. In the common bins, 68.4% of PF node weight lies below 0.1 MW, 58.0% of SHG node weight lies in 0.1--1 MW, and 22.2% of MSG node weight requires no new capacity, with a further 76.9% in 0--0.1 MW. As a scale reference, all 69 Epoch international facility/campus records lie above 10 MW under the primary conversion, with 69.6% in 100--1000 MW. This external comparison shows that the two distributions occupy different capacity scales, but it is not a China-specific, equal-service, or same-statistical-unit LDC siting comparison.

## 5. Required accompanying boundaries

1. Incremental interconnection capacity is a site-side continuous MW screening quantity holding unobserved existing headroom fixed; it is not grid equipment, investment, projects, or construction timing.
2. `LDC_AGGREGATE` is a logical new-capacity portfolio carrying the same national service; it does not correspond to one physical facility or interconnection point.
3. PF, SHG, and MSG node distributions come from weighted representative nodes, not a probability sample of national factory nodes.
4. The statistical unit of the Epoch records is a published facility or campus, not guaranteed to be an independent grid interconnection point; the sample is an international reference, not a China-specific distribution.
5. The Epoch distribution is not normalized to this study's national service volume or total capacity and cannot be used to infer the number or spatial configuration of LDC physical sites.
6. The largest modeled node, P50/P95, Top-k, HHI, and effective node count are not reported at this stage.
7. Water, facility floor area, and offsite land are not yet part of this interpretation.

## 6. Migration status

The aggregate results, node-scale results, and their boundaries above are approved by the authors and may enter the Figure 3 design; Methods, Results, Discussion, and captions must still be synchronized in the later coordinated manuscript migration.
