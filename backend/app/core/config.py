from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_port: int = 8000
    db_path: str = "data/weibo.db"
    monitor_interval: int = 15
    comment_limit: int = 500
    ws_port: int = 8000

    model_config = {"env_file": ".env", "env_prefix": "WEIBO_"}


settings = Settings()
