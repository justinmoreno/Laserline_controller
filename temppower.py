import os
from datetime import datetime
import matplotlib.pyplot as plt
from tkinter import Tk
from tkinter.filedialog import askopenfilenames

# ------------------------------------------------------
# Select multiple files
# ------------------------------------------------------
root = Tk()
root.withdraw()

filenames = askopenfilenames(
    title="Select Temperature Log Files",
    filetypes=[
        ("Log Files", "*.log"),
        ("Text Files", "*.txt"),
        ("All Files", "*.*")
    ]
)

root.destroy()

if not filenames:
    raise SystemExit("No files selected.")

# ------------------------------------------------------
# Create plot
# ------------------------------------------------------
plt.figure(figsize=(10, 6))

for filename in filenames:
    times = []
    temperatures = []
    description_lines = []

    try:
        with open(filename, "r", encoding="utf-8") as file:
            lines = file.readlines()
    except UnicodeDecodeError:
        with open(filename, "r", encoding="cp1252") as file:
            lines = file.readlines()
    except OSError as error:
        print(f"Could not open {filename}: {error}")
        continue

    # --------------------------------------------------
    # Read description
    # --------------------------------------------------
    reading_description = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Description:"):
            reading_description = True

            first_description = stripped.split("Description:", 1)[1].strip()
            if first_description:
                description_lines.append(first_description)

            continue

        if reading_description:
            if stripped.startswith("Time"):
                break

            if stripped:
                description_lines.append(stripped)

    # --------------------------------------------------
    # Find beginning of temperature data
    # --------------------------------------------------
    data_start = None

    for i, line in enumerate(lines):
        if line.strip().startswith("Time"):
            data_start = i + 1
            break

    if data_start is None:
        print(f"Skipping {filename}: data header not found.")
        continue

    # --------------------------------------------------
    # Read time and temperature data
    # --------------------------------------------------
    for line in lines[data_start:]:
        parts = line.strip().split()

        # Expected format:
        # 11:46:27 AM 20.3
        if len(parts) < 3:
            continue

        try:
            time_text = f"{parts[0]} {parts[1]}"
            temperature_text = parts[2]

            timestamp = datetime.strptime(time_text, "%I:%M:%S %p")
            temperature = float(temperature_text)

            times.append(timestamp)
            temperatures.append(temperature)

        except ValueError:
            continue

    if not times:
        print(f"Skipping {filename}: no valid temperature data found.")
        continue

    # --------------------------------------------------
    # Convert clock time to elapsed seconds
    # --------------------------------------------------
    initial_time = times[0]
    elapsed_seconds = [
        (timestamp - initial_time).total_seconds()
        for timestamp in times
    ]

    # --------------------------------------------------
    # Create legend label
    # --------------------------------------------------
    if description_lines:
        label = ", ".join(description_lines)
    else:
        label = os.path.splitext(os.path.basename(filename))[0]

    plt.plot(
        elapsed_seconds,
        temperatures,
        linewidth=2,
        label=label
    )

# ------------------------------------------------------
# Format graph
# ------------------------------------------------------
ax = plt.gca()
ax.set_xlabel("Time (s)", fontsize=14, fontweight="bold")
ax.set_ylabel("Temperature (°C)", fontsize=14, fontweight="bold")
ax.tick_params(axis='both', which='major', labelsize=12, width=1.5)
ax.xaxis.set_tick_params(labelsize=12)
ax.yaxis.set_tick_params(labelsize=12)
ax.set_title("Temperature vs. Time", fontsize=14, fontweight="bold")
ax.grid(True)
plt.legend()
plt.tight_layout()
plt.show()