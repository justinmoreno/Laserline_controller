from pathlib import Path
from PIL import Image, ImageOps

# Allow extremely large scientific/technical images
Image.MAX_IMAGE_PIXELS = None

SOURCE = Path(r"E:\Abstracts and Presentations\ARA 2026\Target Images")
OUTPUT = SOURCE / "PowerPoint Images"

MAX_DIMENSION = 2560
JPEG_QUALITY = 88

OUTPUT.mkdir(exist_ok=True)

files = (
    list(SOURCE.glob("*.tif")) +
    list(SOURCE.glob("*.TIF")) +
    list(SOURCE.glob("*.tiff")) +
    list(SOURCE.glob("*.TIFF"))
)

print(f"Found {len(files)} TIFF files.\n")

successful = []
failed = []

for i, input_path in enumerate(files, start=1):

    print(f"[{i}/{len(files)}] Processing: {input_path.name}")

    try:
        with Image.open(input_path) as img:

            print(f"    Original dimensions: {img.width:,} x {img.height:,}")

            img = ImageOps.exif_transpose(img)

            if img.mode != "RGB":
                img = img.convert("RGB")

            img.thumbnail(
                (MAX_DIMENSION, MAX_DIMENSION),
                Image.Resampling.LANCZOS
            )

            output_path = OUTPUT / f"{input_path.stem}.jpg"

            img.save(
                output_path,
                "JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
                progressive=True
            )

            print(
                f"    -> {img.width:,} x {img.height:,}"
                f" : {output_path.name}"
            )

            successful.append(input_path.name)

    except Exception as e:

        print(f"    FAILED: {type(e).__name__}: {e}")
        failed.append((input_path.name, str(e)))

print("\n" + "=" * 60)
print(f"Successful: {len(successful)}")
print(f"Failed:     {len(failed)}")

if failed:
    print("\nFAILED FILES:")
    for filename, error in failed:
        print(f"  {filename}")
        print(f"      {error}")

print("\nFinished.")