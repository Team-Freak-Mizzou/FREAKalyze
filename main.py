import os
import json
import dearpygui.dearpygui as dpg
from scipy import integrate
import cv2
import numpy as np
import threading
import time
from queue import Queue  # <-- NEW: We'll use this for thread-safe frame transfer

# NAMED CONSTANTS FOR CONVERSIONS
TRANSDUCERMINVOLTAGE = 0.5
TRANSDUCERMAXVOLTAGE = 4.5
TRANSDUCERMAXPRESSURE = 1600  # In PSI
TRANSDUCERSCALINGFACTOR = TRANSDUCERMAXPRESSURE / (TRANSDUCERMAXVOLTAGE - TRANSDUCERMINVOLTAGE)

# Global variables for file paths and video playback
file_path = ''
video_file_path = ''
video_file = ''  
video_playing = False
video_capture = None

# A lock to synchronize access to the capture object
video_lock = threading.Lock()

# A queue for passing frames from the background thread to the main thread
frame_queue = Queue()

# A global status message for the video
video_status = "Ready."

# ------------------------------------------------------------------------
# GRAPH CALLBACKS
# ------------------------------------------------------------------------

def populate_graphs_callback():
    """
    Called when the user clicks 'Populate Graphs and Load Camera Feed' OR 'Restore graphs'.
    Parses the JSON file (selected at startup) and populates the plots with the computed data.
    Also displays the video path (the video won't actually play until unpaused).
    """

    time, thrusts, pressures = read_data()

    # Starting points for sliders, put them 5% inwards on each side
    slider_min = time[ (int) ( ( len(time) ) * .05 ) ]
    slider_max = time[ (int) ( ( len(time) ) * .95 ) ]

    # Update sliding interval lines
    dpg.set_value("min_line_thrust", slider_min)
    dpg.set_value("max_line_thrust", slider_max)
    dpg.set_value("min_line_pressure", slider_min)
    dpg.set_value("max_line_pressure", slider_max)
    
    populate_graphs(time, thrusts, pressures)


def populate_graphs_interval_callback():
    """
    Called when the user clicks 'Graph selected interval".
    Parses the JSON file (selected at startup) and populates the plots with the computed data.
    plots will be narrowed to the data only existing within the specified interval of the JSON file.
    Also display the video path
    """

    trimmed_time = []
    trimmed_thrusts = []
    trimmed_pressures = []

    time, thrusts, pressures = read_data()


    time_min = dpg.get_value("min_line_thrust")
    time_max = dpg.get_value("max_line_thrust")

    min_index = 0
    max_index = 0
    for i, t in enumerate(time):
        if (t <= time_min): min_index = i
        if (t <= time_max): max_index = i

    # Copy everything within the interval to trimmed lists
    for i in range(min_index, max_index):
      trimmed_time.append(time[i])
      trimmed_thrusts.append(thrusts[i])
      trimmed_pressures.append(pressures[i])
        
    populate_interval_window_callback(trimmed_time, trimmed_thrusts, trimmed_pressures)

def populate_graphs(time, thrusts, pressures):
    """
    Callback helper function for graph population callbacks
    """
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

def populate_interval_window_callback(time, thrusts, pressures):
    """
    Callback to populate the interval selection window with interval values
    """
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
    dpg.set_value("avg_thrust_interval", " Average Thrust: " + '{0:,.2f}'.format(avg_thrust) + " N")
    dpg.set_value("max_thrust_interval", " Max Thrust: " + '{0:,.2f}'.format(max_thrust) + " N")
    dpg.set_value("avg_pressure_interval", " Average Pressure: " + '{0:,.2f}'.format(avg_pressure) + " PSI")
    dpg.set_value("max_pressure_interval", " Max Pressure: " + '{0:,.2f}'.format(max_pressure) + " PSI")
    dpg.set_value("burn_time_interval", " Burn Time: " + '{0:.2f}'.format(burn_time) + " s")
    dpg.set_value("total_impulse_interval", " Total Impulse: " + '{0:.2f}'.format(total_impulse) + " Ns")
    dpg.set_value("motor_desig_interval", " Motor Designation: " + motor_class + '{0:.0f}'.format(avg_thrust))



def thrust_line_callback():
    """
    Called when the user updates the graph interval for thrust.
    """
    min = dpg.get_value("min_line_thrust")
    max = dpg.get_value("max_line_thrust")

    dpg.set_value("min_line_pressure", min)
    dpg.set_value("max_line_pressure", max)


def pressure_line_callback():
    """
    Called when the user updates the graph interval for pressure.
    """
    min = dpg.get_value("min_line_pressure")
    max = dpg.get_value("max_line_pressure")

    dpg.set_value("min_line_thrust", min)
    dpg.set_value("max_line_thrust", max)

def exit_callback():
    global video_playing, video_capture
    video_playing = False
    with video_lock:
        if video_capture:
            video_capture.release()
            video_capture = None
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

# ------------------------------------------------------------------------
# VIDEO PLAYBACK FUNCTIONS (THREAD-SAFE)
# ------------------------------------------------------------------------

def play_video_callback(sender, app_data):
    """
    Toggles video playback. If the video file path is set, starts or stops the video loop.
    """
    global video_playing, video_capture, video_file, video_file_path, video_status

    if video_playing:
        # Stop the video
        video_playing = False
        with video_lock:
            if video_capture:
                video_capture.release()
                video_capture = None
        video_status = "Video stopped."
        return

    # Start the video
    if video_file_path:
        video_file = video_file_path
    if not video_file:
        video_status = "No video file specified."
        return

    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        video_status = f"Failed to open video: {video_file}"
        return

    # If we got here, we can start playing
    with video_lock:
        video_capture = cap
        video_playing = True

    video_status = "Playing video..."
    threading.Thread(target=video_loop, daemon=True).start()

def video_loop():
    """
    Reads frames in a background thread, converts them to RGBA, 
    and places them in frame_queue for the main thread to display.
    """
    global video_playing, video_capture, video_status
    fps = 25
    with video_lock:
        if video_capture:
            probe_fps = video_capture.get(cv2.CAP_PROP_FPS)
            if probe_fps > 0:
                fps = probe_fps
    frame_duration = 1.0 / fps

    while True:
        with video_lock:
            if not video_playing or not video_capture:
                break
            ret, frame = video_capture.read()

        if not ret:
            # No more frames or read error
            break

        # Convert BGR -> RGBA
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        # Resize to (640, 480)
        frame = cv2.resize(frame, (640, 480))
        frame = frame.astype(np.float32) / 255.0
        frame_data = frame.flatten().tolist()

        # Push frame data into the queue
        frame_queue.put(frame_data)

        time.sleep(frame_duration)

    # Once done, stop playback
    with video_lock:
        video_playing = False
        if video_capture:
            video_capture.release()
            video_capture = None
    video_status = "Video playback ended."

# ------------------------------------------------------------------------
# UI BUILDING
# ------------------------------------------------------------------------

def build_ui():
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
                dpg.add_drag_line(label="min", color=[0, 255, 0, 255], tag="min_line_thrust", callback=thrust_line_callback)
                dpg.add_drag_line(label="max", color=[255, 0, 0, 255],  tag="max_line_thrust", callback=thrust_line_callback)

            # Pressure Plot
            with dpg.plot(label="Pressure Data", height=160, width=-1, tag="pressure_plot"):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_pressure")
                with dpg.plot_axis(dpg.mvYAxis, label="Pressure (PSI)", tag="y_axis_pressure"):
                    dpg.add_line_series([], [], label="Pressure Data", tag="pressure_series")
                dpg.add_drag_line(label="min", color=[0, 255, 0, 255], tag="min_line_pressure", callback=pressure_line_callback)
                dpg.add_drag_line(label="max", color=[255, 0, 0, 255],  tag="max_line_pressure", callback=pressure_line_callback)






        # Function to add text stats to the child window
        def add_stat_text(parent, tag_prefix, color_mapping):
            with dpg.child_window(parent=parent, width=-1, height=180):
                dpg.add_text(f"Average Thrust:  N", tag=f"{tag_prefix}_avg_thrust", color=color_mapping['avg_thrust'])
                dpg.add_text(f"Max Thrust:  N", tag=f"{tag_prefix}_max_thrust", color=color_mapping['max_thrust'])
                dpg.add_text(f"Average Pressure:  PSI", tag=f"{tag_prefix}_avg_pressure", color=color_mapping['avg_pressure'])
                dpg.add_text(f"Max Pressure:  PSI", tag=f"{tag_prefix}_max_pressure", color=color_mapping['max_pressure'])
                dpg.add_text(f"Burn Time:  s", tag=f"{tag_prefix}_burn_time", color=color_mapping['burn_time'])
                dpg.add_text(f"Total Impulse:  Ns", tag=f"{tag_prefix}_total_impulse", color=color_mapping['total_impulse'])
                dpg.add_text(f"Motor Designation: ", tag=f"{tag_prefix}_motor_desig", color=color_mapping['motor_desig'])

        # Color mappings for the stats to maintain consistency
        color_scheme = {
            "avg_thrust": (0, 255, 255),
            "max_thrust": (255, 200, 200),
            "avg_pressure": (200, 255, 200),
            "max_pressure": (255, 255, 0),
            "burn_time": (255, 165, 0),
            "total_impulse": (255, 105, 180),
            "motor_desig": (100, 200, 255),
        }

        # Buttons
        dpg.add_button(label="Restore graphs", callback=populate_graphs_callback)
        dpg.add_button(label="Graph/Calculate for selected interval", callback=populate_graphs_interval_callback)

        # Key stats sections
        add_stat_text(parent=None, tag_prefix="avg", color_mapping=color_scheme)
        add_stat_text(parent=None, tag_prefix="avg_interval", color_mapping=color_scheme)




        dpg.add_button(label="Restore graphs", callback=populate_graphs_callback)
        dpg.add_button(label="Graph/Calculate for selected interval", callback=populate_graphs_interval_callback)
        
        # Key stats section
        with dpg.child_window(width=-1, height=180):
            dpg.add_text(" Average Thrust:  N", tag="avg_thrust", color=(0, 255, 255))
            dpg.add_text(" Max Thrust:  N", tag="max_thrust", color=(255, 200, 200))
            dpg.add_text(" Average Pressure:  PSI", tag="avg_pressure", color=(200, 255, 200))
            dpg.add_text(" Max Pressure:  PSI", tag="max_pressure", color=(255, 255, 0))
            dpg.add_text(" Burn Time:  s", tag="burn_time", color=(255, 165, 0))
            dpg.add_text(" Total Impulse:  Ns", tag="total_impulse", color=(255, 105, 180))
            dpg.add_text(" Motor Designation: ", tag="motor_desig", color=(100, 200, 255))

        # Key stats section 2
        with dpg.child_window(width=-1, height=180):
            dpg.add_text(" Average Thrust:  N", tag="avg_thrust_interval", color=(0, 255, 255))
            dpg.add_text(" Max Thrust:  N", tag="max_thrust_interval", color=(255, 200, 200))
            dpg.add_text(" Average Pressure:  PSI", tag="avg_pressure_interval", color=(200, 255, 200))
            dpg.add_text(" Max Pressure:  PSI", tag="max_pressure_interval", color=(255, 255, 0))
            dpg.add_text(" Burn Time:  s", tag="burn_time_interval", color=(255, 165, 0))
            dpg.add_text(" Total Impulse:  Ns", tag="total_impulse_interval", color=(255, 105, 180))
            dpg.add_text(" Motor Designation: ", tag="motor_desig_interval", color=(100, 200, 255))
        
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_text(" Rocket Test Video", color=(255, 140, 0))

        with dpg.child_window(width=-1, height=200):
            dpg.add_text("Video Path: ", tag="video_path_label", color=(255,255,0))
            dpg.add_image("video_texture")
            dpg.add_button(label="Play/Pause Video", callback=play_video_callback, width=200)
            dpg.add_text("", tag="video_status")

    with dpg.menu_bar():
        dpg.add_menu_item(label="About")
        dpg.add_menu_item(label="Help")
        dpg.add_menu_item(label="Exit", callback=exit_callback)

    dpg.add_text("FreakAlyze")
    dpg.add_spacer(height=5)

# ------------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------------

def determine_motor_class(impulse):
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

    for ts in data['time_values_seconds']:
       time.append(ts)

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
    with dpg.texture_registry():
        # Create a dynamic texture for the video frames (640x480, RGBA)
        default_texture_data = [0.0] * (640 * 480 * 4)
        dpg.add_dynamic_texture(640, 480, default_texture_data, tag="video_texture")

    dpg.create_viewport(title="FreakAlyze", width=1000, height=700, resizable=True)
    dpg.setup_dearpygui()
    dpg.set_viewport_resize_callback(resize_callback)

    with dpg.window(tag="Primary Window", label="", no_title_bar=True, width=1000, height=700, pos=(0, 0)):
        build_ui()

    with dpg.file_dialog(directory_selector=False, show=False, callback=lambda s,a: None, tag="file_dialog_id"):
        dpg.add_file_extension(".json")

    dpg.show_viewport()

    # --------------------- MANUAL RENDER LOOP ---------------------
    while dpg.is_dearpygui_running():
        # If we have a new frame, update the texture in the main thread
        if not frame_queue.empty():
            new_frame = frame_queue.get()
            dpg.set_value("video_texture", new_frame)

        # Update the status text each frame
        dpg.set_value("video_status", video_status)

        # Render a single Dear PyGui frame
        dpg.render_dearpygui_frame()

    dpg.destroy_context()
