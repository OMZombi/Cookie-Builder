import numpy as np
from PIL import Image

mask = np.zeros((400, 400), dtype=np.uint8)
mask = np.ascontiguousarray(mask)

# Simple rounded-square example silhouette.
for y in range(400):
    for x in range(400):
        dx = max(abs(x - 200) - 120, 0)
        dy = max(abs(y - 200) - 120, 0)
        if dx * dx + dy * dy <= 40 * 40:
            mask[y, x] = 255

# Add simple inner emboss marks.
mask[195:205, 80:320] = 255
Image.fromarray(mask).save("example-mask.png")
