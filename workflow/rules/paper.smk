# Targets for the grid-interconnection paper.
#
# `snakemake paper` builds every figure, table input, and headline number
# used by the paper. Variables are defined in core_scenarios.smk and
# single_industry_sensitivity.smk, which must be included first.

PAPER_FIGURE_ROOT = MANUSCRIPT_FIGURE_ROOT
LOAD_COORDINATION_STEM = PAPER_FIGURE_ROOT + "/figure3_load_coordination"
GM_ARCHITECTURES_STEM = PAPER_FIGURE_ROOT + "/gm_architectures"
GM_SITE_DISTRIBUTION_STEM = PAPER_FIGURE_ROOT + "/gm_site_distribution"
RQ2_MECHANISM_CONFIG = "config/scenarios/rq2_mechanism_summary_v1.yaml"
RQ2_MECHANISM_ROOT = RESULT_OUTPUT_ROOT + "/rq2_mechanisms"
RQ2_MECHANISM_EFFECTS = RQ2_MECHANISM_ROOT + "/rq2_mechanism_effects.csv"
RQ2_MECHANISM_DONE = RQ2_MECHANISM_ROOT + "/rq2_mechanism_effects.validated.done.json"
BESS_PEAK_SHAVING_ROOT = RESULT_OUTPUT_ROOT + "/bess_peak_shaving"
BESS_PEAK_SHAVING_DONE = BESS_PEAK_SHAVING_ROOT + "/bess_peak_shaving.validated.done.json"


rule build_load_coordination_figure:
    input:
        hourly=GROUP_CORE_ROOT + "/C36/hourly.csv",
        msg_no_routing_hourly=GROUP_CORE_ROOT + "/C36/msg_no_routing_hourly.csv",
        core_done=GROUP_CORE_NATIONAL_DONE,
        script="08_code/build_figure3_load_coordination_redesign.py",
    output:
        png=LOAD_COORDINATION_STEM + ".png",
        pdf=LOAD_COORDINATION_STEM + ".pdf",
        svg=LOAD_COORDINATION_STEM + ".svg",
    params:
        stem=LOAD_COORDINATION_STEM,
    conda:
        "../envs/core_model.yaml"
    shell:
        "python {input.script} --output-stem {params.stem}"


rule build_gm_figures:
    input:
        data=FIGURE3_DATA,
        config=FIGURE3_RQ1_CONFIG,
        script="08_code/build_gm_figures.py",
        card_script="08_code/build_figure3_rq1_grid_capacity.py",
    output:
        architectures_pdf=GM_ARCHITECTURES_STEM + ".pdf",
        architectures_png=GM_ARCHITECTURES_STEM + ".png",
        sites_pdf=GM_SITE_DISTRIBUTION_STEM + ".pdf",
        sites_png=GM_SITE_DISTRIBUTION_STEM + ".png",
    params:
        output_dir=PAPER_FIGURE_ROOT,
    conda:
        "../envs/core_model.yaml"
    shell:
        "python {input.script} --config {input.config} --data {input.data} "
        "--output-dir {params.output_dir}"


rule summarize_rq2_mechanisms:
    input:
        config=RQ2_MECHANISM_CONFIG,
        defaults="config/defaults.yaml",
        core=GROUP_CORE_NATIONAL_SUMMARY,
        alignment=GROUP_CORE_NATIONAL_ALIGNMENT,
        coordination=GROUP_CORE_NATIONAL_COORDINATION,
        core_done=GROUP_CORE_NATIONAL_DONE,
        temporal=NATIONAL_TEMPORAL_SHIFTING_VALUE,
        temporal_done=NATIONAL_TEMPORAL_SHIFTING_DONE,
        script="08_code/summarize_rq2_mechanisms.py",
    output:
        effects=RQ2_MECHANISM_EFFECTS,
        done=RQ2_MECHANISM_DONE,
    conda:
        "../envs/core_model.yaml"
    shell:
        "python {input.script} --config {input.config} "
        "--output {output.effects} --done-output {output.done}"


rule analyze_bess_peak_shaving:
    input:
        hourly=GROUP_CORE_HOURLY,
        core_done=GROUP_CORE_NATIONAL_DONE,
        nodes=NODE_DISTRIBUTION_DATA,
        prices="02_data/raw/curated/cnesa_bess_bid_prices_2026_09.csv",
        script="08_code/analyze_bess_peak_shaving.py",
    output:
        sites=BESS_PEAK_SHAVING_ROOT + "/bess_peak_shaving_sites.csv",
        national=BESS_PEAK_SHAVING_ROOT + "/bess_peak_shaving_national.csv",
        components=BESS_PEAK_SHAVING_ROOT + "/bess_cost_components.csv",
        done=BESS_PEAK_SHAVING_DONE,
    params:
        root=BESS_PEAK_SHAVING_ROOT,
    conda:
        "../envs/core_model.yaml"
    shell:
        "python {input.script} --nodes {input.nodes} --prices {input.prices} "
        "--output-root {params.root}"


rule paper:
    input:
        # Fig. 1: grid-interconnection capacity.
        FIGURE3_PDF,
        # GM paper Figs. 1 and 3: architecture schematic and site distribution.
        GM_ARCHITECTURES_STEM + ".pdf",
        GM_SITE_DISTRIBUTION_STEM + ".pdf",
        # Fig. 2: production-compute load coordination (C36).
        LOAD_COORDINATION_STEM + ".pdf",
        # Fig. 3: resource footprint and enterprise payments.
        FIGURE4_MANUSCRIPT_PDF,
        FIGURE4_MANUSCRIPT_DONE,
        # Fig. 2: manufacturing-AI demand scenarios and task composition.
        FIGURE1_PDF,
        FIGURE1_DATA,
        FIGURE1_DONE,
        # Demand table and foundation-model shares.
        NATIONAL_TASK_LEDGER_DONE,
        NATIONAL_LOCAL_CLOUD_COST_DONE,
        # Water table (top provinces and water-stress composition).
        RQ1_SPATIAL_TOP_PROVINCES,
        RQ1_SPATIAL_STRESS_COMPOSITION,
        # Mechanism decomposition (D_load, D_time, D_space).
        RQ2_MECHANISM_DONE,
        # Behind-the-meter battery alternative to additional capacity.
        BESS_PEAK_SHAVING_DONE,
