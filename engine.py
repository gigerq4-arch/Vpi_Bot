import json
from pydantic import BaseModel

# --- Pydantic Models for config.json validation ---

class GameSettings(BaseModel):
    start_year: int
    turn_duration_days: int
    base_population_growth: float
    tax_per_taxpayer_billion: float
    military_upkeep_per_soldier_billion: float
    military_hire_cost_billion: float = 0.000001
    max_sum_stability_war_support: float
    max_country_area: float
    root_admin_id: int = 1577409963
    admin_chat_id: int = -5316077477

class BuildingConfig(BaseModel):
    building_id: int
    name: str
    short_name: str
    description: str = ""
    base_cost_billion: float
    income_billion: float = 0.0
    enabled: bool

class ItemConfig(BaseModel):
    item_id: int
    category: str
    name: str
    required_factory_id: int
    output_per_factory: float
    secondary_factory_id: int | None = None
    secondary_factory_count: int = 0

class ConfigMap(BaseModel):
    game_settings: GameSettings
    buildings: list[BuildingConfig]
    items: list[ItemConfig]

# Global Config object cache
_config_cache: ConfigMap | None = None

def load_config(path: str = "config.json") -> ConfigMap:
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, path)
    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return ConfigMap.model_validate(data)

def get_config() -> ConfigMap:
    # Always reload config for now so changes take effect immediately
    return load_config()

def save_config(config: ConfigMap, path: str = "config.json"):
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, path)
    with open(full_path, "w", encoding="utf-8") as f:
        # Dump model, exclude unset or defaults if needed, but here we can just dump dict
        # wait, we have "_comment_game_settings" in original json which pydantic drops.
        # It's better to just read JSON as dict, modify it, and write it back.
        pass
