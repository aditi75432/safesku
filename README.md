# SafeSKU CPSC benchmark patch

Adds the first reproducible historical CPSC benchmark builder without modifying the existing live/demo ingestion output.

Files:
- `scripts/build_cpsc_benchmark.py`
- `apps/api/tests/test_cpsc_benchmark.py`
- `docs/BENCHMARK_PROTOCOL.md`

Example:

```powershell
python scripts\build_cpsc_benchmark.py --start-date 2020-01-01 --end-date 2023-09-30 --chunk-months 3
```

This writes raw date-window snapshots to `data/raw/cpsc_benchmark/` and normalized benchmark data to `data/benchmark/cpsc/`.
