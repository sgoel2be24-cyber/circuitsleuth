# CircuitSleuth evaluation results

> All data is **synthetic** (seeded generator, `tools/generate_dataset.py`).

30 inspections = 5 variants x 6 scenario templates.
Headline precision/recall/F1 are **verdict-level**: only regions the system actually reports as a defect
(CONFIRMED/LIKELY) count as positives; cleared confounds are not alarms. Localization matching: IoU >= 0.15.

| Metric | Baseline (fixed pipeline) | CircuitSleuth (adaptive) |
|---|---|---|
| Precision | 0.521 | 0.863 |
| Recall | 0.893 | 0.782 |
| F1 | 0.575 | 0.716 |
| False positives | 50 | 10 |
| False negatives | 6 | 8 |
| Mean latency (s) | 0.21 | 0.39 |
| Mean tool calls | 0.0 | 4.6 |
| Escalation rate | 0.0% | 27.3% |
| Registration failures caught | 5 | 5 |

## Per template

| Template | n | Baseline P/R/F1 | Adaptive P/R/F1 | Adaptive tools/inspection |
|---|---|---|---|---|
| scenario_01_clear_defects | 5 | 0.78/0.80/0.78 | 0.90/0.93/0.91 | 5.2 |
| scenario_02_clean_board | 5 | 0.20/1.00/0.20 | 0.80/1.00/0.80 | 2.4 |
| scenario_03_ambiguous_glare | 5 | 0.20/0.80/0.32 | 0.60/0.80/0.67 | 6.0 |
| scenario_04_registration_failure | 5 | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 0.0 |
| scenario_05_no_second_view | 5 | 0.21/0.80/0.33 | 1.00/0.00/0.00 | 4.8 |
| scenario_06_multiple_regions | 5 | 0.73/0.96/0.82 | 0.88/0.96/0.91 | 9.2 |

## Interpretation notes

- The baseline shares the same OpenCV core (registration + detection), so differences
  come from *verification behavior*, not from a stronger detector.
- Scenario 04 (mismatched capture) has no ground-truth defects: correct behavior is
  refusing to report (NOT_EVALUABLE), reflected in registration failures caught.
- Scenario 05 has no secondary view by design: the adaptive agent's correct behavior is
  to request a new capture and escalate to human review instead of guessing, so its
  reported-recall for this template is intentionally 0 while the baseline guesses.
- Escalation rate includes deliberate, honest escalations — for the adaptive system
  these replace fabricated confidence on ambiguous evidence.
