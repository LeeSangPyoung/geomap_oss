import os
import math
import time
import argparse
import logging
import requests
import geopandas as gpd
from tqdm import tqdm
from shapely.geometry import Point
from shapely.strtree import STRtree
from concurrent.futures import ThreadPoolExecutor

# 설정
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OUTPUT_DIR = "osm_tiles_korea_by_zoom"
FAILED_LOG = "failed_osm_tiles.txt"
LOG_FILE = "download.log"
MAX_WORKERS = 8
ZOOM_MIN = 5
HEADERS = {
    "User-Agent": "MyTileDownloader/1.0 (tkatlqdbr@nate.com)"
}

# ✅ 로그 설정 (콘솔 + 파일)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ✅ GeoJSON 로드
CITY_GDF = gpd.read_file("../data/korea_city_boundaries.geojson")

# 위치 판별
def is_land(lat, lon):
    return 33.0 <= lat <= 39.6 and 124.5 <= lon <= 131.0

def is_mountain(lat, lon):
    return (37.0 <= lat <= 38.8 and 127.5 <= lon <= 129.5) or \
           (33.2 <= lat <= 33.6 and 126.2 <= lon <= 126.7)

def get_max_zoom(lat, lon, selected_tree):
    point = Point(lon, lat)
    if len(selected_tree.query(point)) > 0:
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
    tile_dir = os.path.join(OUTPUT_DIR, str(z), str(x))
    tile_path = os.path.join(tile_dir, f"{y}.png")

    if os.path.exists(tile_path):
        return

    os.makedirs(tile_dir, exist_ok=True)
    url = TILE_URL.format(z=z, x=x, y=y)

    try:
        time.sleep(0.01)
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            with open(tile_path, "wb") as f:
                f.write(r.content)
            logging.info(f"[✓] {z}/{x}/{y}")
        else:
            raise Exception(f"HTTP {r.status_code}")
    except Exception as e:
        logging.error(f"[✗] {z}/{x}/{y} - {e}")
        with open(FAILED_LOG, "a") as log:
            log.write(f"{z},{x},{y} - {e}\n")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zoom", type=int, default=17, help="최대 줌 레벨 (default: 17)")
    parser.add_argument("--region", nargs="+", required=True, help="지역 이름 리스트 (예: 서울특별시 경기도)")
    return parser.parse_args()

def main():
    args = parse_args()
    zoom_max = args.zoom
    region_names = args.region

    if os.path.exists(FAILED_LOG):
        os.remove(FAILED_LOG)

    selected = CITY_GDF[CITY_GDF["CTP_KOR_NM"].isin(region_names)]
    if selected.empty:
        raise ValueError(f"선택한 지역을 찾을 수 없습니다: {region_names}")

    selected_geoms = list(selected.geometry)
    selected_tree = STRtree(selected_geoms)

    bounds = CITY_GDF.total_bounds
    min_lon, min_lat, max_lon, max_lat = bounds

    for z in range(ZOOM_MIN, zoom_max + 1):
        x_start, y_end = deg2num(max_lat, min_lon, z)
        x_end, y_start = deg2num(min_lat, max_lon, z)
        logging.info(f"[Zoom {z}] 시작: x={x_start}~{x_end}, y={y_end}~{y_start}")

        task_list = []
        for x in range(x_start, x_end + 1):
            for y in range(y_end, y_start + 1):
                lat, lon = num2deg(x + 0.5, y + 0.5, z)
                point = Point(lon, lat)

                if z <= 12:
                    task_list.append((z, x, y))
                else:
                    if len(selected_tree.query(point)) == 0:
                        continue
                    max_tile_zoom = get_max_zoom(lat, lon, selected_tree)
                    if z <= max_tile_zoom:
                        task_list.append((z, x, y))

        # ✅ 프로그래스 바 + AWX-friendly 로그
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            progress = tqdm(total=len(task_list), desc=f"Zoom {z}")
            next_log_percent = 10

            def wrapped_download(args):
                nonlocal next_log_percent
                download_tile(*args)
                progress.update(1)
                percent = int(progress.n / len(task_list) * 100)
                if percent >= next_log_percent:
                    logging.info(f"[Zoom {z}] 진행률: {percent}%")
                    next_log_percent += 10

            executor.map(wrapped_download, task_list)
            progress.close()

if __name__ == "__main__":
    main()
