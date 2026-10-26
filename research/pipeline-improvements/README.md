# CircuitSleuth pipeline improvement research

Start with [REPORT.md](REPORT.md). Research scripts and all generated results are isolated here. No production change is proposed as already promoted.

Reproduce from the project root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python research/pipeline-improvements/experiments.py --phase probes
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python research/pipeline-improvements/experiments.py --phase tune
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python research/pipeline-improvements/experiments.py --phase test
```

Use the supplied virtual environment. No dependency installation or network access is used by experiments. Machine-readable outputs record environment, seeds, parameters, original measurements, scores and failures. The original benchmark is only read and preserved. Images and annotations generated here are synthetic and cannot establish production PCB accuracy.
