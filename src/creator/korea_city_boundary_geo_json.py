import geopandas as gpd

# 실제 SHP 경로로 수정
shp_path = "D:/oss2map2/oss2map/data/TL_SCCO_SIG/ctp_rvn.shp"

gdf = gpd.read_file(shp_path, encoding='euc-kr')
gdf = gdf.set_crs(epsg=5179)
gdf = gdf.to_crs(epsg=4326)
gdf.to_file("D:/oss2map2/oss2map/data/korea_city_boundaries.geojson", driver="GeoJSON")
