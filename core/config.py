#BaseSettings is a class - read env variables ,
#convert values in declared python types,
#validate config values,load values from .env
from pydantic_settings import BaseSettings
#Settings is a class that defines how configuration should be loaded.
class Settings(BaseSettings):
    DB_USER	: str
    DB_PASSWORD	: str
    DB_HOST	: str
    DB_PORT	: int
    DB_NAME	: str
    SECRET_KEY : str
    ALGORITHM : str
    ACCESS_TOKEN_EXPIRE_MINUTES : int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    SESSION_EXPIRE_DAYS: int
    model_config={
        "env_file":".env"
    }
settings=Settings()#creates an object and loads the actual configuration values.
