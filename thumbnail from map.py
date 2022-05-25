from PIL import Image

import os

os.makedirs("./thumbnail/", exist_ok=True)
for filename in os.listdir("./map/"):
    if os.path.exists(f"./thumbnail/{filename}"): continue
    Image.open(f"./map/{filename}").resize((480, 270)).save(f"./thumbnail/{filename}")