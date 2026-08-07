"""
Interactive hole analysis for a plate photograph.

Workflow
--------
1. Select an image.
2. Crop tightly around the plate.
3. Click two calibration points and enter their known separation.
4. Tune the dark-pixel threshold and geometric filters.
5. Save an annotated image and a CSV table.

Measurements
------------
- Hole count
- Hole area and equivalent circular diameter
- Distance from each hole centroid to the center of the cropped plate
- Averages of the above quantities

Install dependencies:
    py -m pip install opencv-python numpy pandas

Run:
    py plate_hole_analysis.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog


Point = Tuple[int, int]


def choose_image() -> Path | None:
    root = tk.Tk()
    root.withdraw()
    filename = filedialog.askopenfilename(
        title="Select plate image",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return Path(filename) if filename else None


def resize_for_display(image: np.ndarray, max_width: int = 1500, max_height: int = 900):
    h, w = image.shape[:2]
    scale = min(max_width / w, max_height / h, 1.0)
    if scale < 1.0:
        displayed = cv2.resize(
            image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA
        )
    else:
        displayed = image.copy()
    return displayed, scale


def select_crop(image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    display, scale = resize_for_display(image)
    instructions = display.copy()
    cv2.putText(
        instructions,
        "Drag around the plate, then press ENTER. Press C to cancel.",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )

    roi = cv2.selectROI("1 - Crop plate", instructions, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("1 - Crop plate")

    x, y, w, h = roi
    if w == 0 or h == 0:
        raise RuntimeError("Crop selection was cancelled.")

    x0 = int(round(x / scale))
    y0 = int(round(y / scale))
    x1 = int(round((x + w) / scale))
    y1 = int(round((y + h) / scale))

    x0 = max(0, min(x0, image.shape[1] - 1))
    y0 = max(0, min(y0, image.shape[0] - 1))
    x1 = max(x0 + 1, min(x1, image.shape[1]))
    y1 = max(y0 + 1, min(y1, image.shape[0]))

    crop = image[y0:y1, x0:x1].copy()
    return crop, (x0, y0, x1 - x0, y1 - y0)


def select_two_points(image: np.ndarray) -> Tuple[Point, Point]:
    display, scale = resize_for_display(image)
    points_display: List[Point] = []
    base = display.copy()

    def redraw():
        canvas = base.copy()
        cv2.putText(
            canvas,
            "Click two points with a known separation. R = reset, ENTER = accept.",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.70,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
        for i, point in enumerate(points_display):
            cv2.circle(canvas, point, 7, (0, 0, 255), -1)
            cv2.putText(
                canvas,
                str(i + 1),
                (point[0] + 10, point[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
        if len(points_display) == 2:
            cv2.line(canvas, points_display[0], points_display[1], (0, 255, 255), 2)
        cv2.imshow("2 - Calibration", canvas)

    def mouse_callback(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN and len(points_display) < 2:
            points_display.append((x, y))
            redraw()

    cv2.namedWindow("2 - Calibration", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("2 - Calibration", mouse_callback)
    redraw()

    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (13, 10) and len(points_display) == 2:
            break
        if key in (ord("r"), ord("R")):
            points_display.clear()
            redraw()
        if key == 27:
            cv2.destroyWindow("2 - Calibration")
            raise RuntimeError("Calibration was cancelled.")

    cv2.destroyWindow("2 - Calibration")

    points_original = [
        (int(round(x / scale)), int(round(y / scale))) for x, y in points_display
    ]
    return points_original[0], points_original[1]


def ask_positive_float(title: str, prompt: str, initial_value: float) -> float:
    root = tk.Tk()
    root.withdraw()
    while True:
        value = simpledialog.askfloat(
            title,
            prompt,
            initialvalue=initial_value,
            minvalue=1e-12,
            parent=root,
        )
        if value is None:
            root.destroy()
            raise RuntimeError(f"{title} entry was cancelled.")
        if value > 0:
            root.destroy()
            return float(value)


def odd_kernel(value: int) -> int:
    value = max(1, int(value))
    return value if value % 2 == 1 else value + 1


def detect_holes(
    image: np.ndarray,
    threshold_value: int,
    blur_size: int,
    open_size: int,
    close_size: int,
    min_area_px: float,
    max_area_px: float,
    min_circularity: float,
    edge_margin_px: int,
):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur_k = odd_kernel(blur_size)
    if blur_k > 1:
        gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)

    # Dark pixels become white in the binary mask.
    _, mask = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY_INV)

    if open_size > 0:
        k = np.ones((open_size, open_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)

    if close_size > 0:
        k = np.ones((close_size, close_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = image.shape[:2]
    accepted = []

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area_px or area > max_area_px:
            continue

        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue

        circularity = 4.0 * math.pi * area / (perimeter * perimeter)
        if circularity < min_circularity:
            continue

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue

        cx = float(moments["m10"] / moments["m00"])
        cy = float(moments["m01"] / moments["m00"])

        if (
            cx < edge_margin_px
            or cy < edge_margin_px
            or cx > w - edge_margin_px
            or cy > h - edge_margin_px
        ):
            continue

        accepted.append(
            {
                "contour": contour,
                "area_px2": area,
                "circularity": circularity,
                "centroid_x_px": cx,
                "centroid_y_px": cy,
            }
        )

    accepted.sort(key=lambda d: (d["centroid_y_px"], d["centroid_x_px"]))
    return mask, accepted


def tune_detection(image: np.ndarray, pixels_per_unit: float):
    window = "3 - Tune detection"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    unit2_per_pixel2 = 1.0 / (pixels_per_unit**2)

    # Initial values intended for dark holes on a bright metal plate.
    cv2.createTrackbar("Dark threshold", window, 55, 255, lambda x: None)
    cv2.createTrackbar("Blur", window, 3, 15, lambda x: None)
    cv2.createTrackbar("Open", window, 1, 10, lambda x: None)
    cv2.createTrackbar("Close", window, 2, 15, lambda x: None)

    # Areas are entered as hundredths of square calibration units.
    cv2.createTrackbar("Min area x0.01", window, 2, 500, lambda x: None)
    cv2.createTrackbar("Max area x0.01", window, 400, 5000, lambda x: None)
    cv2.createTrackbar("Min circularity %", window, 12, 100, lambda x: None)
    cv2.createTrackbar("Edge margin px", window, 8, 200, lambda x: None)

    last_result = None

    while True:
        threshold_value = cv2.getTrackbarPos("Dark threshold", window)
        blur_size = cv2.getTrackbarPos("Blur", window)
        open_size = cv2.getTrackbarPos("Open", window)
        close_size = cv2.getTrackbarPos("Close", window)
        min_area_unit2 = cv2.getTrackbarPos("Min area x0.01", window) / 100.0
        max_area_unit2 = cv2.getTrackbarPos("Max area x0.01", window) / 100.0
        min_circularity = cv2.getTrackbarPos("Min circularity %", window) / 100.0
        edge_margin_px = cv2.getTrackbarPos("Edge margin px", window)

        if max_area_unit2 <= min_area_unit2:
            max_area_unit2 = min_area_unit2 + 0.01

        min_area_px = min_area_unit2 / unit2_per_pixel2
        max_area_px = max_area_unit2 / unit2_per_pixel2

        mask, holes = detect_holes(
            image=image,
            threshold_value=threshold_value,
            blur_size=blur_size,
            open_size=open_size,
            close_size=close_size,
            min_area_px=min_area_px,
            max_area_px=max_area_px,
            min_circularity=min_circularity,
            edge_margin_px=edge_margin_px,
        )

        overlay = image.copy()
        center = (image.shape[1] // 2, image.shape[0] // 2)
        cv2.drawMarker(
            overlay,
            center,
            (255, 0, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=30,
            thickness=2,
        )

        for i, hole in enumerate(holes, start=1):
            cv2.drawContours(overlay, [hole["contour"]], -1, (0, 0, 255), 2)
            cx = int(round(hole["centroid_x_px"]))
            cy = int(round(hole["centroid_y_px"]))
            cv2.circle(overlay, (cx, cy), 3, (0, 255, 0), -1)
            cv2.putText(
                overlay,
                str(i),
                (cx + 4, cy - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 0, 0),
                1,
                cv2.LINE_AA,
            )

        cv2.putText(
            overlay,
            f"Detected holes: {len(holes)} | ENTER = accept | ESC = cancel",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

        display, _ = resize_for_display(overlay)
        cv2.imshow(window, display)
        last_result = (mask, holes)

        key = cv2.waitKey(40) & 0xFF
        if key in (13, 10):
            break
        if key == 27:
            cv2.destroyWindow(window)
            raise RuntimeError("Detection tuning was cancelled.")

    cv2.destroyWindow(window)
    return last_result


def make_results(
    image: np.ndarray,
    holes,
    pixels_per_unit: float,
    unit_name: str,
) -> Tuple[pd.DataFrame, np.ndarray]:
    center_x = image.shape[1] / 2.0
    center_y = image.shape[0] / 2.0

    rows = []
    annotated = image.copy()
    cv2.drawMarker(
        annotated,
        (int(round(center_x)), int(round(center_y))),
        (255, 0, 255),
        markerType=cv2.MARKER_CROSS,
        markerSize=35,
        thickness=3,
    )

    for index, hole in enumerate(holes, start=1):
        area_unit2 = hole["area_px2"] / (pixels_per_unit**2)
        equivalent_diameter = 2.0 * math.sqrt(area_unit2 / math.pi)
        cx = hole["centroid_x_px"]
        cy = hole["centroid_y_px"]
        distance_from_center = math.hypot(cx - center_x, cy - center_y) / pixels_per_unit

        rows.append(
            {
                "hole_id": index,
                "centroid_x_px": cx,
                "centroid_y_px": cy,
                f"area_{unit_name}2": area_unit2,
                f"equivalent_diameter_{unit_name}": equivalent_diameter,
                f"distance_from_plate_center_{unit_name}": distance_from_center,
                "circularity": hole["circularity"],
            }
        )

        cv2.drawContours(annotated, [hole["contour"]], -1, (0, 0, 255), 2)
        point = (int(round(cx)), int(round(cy)))
        cv2.circle(annotated, point, 3, (0, 255, 0), -1)
        cv2.putText(
            annotated,
            str(index),
            (point[0] + 5, point[1] - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 0, 0),
            1,
            cv2.LINE_AA,
        )

    df = pd.DataFrame(rows)
    return df, annotated


def save_outputs(
    source_path: Path,
    crop: np.ndarray,
    mask: np.ndarray,
    annotated: np.ndarray,
    df: pd.DataFrame,
    unit_name: str,
):
    output_dir = source_path.parent / f"{source_path.stem}_hole_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "hole_measurements.csv"
    annotated_path = output_dir / "holes_annotated.png"
    crop_path = output_dir / "plate_crop.png"
    mask_path = output_dir / "binary_mask.png"
    summary_path = output_dir / "summary.txt"

    df.to_csv(csv_path, index=False)
    cv2.imwrite(str(annotated_path), annotated)
    cv2.imwrite(str(crop_path), crop)
    cv2.imwrite(str(mask_path), mask)

    if df.empty:
        summary = "No holes were detected.\n"
    else:
        area_col = f"area_{unit_name}2"
        diameter_col = f"equivalent_diameter_{unit_name}"
        distance_col = f"distance_from_plate_center_{unit_name}"
        summary = (
            f"Number of holes: {len(df)}\n"
            f"Average hole area: {df[area_col].mean():.4f} {unit_name}^2\n"
            f"Average equivalent hole diameter: "
            f"{df[diameter_col].mean():.4f} {unit_name}\n"
            f"Average distance from plate center: "
            f"{df[distance_col].mean():.4f} {unit_name}\n"
        )

    summary_path.write_text(summary, encoding="utf-8")
    return output_dir, summary


def main():
    try:
        image_path = choose_image()
        if image_path is None:
            return

        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"Could not read image:\n{image_path}")

        crop, _ = select_crop(image)

        p1, p2 = select_two_points(crop)
        pixel_distance = math.dist(p1, p2)
        if pixel_distance <= 0:
            raise RuntimeError("The calibration points must be different.")

        known_distance = ask_positive_float(
            "Calibration",
            "Enter the known distance between the two selected points:",
            initial_value=10.0,
        )

        root = tk.Tk()
        root.withdraw()
        unit_name = simpledialog.askstring(
            "Calibration units",
            "Enter the distance unit, for example mm:",
            initialvalue="mm",
            parent=root,
        )
        root.destroy()
        if not unit_name:
            unit_name = "units"
        unit_name = unit_name.strip().replace(" ", "_")

        pixels_per_unit = pixel_distance / known_distance

        mask, holes = tune_detection(crop, pixels_per_unit)
        df, annotated = make_results(crop, holes, pixels_per_unit, unit_name)
        output_dir, summary = save_outputs(
            image_path, crop, mask, annotated, df, unit_name
        )

        print(summary)
        print(f"Pixels per {unit_name}: {pixels_per_unit:.6f}")
        print(f"Results saved to: {output_dir}")

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "Hole analysis complete",
            summary + f"\nResults saved to:\n{output_dir}",
            parent=root,
        )
        root.destroy()

        display, _ = resize_for_display(annotated)
        cv2.imshow("Final annotated result - press any key to close", display)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    except Exception as exc:
        cv2.destroyAllWindows()
        print(f"Error: {exc}", file=sys.stderr)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Hole analysis error", str(exc), parent=root)
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
