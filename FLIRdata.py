import numpy as np
import matplotlib.pyplot as plt
from tkinter import Tk, filedialog


# ---------------------------------------------------------
# Select CSV file
# ---------------------------------------------------------

root = Tk()
root.withdraw()

filename = filedialog.askopenfilename(
    title="Select IR Camera CSV File",
    filetypes=[
        ("CSV files", "*.csv"),
        ("All files", "*.*")
    ]
)

root.destroy()

if not filename:
    print("No file selected.")
    raise SystemExit


# ---------------------------------------------------------
# Load temperature data
# ---------------------------------------------------------

temperature = np.loadtxt(
    filename,
    delimiter=",",
    skiprows=53
)

rows, cols = temperature.shape

print(f"Image size: {rows} x {cols}")
print(f"Minimum temperature: {np.nanmin(temperature):.2f} °C")
print(f"Maximum temperature: {np.nanmax(temperature):.2f} °C")


# ---------------------------------------------------------
# Function to get temperature values along a line
# ---------------------------------------------------------

def sample_line(data, x1, y1, x2, y2):
    """
    Sample temperature values along a line between
    (x1, y1) and (x2, y2).

    Returns:
        distance     = distance along line in pixels
        temperatures = sampled temperature values
    """

    # Length of line
    length = np.hypot(x2 - x1, y2 - y1)

    # Use approximately one sample per pixel
    num_points = max(int(np.ceil(length)) + 1, 2)

    # Coordinates along line
    x = np.linspace(x1, x2, num_points)
    y = np.linspace(y1, y2, num_points)

    # Round to nearest image pixel
    xi = np.rint(x).astype(int)
    yi = np.rint(y).astype(int)

    # Keep indices inside image
    xi = np.clip(xi, 0, data.shape[1] - 1)
    yi = np.clip(yi, 0, data.shape[0] - 1)

    # Remove duplicate pixels
    coordinates = np.column_stack((xi, yi))
    _, unique_indices = np.unique(
        coordinates,
        axis=0,
        return_index=True
    )

    unique_indices = np.sort(unique_indices)

    xi = xi[unique_indices]
    yi = yi[unique_indices]

    # Get temperatures
    temperatures = data[yi, xi]

    # Calculate cumulative distance in pixels
    dx = np.diff(xi)
    dy = np.diff(yi)

    distance = np.concatenate((
        [0],
        np.cumsum(np.hypot(dx, dy))
    ))

    return distance, temperatures


# ---------------------------------------------------------
# Set up figures
# ---------------------------------------------------------

# Figure 1: Thermal image
fig_image, ax_image = plt.subplots(figsize=(10, 8))

image = ax_image.imshow(
    temperature,
    cmap="inferno",
    origin="upper",
    interpolation="nearest"
)

cbar = fig_image.colorbar(image, ax=ax_image)
cbar.set_label("Temperature (°C)", fontsize=14, fontweight="bold")

ax_image.set_xlabel("X Pixel",fontsize=14, fontweight="bold")
ax_image.set_ylabel("Y Pixel",fontsize=14, fontweight="bold")
ax_image.set_title(
    "IR Temperature Map\n"
    "Click and drag to draw temperature profile lines"
)


# Figure 2: Line temperature profiles
fig_profile, ax_profile = plt.subplots(figsize=(10, 6))

ax = plt.gca()
ax_profile.set_xlabel("Distance Along Line (pixels)",fontsize=14, fontweight="bold")
ax_profile.set_ylabel("Temperature (°C)",fontsize=14, fontweight="bold")
ax.tick_params(axis='both', which='major', labelsize=12, width=1.5)
ax.xaxis.set_tick_params(labelsize=12)
ax.yaxis.set_tick_params(labelsize=12)
ax_profile.set_title("Temperature Profiles",fontsize=14, fontweight="bold")
ax_profile.grid(True)

fig_profile.tight_layout()


# ---------------------------------------------------------
# Variables used while drawing
# ---------------------------------------------------------

start_point = None
temporary_line = None
line_count = 0


# ---------------------------------------------------------
# Mouse press
# ---------------------------------------------------------

def on_press(event):
    global start_point, temporary_line

    # Only respond to clicks on thermal image
    if event.inaxes != ax_image:
        return

    # Only use left mouse button
    if event.button != 1:
        return

    start_point = (event.xdata, event.ydata)

    # Create temporary line
    temporary_line, = ax_image.plot(
        [event.xdata, event.xdata],
        [event.ydata, event.ydata],
        linewidth=2
    )

    fig_image.canvas.draw_idle()


# ---------------------------------------------------------
# Mouse movement
# ---------------------------------------------------------

def on_motion(event):
    global temporary_line

    if start_point is None:
        return

    if event.inaxes != ax_image:
        return

    if temporary_line is None:
        return

    x1, y1 = start_point

    temporary_line.set_data(
        [x1, event.xdata],
        [y1, event.ydata]
    )

    fig_image.canvas.draw_idle()


# ---------------------------------------------------------
# Mouse release
# ---------------------------------------------------------

def on_release(event):
    global start_point
    global temporary_line
    global line_count

    if start_point is None:
        return

    if event.inaxes != ax_image:
        start_point = None

        if temporary_line is not None:
            temporary_line.remove()
            temporary_line = None

        fig_image.canvas.draw_idle()
        return

    x1, y1 = start_point
    x2, y2 = event.xdata, event.ydata

    # Do not create extremely short lines
    if np.hypot(x2 - x1, y2 - y1) < 1:
        temporary_line.remove()
        temporary_line = None
        start_point = None

        fig_image.canvas.draw_idle()
        return

    line_count += 1

    # Sample temperatures
    distance, line_temperature = sample_line(
        temperature,
        x1,
        y1,
        x2,
        y2
    )

    # Plot profile
    profile_line, = ax_profile.plot(
        distance,
        line_temperature,
        linewidth=2,
        label=f"Line {line_count}"
    )

    # Make image line use same color as profile
    temporary_line.set_color(profile_line.get_color())

    # Add line number to thermal image
    ax_image.text(
        x1,
        y1,
        str(line_count),
        color="white",
        fontsize=10,
        fontweight="bold",
        bbox=dict(
            facecolor="black",
            alpha=0.6,
            edgecolor="none"
        )
    )

    # Add legend
    ax_profile.legend()

    # Rescale profile graph
    ax_profile.relim()
    ax_profile.autoscale_view()

    fig_profile.canvas.draw_idle()
    fig_image.canvas.draw_idle()

    print(
        f"Line {line_count}: "
        f"({x1:.0f}, {y1:.0f}) -> "
        f"({x2:.0f}, {y2:.0f}), "
        f"Length = {distance[-1]:.1f} pixels"
    )

    # Reset
    start_point = None
    temporary_line = None


# ---------------------------------------------------------
# Connect mouse events
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

fig_image.tight_layout()

plt.show()