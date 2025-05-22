from flask import Flask, send_file, abort, Response
import sqlite3
from io import BytesIO
from PIL import Image
import math

app = Flask(__name__)
MBTILES_PATH = "./osm_korea.mbtiles"

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

@app.route("/tiles/korea/<int:z>/<int:x>/<int:y>.png")
def serve_tile(z, x, y):
    tile_data = get_tile_data(z, x, y)

    if tile_data:
        return Response(tile_data, mimetype='image/png')

    # Fallback to z=12
    if z > 12:
        scale = 2 ** (z - 12)
        x12 = x // scale
        y12 = y // scale
        tile_data = get_tile_data(12, x12, y12)

        if tile_data:
            # Crop the correct tile section
            img = Image.open(BytesIO(tile_data))
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
