from flask import Flask, Response, abort
import sqlite3
from io import BytesIO
from PIL import Image
import argparse

# ✅ argparse로 --map_port, --min_zoom 받기
parser = argparse.ArgumentParser()
parser.add_argument('--map_port', type=int, default=8091, help='Port to run the server on')
parser.add_argument('--min_zoom', type=int, default=10, help='Minimum zoom level allowed for fallback')
parser.add_argument('--mbtiles', type=str, default="./vworld_korea.mbtiles", help='Path to MBTiles file')
args = parser.parse_args()

app = Flask(__name__)
MBTILES_PATH = args.mbtiles

# ✅ 타일 데이터 조회
def get_tile_data(z, x, y):
    conn = sqlite3.connect(MBTILES_PATH)
    cursor = conn.cursor()
    flipped_y = (2 ** z - 1) - y
    cursor.execute("""
        SELECT tile_data FROM tiles
        WHERE zoom_level=? AND tile_column=? AND tile_row=?
    """, (z, x, flipped_y))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# ✅ fallback 타일 조회 (min_zoom까지 내려감)
def get_best_available_tile(z, x, y):
    conn = sqlite3.connect(MBTILES_PATH)
    cursor = conn.cursor()

    for fallback_z in range(z - 1, args.min_zoom - 1, -1):
        scale = 2 ** (z - fallback_z)
        tx = x // scale
        ty = y // scale
        flipped_ty = (2 ** fallback_z - 1) - ty

        cursor.execute("""
            SELECT tile_data FROM tiles
            WHERE zoom_level=? AND tile_column=? AND tile_row=?
        """, (fallback_z, tx, flipped_ty))
        row = cursor.fetchone()

        if row:
            conn.close()
            return fallback_z, tx, ty, row[0]

    conn.close()
    return None

# ✅ 타일 요청 엔드포인트
@app.route("/tiles/vworld_korea/<int:z>/<int:x>/<int:y>.png")
def serve_tile(z, x, y):
    tile_data = get_tile_data(z, x, y)
    if tile_data:
        return Response(tile_data, mimetype='image/png')

    fallback = get_best_available_tile(z, x, y)
    if fallback:
        fallback_z, tx, ty, tile_data = fallback
        img = Image.open(BytesIO(tile_data))

        scale = 2 ** (z - fallback_z)
        tile_size = 256
        dx = (x % scale) * (tile_size // scale)
        dy = (y % scale) * (tile_size // scale)
        box = (dx, dy, dx + tile_size // scale, dy + tile_size // scale)

        cropped = img.crop(box).resize((256, 256), resample=Image.LANCZOS)
        output = BytesIO()
        cropped.save(output, format='PNG')
        output.seek(0)
        return Response(output.read(), mimetype='image/png')

    return abort(404)

# ✅ 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=args.map_port)
