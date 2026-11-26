# Cookie-Builder

Cookie-Builder converts an image into a printable cookie-cutter STL. It separates the object's outer silhouette from detailed inner line art so embossing elements remain lower than the cutting edge.

## Features

- Load PNG/JPG/BMP/TIFF images
- Detect an object silhouette
- Extract and simplify inner line-art for embossing
- Generate a cookie cutter with independently configurable:
  - outer dimensions
  - wall thickness
  - cutter height
  - emboss height
  - base thickness
- Export binary STL
- Inspect a 2D preview of the detected silhouette and emboss lines

## Installation

Requires Python 3.10+

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Usage

Generate an STL:

```bash
python src/cookie_builder.py input.png output.stl --size-mm 80
```

For an image with transparent background:

```bash
python src/cookie_builder.py input.png output.stl --size-mm 80 --threshold 128 --wall-mm 1.2 --emboss-mm 1.0
```

Useful options:

```text
--size-mm          Largest silhouette dimension in millimeters (default: 80)
--wall-mm          Cookie-cutter wall thickness (default: 1.2)
--cutter-height-mm Overall raised cutter wall height (default: 12)
--emboss-mm        Embossing line height above the base (default: 1.0)
--base-mm          Base plate thickness (default: 2.0)
--simplify-mm      Ramer-Douglas-Peucker contour tolerance (default: 0.25)
--threshold        Grayscale threshold, 0-255 (default: 128)
--invert           Invert the detected foreground mask
--preview          Save a PNG preview beside the STL
--quiet            Suppress progress messages
```

## 3D geometry

The generated model consists of:

1. A rectangular or silhouette base plate
2. A full-height outer cutting wall
3. Lower-height embossing line meshes inside the silhouette

The default emboss height is deliberately lower than the cutter wall height. A line-oriented image should have high contrast: black lines on white or transparent areas work best.

## Development

Run a syntax check:

```bash
python -m compileall src tests
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Notes

Generated geometry should be checked in a slicer before printing. Thin details, poor image contrast, and disconnected contours can require manual cleanup.
