"""Environment-based configuration.

Every knob the pipeline exposes can be overridden with an environment variable
prefixed with CIRCUITSLEUTH_ (pydantic-settings). Defaults are chosen so the
system runs out of the box on a laptop without cloud access.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CIRCUITSLEUTH_", env_file=".env", extra="ignore")

    app_name: str = "CircuitSleuth"
    version: str = "1.0.0"

    # --- storage ---
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    demo_dir_name: str = "demo"
    runs_dir_name: str = "runs"

    # --- agent budget (stop conditions) ---
    max_tool_calls: int = 12
    max_iterations: int = 24
    max_candidates_tracked: int = 40

    # --- detection thresholds ---
    min_candidate_area_px: int = 12
    max_candidate_area_frac: float = 0.05  # relative to image area
    diff_percentile_floor: float = 97.0

    # --- registration gates ---
    good_inliers: int = 30
    good_inlier_ratio: float = 0.35
    good_residual_px: float = 2.0
    marginal_inliers: int = 12
    marginal_residual_px: float = 5.0

    # --- uploads ---
    max_upload_bytes: int = 20 * 1024 * 1024
    max_image_dim_px: int = 6000

    # --- CORS (dev frontend) ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def demo_dir(self) -> Path:
        return self.data_dir / self.demo_dir_name

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / self.runs_dir_name


settings = Settings()
