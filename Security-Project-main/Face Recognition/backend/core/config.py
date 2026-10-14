from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Face Auth System"
    DATABASE_URL: str = "sqlite:///./face_auth.db"

    # Face recognition
    FACE_MODEL: str = "ArcFace"          # 512-d embedding
    DETECTOR_BACKEND: str = "opencv"     # fast & dependency-light
    SIMILARITY_THRESHOLD: float = 0.68   # cosine similarity required to match


settings = Settings()
