from pydantic_settings import BaseSettings, SettingsConfigDict


class SaferProductsSettings(BaseSettings):
    saferproducts_base_url: str = (
        "https://www.saferproducts.gov/WebApi/Cpsc.Cpsrms.Web.Api.svc"
    )
    saferproducts_api_key: str

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
