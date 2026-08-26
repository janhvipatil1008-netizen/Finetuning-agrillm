# Superseded pre-review draft

These two files are the **pre-review draft** of the output schema and system
prompt. They were superseded on **2026-08-27** by the reviewed versions now in
`src/`, and are kept here only so the earlier design is recoverable.

**Do not import from this directory.** Nothing in the pipeline should read these
files. The live, frozen artifacts are `src/schema.py` and `src/system_prompt.txt`,
guarded by `src/freeze_check.py`.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `schema.py` | 3868 | `28b3e6e56cae53425e72fcacfad81bf8e2f0efa8e8227279363d97273836dc56` |
| `system_prompt.txt` | 6404 | `a6bca9d1092d743a6d1b05dac861a9e5e2b7f460aeadc620ba14c9db0981d438` |

## Why it was replaced

The draft modelled dose as a single free-text `dose_per_acre: str` and carried no
cross-field validation. That could not represent the bases CIB&RC actually prints
(per tree, per plant, per kg seed, per sq m, percentage concentration, per litre
of water, prose), so any orchard or seed-treatment claim would have forced the
model to invent an acre figure. It also could not distinguish an unknown
pre-harvest interval from a genuine zero-day interval, and permitted
self-contradictory advisories — out-of-scope answers carrying chemical options,
or recommendations on a query the model had not understood.

The reviewed schema replaces the dose string with a `Dose` model carrying an
explicit `basis`, makes `phi_days` optional so `None` and `0` stay distinct, and
enforces the safety invariants in `model_validator` hooks pinned by
`tests/test_schema.py`.
