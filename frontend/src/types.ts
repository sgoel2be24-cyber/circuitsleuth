export type Verdict =
  | 'SUSPECTED'
  | 'CONFIRMED_DEFECT'
  | 'LIKELY_DEFECT'
  | 'CLEARED'
  | 'NEEDS_REVIEW'
  | 'NOT_EVALUABLE'

export interface RegistrationMetrics {
  detector: string
  inliers?: number
  inlier_ratio?: number
  mean_residual_px?: number
  coverage_score?: number
  quality: 'good' | 'marginal' | 'poor' | 'failed'
  failure_reason?: string | null
  attempts?: string[]
  photometric_score?: number
  ecc_refine_correlation?: number
  [k: string]: unknown
}

export interface Evidence {
  evidence_kind: string
  source_tool: string
  summary: string
  metrics: Record<string, unknown>
  supports_defect: boolean | null
  artifact: string | null
  timestamp: number
  duration_s?: number
  honesty?: string
}

export interface Candidate {
  region_id: string
  bbox: [number, number, number, number]
  area_px: number
  centroid: [number, number]
  difference_score: number
  structural_mismatch_score: number
  evidence_quality_score: number
  status: Verdict
  label: string | null
  label_basis: string | null
  evidence: Evidence[]
  tools_used: string[]
  notes: string[]
  illumination_suspect?: boolean
  touches_invalid_warp_region?: boolean
}

export interface InspectionEvent {
  seq: number
  ts: number
  phase: string
  type: string
  message: string
  evidence: Record<string, unknown>
  region_id: string | null
  artifacts: string[]
}

export interface ReviewRequest {
  region_id: string
  reason: string
  requested_action: string
  created_at: string
  bbox?: [number, number, number, number]
  resolved?: string
}

export interface Summary {
  id: string
  created_at: string
  status: string
  source: string
  scenario_id: string | null
  confirmed: number
  likely?: number
  cleared: number
  needs_review: number
  not_evaluable: number
  candidate_count: number
  tool_calls_used: number
  duration_s: number | null
  stop_reason?: string | null
}

export interface Inspection {
  summary: Summary | null
  status: string
  config: { max_tool_calls: number; max_iterations: number }
  registration: RegistrationMetrics | null
  detection: { params?: Record<string, unknown>; candidate_count?: number; artifacts?: Record<string, string> } | null
  candidates: Record<string, Candidate>
  review_requests: ReviewRequest[]
  report: Report | null
  stop_reason: string | null
  tool_calls_used: number
  iterations: number
  images: Record<string, string>
}

export interface ReportVerdict {
  region_id: string
  bbox: { x: number; y: number; w: number; h: number }
  status: Verdict
  label: string | null
  label_basis: string | null
  difference_score: number
  structural_mismatch_score: number
  evidence: Evidence[]
  tools_used: string[]
  notes: string[]
}

export interface Report {
  inspection_id: string
  generated_at: string
  registration: RegistrationMetrics | null
  verdicts: ReportVerdict[]
  review_requests: ReviewRequest[]
  tool_calls_used: number
  iterations: number
  stop_reason: string
  limitations: string[]
}

export interface Scenario {
  id: string
  title: string
  description: string
  expected: string[]
  has_secondary_view: boolean
  synthetic: boolean
}
