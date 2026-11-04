PYTHON ?= python
CORES ?= 4

.PHONY: reproduce list test fetch-data full-run

# Level 1: rebuild all post-optimization results and figures from the saved model
# outputs, then compare every regenerated CSV with the shipped version.
reproduce:
	$(PYTHON) 08_code/reproduce_paper_results.py

list:
	$(PYTHON) 08_code/reproduce_paper_results.py --list

test:
	$(PYTHON) -m unittest discover -s tests

# Level 2: download EWELD, then rerun the full workflow (needs Gurobi and an
# hourly price series; see README.md).
fetch-data:
	$(PYTHON) 08_code/fetch_external_data.py

full-run:
	snakemake paper --cores $(CORES) --forceall
