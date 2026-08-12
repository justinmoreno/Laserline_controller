#!/usr/bin/env python3
"""
Projectile Velocity Tracker

Features
--------
- Calibrate pixel distance to millimeters using two points.
- Supports 8-bit and 16-bit grayscale TIFF images without washing them out.
- Calibration window allows zoom/pan before point selection.
- Tracking images open maximized/full-screen when supported.
- One projectile point is selected per image.
- Velocity is calculated from frame-to-frame displacement and frame rate.
- Results are printed and optionally saved to CSV.

Install:
    pip install matplotlib pillow numpy
"""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from tkinter import Tk, filedialog, messagebox, simpledialog


IMAGE_TYPES = [
    ("Image files", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
    ("TIFF files", "*.tif *.tiff"),
    ("PNG files", "*.png"),
    ("JPEG files", "*.jpg *.jpeg"),
    ("Bitmap files", "*.bmp"),
    ("All files", "*.*"),
]


@dataclass
class TrackedPoint:
    frame_number: int
    filename: str
    x_px: float
    y_px: float


def create_hidden_root() -> Tk:
    root = Tk()
    root.withdraw()
    root.update()
    return root


def load_image_for_display(path: Path):
    """
    Load an image while preserving high-bit-depth grayscale data.

    Returns
    -------
    array : numpy.ndarray
        Image data suitable for matplotlib.imshow().
    imshow_kwargs : dict
        Keyword arguments for imshow().

    Notes
    -----
    16-bit grayscale TIFF images are NOT converted through PIL RGB because
    that can destroy the useful intensity range. Instead, matplotlib displays
    the original grayscale values with percentile-based contrast stretching.
    """
    try:
        with Image.open(path) as image:
            arr = np.asarray(image)

            # Copy before closing PIL image/file.
            arr = np.array(arr, copy=True)

    except Exception as exc:
        raise RuntimeError(f"Could not open image:\n{path}\n\n{exc}") from exc

    kwargs = {}

    if arr.ndim == 2:
        # Grayscale image, including uint16 TIFF.
        finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr.ravel()

        if finite.size:
            # Robust contrast stretch. 0.5/99.5 works well for high-speed-camera TIFFs.
            vmin, vmax = np.percentile(finite, [0.5, 99.5])

            if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
                vmin = float(np.min(finite))
                vmax = float(np.max(finite))

            if vmax <= vmin:
                vmax = vmin + 1.0

            kwargs = {
                "cmap": "gray",
                "vmin": float(vmin),
                "vmax": float(vmax),
                "interpolation": "nearest",
            }
        else:
            kwargs = {"cmap": "gray", "interpolation": "nearest"}

    elif arr.ndim == 3:
        # Some TIFFs are 16-bit RGB. Scale them into [0, 1] if needed.
        if arr.dtype == np.uint16:
            lo = np.percentile(arr, 0.5)
            hi = np.percentile(arr, 99.5)
            if hi <= lo:
                lo = float(arr.min())
                hi = float(arr.max())
            if hi > lo:
                arr = np.clip((arr.astype(np.float32) - lo) / (hi - lo), 0.0, 1.0)

    return arr, kwargs


def toolbar_is_active(fig) -> bool:
    """
    Return True when Matplotlib's pan or zoom tool is currently active.
    """
    toolbar = getattr(fig.canvas.manager, "toolbar", None)
    if toolbar is None:
        return False

    mode = getattr(toolbar, "mode", "")
    if mode is None:
        return False

    return bool(str(mode).strip())


def maximize_figure(fig) -> None:
    """
    Maximize the Matplotlib figure using backend-specific methods.

    TkAgg on Windows:
        manager.window.state("zoomed")
    Qt backends:
        manager.window.showMaximized()
    Other backends:
        full_screen_toggle() fallback
    """
    manager = fig.canvas.manager
    window = getattr(manager, "window", None)

    # TkAgg / Windows
    if window is not None:
        try:
            window.state("zoomed")
            fig.canvas.draw_idle()
            return
        except Exception:
            pass

    # Qt
    if window is not None:
        try:
            window.showMaximized()
            fig.canvas.draw_idle()
            return
        except Exception:
            pass

    # Generic fallback
    try:
        manager.full_screen_toggle()
        fig.canvas.draw_idle()
    except Exception:
        pass


def select_reference_image(root: Tk) -> Optional[Path]:
    filename = filedialog.askopenfilename(
        parent=root,
        title="Select the reference image",
        filetypes=IMAGE_TYPES,
    )
    return Path(filename) if filename else None


def calibrate_image(root: Tk, image_path: Path) -> Optional[float]:
    image, imshow_kwargs = load_image_for_display(image_path)

    selected: list[tuple[float, float]] = []
    accepted = {"value": False}
    markers = []

    fig, ax = plt.subplots()
    ax.imshow(image, **imshow_kwargs)
    ax.set_xlabel("x [pixels]")
    ax.set_ylabel("y [pixels]")

    def update_title():
        if len(selected) == 0:
            status = "Select calibration point 1"
        elif len(selected) == 1:
            status = "Select calibration point 2"
        else:
            pixel_distance = math.dist(selected[0], selected[1])
            status = f"Distance = {pixel_distance:.3f} pixels | Press Enter to accept"

        ax.set_title(
            "CALIBRATION\n"
            f"{status}\n"
            "You may Zoom/Pan first. Turn the toolbar tool OFF before clicking points.\n"
            "Left click = select | Backspace/right-click = undo | Enter = accept | Q/Esc = cancel"
        )
        fig.canvas.draw_idle()

    def redraw_markers():
        nonlocal markers
        for marker in markers:
            try:
                marker.remove()
            except Exception:
                pass
        markers = []

        for i, (x, y) in enumerate(selected, start=1):
            marker, = ax.plot(
                x, y,
                marker="o",
                markersize=10,
                markerfacecolor="none",
                markeredgewidth=2,
            )
            markers.append(marker)
            ax.annotate(
                str(i),
                (x, y),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=12,
            )

        fig.canvas.draw_idle()

    def on_click(event):
        if event.inaxes != ax:
            return

        # Right click undoes even after zoom/pan.
        if event.button == 3:
            if selected:
                selected.pop()
                # Clear and redraw whole axes so annotation numbers stay correct.
                ax.clear()
                ax.imshow(image, **imshow_kwargs)
                ax.set_xlabel("x [pixels]")
                ax.set_ylabel("y [pixels]")
                redraw_markers()
                update_title()
            return

        if event.button != 1:
            return

        # Do not accidentally place a calibration point while using zoom/pan.
        if toolbar_is_active(fig):
            return

        if event.xdata is None or event.ydata is None:
            return

        if len(selected) < 2:
            selected.append((float(event.xdata), float(event.ydata)))
            redraw_markers()
            update_title()

    def on_key(event):
        key = (event.key or "").lower()

        if key in {"q", "escape"}:
            accepted["value"] = False
            plt.close(fig)

        elif key in {"backspace", "delete"}:
            if selected:
                selected.pop()
                ax.clear()
                ax.imshow(image, **imshow_kwargs)
                ax.set_xlabel("x [pixels]")
                ax.set_ylabel("y [pixels]")
                redraw_markers()
                update_title()

        elif key in {"enter", "return"} and len(selected) == 2:
            accepted["value"] = True
            plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)

    update_title()
    plt.show()

    if not accepted["value"] or len(selected) != 2:
        return None

    pixel_distance = math.dist(selected[0], selected[1])
    if pixel_distance <= 0:
        messagebox.showerror(
            "Calibration error",
            "The two calibration points must be different.",
            parent=root,
        )
        return None

    real_distance_mm = simpledialog.askfloat(
        "Calibration distance",
        "Enter the real distance between the two selected points [mm]:",
        parent=root,
        minvalue=1e-12,
    )
    if real_distance_mm is None:
        return None

    mm_per_pixel = real_distance_mm / pixel_distance

    messagebox.showinfo(
        "Calibration complete",
        f"Pixel distance: {pixel_distance:.4f} px\n"
        f"Scale: {mm_per_pixel:.8f} mm/px",
        parent=root,
    )
    return mm_per_pixel


def select_sequence(root: Tk) -> list[Path]:
    filenames = filedialog.askopenfilenames(
        parent=root,
        title="Select projectile image sequence",
        filetypes=IMAGE_TYPES,
    )
    return [Path(name) for name in filenames]


def select_point_on_image(
    image_path: Path,
    image_index: int,
    image_count: int,
    previous_point: Optional[tuple[float, float]],
) -> tuple[str, Optional[tuple[float, float]]]:

    image, imshow_kwargs = load_image_for_display(image_path)
    selected: list[tuple[float, float]] = []
    action = {"value": "closed"}

    fig, ax = plt.subplots()
    ax.imshow(image, **imshow_kwargs)
    ax.set_xlabel("x [pixels]")
    ax.set_ylabel("y [pixels]")

    # Use most of the screen for the image.
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.08, top=0.88)

    selected_marker = {"artist": None}

    if previous_point is not None:
        ax.plot(
            previous_point[0],
            previous_point[1],
            marker="+",
            markersize=16,
            markeredgewidth=2,
            label="Previous point",
        )
        ax.legend(loc="upper right")

    def update_title():
        if selected:
            status = f"Selected x={selected[0][0]:.2f}, y={selected[0][1]:.2f} px"
        else:
            status = "Click projectile location"

        ax.set_title(
            f"Image {image_index + 1} of {image_count}: {image_path.name}\n"
            f"{status}\n"
            "Enter = accept | Backspace/right-click = redo | Q/Escape = stop",
            fontsize=13,
        )
        fig.canvas.draw_idle()

    def clear_selected_marker():
        artist = selected_marker["artist"]
        if artist is not None:
            try:
                artist.remove()
            except Exception:
                pass
            selected_marker["artist"] = None

    def on_click(event):
        if event.inaxes != ax:
            return

        if event.button == 3:
            selected.clear()
            clear_selected_marker()
            update_title()
            return

        if event.button != 1:
            return

        # If user happens to use the toolbar, do not create a point while zooming/panning.
        if toolbar_is_active(fig):
            return

        if event.xdata is None or event.ydata is None:
            return

        selected[:] = [(float(event.xdata), float(event.ydata))]
        clear_selected_marker()

        marker, = ax.plot(
            selected[0][0],
            selected[0][1],
            marker="o",
            markersize=10,
            markerfacecolor="none",
            markeredgewidth=2,
        )
        selected_marker["artist"] = marker
        update_title()

    def on_key(event):
        key = (event.key or "").lower()

        if key in {"q", "escape"}:
            action["value"] = "stop"
            plt.close(fig)

        elif key in {"backspace", "delete"}:
            selected.clear()
            clear_selected_marker()
            update_title()

        elif key in {"enter", "return"} and selected:
            action["value"] = "accepted"
            plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)

    update_title()

    # Draw the window first, then maximize it.
    plt.show(block=False)
    plt.pause(0.15)
    maximize_figure(fig)

    # Keep event loop running until the figure is closed.
    plt.show()

    if action["value"] == "accepted" and selected:
        return "accepted", selected[0]

    if action["value"] == "stop":
        return "stop", None

    return "closed", None


def track_sequence(image_paths: list[Path]) -> list[TrackedPoint]:
    tracked: list[TrackedPoint] = []
    previous_point: Optional[tuple[float, float]] = None

    for index, image_path in enumerate(image_paths):
        status, point = select_point_on_image(
            image_path=image_path,
            image_index=index,
            image_count=len(image_paths),
            previous_point=previous_point,
        )

        if status != "accepted" or point is None:
            break

        tracked.append(
            TrackedPoint(
                frame_number=index,
                filename=image_path.name,
                x_px=point[0],
                y_px=point[1],
            )
        )
        previous_point = point

    return tracked


def calculate_results(
    points: list[TrackedPoint],
    mm_per_pixel: float,
    frame_rate_hz: float,
) -> list[dict[str, object]]:

    results: list[dict[str, object]] = []
    cumulative_distance_mm = 0.0

    x0 = points[0].x_px
    y0 = points[0].y_px

    for i, point in enumerate(points):
        time_s = i / frame_rate_hz

        x_mm = point.x_px * mm_per_pixel
        y_mm = point.y_px * mm_per_pixel

        displacement_from_start_mm = (
            math.hypot(point.x_px - x0, point.y_px - y0) * mm_per_pixel
        )

        if i == 0:
            dx_mm = 0.0
            dy_mm = 0.0
            step_distance_mm = 0.0
            vx_m_s = None
            vy_m_s = None
            speed_m_s = None
        else:
            previous = points[i - 1]

            dx_mm = (point.x_px - previous.x_px) * mm_per_pixel
            # Image y coordinates increase downward, so invert sign for physical +y upward.
            dy_mm = -(point.y_px - previous.y_px) * mm_per_pixel

            step_distance_mm = math.hypot(dx_mm, dy_mm)
            cumulative_distance_mm += step_distance_mm

            dt = 1.0 / frame_rate_hz
            vx_m_s = (dx_mm / 1000.0) / dt
            vy_m_s = (dy_mm / 1000.0) / dt
            speed_m_s = step_distance_mm / 1000.0 / dt

        results.append(
            {
                "point_number": i + 1,
                "frame_number": point.frame_number,
                "filename": point.filename,
                "time_s": time_s,
                "x_px": point.x_px,
                "y_px": point.y_px,
                "x_mm": x_mm,
                "y_mm": y_mm,
                "dx_mm": dx_mm,
                "dy_mm": dy_mm,
                "step_distance_mm": step_distance_mm,
                "cumulative_path_distance_mm": cumulative_distance_mm,
                "displacement_from_start_mm": displacement_from_start_mm,
                "vx_m_s": vx_m_s,
                "vy_m_s": vy_m_s,
                "speed_m_s": speed_m_s,
            }
        )

    return results


def print_results(
    results: list[dict[str, object]],
    mm_per_pixel: float,
    frame_rate_hz: float,
) -> None:

    print("\nProjectile tracking results")
    print("=" * 145)
    print(f"Scale:      {mm_per_pixel:.8f} mm/px")
    print(f"Frame rate: {frame_rate_hz:.6g} frames/s")
    print("-" * 145)

    print(
        f"{'Pt':>4} {'Frame':>6} {'Time[s]':>10} "
        f"{'x[px]':>10} {'y[px]':>10} "
        f"{'dx[mm]':>10} {'dy[mm]':>10} "
        f"{'Dist[mm]':>11} {'Vx[m/s]':>11} {'Vy[m/s]':>11} "
        f"{'Speed[m/s]':>12}  File"
    )
    print("-" * 145)

    for row in results:
        vx = row["vx_m_s"]
        vy = row["vy_m_s"]
        speed = row["speed_m_s"]

        vx_text = "—" if vx is None else f"{vx:.6f}"
        vy_text = "—" if vy is None else f"{vy:.6f}"
        speed_text = "—" if speed is None else f"{speed:.6f}"

        print(
            f"{int(row['point_number']):4d} "
            f"{int(row['frame_number']):6d} "
            f"{float(row['time_s']):10.6f} "
            f"{float(row['x_px']):10.3f} "
            f"{float(row['y_px']):10.3f} "
            f"{float(row['dx_mm']):10.4f} "
            f"{float(row['dy_mm']):10.4f} "
            f"{float(row['step_distance_mm']):11.4f} "
            f"{vx_text:>11} "
            f"{vy_text:>11} "
            f"{speed_text:>12}  "
            f"{row['filename']}"
        )

    if len(results) >= 2:
        total_time_s = float(results[-1]["time_s"])
        total_path_mm = float(results[-1]["cumulative_path_distance_mm"])
        net_displacement_mm = float(results[-1]["displacement_from_start_mm"])

        average_speed_m_s = (
            total_path_mm / 1000.0 / total_time_s
            if total_time_s > 0
            else 0.0
        )

        average_velocity_magnitude_m_s = (
            net_displacement_mm / 1000.0 / total_time_s
            if total_time_s > 0
            else 0.0
        )

        print("-" * 145)
        print(f"Total elapsed time:               {total_time_s:.8f} s")
        print(f"Total path distance:              {total_path_mm:.6f} mm")
        print(f"Net displacement magnitude:       {net_displacement_mm:.6f} mm")
        print(f"Average path speed:               {average_speed_m_s:.6f} m/s")
        print(f"Average velocity magnitude:       {average_velocity_magnitude_m_s:.6f} m/s")


def save_results(
    root: Tk,
    results: list[dict[str, object]],
    mm_per_pixel: float,
    frame_rate_hz: float,
) -> Optional[Path]:

    filename = filedialog.asksaveasfilename(
        parent=root,
        title="Save tracking results",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile="projectile_tracking_results.csv",
    )

    if not filename:
        return None

    output_path = Path(filename)

    fieldnames = [
        "point_number",
        "frame_number",
        "filename",
        "time_s",
        "x_px",
        "y_px",
        "x_mm",
        "y_mm",
        "dx_mm",
        "dy_mm",
        "step_distance_mm",
        "cumulative_path_distance_mm",
        "displacement_from_start_mm",
        "vx_m_s",
        "vy_m_s",
        "speed_m_s",
        "calibration_mm_per_pixel",
        "frame_rate_hz",
    ]

    try:
        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()

            for row in results:
                output_row = dict(row)
                output_row["calibration_mm_per_pixel"] = mm_per_pixel
                output_row["frame_rate_hz"] = frame_rate_hz
                writer.writerow(output_row)

    except OSError as exc:
        messagebox.showerror(
            "Save error",
            f"Could not save the CSV file:\n{exc}",
            parent=root,
        )
        return None

    return output_path


def main() -> int:
    root = create_hidden_root()

    try:
        reference_path = select_reference_image(root)
        if reference_path is None:
            print("No reference image selected. Program ended.")
            return 0

        mm_per_pixel = calibrate_image(root, reference_path)
        if mm_per_pixel is None:
            print("Calibration cancelled. Program ended.")
            return 0

        image_paths = select_sequence(root)
        if not image_paths:
            print("No image sequence selected. Program ended.")
            return 0

        points = track_sequence(image_paths)

        if len(points) < 2:
            messagebox.showwarning(
                "Not enough points",
                "At least two tracked points are required to calculate velocity.",
                parent=root,
            )
            return 0

        frame_rate_hz = simpledialog.askfloat(
            "Frame rate",
            "Enter the image frame rate [frames per second]:",
            parent=root,
            minvalue=1e-12,
        )

        if frame_rate_hz is None:
            print("Frame-rate entry cancelled. Program ended.")
            return 0

        results = calculate_results(points, mm_per_pixel, frame_rate_hz)
        print_results(results, mm_per_pixel, frame_rate_hz)

        output_path = save_results(
            root,
            results,
            mm_per_pixel,
            frame_rate_hz,
        )

        if output_path is not None:
            messagebox.showinfo(
                "Results saved",
                f"Results were saved to:\n{output_path}",
                parent=root,
            )
            print(f"\nCSV saved to: {output_path}")
        else:
            print("\nResults were not saved to a CSV file.")

        return 0

    except Exception as exc:
        messagebox.showerror(
            "Unexpected error",
            str(exc),
            parent=root,
        )
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    finally:
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
