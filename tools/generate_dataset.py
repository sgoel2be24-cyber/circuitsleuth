"""Synthetic PCB dataset generator for CircuitSleuth.

Renders reproducible, clearly-labeled *synthetic* single-layer PCB pairs:
  reference.png  defect-free board
  test.png       same board, re-rendered with independent illumination/noise
                 and zero or more injected defects
  view2.png      optional second capture (different illumination realization)
  annotations.json  ground-truth defect bounding boxes (test-image coords)
  meta.json         provenance + scenario description

Everything is generated at 2x supersampling and downscaled for anti-aliasing.
Seeds are recorded in meta.json so every image is byte-reproducible.

This data is synthetic: it exists for controlled demos, unit tests and
benchmarks. It makes no claim about real-world accuracy.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

SS = 2  # supersample factor

MASK_COLOR = np.array([38.0, 66.0, 46.0])     # dark green solder mask (BGR)
COPPER_COLOR = np.array([105.0, 150.0, 196.0])  # light copper traces (BGR)
PAD_COLOR = np.array([125.0, 168.0, 214.0])
SILK_COLOR = np.array([225.0, 235.0, 240.0])
HOLE_COLOR = np.array([18.0, 22.0, 20.0])


@dataclass
class Defect:
    kind: str
    bbox_ss: tuple[int, int, int, int]  # in supersampled coords

    def to_json(self) -> dict:
        x, y, w, h = self.bbox_ss  # already converted to final coords by render()
        return {"type": self.kind, "bbox": [int(x), int(y), int(w), int(h)], "synthetic": True}


@dataclass
class Board:
    """Procedural single-layer board: traces + pads + silk."""

    seed: int
    w: int = 900
    h: int = 600
    traces: list = field(default_factory=list)   # (points_ss, width)
    pads: list = field(default_factory=list)     # (x_ss, y_ss, r, hole_r)
    rng: np.random.Generator = field(init=False)

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)
        self._layout()

    def _layout(self) -> None:
        rng = self.rng
        rows = np.linspace(90, self.h - 90, 8).astype(int)
        used: set[int] = set()

        def pick_row(near: int | None = None) -> int:
            avail = [r for r in rows if r not in used]
            if not avail:
                return int(rng.choice(rows))
            r = int(min(avail, key=lambda v: abs(v - near) if near is not None else rng.random()))
            used.add(r)
            return r

        # horizontal-ish signal nets
        for i in range(9):
            y = pick_row()
            xs = sorted(rng.choice(np.arange(140, self.w - 140, 40), size=2, replace=False).tolist())
            pts = [(40, y), (int(xs[0]), y)]
            if i % 3 == 1:
                y2 = y + int(rng.choice([-44, 44]))
                pts += [(int(xs[0]), y2), (int(xs[1]), y2), (self.w - 40, y2)]
                used.add(y2)
            else:
                pts += [(self.w - 40, y)]
            self._add_net(pts)
        # vertical power nets
        for i in range(4):
            x = 120 + i * 210 + int(rng.integers(-25, 25))
            y0 = pick_row()
            y1 = pick_row()
            if y1 < y0:
                y0, y1 = y1, y0
            self._add_net([(x, max(60, y0 - 50)), (x, y0), (x, y1), (x, min(self.h - 60, y1 + 50))])
        # ground ring
        self._add_net([(30, 30), (self.w - 30, 30), (self.w - 30, self.h - 30), (30, self.h - 30), (30, 30)], width=8)

    def _add_net(self, pts: list[tuple[int, int]], width: int = 7) -> None:
        pts_ss = [(int(x * SS), int(y * SS)) for x, y in pts]
        self.traces.append((pts_ss, width * SS))
        for end in (pts_ss[0], pts_ss[-1]):
            self.pads.append((end[0], end[1], 11 * SS, 5 * SS))

    # ---------- rendering ----------

    def render(
        self,
        *,
        defects: list[dict] | None = None,
        illum_seed: int = 0,
        noise_seed: int = 0,
        glare: tuple[int, int, float] | None = None,
        noise_sigma: float = 3.5,
        illum_strength: float = 0.16,
    ) -> tuple[np.ndarray, list[Defect]]:
        rng_illum = np.random.default_rng(illum_seed)
        rng_noise = np.random.default_rng(noise_seed)
        canvas = np.tile(MASK_COLOR, (self.h * SS, self.w * SS, 1)).astype(np.float32)

        # subtle mask texture
        tex = rng_noise.normal(0, 2.5, (self.h * SS, self.w * SS, 1)).astype(np.float32)
        canvas += tex

        # silk (under everything visual but above mask)
        silk = np.zeros((self.h * SS, self.w * SS), np.uint8)
        cv2.rectangle(silk, (10 * SS, 10 * SS), ((self.w - 10) * SS, (self.h - 10) * SS), 255, 2 * SS)
        cv2.circle(silk, (50 * SS, (self.h - 50) * SS), 8 * SS, 255, 2 * SS)
        cv2.circle(silk, ((self.w - 50) * SS, 50 * SS), 8 * SS, 255, 2 * SS)
        cv2.putText(silk, "CS-2606 REV-B", (60 * SS, 46 * SS), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0 * SS, 255, max(1, SS // 2), cv2.LINE_AA)
        canvas[silk > 0] = SILK_COLOR

        # copper layer
        for pts_ss, width in self.traces:
            for i in range(len(pts_ss) - 1):
                cv2.line(canvas, pts_ss[i], pts_ss[i + 1], COPPER_COLOR, int(width), cv2.LINE_AA)
            for p in pts_ss:
                cv2.circle(canvas, p, int(width // 2), COPPER_COLOR, -1, cv2.LINE_AA)
        for (px, py, r, hr) in self.pads:
            cv2.circle(canvas, (px, py), r, PAD_COLOR, -1, cv2.LINE_AA)
            cv2.circle(canvas, (px, py), hr, HOLE_COLOR, -1, cv2.LINE_AA)

        # defect injection happens post-copper, pre-illumination
        rendered: list[Defect] = []
        for d in defects or []:
            bbox = self._draw_defect(canvas, d)
            rendered.append(Defect(d["kind"], bbox))

        # illumination: smooth low-frequency field + vignette
        gh, gw = 6, 9
        field_small = rng_illum.normal(1.0, illum_strength, (gh, gw)).astype(np.float32)
        field = cv2.resize(field_small, (self.w * SS, self.h * SS), interpolation=cv2.INTER_CUBIC)
        field = field[..., None]
        yy, xx = np.mgrid[0:self.h * SS, 0:self.w * SS].astype(np.float32)
        cx, cy = (self.w * SS) / 2, (self.h * SS) / 2
        vign = 1.0 - illum_strength * 0.8 * (((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
        canvas *= (field * vign[..., None]).astype(np.float32)

        # glare blob (specular highlight)
        if glare is not None:
            gx, gy, peak = glare
            blob = np.zeros((self.h * SS, self.w * SS), np.float32)
            cv2.circle(blob, (gx * SS, gy * SS), 70 * SS, float(peak), -1)
            blob = cv2.GaussianBlur(blob, (0, 0), 22 * SS)
            canvas += blob[..., None]

        canvas += rng_noise.normal(0, noise_sigma, canvas.shape).astype(np.float32)
        canvas = np.clip(canvas, 0, 255).astype(np.uint8)
        out = cv2.resize(canvas, (self.w, self.h), interpolation=cv2.INTER_AREA)
        for r in rendered:
            r.bbox_ss = (r.bbox_ss[0] // SS, r.bbox_ss[1] // SS, r.bbox_ss[2] // SS, r.bbox_ss[3] // SS)
        return out, rendered

    def _bg_patch(self, canvas: np.ndarray, cx: int, cy: int, rx: int, ry: int, angle: float = 0) -> None:
        """Erase copper by repainting solder-mask color inside an ellipse."""
        cv2.ellipse(canvas, (cx, cy), (rx, ry), angle, 0, 360, MASK_COLOR, -1, cv2.LINE_AA)

    def _draw_defect(self, canvas: np.ndarray, d: dict) -> tuple[int, int, int, int]:
        kind = d["kind"]
        rng = np.random.default_rng(d.get("seed", 7))
        if kind in ("open_circuit", "mousebite", "pinhole", "spur"):
            pts_ss, width = self.traces[int(rng.integers(0, len(self.traces)))]
            seg = int(rng.integers(0, max(1, len(pts_ss) - 1)))
            (x0, y0), (x1, y1) = pts_ss[seg], pts_ss[seg + 1]
            t = float(rng.uniform(0.3, 0.7))
            mx, my = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
            if kind == "open_circuit":
                gap = int(rng.integers(26, 40))
                ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
                self._bg_patch(canvas, mx, my, gap // 2 + 4, width // 2 + 5, ang)
                return (mx - gap // 2 - 6, my - width // 2 - 7, gap + 12, width + 14)
            if kind == "mousebite":
                r = int(rng.integers(11, 16))
                self._bg_patch(canvas, mx, my + width // 3, r, r)
                return (mx - r, my - width // 2 - 4, 2 * r, width + r + 8)
            if kind == "pinhole":
                r = int(rng.integers(6, 9))
                self._bg_patch(canvas, mx, my, r, r)
                return (mx - r - 3, my - r - 3, 2 * r + 6, 2 * r + 6)
            if kind == "spur":
                length, lw = int(rng.integers(26, 40)), 5 * SS
                nx, ny = -(y1 - y0), (x1 - x0)
                n = math.hypot(nx, ny) or 1.0
                ex, ey = int(mx + nx / n * length), int(my + ny / n * length)
                cv2.line(canvas, (mx, my), (ex, ey), COPPER_COLOR, lw, cv2.LINE_AA)
                bx = min(mx, ex) - 8
                by = min(my, ey) - 8
                return (bx, by, abs(ex - mx) + 16, abs(ey - my) + 16)
        if kind in ("short_circuit", "spurious_copper"):
            # choose two nearby horizontal trace points to bridge
            horiz = [(pts, w) for pts, w in self.traces if len(pts) >= 2 and pts[0][1] == pts[1][1] and 60 < pts[0][1] < self.h - 60]
            if len(horiz) < 2:
                horiz = self.traces[:2]
            (pa, wa), (pb, wb) = horiz[0], horiz[1]
            ya, yb = pa[0][1], pb[0][1]
            if abs(ya - yb) < 40:
                yb = ya + 46
            x = int(rng.integers(120, self.w - 120)) * SS
            ya_s, yb_s = int(ya), int(yb)
            if kind == "short_circuit":
                cv2.line(canvas, (x, ya_s), (x, yb_s), COPPER_COLOR, 5 * SS, cv2.LINE_AA)
                return (x - 6 * SS, min(ya_s, yb_s) - 4 * SS, 12 * SS, abs(yb_s - ya_s) + 8 * SS)
            # spurious copper blob floating between traces
            cy = (ya_s + yb_s) // 2
            rx, ry = int(rng.integers(16, 26)), int(rng.integers(11, 17))
            cv2.ellipse(canvas, (x, cy), (rx, ry), float(rng.uniform(0, 60)), 0, 360,
                        COPPER_COLOR * 0.92, -1, cv2.LINE_AA)
            return (x - rx - 4 * SS, cy - ry - 4 * SS, 2 * rx + 8 * SS, 2 * ry + 8 * SS)
        raise ValueError(f"unknown defect kind: {kind}")


# ---------------------------------------------------------------------------
# Scenario definitions


def build_scenario(scenario_id: str, variant_seed: int = 0) -> dict:
    """Return files+meta for one demo scenario (deterministic).

    `variant_seed` shifts every seed so the benchmark can generate many
    statistically independent instances of each scenario template.
    """
    vs = variant_seed

    def S(base: int) -> int:
        return base + vs * 7 + 1

    base: dict = {}

    if scenario_id == "scenario_01_clear_defects":
        board = Board(seed=S(101))
        defects = [
            {"kind": "open_circuit", "seed": S(11)},
            {"kind": "short_circuit", "seed": S(12)},
            {"kind": "spur", "seed": S(13)},
        ]
        ref, _ = board.render(illum_seed=S(1), noise_seed=S(1))
        test, rendered = board.render(defects=defects, illum_seed=S(2), noise_seed=S(2))
        view2, _ = board.render(defects=defects, illum_seed=S(3), noise_seed=S(3))
        meta = {
            "title": "Clearly defective board",
            "description": "Three gross defects (open circuit, short circuit, spur) under good imaging conditions with a second capture available.",
            "expected": [
                "registration good", "anomalies detected", "agent verifies top regions",
                "defects confirmed with evidence", "report produced",
            ],
        }

    elif scenario_id == "scenario_02_clean_board":
        board = Board(seed=S(202))
        ref, _ = board.render(illum_seed=S(5), noise_seed=S(5))
        test, rendered = board.render(illum_seed=S(6), noise_seed=S(6))
        view2, _ = board.render(illum_seed=S(7), noise_seed=S(7))
        meta = {
            "title": "Clean board",
            "description": "Defect-free board with mild illumination shift between captures. The system must not manufacture defects.",
            "expected": ["registration good", "no defect confirmed", "report reflects clean result"],
        }

    elif scenario_id == "scenario_03_ambiguous_glare":
        board = Board(seed=S(303))
        defects = [{"kind": "pinhole", "seed": S(21)}]
        ref, _ = board.render(illum_seed=S(8), noise_seed=S(8))
        gx = int(200 + (S(0) % 500))
        test, rendered = board.render(defects=defects, illum_seed=S(9), noise_seed=S(9), glare=(gx, 300, 85.0))
        view2, _ = board.render(defects=defects, illum_seed=S(10), noise_seed=S(10))
        meta = {
            "title": "Ambiguous evidence under glare",
            "description": "A small pinhole defect captured under a strong specular glare. Initial evidence is confounded; the agent should test the illumination hypothesis and consult the independent view.",
            "expected": [
                "initial candidate uncertain or confound-flagged",
                "agent runs adaptive-threshold / independent-view analysis",
                "verdict changes or uncertainty explicitly documented",
            ],
        }

    elif scenario_id == "scenario_04_registration_failure":
        board = Board(seed=S(404))
        wrong = Board(seed=S(999) + 3)
        ref, _ = board.render(illum_seed=S(11), noise_seed=S(11))
        test_wrong, rendered = wrong.render(illum_seed=S(12), noise_seed=S(12))
        M = cv2.getRotationMatrix2D((450, 300), 5.0, 1.0)
        test = cv2.warpAffine(test_wrong, M, (900, 600))
        view2 = None
        meta = {
            "title": "Registration failure (mismatched capture)",
            "description": "The operator loaded a test image of a different board revision. Feature registration cannot align it; the system must refuse to report defects and mark the inspection NOT_EVALUABLE after attempting recovery.",
            "expected": ["registration poor/failed", "recovery attempted", "NOT_EVALUABLE — no fabricated defects"],
        }

    elif scenario_id == "scenario_05_no_second_view":
        board = Board(seed=S(505))
        defects = [{"kind": "spur", "seed": S(31)}]
        ref, _ = board.render(illum_seed=S(13), noise_seed=S(13))
        gx = int(200 + (S(2) % 500))
        test, rendered = board.render(defects=defects, illum_seed=S(14), noise_seed=S(14), glare=(gx, 420, 70.0))
        view2 = None
        meta = {
            "title": "Ambiguous region, no second view",
            "description": "A moderate spur under glare with no secondary capture available. The agent must request additional visual evidence, receive 'capture required', and create a human review task instead of guessing.",
            "expected": [
                "agent requests additional view", "additional-capture-required status returned",
                "human review requested",
            ],
        }

    elif scenario_id == "scenario_06_multiple_regions":
        board = Board(seed=S(606))
        defects = [
            {"kind": "open_circuit", "seed": S(41)},
            {"kind": "mousebite", "seed": S(42)},
            {"kind": "spur", "seed": S(43)},
            {"kind": "spurious_copper", "seed": S(44)},
            {"kind": "pinhole", "seed": S(45)},
        ]
        ref, _ = board.render(illum_seed=S(15), noise_seed=S(15))
        test, rendered = board.render(defects=defects, illum_seed=S(16), noise_seed=S(16))
        view2, _ = board.render(defects=defects, illum_seed=S(17), noise_seed=S(17))
        meta = {
            "title": "Multiple suspicious regions (budget-limited)",
            "description": "Five defects of mixed severity. The agent prioritizes by evidence quality and respects its tool-call budget, maintaining independent per-region states.",
            "expected": ["regions prioritized", "budget respected", "independent region states", "explained decisions"],
        }

    else:
        raise ValueError(f"unknown scenario {scenario_id}")

    base = {
        "reference": ref,
        "test": test,
        "view2": view2,
        "annotations": [d.to_json() for d in rendered],
        "meta": {
            "id": scenario_id,
            "synthetic": True,
            **meta,
            "has_secondary_view": view2 is not None,
        },
    }
    return base


SCENARIO_IDS = [
    "scenario_01_clear_defects",
    "scenario_02_clean_board",
    "scenario_03_ambiguous_glare",
    "scenario_04_registration_failure",
    "scenario_05_no_second_view",
    "scenario_06_multiple_regions",
]


def write_scenario(out_dir: Path, scenario_id: str) -> Path:
    data = build_scenario(scenario_id)
    d = out_dir / scenario_id
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "reference.png"), data["reference"])
    cv2.imwrite(str(d / "test.png"), data["test"])
    if data["view2"] is not None:
        cv2.imwrite(str(d / "view2.png"), data["view2"])
    (d / "annotations.json").write_text(json.dumps(data["annotations"], indent=2))
    (d / "meta.json").write_text(json.dumps(data["meta"], indent=2))
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "demo")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    for sid in SCENARIO_IDS:
        d = args.out / sid
        if d.exists() and not args.force:
            print(f"skip {sid} (exists; use --force)")
            continue
        write_scenario(args.out, sid)
        print(f"wrote {d}")


if __name__ == "__main__":
    main()
