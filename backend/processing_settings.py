"""Persistent settings for fiber detection and circle-based measurements."""
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .paths import DATA_HOME


class ProcessingSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')

    smooth: StrictBool = True
    local_background: StrictBool = True
    alignment: StrictBool = False
    continuity: StrictBool = True
    prune_spurs: StrictBool = False
    clahe: StrictBool = False
    oriented: StrictBool = False
    zoned_sampling: StrictBool = True
    zone_rows: int = Field(default=2, ge=1, le=8, strict=True)
    zone_columns: int = Field(default=4, ge=1, le=8, strict=True)
    redistribute_zones: StrictBool = True
    diameter_method: Literal['three_profiles', 'legacy'] = 'three_profiles'


SETTINGS_PATH = DATA_HOME / 'data' / 'processing-settings.json'
_lock = Lock()


def processing_settings():
    try:
        return ProcessingSettings.model_validate_json(SETTINGS_PATH.read_bytes())
    except FileNotFoundError:
        return ProcessingSettings()


def update_processing_settings(patch: ProcessingSettings):
    with _lock:
        settings = processing_settings().model_copy(update=patch.model_dump(exclude_unset=True))
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=SETTINGS_PATH.parent, delete=False) as pending:
            path = Path(pending.name)
        try:
            path.write_text(settings.model_dump_json(indent=2), encoding='utf8')
            path.replace(SETTINGS_PATH)
        finally:
            path.unlink(missing_ok=True)
        return settings
