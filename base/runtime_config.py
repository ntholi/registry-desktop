import json
import os
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CountryConfig:
    code: str
    label: str
    cms_base_url: str
    database_name: str


@dataclass(frozen=True, slots=True)
class AppSettings:
    country_code: str | None
    database_host: str
    database_port: int
    database_user: str
    database_password: str


def _clean_base_url(value: str) -> str:
    return value.rstrip("/")


COUNTRY_CONFIGS: dict[str, CountryConfig] = {
    "lesotho": CountryConfig(
        code="lesotho",
        label="Lesotho",
        cms_base_url=_clean_base_url(
            "https://cmslesotho.limkokwing.net/campus/registry"
        ),
        database_name="cms_lesotho",
    ),
    "eswatini": CountryConfig(
        code="eswatini",
        label="Eswatini",
        cms_base_url=_clean_base_url(
            "https://cmseswatini.limkokwing.net/campus/registry"
        ),
        database_name="cms_eswatini",
    ),
    "botswana": CountryConfig(
        code="botswana",
        label="Botswana",
        cms_base_url=_clean_base_url(
            "https://cmsbotswana.limkokwing.net/campus/registry"
        ),
        database_name="cms_botswana",
    ),
}

DEFAULT_DATABASE_HOST = "localhost"
DEFAULT_DATABASE_PORT = 5432


def _get_settings_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "Limkokwing Registry Desktop"
    return Path.home() / ".registry-desktop"


def get_settings_file_path() -> Path:
    return _get_settings_dir() / "settings.json"


def _normalize_country_code(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if normalized in COUNTRY_CONFIGS:
        return normalized
    return None


def _normalize_database_host(value: str | None) -> str:
    normalized = (value or "").strip()
    if normalized:
        return normalized
    return DEFAULT_DATABASE_HOST


def _normalize_database_port(value: int | str | None) -> int:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_DATABASE_PORT

    if 1 <= port <= 65535:
        return port

    return DEFAULT_DATABASE_PORT


def _load_settings() -> AppSettings:
    settings_path = get_settings_file_path()
    if not settings_path.exists():
        return AppSettings(
            country_code=None,
            database_host=DEFAULT_DATABASE_HOST,
            database_port=DEFAULT_DATABASE_PORT,
            database_user="",
            database_password="",
        )

    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings(
            country_code=None,
            database_host=DEFAULT_DATABASE_HOST,
            database_port=DEFAULT_DATABASE_PORT,
            database_user="",
            database_password="",
        )

    return AppSettings(
        country_code=_normalize_country_code(raw.get("country_code")),
        database_host=_normalize_database_host(raw.get("database_host")),
        database_port=_normalize_database_port(raw.get("database_port")),
        database_user=(raw.get("database_user") or "").strip(),
        database_password=str(raw.get("database_password") or ""),
    )


def _write_settings(settings: AppSettings) -> None:
    settings_path = get_settings_file_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = settings_path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(
            {
                "country_code": settings.country_code,
                "database_host": settings.database_host,
                "database_port": settings.database_port,
                "database_user": settings.database_user,
                "database_password": settings.database_password,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    temp_path.replace(settings_path)


_settings = _load_settings()
_current_country_code = _settings.country_code


def get_app_settings() -> AppSettings:
    return _settings


def has_complete_runtime_configuration() -> bool:
    return bool(
        _settings.country_code
        and _settings.database_host
        and _settings.database_user
        and _settings.database_port
    )


def forget_saved_runtime_settings() -> bool:
    settings_path = get_settings_file_path()
    if not settings_path.exists():
        return False

    settings_path.unlink()
    return True


def save_runtime_settings(
    country_code: str | None,
    database_host: str,
    database_port: int | str,
    database_user: str,
    database_password: str,
) -> AppSettings:
    global _settings, _current_country_code

    settings = AppSettings(
        country_code=_normalize_country_code(country_code),
        database_host=_normalize_database_host(database_host),
        database_port=_normalize_database_port(database_port),
        database_user=database_user.strip(),
        database_password=database_password,
    )
    _settings = settings
    _current_country_code = settings.country_code

    if settings.country_code:
        os.environ["REGISTRY_COUNTRY"] = settings.country_code
    else:
        os.environ.pop("REGISTRY_COUNTRY", None)

    _write_settings(settings)
    return settings


def get_available_countries() -> list[CountryConfig]:
    return list(COUNTRY_CONFIGS.values())


def get_country_config(country_code: str) -> CountryConfig:
    normalized = _normalize_country_code(country_code)
    if not normalized:
        raise ValueError(f"Unsupported country code: {country_code}")
    return COUNTRY_CONFIGS[normalized]


def set_current_country(
    country_code: str | None, persist: bool = False
) -> CountryConfig | None:
    global _settings, _current_country_code

    normalized = _normalize_country_code(country_code)
    _current_country_code = normalized
    _settings = replace(_settings, country_code=normalized)

    if normalized:
        os.environ["REGISTRY_COUNTRY"] = normalized
    else:
        os.environ.pop("REGISTRY_COUNTRY", None)

    if persist:
        _write_settings(_settings)

    if not normalized:
        return None

    return COUNTRY_CONFIGS[normalized]


def get_current_country_code() -> str:
    return _current_country_code or ""


def get_current_country_config() -> CountryConfig:
    if not _current_country_code:
        raise ValueError("No country has been selected")
    return COUNTRY_CONFIGS[_current_country_code]


def get_current_country_label() -> str:
    if not _current_country_code:
        return "Not Selected"
    return get_current_country_config().label


def get_current_cms_base_url() -> str:
    return get_current_country_config().cms_base_url


def get_current_database_name() -> str:
    return get_current_country_config().database_name


def get_current_session_file() -> str:
    return f"session_{_current_country_code or 'default'}.pkl"
