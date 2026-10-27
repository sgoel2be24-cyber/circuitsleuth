# Final check — 27 October 2026

Team **Update**: Shikhar Goel and Ishpreet Singh.

**Application checks passed. Competition submission still requires final human
rules/eligibility confirmation and the actual submission receipt.** This note
supersedes the five open findings in [the earlier review](REVIEW_2026-10-27.md).

## Fixes and validation

| Finding | Final behavior and acceptance evidence |
|---|---|
| Completed-run MCP mutation / accidental restart | Only created runs accept MCP mutators; report finalizes the session, escalating unfinished regions. UI and REST respect MCP ownership. Tests cover both directions and unchanged terminal evidence. |
| Overlapping stale writers | Per-run OS locks cover full REST/MCP mutations. Separate-process contention and release after exceptions tested. Completion is published after the last awaited write. |
| Capture provenance | `/views` and `/rerun` attach new captures to a fresh child, returning its ID. Parent, SHA256 inputs and capture event are recorded. Original files/index/events are unchanged on successful capture, invalid upload and injected child-start failure. |
| Clipped glare | Erode valid support with a one-pixel halo. Regression suppresses the reproduced clipped-patch candidate. A wide halo was rejected after fixed FP increased from 50 to 53. |
| Rejected-review label | CLEARED has a null final label consistently in state, API and exported report. Accepted-review regression still passes. |
| Failed start | Created is separate from running; guard resets after failure and Retry Start is actionable. Browser saw one injected 503, then one successful retry on the same ID, ending completed. |

Final local verification: **116 passed, 2 Windows-specific skips**, compatible
locked Python dependencies, OpenCV **5.0.0**, frontend lint/build, and all eight
MCP tools through actual stdio. [Raw local log](../output/final-check-2026-10-27/local-checks.log).
All six HTTP demo behavior checks pass through the normal app, the local
public gateway and its actual public HTTPS URL, with reports, events, planning references, PNGs and
hash manifests preserved under `output/final-check-2026-10-27/`.

The accepted glare correction preserves every tested per-case non-timing
benchmark output: fixed/adaptive macro precision **0.5208 / 0.8627**, recall
**0.8933 / 0.7822**, F1 **0.5751 / 0.7155**, TP/FP/FN **44/50/6 / 42/10/8**.
Review rate **27.27%**. This is a 30-case synthetic localization/verdict
benchmark at IoU 0.15, not manufacturing accuracy. Prior external domain-gap,
wrong-board and small-defect limits remain. [Benchmark JSON](../output/final-check-2026-10-27/benchmark.json).

## AWS and public demonstration

The AWS execution receipt is valid for commit `6281c2b`, in Stockholm,
OpenCV 5.0.0, actual HTTP smoke, all six scenarios and 72 checked hashes.
The final fixes postdate that receipt; no new AWS run is claimed here. Final
Docker CI is recorded against the pushed commit through GitHub Actions.

Public demo: https://decided-attributes-southwest-africa.trycloudflare.com. It runs real OpenCV inspections
on a separate synthetic-only store on the team Mac. Personal uploads are
blocked; requests, run count, tool budgets and concurrency are bounded. Shared
runs may reset. It depends on the Mac/server/tunnel staying online and has no
uptime guarantee. It is distinct from the earlier private AWS deployment.
Cloudflare Quick Tunnels do not support SSE; persisted event loading and
event/state polling recover the actual trace. A direct reload of a completed
public run recovered all 23 events. See [operating instructions](PUBLIC_DEMO.md). [Cloudflare limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

No new AWS resource or paid service was launched. Cash budget remains **₹0**.
The earlier USD 1 Free Plan credit approval and cleanup obligations remain as
recorded in [AWS execution](AWS_EXECUTION_2026-10-27.md).

## Delivery

- Public source: https://github.com/sgoel2be24-cyber/circuitsleuth .
- Final team-selected video: https://youtu.be/ucM4NiEHInE (unlisted; anonymous oEmbed passed).
- Video is 2m03s locally / 2m04s in YouTube's player. Recording-guide text and
  camera placeholders remain; the team explicitly selected it as the final
  recording after this presentation limitation was disclosed.
- Both Devpost profiles appear on the project team, including ISHPREET0101.
- Portal source limit is **35 MB**. Use `tools/package_submission.py --portal`;
  the ZIP retains runnable demo fixtures, source, tests, annotations and research
  results/provenance. Bulky research capture images and the separate video stay
  in the full public repository. The source manifest identifies the exact commit.
- High-confidence secret scan found no matches in the candidate text files;
  this is a scoped pattern check, not a guarantee of absence.

Competition entry is **not submitted** until Devpost returns a submitted status
and timestamp. The official API's cutoff is **27 October 2026, 12:15 IST**.
Final eligibility, rights and rules agreement must come from the team. No COOL
award is claimed; intended special consideration is Agentic Vision.
