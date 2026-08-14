import os
from datetime import datetime
import matplotlib.pyplot as plt
from tkinter import Tk
from tkinter.filedialog import askopenfilenames


def read_file(filename):
    """
    Automatically detects and reads either:
      1. Thermocouple log: Time / Temp
      2. Pyrometer log:    time / ATemp

    Returns:
        time_seconds, temperatures, label
    """

    # --------------------------------------------------
    # Read file
    # --------------------------------------------------
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(filename, "r", encoding="cp1252") as f:
            lines = f.readlines()

    # ==================================================
    # Detect PYROMETER file
    # ==================================================
    for i, line in enumerate(lines):
        columns = line.split()

        if "time" in columns and "ATemp" in columns:

            print(f"Pyrometer file detected: {filename}")

            time_index = columns.index("time")
            temp_index = columns.index("ATemp")

            times = []
            temperatures = []

            for data_line in lines[i + 1:]:
                parts = data_line.split()

                if len(parts) <= max(time_index, temp_index):
                    continue

                try:
                    t = float(parts[time_index])
                    temp = float(parts[temp_index])

                    times.append(t)
                    temperatures.append(temp)

                except ValueError:
                    continue

            # Time is already in seconds in pyrometer file
            label = "Pyrometer"

            return times, temperatures, label

    # ==================================================
    # Otherwise try THERMOCOUPLE format
    # ==================================================

    description_lines = []
    reading_description = False
    data_start = None

    for i, line in enumerate(lines):

        stripped = line.strip()

        # Read description
        if stripped.startswith("Description:"):
            reading_description = True

            first_description = stripped.split(
                "Description:", 1
            )[1].strip()

            if first_description:
                description_lines.append(first_description)

            continue

        if reading_description:

            if stripped.startswith("Time"):
                reading_description = False

            elif stripped:
                description_lines.append(stripped)

        # Find Time / Temp header
        columns = stripped.split()

        if len(columns) >= 2:
            if columns[0] == "Time" and columns[1] == "Temp":
                data_start = i + 1
                break

    if data_start is None:
        raise ValueError(
            f"Could not recognize file format: {filename}"
        )

    print(f"Thermocouple file detected: {filename}")

    times = []
    temperatures = []

    # --------------------------------------------------
    # Read thermocouple data
    # --------------------------------------------------
    for line in lines[data_start:]:

        parts = line.split()

        # Example:
        # 11:46:27 AM 20.3
        if len(parts) < 3:
            continue

        try:
            time_text = f"{parts[0]} {parts[1]}"

            timestamp = datetime.strptime(
                time_text,
                "%I:%M:%S %p"
            )

            temperature = float(parts[2])

            times.append(timestamp)
            temperatures.append(temperature)

        except ValueError:
            continue

    if not times:
        raise ValueError(
            f"No temperature data found in {filename}"
        )

    # Convert clock time to elapsed seconds
    t0 = times[0]

    elapsed_seconds = [
        (t - t0).total_seconds()
        for t in times
    ]

    # Use Description for legend
    if description_lines:
        label = ", ".join(description_lines)
    else:
        label = os.path.splitext(
            os.path.basename(filename)
        )[0]

    return elapsed_seconds, temperatures, label


# ======================================================
# Select files
# ======================================================

root = Tk()
root.withdraw()

filenames = askopenfilenames(
    title="Select Temperature Files",
    filetypes=[
        ("Temperature Files", "*.log *.txt"),
        ("Log Files", "*.log"),
        ("Text Files", "*.txt"),
        ("All Files", "*.*")
    ]
)

root.destroy()

if not filenames:
    raise SystemExit("No files selected.")


# ======================================================
# Plot
# ======================================================

plt.figure(figsize=(11, 7))

for filename in filenames:

    try:
        time_seconds, temperatures, label = read_file(filename)

        plt.plot(
            time_seconds,
            temperatures,
            linewidth=2,
            label=label
        )

    except Exception as error:
        print(f"Error reading {filename}:")
        print(error)


# ======================================================
# Format graph
# ======================================================

plt.xlabel("Time (s)")
plt.ylabel("Temperature (°C)")
plt.title("Temperature vs. Time")

plt.grid(True)

plt.legend()

plt.tight_layout()

plt.show()