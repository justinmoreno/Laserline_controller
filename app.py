"""
app.py

Laserline Research Controller

Entry point.
"""

from gui import LaserGUI


def main():

    gui = LaserGUI()

    gui.run()


if __name__ == "__main__":
    main()