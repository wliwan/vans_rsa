from enum import Enum, StrEnum


class EnumBase(Enum):
    @classmethod
    def get_member_values(cls):
        return [item.value for item in cls._member_map_.values()]

    @classmethod
    def get_member_names(cls):
        return [name for name in cls._member_names_]


class MethodType(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class RegionType(StrEnum):
    COUNTRY = "COUNTRY"
    STATE = "STATE"
    CITY = "CITY"


class BoundaryType(StrEnum):
    GEOJSON = "GEOJSON"
    KML = "KML"
    SHP = "SHP"
    GPKG = "GPKG"


class BoundaryStatus(StrEnum):
    PENDING = "PENDING"       # 待下载
    DOWNLOADING = "DOWNLOADING"  # 下载中
    SUCCESS = "SUCCESS"       # 下载成功
    FAILED = "FAILED"         # 下载失败


class RoadNetworkType(StrEnum):
    OSM = "OSM"
    GRAPHML = "GRAPHML"
    GPKG = "GPKG"
    SHP = "SHP"


class RoadNetworkStatus(StrEnum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

