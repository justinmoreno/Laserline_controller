import os
import csv
import numpy as np
import matplotlib.pyplot as plt

from tkinter import Tk, filedialog
from matplotlib.widgets import Button


# ============================================================
# SETTINGS
# ============================================================

SKIP_ROWS = 53
IMAGE_WIDTH = 640
EXPECTED_IMAGE_SHAPE = (512, 640)


# ============================================================
# ROBUST IR CSV LOADER
# ============================================================

def load_ir_csv(filename, skip_rows=SKIP_ROWS, image_width=IMAGE_WIDTH):
    """
    Load a FLIR CSV file robustly.

    - Skips metadata rows.
    - Uses only the first `image_width` columns if a row contains extras.
    - Reports short or malformed rows.
    - Returns a NumPy array of temperatures.
    """

    rows = []
    extra_column_rows = []
    short_rows = []
    non_numeric_rows = []

    with open(filename, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)

        for row_number, row in enumerate(reader, start=1):
            if row_number <= skip_rows:
                continue

            if not row:
                continue

            if len(row) > image_width:
                extra_column_rows.append((row_number, len(row)))
                row = row[:image_width]

            elif len(row) < image_width:
                short_rows.append((row_number, len(row)))
                continue

            try:
                values = [float(value) for value in row]
                rows.append(values)
            except ValueError:
                non_numeric_rows.append(row_number)

    data = np.array(rows, dtype=float)
    basename = os.path.basename(filename)

    if extra_column_rows:
        print(
            f"\nWarning: {basename} contains "
            f"{len(extra_column_rows)} row(s) with extra columns."
        )

        for row_number, width in extra_column_rows[:10]:
            print(
                f"  Row {row_number}: {width} columns "
                f"(using first {image_width})"
            )

        if len(extra_column_rows) > 10:
            print(f"  ...and {len(extra_column_rows) - 10} more.")

    if short_rows:
        print(
            f"\nWARNING: {basename} contains "
            f"{len(short_rows)} row(s) with fewer than "
            f"{image_width} columns. These rows were skipped."
        )

        for row_number, width in short_rows[:10]:
            print(f"  Row {row_number}: {width} columns")

        if len(short_rows) > 10:
            print(f"  ...and {len(short_rows) - 10} more.")

    if non_numeric_rows:
        print(
            f"\nWARNING: {basename} contains "
            f"{len(non_numeric_rows)} non-numeric row(s). "
            "These rows were skipped."
        )
        print("  First affected rows:", non_numeric_rows[:10])

    return data


# ============================================================
# SELECT CSV FILES
# ============================================================

root = Tk()
root.withdraw()

filenames = filedialog.askopenfilenames(
    title="Select IR Camera CSV Files",
    filetypes=[
        ("CSV files", "*.csv"),
        ("All files", "*.*")
    ]
)

root.destroy()

if not filenames:
    print("No files selected.")
    raise SystemExit

filenames = list(filenames)

print(f"\nSelected {len(filenames)} file(s):")

for filename in filenames:
    print("  ", os.path.basename(filename))


# ============================================================
# LOAD ALL TEMPERATURE FILES
# ============================================================

temperature_data = []

for filename in filenames:
    print(f"\nLoading {os.path.basename(filename)}...")

    data = load_ir_csv(filename)

    print(f"Loaded shape: {data.shape}")

    if data.shape != EXPECTED_IMAGE_SHAPE:
        raise ValueError(
            f"\n{os.path.basename(filename)} produced an "
            f"unexpected image size of {data.shape}.\n"
            f"Expected {EXPECTED_IMAGE_SHAPE}.\n"
            "Check for missing, malformed, or extra rows in the CSV."
        )

    temperature_data.append(data)

    print(f"  Min = {np.nanmin(data):.2f} °C")
    print(f"  Max = {np.nanmax(data):.2f} °C")


# ============================================================
# VERIFY ALL FILES HAVE THE SAME SHAPE
# ============================================================

reference_shape = temperature_data[0].shape

for i, data in enumerate(temperature_data):
    if data.shape != reference_shape:
        raise ValueError(
            "\nImage size mismatch:\n"
            f"{os.path.basename(filenames[0])}: {reference_shape}\n"
            f"{os.path.basename(filenames[i])}: {data.shape}\n\n"
            "All CSV files must have the same image dimensions."
        )

rows, cols = reference_shape

print("\nAll files loaded successfully.")
print(f"Image size: {rows} x {cols}")


# ============================================================
# SAMPLE TEMPERATURE ALONG A LINE
# ============================================================

def sample_line(data, x1, y1, x2, y2):
    """
    Extract temperature values along a line.

    Returns:
        distance:
            Cumulative distance along the selected line in pixels.

        temperatures:
            Temperature values sampled from the image.
    """

    length = np.hypot(x2 - x1, y2 - y1)
    num_points = max(int(np.ceil(length)) + 1, 2)

    x = np.linspace(x1, x2, num_points)
    y = np.linspace(y1, y2, num_points)

    xi = np.rint(x).astype(int)
    yi = np.rint(y).astype(int)

    xi = np.clip(xi, 0, data.shape[1] - 1)
    yi = np.clip(yi, 0, data.shape[0] - 1)

    coordinates = np.column_stack((xi, yi))

    _, unique_indices = np.unique(
        coordinates,
        axis=0,
        return_index=True
    )

    unique_indices = np.sort(unique_indices)

    xi = xi[unique_indices]
    yi = yi[unique_indices]

    temperatures = data[yi, xi]

    dx = np.diff(xi)
    dy = np.diff(yi)

    distance = np.concatenate(
        ([0], np.cumsum(np.hypot(dx, dy)))
    )

    return distance, temperatures


# ============================================================
# SET UP THERMAL IMAGE
# ============================================================

first_temperature = temperature_data[0]

fig_image, ax_image = plt.subplots(figsize=(11, 8))
plt.subplots_adjust(bottom=0.15)

image = ax_image.imshow(
    first_temperature,
    cmap="inferno",
    origin="upper",
    interpolation="nearest"
)

cbar = fig_image.colorbar(image, ax=ax_image)
cbar.set_label("Temperature (°C)", fontsize=14, fontweight="bold")
cbar.ax.tick_params(labelsize=14)

ax_image.set_xlabel("X Pixel", fontsize=14, fontweight="bold")
ax_image.set_ylabel("Y Pixel", fontsize=14, fontweight="bold")
ax_image.tick_params(axis="both", labelsize=14)

ax_image.set_title(
    "IR Temperature Map\n"
    f"Reference Image: {os.path.basename(filenames[0])}\n"
    "Click and drag to draw profile lines"
)


# ============================================================
# SET UP PROFILE GRAPH
# ============================================================

fig_profile, ax_profile = plt.subplots(figsize=(11, 7))

ax_profile.set_xlabel("Distance Along Line (pixels)", fontsize=14, fontweight="bold")
ax_profile.set_ylabel("Temperature (°C)", fontsize=14, fontweight="bold")
ax_profile.set_title("Temperature Profiles", fontsize=14, fontweight="bold")
ax_profile.tick_params(axis="both", labelsize=14)
ax_profile.grid(True)

fig_profile.tight_layout()


# ============================================================
# DATA STORAGE
# ============================================================

line_records = []

start_point = None
temporary_line = None


# ============================================================
# UPDATE PROFILE GRAPH
# ============================================================

def update_profile_plot():
    if len(ax_profile.lines) > 0:
        ax_profile.legend(fontsize=8, loc="best")
        ax_profile.relim()
        ax_profile.autoscale_view()
    else:
        legend = ax_profile.get_legend()

        if legend is not None:
            legend.remove()

        ax_profile.relim()
        ax_profile.autoscale_view()

    fig_profile.canvas.draw_idle()


# ============================================================
# MOUSE PRESS
# ============================================================

def on_press(event):
    global start_point
    global temporary_line

    if event.inaxes != ax_image:
        return

    if event.button != 1:
        return

    if event.xdata is None or event.ydata is None:
        return

    start_point = (event.xdata, event.ydata)

    temporary_line, = ax_image.plot(
        [event.xdata, event.xdata],
        [event.ydata, event.ydata],
        color="white",
        linewidth=2,
        linestyle="--"
    )

    fig_image.canvas.draw_idle()


# ============================================================
# MOUSE MOTION
# ============================================================

def on_motion(event):
    global temporary_line

    if start_point is None:
        return

    if temporary_line is None:
        return

    if event.inaxes != ax_image:
        return

    if event.xdata is None or event.ydata is None:
        return

    x1, y1 = start_point

    temporary_line.set_data(
        [x1, event.xdata],
        [y1, event.ydata]
    )

    fig_image.canvas.draw_idle()


# ============================================================
# MOUSE RELEASE
# ============================================================

def on_release(event):
    global start_point
    global temporary_line

    if start_point is None:
        return

    if (
        event.inaxes != ax_image
        or event.xdata is None
        or event.ydata is None
    ):
        if temporary_line is not None:
            temporary_line.remove()
            temporary_line = None

        start_point = None
        fig_image.canvas.draw_idle()
        return

    x1, y1 = start_point
    x2, y2 = event.xdata, event.ydata

    if np.hypot(x2 - x1, y2 - y1) < 1:
        temporary_line.remove()
        temporary_line = None
        start_point = None
        fig_image.canvas.draw_idle()
        return

    line_number = len(line_records) + 1

    distance, first_profile = sample_line(
        temperature_data[0],
        x1,
        y1,
        x2,
        y2
    )

    profile_lines = []

    first_filename = os.path.basename(filenames[0])

    first_curve, = ax_profile.plot(
        distance,
        first_profile,
        linewidth=2,
        label=f"Line {line_number} - {first_filename}"
    )

    profile_lines.append(first_curve)
    line_color = first_curve.get_color()

    temporary_line.set_color(line_color)
    temporary_line.set_linestyle("-")
    temporary_line.set_linewidth(2.5)

    final_image_line = temporary_line

    line_text = ax_image.text(
        x1,
        y1,
        f" {line_number} ",
        color="white",
        fontsize=10,
        fontweight="bold",
        verticalalignment="center",
        horizontalalignment="center",
        bbox=dict(
            facecolor=line_color,
            alpha=0.9,
            edgecolor="white"
        )
    )

    for i in range(1, len(temperature_data)):
        distance_i, profile_i = sample_line(
            temperature_data[i],
            x1,
            y1,
            x2,
            y2
        )

        filename_i = os.path.basename(filenames[i])

        curve, = ax_profile.plot(
            distance_i,
            profile_i,
            linewidth=1.5,
            label=f"Line {line_number} - {filename_i}"
        )

        profile_lines.append(curve)

    record = {
        "number": line_number,
        "coords": (x1, y1, x2, y2),
        "image_line": final_image_line,
        "image_text": line_text,
        "profile_lines": profile_lines
    }

    line_records.append(record)

    print(
        f"\nLine {line_number}: "
        f"({x1:.1f}, {y1:.1f}) -> "
        f"({x2:.1f}, {y2:.1f})"
    )

    print(f"Length: {distance[-1]:.1f} pixels")

    for filename, data in zip(filenames, temperature_data):
        _, profile = sample_line(
            data,
            x1,
            y1,
            x2,
            y2
        )

        print(
            f"  {os.path.basename(filename)}: "
            f"min={np.nanmin(profile):.2f} °C, "
            f"max={np.nanmax(profile):.2f} °C, "
            f"mean={np.nanmean(profile):.2f} °C"
        )

    update_profile_plot()
    fig_image.canvas.draw_idle()

    start_point = None
    temporary_line = None


# ============================================================
# UNDO LAST LINE
# ============================================================

def undo_last_line(event):
    if not line_records:
        print("Nothing to undo.")
        return

    record = line_records.pop()

    record["image_line"].remove()
    record["image_text"].remove()

    for curve in record["profile_lines"]:
        curve.remove()

    print(f"Removed Line {record['number']}")

    fig_image.canvas.draw_idle()
    update_profile_plot()


# ============================================================
# CLEAR ALL LINES
# ============================================================

def clear_all_lines(event):
    global start_point
    global temporary_line

    if temporary_line is not None:
        try:
            temporary_line.remove()
        except ValueError:
            pass

        temporary_line = None

    start_point = None

    while line_records:
        record = line_records.pop()

        record["image_line"].remove()
        record["image_text"].remove()

        for curve in record["profile_lines"]:
            curve.remove()

    print("All lines cleared.")

    fig_image.canvas.draw_idle()
    update_profile_plot()


# ============================================================
# BUTTONS
# ============================================================

undo_button_axis = fig_image.add_axes(
    [0.30, 0.035, 0.17, 0.055]
)

clear_button_axis = fig_image.add_axes(
    [0.53, 0.035, 0.17, 0.055]
)

undo_button = Button(
    undo_button_axis,
    "Undo Last Line"
)

clear_button = Button(
    clear_button_axis,
    "Clear All Lines"
)

undo_button.on_clicked(undo_last_line)
clear_button.on_clicked(clear_all_lines)


# ============================================================
# CONNECT MOUSE EVENTS
# ============================================================

fig_image.canvas.mpl_connect(
    "button_press_event",
    on_press
)

fig_image.canvas.mpl_connect(
    "motion_notify_event",
    on_motion
)

fig_image.canvas.mpl_connect(
    "button_release_event",
    on_release
)


# ============================================================
# DISPLAY
# ============================================================

plt.show()