
from datetime import datetime
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import matplotlib.pyplot as plt

# ------------------------------------------------------------------
# File name
# ------------------------------------------------------------------
from tkinter import Tk
from tkinter.filedialog import askopenfilename

# Hide the root tkinter window
root = Tk()
root.withdraw()

# Open Windows file browser
filename = askopenfilename(
    title="Select Temperature Log File",
    filetypes=[("Log Files", "*.log"),
               ("Text Files", "*.txt"),
               ("All Files", "*.*")]
)

# Exit if no file selected
if not filename:
    raise SystemExit("No file selected.")

# ------------------------------------------------------------------
# Read data
# ------------------------------------------------------------------
times = []
temperatures = []

with open(filename, "r") as f:
    lines = f.readlines()

# Find where the data table begins
data_start = None
for i, line in enumerate(lines):
    if line.strip().startswith("Time"):
        data_start = i + 1
        break

if data_start is None:
    raise ValueError("Could not locate data table.")

# Read temperature data
for line in lines[data_start:]:
    line = line.strip()

    if not line:
        continue

    parts = line.split("\t")
    if len(parts) != 2:
        continue

    try:
        t = datetime.strptime(parts[0], "%I:%M:%S %p")
        temp = float(parts[1])

        times.append(t)
        temperatures.append(temp)

    except ValueError:
        continue

# ------------------------------------------------------------------
# Convert timestamps to elapsed seconds
# ------------------------------------------------------------------
t0 = times[0]
time_seconds = [(t - t0).total_seconds() for t in times]

# ------------------------------------------------------------------
# Plot
# ------------------------------------------------------------------
plt.figure(figsize=(10,6))
plt.plot(time_seconds, temperatures, linewidth=2)

plt.xlabel("Time (s)")
plt.ylabel("Temperature (°C)")
plt.title("Temperature vs Time")
plt.grid(True)

plt.tight_layout()
plt.show()