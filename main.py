import os
import json
import dearpygui.dearpygui as dpg
from scipy import integrate

# NAMED CONSTANTS FOR CONVERSIONS
TRANSDUCERMINVOLTAGE = 0.5
TRANSDUCERMAXVOLTAGE = 4.5
TRANSDUCERMAXPRESSURE = 1600  # In PSI
TRANSDUCERSCALINGFACTOR = TRANSDUCERMAXPRESSURE / (TRANSDUCERMAXVOLTAGE - TRANSDUCERMINVOLTAGE)

# Global variable to hold the selected JSON file path
file_path = ''
# Global variable to hold the video file path
video_file_path = ''

def populate_graphs_callback():
    """
    Called when the user clicks 'Populate Graphs and Load Camera Feed'.
    Parses the JSON file (selected at startup) and populates the plots with the computed data.
    Also displays the video path (the video won't actually play until unpaused).
    """
    time, thrusts, pressures = read_data()

    # Calculate key stats/motor characteristics
    if time:
        burn_time = time[-1]
    else:
        burn_time = 0.0

    if thrusts:
        avg_thrust = sum(thrusts) / len(thrusts)
        max_thrust = max(thrusts)
    else:
        avg_thrust = 0.0
        max_thrust = 0.0

    if pressures:
        avg_pressure = sum(pressures) / len(pressures)
        max_pressure = max(pressures)
    else:
        avg_pressure = 0.0
        max_pressure = 0.0

    if thrusts:
        total_impulse = integrate.simpson(thrusts, x=time)
    else:
        total_impulse = 0.0

    motor_class = determine_motor_class(total_impulse)

    # Update plot series
    dpg.set_item_label("thrust_series", "Thrust Data")
    dpg.set_item_label("pressure_series", "Pressure Data")
    dpg.set_value("thrust_series", [time, thrusts])
    dpg.set_value("pressure_series", [time, pressures])
    
    # Update key stats labels
    dpg.set_value("avg_thrust", " Average Thrust: " + '{0:,.2f}'.format(avg_thrust) + " N")
    dpg.set_value("max_thrust", " Max Thrust: " + '{0:,.2f}'.format(max_thrust) + " N")
    dpg.set_value("avg_pressure", " Average Pressure: " + '{0:,.2f}'.format(avg_pressure) + " PSI")
    dpg.set_value("max_pressure", " Max Pressure: " + '{0:,.2f}'.format(max_pressure) + " PSI")
    dpg.set_value("burn_time", " Burn Time: " + '{0:.2f}'.format(burn_time) + " s")
    dpg.set_value("total_impulse", " Total Impulse: " + '{0:.2f}'.format(total_impulse) + " Ns")
    dpg.set_value("motor_desig", " Motor Designation: " + motor_class + '{0:.0f}'.format(avg_thrust))

    # Adjust plot axes to fit the new data
    dpg.fit_axis_data("y_axis_thrust")
    dpg.fit_axis_data("y_axis_pressure")
    dpg.fit_axis_data("x_axis_thrust")
    dpg.fit_axis_data("x_axis_pressure")

    # Show the video path in the UI
    dpg.set_value("video_path_label", f"Video Path: {video_file_path}")


def exit_callback():
    """
    Closes the application.
    """
    dpg.stop_dearpygui()


def resize_callback(sender, app_data, user_data):
    """
    Adjust UI elements dynamically when the viewport is resized.
    """
    width, height = dpg.get_viewport_width(), dpg.get_viewport_height()

    if dpg.does_item_exist("Primary Window"):
        dpg.set_item_width("Primary Window", width)
        dpg.set_item_height("Primary Window", height)

    if dpg.does_item_exist("thrust_plot"):
        dpg.set_item_width("thrust_plot", width * 0.68)
    if dpg.does_item_exist("pressure_plot"):
        dpg.set_item_width("pressure_plot", width * 0.68)


def build_ui():
    """
    Builds the main UI layout.
    """
    with dpg.group():
        # Button to populate the graphs
        dpg.add_button(label="Populate Graphs and Load Camera Feed", callback=populate_graphs_callback)

        # Plots section
        with dpg.child_window(width=-1, height=350):
            # Thrust Plot
            with dpg.plot(label="Thrust Data", height=160, width=-1, tag="thrust_plot"):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_thrust")
                with dpg.plot_axis(dpg.mvYAxis, label="Thrust (N)", tag="y_axis_thrust"):
                    dpg.add_line_series([], [], label="Thrust Data", tag="thrust_series")
            # Pressure Plot
            with dpg.plot(label="Pressure Data", height=160, width=-1, tag="pressure_plot"):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_pressure")
                with dpg.plot_axis(dpg.mvYAxis, label="Pressure (PSI)", tag="y_axis_pressure"):
                    dpg.add_line_series([], [], label="Pressure Data", tag="pressure_series")
        
        # Key stats section
        with dpg.child_window(width=-1, height=180):
            dpg.add_text(" Average Thrust:  N", tag="avg_thrust", color=(0, 255, 255))
            dpg.add_text(" Max Thrust:  N", tag="max_thrust", color=(255, 200, 200))
            dpg.add_text(" Average Pressure:  PSI", tag="avg_pressure", color=(200, 255, 200))
            dpg.add_text(" Max Pressure:  PSI", tag="max_pressure", color=(255, 255, 0))
            dpg.add_text(" Burn Time:  s", tag="burn_time", color=(255, 165, 0))
            dpg.add_text(" Total Impulse:  Ns", tag="total_impulse", color=(255, 105, 180))
            dpg.add_text(" Motor Designation: ", tag="motor_desig", color=(100, 200, 255))
        
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_text(" Rocket Test Video", color=(255, 140, 0))
        with dpg.child_window(width=-1, height=200):
            # Show the video path here
            dpg.add_text("Video Path: ", tag="video_path_label", color=(255, 255, 0))
            # Placeholder button
            dpg.add_button(label=" Play Video (Placeholder)", width=200)


def determine_motor_class(impulse):
    """
    Returns a letter (A, B, C, ...) based on the total impulse.
    """
    if impulse <= 2.5:
        return 'A'
    elif impulse <= 5:
        return 'B'
    elif impulse <= 10:
        return 'C'
    elif impulse <= 20:
        return 'D'
    elif impulse <= 40:
        return 'E'
    elif impulse <= 80:
        return 'F'
    elif impulse <= 160:
        return 'G'
    elif impulse <= 320:
        return 'H'
    elif impulse <= 640:
        return 'I'
    elif impulse <= 1280:
        return 'J'
    elif impulse <= 2560:
        return 'K'
    elif impulse <= 5120:
        return 'L'
    elif impulse <= 10240:
        return 'M'
    elif impulse <= 20480:
        return 'N'
    elif impulse <= 40960:
        return 'O'
    elif impulse <= 81920:
        return 'P'
    return ""


def read_data():
    """
    Parses the JSON file (specified by file_path) for graphing,
    converting raw voltage readings into thrust (N) and pressure (PSI) values.
    """
    global file_path
    if not file_path or not os.path.isfile(file_path):
        return [], [], []

    with open(file_path, 'r') as f:
        data = json.load(f)

    loads = []
    pressures = []
    time = []

    # Convert load cell data into Newtons
    for lv in data['load_cell_voltages_mv']:
        loadAdjVoltage = (lv - 1.25) / 201
        calibratedLoad = 100387.5 * loadAdjVoltage - 3.8069375
        calibratedLoad = calibratedLoad * 9.81
        loads.append(calibratedLoad)

    # Convert transducer data into PSI
    for pv in data['pressure_transducer_voltages_v']:
        pressAdjVoltage = pv - TRANSDUCERMINVOLTAGE
        pressure = pressAdjVoltage * TRANSDUCERSCALINGFACTOR
        pressures.append(pressure)
       
    n_samples = min(len(loads), len(pressures))
    sample_rate = data['sample_rate']

    for i in range(n_samples):
        time.append(round((i + 1) * (1 / sample_rate), 3))

    return (time, loads, pressures)


def find_files_in_directory(dir_path):
    """
    Searches the given directory for a .json and .mp4 file.
    Also checks if the JSON itself contains a 'video_path' for the .mp4.
    Returns (json_file_path, video_file_path).
    """
    found_json = None
    found_mp4 = None

    # Look for a .json and a .mp4 in the directory
    for item in os.listdir(dir_path):
        full_path = os.path.join(dir_path, item)
        if os.path.isfile(full_path):
            if item.lower().endswith(".json") and found_json is None:
                found_json = full_path
            elif item.lower().endswith(".mp4") and found_mp4 is None:
                found_mp4 = full_path

    # If the JSON references the mp4 path, override found_mp4
    if found_json:
        with open(found_json, 'r') as jf:
            try:
                data = json.load(jf)
                if 'video_path' in data:
                    possible_path = data['video_path']
                    if not os.path.isabs(possible_path):
                        possible_path = os.path.join(dir_path, possible_path)
                    if os.path.isfile(possible_path) and possible_path.lower().endswith(".mp4"):
                        found_mp4 = possible_path
            except:
                pass

    return found_json, found_mp4


if __name__ == "__main__":
    # Prompt for directory selection using Tkinter before launching the GUI
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    dir_path = filedialog.askdirectory(title="Select a Directory Containing JSON & MP4")
    root.destroy()

    # If the user selected a directory, find the .json and .mp4
    if dir_path:
        json_file, mp4_file = find_files_in_directory(dir_path)
        if json_file:
            file_path = json_file
        if mp4_file:
            video_file_path = mp4_file

    # Setup and launch the Dear PyGui application
    dpg.create_context()
    dpg.create_viewport(title="FreakAlyze", width=1000, height=700, resizable=True)
    dpg.setup_dearpygui()
    dpg.set_viewport_resize_callback(resize_callback)
    
    with dpg.window(tag="Primary Window", label="", no_title_bar=True, width=1000, height=700, pos=(0, 0)):
        build_ui()
    
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
