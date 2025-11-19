from enum import Enum


class MetricType(str, Enum):
    ZONE_GENERATION = "zone_generation"
    ZONE_IMPORT = "zone_import"
    ZONE_EXPORT = "zone_export"
    ZONE_DEMAND = "zone_demand"
    FACTOR = "factor"
    LOCAL_FOOTPRINT = "local_footprint"
    GLOBAL_FOOTPRINT = "global_footprint"
    FLOW_SHARE = "flow_share"
    MIX_SHARE = "mix_share"
    FOOTPRINT_SHARE = "footprint_share"
    UNKNOWN = "unknown"
