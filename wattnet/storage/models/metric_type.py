from enum import Enum


class MetricType(str, Enum):
    ZONE_GENERATION = "zone_generation"
    ZONE_IMPORT = "zone_import"
    ZONE_EXPORT = "zone_export"
    ZONE_LOAD = "zone_load"
    FACTOR = "factor"
    LOCAL_FOOTPRINT = "local_footprint"
    GLOBAL_FOOTPRINT = "global_footprint"
    LOCAL_IMPACT = "local_impact"
    GLOBAL_IMPACT = "global_impact"
    LOCAL_SCORE = "local_score"
    GLOBAL_SCORE = "global_score"
    FLOW_SHARE = "flow_share"
    MIX_SHARE = "mix_share"
    FOOTPRINT_SHARE = "footprint_share"
    IMPACT_SHARE = "impact_share"
    UNKNOWN = "unknown"
