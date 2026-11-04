# U.S. manufacturing AI demand

Version: `us_manufacturing_ai_demand_v0.3.0`; year: 2030 base.

U.S. official activity levels, adoption rates, task units per adopter, and per-task compute intensity jointly yield **51,298,423 effective service units/day**. The fixed reference system gives annual facility electricity of **6.909 TWh**; this electricity is used only as an order-of-magnitude demand check and is not a Figure 2 local or cloud cost result.

## Interpretation boundaries

- The total is a pure bottom-up sum over the six tasks; there is no national multiplier back-calculated from China's electricity use.
- The China--U.S. electricity ratio at the same tier is used only as an external check on manufacturing economic scale and does not enter the demand formula.
- Per-unit service intensity and 24-hour task shapes are carried over from the existing model and are scenario assumptions; U.S. official data supply activity levels, adoption rates, and industry structure.
- This module no longer publishes a standalone local--cloud payment table; authoritative cost results are produced by `analyze_us_industry_heterogeneous_hardware.py` under the managed-service--residual-capacity contract shared by China and the U.S.
