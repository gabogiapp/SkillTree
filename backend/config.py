import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    # Project & Data Paths
    BASE_DIR: Path = BASE_DIR
    CSV_FILENAME: str = os.getenv("CSV_FILENAME", "skills_parent_child_10000.csv")
    CSV_PATH: Path = BASE_DIR / CSV_FILENAME if (BASE_DIR / CSV_FILENAME).exists() else BASE_DIR / "skills_parent_child_10000.csv"
    
    # Multi-dataset support: includes both datasets into unified graph
    DATASET_FILES: list[str] = ["skills_parent_child_10000.csv", "pure_skill_to_skill_edges.csv"]
    CSV_PATHS: list[Path] = [BASE_DIR / f for f in DATASET_FILES if (BASE_DIR / f).exists()]


    
    # LLM Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "250"))
    
    # Graph Engine Settings
    FUZZY_MATCH_THRESHOLD: float = float(os.getenv("FUZZY_MATCH_THRESHOLD", "82.0"))
    DEFAULT_EXPANSION_COUNT: int = int(os.getenv("DEFAULT_EXPANSION_COUNT", "3"))
    MAX_PATH_HOPS: int = int(os.getenv("MAX_PATH_HOPS", "10"))
    
    # App Settings
    APP_NAME: str = "The Skill Tree - Infinite Craft Engine"
    API_V1_PREFIX: str = "/api"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

settings = Settings()
