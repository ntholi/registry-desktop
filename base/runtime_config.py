import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class CountryConfig:
    code: str
    label: str
    cms_base_url: str
    database_name: str


def _clean_base_url(value: str) -> str:
    return value.rstrip("/")


COUNTRY_CONFIGS: dict[str, CountryConfig] = {
    "lesotho": CountryConfig(
        code="lesotho",
        label="Lesotho",
        cms_base_url=_clean_base_url(
            os.getenv(
                "CMS_LESOTHO_URL",
                "https://cmslesotho.limkokwing.net/campus/registry",
            )
        ),
        database_name=os.getenv("DATABASE_LESOTHO_NAME", "cms_lesotho"),
    ),
    "eswatini": CountryConfig(
        code="eswatini",
        label="Eswatini",
        cms_base_url=_clean_base_url(
            os.getenv(
                "CMS_ESWATINI_URL",
                "https://cmseswatini.limkokwing.net/campus/registry",
            )
        ),
        database_name=os.getenv("DATABASE_ESWATINI_NAME", "cms_eswatini"),
    ),
}


def _normalize_country_code(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in COUNTRY_CONFIGS:
        return normalized
    return "lesotho"


def _infer_country_code() -> str:
    configured = (os.getenv("REGISTRY_COUNTRY") or "").strip().lower()
    if configured in COUNTRY_CONFIGS:
        return configured

    candidates = (
        os.getenv("DATABASE_LOCAL_URL"),
        os.getenv("DATABASE_REMOTE_URL"),
        os.getenv("DATABASE_PORTAL_URL"),
    )

    for candidate in candidates:
        text = (candidate or "").strip().lower()
        if not text:
            continue
        if "cms_eswatini" in text or "eswatini" in text:
            return "eswatini"
        if "cms_lesotho" in text or "lesotho" in text:
            return "lesotho"

    return "lesotho"


_current_country_code = _infer_country_code()


def get_available_countries() -> list[CountryConfig]:
    return [COUNTRY_CONFIGS["lesotho"], COUNTRY_CONFIGS["eswatini"]]


def get_country_config(country_code: str) -> CountryConfig:
    return COUNTRY_CONFIGS[_normalize_country_code(country_code)]


def set_current_country(country_code: str) -> CountryConfig:
    global _current_country_code
    _current_country_code = _normalize_country_code(country_code)
    os.environ["REGISTRY_COUNTRY"] = _current_country_code
    return COUNTRY_CONFIGS[_current_country_code]


def get_current_country_code() -> str:
    return _current_country_code


def get_current_country_config() -> CountryConfig:
    return COUNTRY_CONFIGS[_current_country_code]


def get_current_country_label() -> str:
    return get_current_country_config().label


def get_current_cms_base_url() -> str:
    return get_current_country_config().cms_base_url


def get_current_database_name() -> str:
    return get_current_country_config().database_name


def get_current_session_file() -> str:
    return f"session_{_current_country_code}.pkl"
