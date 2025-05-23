import os
import json
import sys # for shutdown
import dearpygui.dearpygui as dpg
from scipy import integrate
import cv2
import numpy as np
import threading
import time
import webbrowser
from queue import Queue  # Thread-safe frame transfer

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
dir_path = ""

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
    time_data, thrusts, pressures = read_data()

    # Starting points for sliders, put them 5% inwards on each side
    slider_min = time_data[int(len(time_data) * 0.05)]
    slider_max = time_data[int(len(time_data) * 0.95)]

    # Update sliding interval lines
    dpg.set_value("min_line_thrust", slider_min)
    dpg.set_value("max_line_thrust", slider_max)
    dpg.set_value("min_line_pressure", slider_min)
    dpg.set_value("max_line_pressure", slider_max)
    
    populate_graphs(time_data, thrusts, pressures)


def populate_interval_window_callback():
    """
    Called when the user clicks 'Graph selected interval".
    Parses the JSON file and populates the plots with data only from the specified interval.
    """
    trimmed_time = []
    trimmed_thrusts = []
    trimmed_pressures = []

    time_data, thrusts, pressures = read_data()

    if thrusts:
        time_min = dpg.get_value("min_line_thrust")
        time_max = dpg.get_value("max_line_thrust")
    elif pressures:
        time_min = dpg.get_value("min_line_pressure")
        time_max = dpg.get_value("max_line_pressure")
    else:
        messagebox.showerror(
            "Alert",
            "No data to be plotted"
        )
        return time_data, thrusts, pressures

    min_index = 0
    max_index = 0
    for i, t in enumerate(time_data):
        if t <= time_min:
            min_index = i
        if t <= time_max:
            max_index = i

    # Copy data within the interval
    for i in range(min_index, max_index):
        if time_data: trimmed_time.append(time_data[i])
        if thrusts: trimmed_thrusts.append(thrusts[i])
        if pressures: trimmed_pressures.append(pressures[i])
        
    populate_interval_window(trimmed_time, trimmed_thrusts, trimmed_pressures)

def populate_graphs(time_data, thrusts, pressures):
    """
    Callback helper function for graph population callbacks.
    Calculates key stats and updates the graph series and stat labels.
    """
    # Calculate key stats/motor characteristics
    burn_time = time_data[-1] if time_data else 0.0

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
    
    total_impulse = integrate.simpson(thrusts, x=time_data) if thrusts else 0.0

    motor_class = determine_motor_class(total_impulse)

    # Update plot series
    if pressures:
        dpg.set_item_label("pressure_series", "Pressure Data")
        dpg.set_value("pressure_series", [time_data, pressures])
    if thrusts:
        dpg.set_item_label("thrust_series", "Thrust Data")
        dpg.set_value("thrust_series", [time_data, thrusts])
    
    # Update key stats labels
    dpg.set_value("avg_thrust", " Average Thrust: " + '{0:,.2f}'.format(avg_thrust) + " N")
    dpg.set_value("max_thrust", " Max Thrust: " + '{0:,.2f}'.format(max_thrust) + " N")
    dpg.set_value("avg_pressure", " Average Pressure: " + '{0:,.2f}'.format(avg_pressure) + " PSI")
    dpg.set_value("max_pressure", " Max Pressure: " + '{0:,.2f}'.format(max_pressure) + " PSI")
    dpg.set_value("burn_time", " Burn Time: " + '{0:.2f}'.format(burn_time) + " s")
    dpg.set_value("total_impulse", " Total Impulse: " + '{0:.2f}'.format(total_impulse) + " Ns")
    dpg.set_value("motor_desig", " Motor Designation: " + motor_class + '{0:.0f}'.format(avg_thrust))

    # Adjust plot axes to fit the new data
    if pressures:
        dpg.fit_axis_data("x_axis_pressure")
        dpg.fit_axis_data("y_axis_pressure")
    if thrusts:
        dpg.fit_axis_data("y_axis_thrust")
        dpg.fit_axis_data("x_axis_thrust")

    # Show the video path in the UI
    dpg.set_value("video_path_label", f"Video Path: {video_file_path}")

def populate_interval_window(time_data, thrusts, pressures):
    """
    Callback to populate the interval selection window with interval values.
    """
    burn_time = time_data[-1] if time_data else 0.0

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

    total_impulse = integrate.simpson(thrusts, x=time_data) if thrusts else 0.0

    motor_class = determine_motor_class(total_impulse)

    # Update interval-specific key stats labels
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
    min_val = dpg.get_value("min_line_thrust")
    max_val = dpg.get_value("max_line_thrust")

    dpg.set_value("min_line_pressure", min_val)
    dpg.set_value("max_line_pressure", max_val)

    # Update interval stats
    populate_interval_window_callback()


def pressure_line_callback():
    """
    Called when the user updates the graph interval for pressure.
    """
    min_val = dpg.get_value("min_line_pressure")
    max_val = dpg.get_value("max_line_pressure")

    dpg.set_value("min_line_thrust", min_val)
    dpg.set_value("max_line_thrust", max_val)

    # Update interval stats
    populate_interval_window_callback()


def exit_callback():
    global video_playing, video_capture
    video_playing = False
    with video_lock:
        if video_capture:
            video_capture.release()
            video_capture = None
    dpg.stop_dearpygui()

#this will take you to our github if you press the "help" button
def help_callback(sender, app_data, user_data):
    webbrowser.open("https://github.com/Team-Freak-Mizzou/FREAKalyze")

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
    dpg.set_value("time_line_thrust", 0)
    dpg.set_value("time_line_pressure", 0)
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

    i = 0

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
        # Resize to (800, 600) for a larger display
        frame = cv2.resize(frame, (800, 600))
        frame = frame.astype(np.float32) / 255.0
        frame_data = frame.flatten().tolist()

        # Push frame data into the queue
        frame_queue.put(frame_data)

        shift_video_line(frame_duration)
        time.sleep(frame_duration)

    # Once done, stop playback
    with video_lock:
        video_playing = False
        if video_capture:
            video_capture.release()
            video_capture = None
    video_status = "Video playback ended."


def shift_video_line(shift):
    """
    Invoked when the line for video playback should be moved
    """
    curr = dpg.get_value("time_line_thrust")
    curr += shift

    dpg.set_value("time_line_thrust", curr)
    dpg.set_value("time_line_pressure", curr)

# ------------------------------------------------------------------------
# UI BUILDING
# ------------------------------------------------------------------------

def build_ui():
    with dpg.group():
        # Top-level button with extra width and padding
        dpg.add_button(label="Populate Graphs and Load Camera Feed", callback=populate_graphs_callback, width=250)
        dpg.add_spacer(height=10)
        
        # Plots section
        with dpg.child_window(width=-1, height=350):
            # Thrust Plot
            with dpg.plot(label="Thrust Data", height=160, width=-1, tag="thrust_plot"):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_thrust")
                with dpg.plot_axis(dpg.mvYAxis, label="Thrust (N)", tag="y_axis_thrust"):
                    dpg.add_line_series([], [], label="Thrust Data", tag="thrust_series")
                dpg.add_drag_line(label="min", color=[0, 255, 0, 255], tag="min_line_thrust", callback=thrust_line_callback)
                dpg.add_drag_line(label="max", color=[255, 0, 0, 255], tag="max_line_thrust", callback=thrust_line_callback)
                dpg.add_drag_line(label="video", color=[0, 0, 0, 255], tag="time_line_thrust", default_value=0)

            # Pressure Plot
            with dpg.plot(label="Pressure Data", height=160, width=-1, tag="pressure_plot"):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_pressure")
                with dpg.plot_axis(dpg.mvYAxis, label="Pressure (PSI)", tag="y_axis_pressure"):
                    dpg.add_line_series([], [], label="Pressure Data", tag="pressure_series")
                dpg.add_drag_line(label="min", color=[0, 255, 0, 255], tag="min_line_pressure", callback=pressure_line_callback)
                dpg.add_drag_line(label="max", color=[255, 0, 0, 255], tag="max_line_pressure", callback=pressure_line_callback)
                dpg.add_drag_line(label="video", color=[0, 0, 0, 255], tag="time_line_pressure", default_value=0)
                
        dpg.add_button(label="Restore graphs", callback=populate_graphs_callback, width=200)
        dpg.add_spacer(height=15)
        
        # Key Stats Sections: Overall and Interval-specific side by side
        with dpg.group(horizontal=True):
            with dpg.child_window(width=600, height=250, border=True):
                dpg.add_text("Overall dataset characteristics", color=(255, 140, 0))
                dpg.add_spacer(height=5)
                dpg.add_text(" Average Thrust:  N", tag="avg_thrust", color=(0, 255, 255))
                dpg.add_text(" Max Thrust:  N", tag="max_thrust", color=(255, 200, 200))
                dpg.add_text(" Average Pressure:  PSI", tag="avg_pressure", color=(200, 255, 200))
                dpg.add_text(" Max Pressure:  PSI", tag="max_pressure", color=(255, 255, 0))
                dpg.add_text(" Burn Time:  s", tag="burn_time", color=(255, 165, 0))
                dpg.add_text(" Total Impulse:  Ns", tag="total_impulse", color=(255, 105, 180))
                dpg.add_text(" Motor Designation: ", tag="motor_desig", color=(100, 200, 255))
            with dpg.child_window(width=600, height=250, border=True):
                dpg.add_text("Interval-specific dataset characteristics", color=(255, 140, 0))
                dpg.add_spacer(height=5)
                dpg.add_text(" Average Thrust:  N", tag="avg_thrust_interval", color=(0, 255, 255))
                dpg.add_text(" Max Thrust:  N", tag="max_thrust_interval", color=(255, 200, 200))
                dpg.add_text(" Average Pressure:  PSI", tag="avg_pressure_interval", color=(200, 255, 200))
                dpg.add_text(" Max Pressure:  PSI", tag="max_pressure_interval", color=(255, 255, 0))
                dpg.add_text(" Burn Time:  s", tag="burn_time_interval", color=(255, 165, 0))
                dpg.add_text(" Total Impulse:  Ns", tag="total_impulse_interval", color=(255, 105, 180))
                dpg.add_text(" Motor Designation: ", tag="motor_desig_interval", color=(100, 200, 255))
                
        dpg.add_spacer(height=15)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Video Section with improved layout
        dpg.add_text("Rocket Test Video", color=(255, 140, 0), bullet=True)
        # Video control button moved to the top of the video section
        dpg.add_button(label="Play/Pause Video", callback=play_video_callback, width=200)
        dpg.add_spacer(height=5)
        dpg.add_text("Video Path: ", tag="video_path_label", color=(255, 255, 0))
        dpg.add_spacer(height=5)
        # Enlarged video window with a border; updated to 800x600 display
        with dpg.child_window(width=-1, height=600, border=True):
            dpg.add_image("video_texture")
        dpg.add_spacer(height=5)
        dpg.add_text("", tag="video_status")
    
    # Menu Bar at the top
    with dpg.menu_bar():
        dpg.add_menu_item(label="Help", callback=help_callback)
        dpg.add_menu_item(label="Choose new folder", callback=open_folder_dialogue)
        dpg.add_menu_item(label="Exit", callback=exit_callback)
    
    dpg.add_spacer(height=10)
    dpg.add_text("FreakAlyze", color=(200, 200, 200))
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

def trim_to_smallest_nonempty(*lists):
    # Filter out empty lists
    non_empty_lists = [lst for lst in lists if lst]
    if not non_empty_lists:
        return [[] for _ in lists]  # All lists are empty

    # Find the minimum length among non-empty lists
    min_len = min(len(lst) for lst in non_empty_lists)

    # Trim all lists to that length
    return [lst[:min_len] for lst in lists]

def read_data():
    """
    Parses the JSON file (specified by file_path) for graphing,
    converting raw voltage readings into thrust (N) and pressure (PSI) values.
    """
    global file_path
    if not file_path or not os.path.isfile(file_path):
        return [], [], []

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except:
        messagebox.showerror(
            "Alert",
            "Unable to read .json data file. Please verify that all fields are formatted correctly."
        )
        return [], [], []

    loads = []
    pressures = []
    time_data = []

    # Convert load cell data into Newtons
    try:
        for lv in data['load_cell_voltages_mv']:
            loadAdjVoltage = (lv - 1.25) / 201
            calibratedLoad = 100387.5 * loadAdjVoltage - 3.8069375
            calibratedLoad = calibratedLoad * 9.81
            loads.append(calibratedLoad)
    except:
        print("Invalid load cell values")

    # Convert transducer data into PSI
    try:
        for pv in data['pressure_transducer_voltages_v']:
            pressAdjVoltage = pv - TRANSDUCERMINVOLTAGE
            pressure = pressAdjVoltage * TRANSDUCERSCALINGFACTOR
            pressures.append(pressure)
    except:
        print("Invalid pressure values")

    try:
        for ts in data['time_values_seconds']:
            time_data.append(ts)
    except:
        messagebox.showerror(
            "Alert",
            "Invalid timestamp values. Exiting."
        )
        sys.exit(1) # Not working?

    time_data_tr, loads_tr, pressures_tr = trim_to_smallest_nonempty(time_data, loads, pressures)

    return (time_data_tr, loads_tr, pressures_tr)


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

def open_folder_dialogue():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    dir_path = filedialog.askdirectory(title="Select a Directory Containing JSON & MP4")
    root.destroy()

    # If the user selected a directory, find the .json and .mp4
    if dir_path == "":
        exit()
    else:
        json_file, mp4_file = find_files_in_directory(dir_path)
        if json_file:
            global file_path
            file_path = json_file
        if mp4_file:
            global video_file_path
            video_file_path = mp4_file

# ------------------------------------------------------------------------
# MAIN APPLICATION SETUP
# ------------------------------------------------------------------------

if __name__ == "__main__":
    # Prompt for directory selection using Tkinter before launching the GUI
    import tkinter as tk
    from tkinter import filedialog
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    dir_path = filedialog.askdirectory(title="Select a Directory Containing JSON & MP4")
    root.destroy()

    # If the user selected a directory, find the .json and .mp4
    if dir_path == "":
        exit()
    else:
        json_file, mp4_file = find_files_in_directory(dir_path)
        if json_file:
            file_path = json_file
        if mp4_file:
            video_file_path = mp4_file

    if not json_file and not mp4_file:
        messagebox.showerror(
            "Alert",
            "Missing Files: Startup folder must contain both a .json and an .mp4.  Exiting."
        )
        sys.exit(1)
    
    if not json_file:
        messagebox.showerror(
            "Alert",
            "Missing JSON: You can continue, but graphing is not available"
        )

    if not mp4_file:
        messagebox.showerror(
            "Alert",
            "Missing MP4: You can continue, but video playback is not available"
        )

    # Setup and launch the Dear PyGui application
    dpg.create_context()
    
    # ------------------ CUSTOM THEME ------------------
    with dpg.theme() as my_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [30, 30, 30, 255])      # Dark window background
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, [45, 45, 45, 255])       # Child window background
            dpg.add_theme_color(dpg.mvThemeCol_Button, [70, 130, 180, 255])      # Steel blue buttons
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [90, 150, 200, 255])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [50, 110, 160, 255])
            dpg.add_theme_color(dpg.mvThemeCol_Text, [220, 220, 220, 255])         # Light text color
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 10)               # Rounded window corners
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)                 # Rounded child frames
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 8)                # Spacing between items
    dpg.bind_theme(my_theme)
    # ----------------------------------------------------

    with dpg.texture_registry():
        # Create a dynamic texture for the video frames (800x600, RGBA)
        default_texture_data = [0.0] * (800 * 600 * 4)
        dpg.add_dynamic_texture(800, 600, default_texture_data, tag="video_texture")

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
