import os
import sys
import json
import tempfile
import unittest
import threading
import time
from queue import Queue
from scipy import integrate

# Ensure the current directory is in sys.path so we can import main.py
sys.path.insert(0, os.path.abspath('.'))

# Import the functions and globals from your main module
from main import (
    determine_motor_class,
    read_data,
    find_files_in_directory,
    populate_graphs,
    populate_interval_window,
    file_path
)

# Import dearpygui so we can patch its functions.
import dearpygui.dearpygui as dpg

# Dummy dictionaries to capture calls to dpg.set_value and dpg.set_item_label
captured_values = {}
captured_labels = {}

def dummy_set_value(key, value):
    captured_values[key] = value

def dummy_set_item_label(item, label):
    captured_labels[item] = label

# Dummy dummy for fit_axis_data so it does nothing
def dummy_fit_axis_data(*args, **kwargs):
    return

class TestApp(unittest.TestCase):
    def setUp(self):
        # Create a dummy context for Dear PyGui
        dpg.create_context()
        # Backup and patch dpg setter functions and fit_axis_data
        self._original_set_value = dpg.set_value
        self._original_set_item_label = dpg.set_item_label
        self._original_fit_axis_data = dpg.fit_axis_data
        dpg.set_value = dummy_set_value
        dpg.set_item_label = dummy_set_item_label
        dpg.fit_axis_data = dummy_fit_axis_data

        # Clear our dummy dictionaries
        captured_values.clear()
        captured_labels.clear()

    def tearDown(self):
        # Restore the original dpg functions
        dpg.set_value = self._original_set_value
        dpg.set_item_label = self._original_set_item_label
        dpg.fit_axis_data = self._original_fit_axis_data
        dpg.destroy_context()

    def test_determine_motor_class(self):
        self.assertEqual(determine_motor_class(1), 'A')
        self.assertEqual(determine_motor_class(2.5), 'A')
        self.assertEqual(determine_motor_class(3), 'B')
        self.assertEqual(determine_motor_class(10), 'C')
        self.assertEqual(determine_motor_class(15), 'D')
        self.assertEqual(determine_motor_class(35), 'E')
        self.assertEqual(determine_motor_class(63.33), 'F')
        self.assertEqual(determine_motor_class(100), 'G')
        self.assertEqual(determine_motor_class(5000), 'L')
        self.assertEqual(determine_motor_class(100000), '')

    def test_read_data(self):
        # Create a temporary JSON file with known data.
        test_data = {
            "load_cell_voltages_mv": [1.25, 1.45, 1.65],
            "pressure_transducer_voltages_v": [1.0, 2.0, 3.0],
            "time_values_seconds": [0, 1, 2]
        }
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
            json.dump(test_data, tmp)
            tmp_file = tmp.name

        try:
            # Set the global file_path in main.py to our temporary file.
            import main  # Import the main module
            main.file_path = tmp_file

            time_data, loads, pressures = read_data()
            # Check that the arrays have the expected length.
            self.assertEqual(len(time_data), 3)
            self.assertEqual(len(loads), 3)
            self.assertEqual(len(pressures), 3)
            # Check that the time_data is as expected.
            self.assertEqual(time_data, [0, 1, 2])
        finally:
            os.remove(tmp_file)

    def test_find_files_in_directory(self):
        # Create a temporary directory with a dummy JSON and MP4 file.
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            mp4_path = os.path.join(tmpdir, "test.mp4")
            # Write dummy JSON with a video_path key.
            with open(json_path, "w") as f:
                json.dump({"video_path": "test.mp4"}, f)
            # Create an empty mp4 file.
            with open(mp4_path, "w") as f:
                f.write("dummy content")
            found_json, found_mp4 = find_files_in_directory(tmpdir)
            self.assertEqual(found_json, json_path)
            self.assertEqual(found_mp4, mp4_path)

    def test_populate_graphs(self):
        # Provide sample data arrays.
        time_data = [0, 1, 2, 3]
        thrusts = [10, 20, 30, 40]  # avg = 25, max = 40
        pressures = [100, 200, 300, 400]  # avg = 250, max = 400

        populate_graphs(time_data, thrusts, pressures)

        burn_time = 3.0
        avg_thrust = sum(thrusts) / len(thrusts)
        max_thrust = max(thrusts)
        avg_pressure = sum(pressures) / len(pressures)
        max_pressure = max(pressures)
        total_impulse = integrate.simpson(thrusts, x=time_data)
        motor_class = determine_motor_class(total_impulse)

        self.assertEqual(captured_values.get("avg_thrust"),
                         " Average Thrust: " + '{0:,.2f}'.format(avg_thrust) + " N")
        self.assertEqual(captured_values.get("max_thrust"),
                         " Max Thrust: " + '{0:,.2f}'.format(max_thrust) + " N")
        self.assertEqual(captured_values.get("avg_pressure"),
                         " Average Pressure: " + '{0:,.2f}'.format(avg_pressure) + " PSI")
        self.assertEqual(captured_values.get("max_pressure"),
                         " Max Pressure: " + '{0:,.2f}'.format(max_pressure) + " PSI")
        self.assertEqual(captured_values.get("burn_time"),
                         " Burn Time: " + '{0:.2f}'.format(burn_time) + " s")
        self.assertEqual(captured_values.get("total_impulse"),
                         " Total Impulse: " + '{0:.2f}'.format(total_impulse) + " Ns")
        self.assertEqual(captured_values.get("motor_desig"),
                         " Motor Designation: " + motor_class + '{0:.0f}'.format(avg_thrust))

    def test_populate_interval_window(self):
        # Provide sample data arrays for interval-specific stats.
        time_data = [0, 1, 2, 3]
        thrusts = [10, 20, 30, 40]
        pressures = [100, 200, 300, 400]

        populate_interval_window(time_data, thrusts, pressures)

        burn_time = 3.0
        avg_thrust = 25.00
        max_thrust = 40.00
        avg_pressure = 250.00
        max_pressure = 400.00
        total_impulse = integrate.simpson(thrusts, x=time_data)
        motor_class = determine_motor_class(total_impulse)

        self.assertEqual(captured_values.get("avg_thrust_interval"),
                         " Average Thrust: " + '{0:,.2f}'.format(avg_thrust) + " N")
        self.assertEqual(captured_values.get("max_thrust_interval"),
                         " Max Thrust: " + '{0:,.2f}'.format(max_thrust) + " N")
        self.assertEqual(captured_values.get("avg_pressure_interval"),
                         " Average Pressure: " + '{0:,.2f}'.format(avg_pressure) + " PSI")
        self.assertEqual(captured_values.get("max_pressure_interval"),
                         " Max Pressure: " + '{0:,.2f}'.format(max_pressure) + " PSI")
        self.assertEqual(captured_values.get("burn_time_interval"),
                         " Burn Time: " + '{0:.2f}'.format(burn_time) + " s")
        self.assertEqual(captured_values.get("total_impulse_interval"),
                         " Total Impulse: " + '{0:.2f}'.format(total_impulse) + " Ns")
        self.assertEqual(captured_values.get("motor_desig_interval"),
                         " Motor Designation: " + motor_class + '{0:.0f}'.format(avg_thrust))


if __name__ == '__main__':
    unittest.main()
