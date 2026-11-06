from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Tell Pydantic where and how to look for config data
    model_config = SettingsConfigDict(
        env_file = ".env", # Look in .env
        env_file_encoding = "utf-8", # Standard encoding format for non-ASCII characters
        extra="ignore", # Ignore the extra line in .env 
    )

    secret_key: SecretStr # Cryptographic key used to sign and verify login tokens
    algorithm: str = "HS256" # Encryption algorithm for the digital signature
    access_token_expire_minutes: int = 20160 # How long a token last in minutes (2 weeks)

# Load variables from .env
settings = Settings() 