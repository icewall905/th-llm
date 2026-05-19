from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_base_url: str = "http://10.0.10.23:8080/v1"
    llm_model: str = ""
    llm_api_key: str = "none"
    small_blind: int = 10
    big_blind: int = 20
    starting_stack: int = 1000

    class Config:
        env_file = ".env"


settings = Settings()
