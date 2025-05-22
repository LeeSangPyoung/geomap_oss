import os
import math
import requests
import time
import argparse
import geopandas as gpd
from shapely.geometry import Point
from concurrent.futures import ThreadPoolExecutor, as_completed

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OUTPUT_DIR = "osm_tiles_korea_by_zoom"
FAILED_LOG = "failed_osm_tiles.txt"
MAX_WORKERS = 4
HEADERS = {
    "User-Agent": "MyTileDownloader/1.0 (tkatlqdbr@nate.com)"
}

ZOOM_MIN = 5
CITY_GDF = gpd.read_file("D:/oss2map2/oss2map/data/korea_city_boundaries.geojson")

def is_in_city(lat, lon):
    point = Point(lon, lat)
    return CITY_GDF.contains(point).any()

def is_land(lat, lon):
    return 33.0 <= lat <= 39.6 and 124.5 <= lon <= 131.5

def is_mountain(lat, lon):
    return (37.0 <= lat <= 38.8 and 127.5 <= lon <= 129.5) or (33.2 <= lat <= 33.6 and 126.2 <= lon <= 126.7)

def get_max_zoom(lat, lon):
    if is_in_city(lat, lon):
        return 17
    elif is_mountain(lat, lon):
        return 14
    elif is_land(lat, lon):
        return 14
    else:
        return 12

def deg2num(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile

def num2deg(x, y, zoom):
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

def download_tile(z, x, y):
    url = TILE_URL.format(z=z, x=x, y=y)
    tile_dir = os.path.join(OUTPUT_DIR, str(z), str(x))
    tile_path = os.path.join(tile_dir, f"{y}.png")

    if os.path.exists(tile_path):
        return

    os.makedirs(tile_dir, exist_ok=True)

    try:
        time.sleep(0.01)
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            with open(tile_path, "wb") as f:
                f.write(r.content)
            print(f"[✓] {z}/{x}/{y}")
        else:
            raise Exception(f"HTTP {r.status_code}")
    except Exception as e:
        with open(FAILED_LOG, "a") as log:
            log.write(f"{z},{x},{y} - {e}\n")
        print(f"[✗] {z}/{x}/{y} - {e}")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zoom", type=int, default=17, help="최대 줌 레벨 (default: 17)")
    parser.add_argument("--region", nargs="+", required=True, help="지역 이름 리스트 (예: 서울특별시 경기도)")
    return parser.parse_args()

def main():
    args = parse_args()
    zoom_max = args.zoom
    region_names = args.region

    selected = CITY_GDF[CITY_GDF["CTP_KOR_NM"].isin(region_names)]
    if selected.empty:
        raise ValueError(f"선택한 지역을 찾을 수 없습니다: {region_names}")

    bounds = selected.total_bounds  # minx, miny, maxx, maxy
    min_lon, min_lat, max_lon, max_lat = bounds

    for z in range(ZOOM_MIN, zoom_max + 1):
        x_start, y_start = deg2num(max_lat, min_lon, z)
        x_end, y_end = deg2num(min_lat, max_lon, z)
        print(f"\n[Zoom {z}] x: {x_start}~{x_end}, y: {y_start}~{y_end} for {region_names}")

        tasks = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for x in range(x_start, x_end + 1):
                for y in range(y_start, y_end + 1):
                    lat, lon = num2deg(x + 0.5, y + 0.5, z)
                    max_tile_zoom = get_max_zoom(lat, lon)
                    if z <= max_tile_zoom:
                        tasks.append(executor.submit(download_tile, z, x, y))
            for future in as_completed(tasks):
                _ = future.result()

if __name__ == "__main__":
    main()
