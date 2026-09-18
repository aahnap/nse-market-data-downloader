"""
Loads config/datasets.yaml into simple Python objects.

Keeping this as its own module means the rest of the application never
touches YAML or file paths directly -- it just asks for "the config".
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

import yaml

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "datasets.yaml",
)


@dataclass
class CommonConfig:
    base_url: str
    user_agent: str
    request_timeout_seconds: int
    max_retries: int
    backoff_base_seconds: int
    warmup_pause_seconds: int


@dataclass
class DatasetConfig:
    key: str
    display_name: str
    page_url: str
    api_urls: Dict[str, str]
    file_prefix: str
    required_columns: List[str] = field(default_factory=list)


@dataclass
class AppConfig:
    common: CommonConfig
    datasets: Dict[str, DatasetConfig]


def load_config(path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Read the YAML file and return a typed AppConfig object."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    common_raw = raw["common"]
    common = CommonConfig(
        base_url=common_raw["base_url"],
        user_agent=common_raw["user_agent"],
        request_timeout_seconds=common_raw["request_timeout_seconds"],
        max_retries=common_raw["max_retries"],
        backoff_base_seconds=common_raw["backoff_base_seconds"],
        warmup_pause_seconds=common_raw["warmup_pause_seconds"],
    )

    datasets: Dict[str, DatasetConfig] = {}
    for key, d in raw["datasets"].items():
        datasets[key] = DatasetConfig(
            key=key,
            display_name=d["display_name"],
            page_url=d["page_url"],
            api_urls=d["api_urls"],
            file_prefix=d["file_prefix"],
            required_columns=d.get("required_columns", []),
        )

    return AppConfig(common=common, datasets=datasets)
