# CircuitSleuth master-plan audit

Audit date: 25 October 2026. Scope: the supplied master-build prompt, current source, saved evaluation outputs, deployment files and official competition pages. The attachment ends mid-sentence in section 11; no missing continuation was assumed. This is a source audit, not evidence that cloud deployment or submission occurred. Fresh test/build/browser results belong in the change verification record.

## Competition and submission gate

The official header gives **26 October, 11:45 PM PDT**, while the body says 11:59 PM. Use the earlier time: **27 October 2026, 12:15 PM IST**. Every entry needs substantive OpenCV 5 and meaningful AWS execution. Final materials include a technical report, judge-accessible code/archive, pinned setup instructions, architecture diagram, endpoint or arranged screen-share, evaluation and a judge-accessible video of at most five minutes covering the team, working application, architecture and results. Agentic evidence must show visual outputs changing later actions. [Official requirements](https://opencv26.devpost.com/)

Technical execution accounts for 30% of overall judging; UX is 10%. For Agentic Vision, integration, orchestration, evaluation and failure handling together dominate the rubric. A beautiful local demo alone cannot establish eligibility. [Official rules](https://opencv26.devpost.com/rules)

**Submission blocker: AWS execution remains unverified.** `GET /api/system/info` explicitly returns `aws_execution_verified: false`. No amount of local test coverage or deployment documentation closes this requirement. Obtain explicit authorization before creating paid services; then retain health/version output, a real inspection/report and logs from the AWS workload.

## Requirement-to-evidence matrix

Statuses describe inspected implementation. “Implemented” does not imply production validation.

| Master-plan requirement | Status | Concrete evidence and boundary |
|---|---|---|
| Reference-based PCB surface inspection | Implemented, synthetic validation only | `backend/app/cv/{registration,detection,region_tools,verification}.py`; generated fixtures cover the six named surface defect patterns. Assembly inspection is not claimed. |
| Substantive OpenCV 5 | Implemented; runtime check required | `backend/requirements.txt` pins `opencv-python-headless==5.0.0.93`; health/system endpoints expose `cv2.__version__`; backend tests assert major version 5. Version metadata alone does not enforce a startup refusal under a wrong installed major. |
| Real AWS workload | Unverified, blocking | Docker/compose/App Runner instructions exist under `deploy/`; no AWS execution evidence is present. Local filesystem and SQLite are used; S3 is absent. |
| Image uploads, demos and extra views | Implemented | REST creation accepts reference/test/optional view2. `decode_bgr` checks bytes, decoding and dimensions; configured defaults are 20 MiB/file, maximum side 6000 px, minimum side 64 px. One supplemental full-board view is supported, not an arbitrary camera fleet. |
| Image orientation and safe input handling | Partial | OpenCV decoding standardizes BGR. `normalize_orientation` is documented as a no-op; explicit EXIF fixtures are absent. Confirm behavior with real rotated phone captures before claiming camera normalization. |
| Measured registration, recovery and refusal | Implemented | SIFT/ORB mutual matching, affine RANSAC, photometric validation, ECC and coverage/residual quality gates in `cv/registration.py`; orchestrator retries with enhanced preprocessing, then refuses after failure. It is an affine implementation, not a validated arbitrary-perspective homography pipeline. |
| Difference/structural detection and regions | Implemented | Difference + local NCC + added-material channels, glare exclusion, connected components and clamped crops; candidate bbox, area, severity and quality scores are real outputs. Scores are explicitly heuristic. |
| Coordinates match displayed evidence | Must verify in UI | Detection boxes use the aligned/reference frame. Original test and secondary views may have distinct transforms; overlays must use registered images or transformed geometry. Never stretch an aligned heatmap over an unregistered view. |
| Adaptive secondary inspection | Implemented | Policy selects local realignment, illumination confound test, alternate view/capture request, edge topology, zoom or verification using measured candidate state. Crops are reprocessing; generated view2 is a distinct synthetic render, not a physical recapture. |
| Evidence-backed five-way verdict | Implemented, rule based | `cv/verification.py` produces confirmed/likely/cleared/review/not-evaluable and hedged labels. Preserve disagreements and unavailable evidence. Heuristic classification has no calibrated per-class real-world accuracy. |
| Bounded perception/decision/action loop | Implemented | `agent/policy.py` and `orchestrator.py`; each iteration scores each open region's proposed next action, executes a shared toolbelt method and updates state. It does not search every possible tool/region combination despite broad wording in earlier docs. |
| Stop conditions and human control | Partial at audit | Tool/iteration budgets, terminal regions and registration refusal exist. Operator confirmation/rejection and extra-view reruns exist. Explicit operator cancellation was absent at initial source review. |
| Real MCP tools and client example | Implemented | Eight SDK-decorated stdio tools, `mcp_config.example.json`, `tools/mcp_smoke_test.py`, `test_mcp.py`. Runtime agent calls the same tool implementation in-process; it does not communicate over MCP transport. Describe the two entry points precisely. |
| Persistent state and real telemetry | Implemented, single-instance limits | SQLite index/event log + per-run state/artifacts, SSE feed and startup interrupted-run sweep. Concurrent mutation and recovery need regression coverage. App Runner local disk is ephemeral; it does not provide durable multi-instance history. |
| Dashboard/new/workspace/details/report | Implemented; UI refinement in progress | React pages plus board canvas, agent feed and region details. Records drive counts/latency; report downloads and human decisions use backend outputs. Verify loading/error/reconnect, mobile layout, keyboard viewer controls and report freshness after review. |
| No fabricated clean-board outcome | Must verify in UI | Registration failure can finalize an inspection with zero candidates. Only show a clean result when alignment was usable and the stop reason is `no_candidates`; failure is not evidence of a clean board. |
| Reproducible baseline comparison | Implemented, limited | `evaluation/benchmark.py` runs shared registration/detection with fixed vs adaptive verification over seeded synthetic variants. Saved `results.json`/`.md` exist. Independent action success/usefulness metrics and physical-PCB validation are not established. |
| Pinned reproducible dependencies | Partial at audit | Frontend has a package lock. Backend requirements mostly use version ranges; create and test an exact environment lock before claiming fully pinned reproduction. |
| Container/cloud delivery | Unverified | Single-container Dockerfile and compose exist. Build/run must be tested; verify frontend Node engine compatibility, SPA deep-link handling, persistence and health checks. Deployment commands are instructions, not deployment evidence. |
| Technical documentation and submission | Partial | README + architecture/MCP/demo/evaluation docs and Devpost/video-script drafts exist. No recorded public/unlisted video or observed submitted portal state. Git remote existence does not prove judge access. |
| COOL award | Out of core scope | No verified COOL/Graviton execution. Do not opt into or claim this award without its actual workload and comparison evidence. |

## Evaluation claims to keep precise

Saved results contain 30 inspections (six templates, five variants each), using **IoU ≥ 0.15**, class-agnostic matching and macro averages across inspections. These are not mAP, micro-F1 or calibrated defect-class accuracy. Empty/no-defect examples receive perfect scores when no findings are reported; that affects the mean. Detection and reported-verdict metrics are distinct.

| Saved result | Fixed baseline | Adaptive |
|---|---:|---:|
| Reported macro-F1 | 0.571 | 0.716 |
| Reported precision | 0.516 | 0.863 |
| Reported recall | 0.893 | 0.782 |
| False positives | 52 | 10 |
| False negatives | 6 | 8 |
| Mean latency | 0.80 s | 1.42 s |

The adaptive result reduces false alarms while sacrificing reported recall and adding latency. Missing-view cases deliberately escalate instead of reporting a defect; disclose that tradeoff alongside the F1 improvement. These numbers were read from stored artifacts during this audit, not independently reproduced here. The generated scenes have stable viewpoint/layout; they do not establish robustness across physical cameras, manufacturing processes or perspective changes.

## Dataset research and next validation

[DeepPCB upstream](https://github.com/tangsanli5201/DeepPCB) contains paired reference/test images and six defect labels. Its [MIT license](https://github.com/tangsanli5201/DeepPCB/blob/master/LICENSE) requires retaining its copyright and permission notice with redistributed material. Record the selected upstream revision, image IDs, original annotations and license when importing a subset; cite the authors' supplied paper reference. Upstream says some defects were artificially added, so label this correctly rather than calling the whole dataset naturally occurring defects. Current bundled demos are generated locally; no DeepPCB benchmark is claimed.

Recommended follow-up: use an untouched, attributed subset for a separately named external benchmark; retain its native label mapping and report localization at stated IoU thresholds. Keep synthetic multi-view demonstrations separate from external single-pair results. Do not tune on the reported evaluation subset and then present it as held-out validation.

## Priority before submission

1. Finish local correctness fixes, rebuild UI, run backend/MCP tests and complete desktop/mobile journeys. Recheck coordinate frames, registration-failure labels, report updates, invalid uploads and restart handling.
2. Produce tested dependency locks and verify a container build/run if Docker is available. Document any environment that could not be exercised.
3. With explicit cloud authorization, execute the OpenCV workload on AWS and capture reproducible evidence. Until then the entry is locally demonstrable and **not verified as competition compliant**.
4. Package a coherent technical report from the existing docs, refresh screenshots/results, record the team/application/architecture/results video and confirm judge access to code and demo.
5. Submit through Devpost by the earlier deadline and verify the portal's final status. No submission was performed by this audit.
