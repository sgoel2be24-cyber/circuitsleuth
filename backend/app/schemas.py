"""Pydantic schemas shared by the API, the agent orchestrator and the MCP tools.

Naming rule used across the whole system: numeric values that are heuristic
quality measures are named `*_score` and are documented as heuristics; they are
never presented as calibrated probabilities.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Verdict = Literal[
    "CONFIRMED_DEFECT",
    "LIKELY_DEFECT",
    "CLEARED",
    "NEEDS_REVIEW",
    "NOT_EVALUABLE",
    "SUSPECTED",  # transient state before verification
]

RegistrationQuality = Literal["good", "marginal", "poor", "failed"]

EvidenceKind = Literal[
    "difference_severity",
    "structural_mismatch",
    "edge_topology",
    "independent_view",
    "local_realignment",
    "illumination_confound",
]

ToolName = Literal[
    "align_images",
    "detect_defects",
    "inspect_region",
    "request_additional_view",
    "verify_candidate",
    "request_human_review",
    "generate_inspection_report",
    "get_inspection_context",
]


class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h


class RegistrationMetrics(BaseModel):
    detector: str = "unknown"
    keypoints_reference: int = 0
    keypoints_test: int = 0
    good_matches: int = 0
    inliers: int = 0
    inlier_ratio: float = 0.0
    mean_residual_px: float = 0.0
    coverage_score: float = Field(default=0.0, description="0..1 spread of inlier matches across the frame")
    warp_matrix: list[list[float]] = Field(default_factory=list)
    attempts: list[str] = Field(default_factory=list, description="strategies tried, in order")
    quality: RegistrationQuality = "failed"
    failure_reason: str | None = None

    model_config = {"extra": "ignore"}


class CandidateEvidence(BaseModel):
    evidence_kind: EvidenceKind
    source_tool: str
    summary: str
    metrics: dict[str, float | int | str | bool | None]
    supports_defect: bool | None = None
    artifact: str | None = None
    timestamp: float
    duration_s: float | None = None
    honesty: str | None = None


class Candidate(BaseModel):
    region_id: str
    bbox: BBox
    area_px: int
    centroid: tuple[int, int]
    difference_score: float = Field(description="heuristic: normalized mean abs-difference, 0..1+")
    structural_mismatch_score: float = Field(description="heuristic: 1 - local NCC, 0..1")
    evidence_quality_score: float = Field(description="heuristic: local contrast/registration confidence, 0..1")
    status: Verdict = "SUSPECTED"
    label: str | None = Field(default=None, description="defect class or 'unclassified_surface_anomaly'")
    label_basis: str | None = None
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    priority_score: float = 0.0
    notes: list[str] = Field(default_factory=list)


class InspectionConfig(BaseModel):
    max_tool_calls: int = Field(default=12, ge=3, le=40)
    max_iterations: int = Field(default=24, ge=5, le=100)
    require_independent_view_for_confirm: bool = False


class DemoScenario(BaseModel):
    id: str
    title: str
    description: str
    expected_behaviors: list[str]
    has_secondary_view: bool
    synthetic: bool = True
    files: dict[str, str] = Field(default_factory=dict)


class InspectionSummary(BaseModel):
    id: str
    created_at: str
    status: str
    source: str
    scenario_id: str | None = None
    config: InspectionConfig
    candidate_count: int = 0
    confirmed: int = 0
    cleared: int = 0
    needs_review: int = 0
    not_evaluable: int = 0
    tool_calls_used: int = 0
    duration_s: float | None = None


class InspectionEvent(BaseModel):
    seq: int
    ts: float
    phase: str
    type: str
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    region_id: str | None = None
    artifacts: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    region_id: str
    reason: str
    requested_action: str
    created_at: str
    bbox: list[int] | None = None
    resolved: Literal["confirmed", "rejected"] | None = None


class OperatorReview(BaseModel):
    region_id: str = Field(min_length=1, max_length=100)
    decision: Literal["confirmed", "rejected"]
    note: str = Field(default="", max_length=2000)


class ReportVerdict(BaseModel):
    region_id: str
    bbox: BBox
    status: Verdict
    label: str | None
    label_basis: str | None
    difference_score: float
    structural_mismatch_score: float
    evidence: list[CandidateEvidence]
    tools_used: list[str]
    notes: list[str]


class InspectionReport(BaseModel):
    inspection_id: str
    generated_at: str
    registration: RegistrationMetrics | None
    verdicts: list[ReportVerdict]
    review_requests: list[ReviewRequest]
    tool_calls_used: int
    iterations: int
    stop_reason: str
    limitations: list[str] = Field(default_factory=list)
