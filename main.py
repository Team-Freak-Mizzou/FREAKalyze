import json
import dearpygui.dearpygui as dpg
from scipy import integrate
import cv2
import numpy as np
import threading
import time

# NAMED CONSTANTS FOR CONVERSIONS, maybe move in future?
TRANSDUCERMINVOLTAGE = 0.5
TRANSDUCERMAXVOLTAGE = 4.5
TRANSDUCERMAXPRESSURE = 1600  # In PSI
TRANSDUCERSCALINGFACTOR = TRANSDUCERMAXPRESSURE / (TRANSDUCERMAXVOLTAGE - TRANSDUCERMINVOLTAGE)
file_path = ''

# Global variables for video playback
video_file = ''
video_playing = False
video_capture = None

# -------------------------
# Callback stubs
# -------------------------

def upload_file_callback(sender, app_data):
    """
    Called when user selects a file.
    Sets a label to show the file chosen.
    """
    if "file_path_name" in app_data:
        global file_path 
        file_path = app_data['file_path_name']
    dpg.set_value("file_label", f"File: {file_path} Successfully Uploaded")

def populate_graphs_callback():
    """
    Called when user clicks 'Populate Graphs and Load Camera Feed'.
    Loads data from the uploaded JSON file, populates the graphs,
    and (if present) reads the video file path.
    """
    # Get the data lists for graphing and video info
    time_data, pressures, loads = read_data()

    # Calculate key stats/motor characteristics
    burn_time = time_data[-1]
    avg_thrust = sum(loads) / len(loads)
    avg_pressure = sum(pressures) / len(pressures)
    max_thrust = max(loads)
    max_pressure = max(pressures)
    total_impulse = integrate.simpson(loads, x=time_data)
    motor_class = determine_motor_class(total_impulse)

    # Update plots with the new data
    dpg.set_item_label("thrust_series", "Thrust Data")
    dpg.set_item_label("pressure_series", "Pressure Data")
    dpg.set_value("thrust_series", [time_data, loads])
    dpg.set_value("pressure_series", [time_data, pressures])
    
    # Update key statistics
    dpg.set_value("avg_thrust", "Average Thrust: " + '{0:,.2f}'.format(avg_thrust) + " N")
    dpg.set_value("max_thrust", "Max Thrust: " + '{0:,.2f}'.format(max_thrust) + " N")
    dpg.set_value("avg_pressure", "Average Pressure: " + '{0:,.2f}'.format(avg_pressure) + " PSI")
    dpg.set_value("max_pressure", "Max Pressure: " + '{0:,.2f}'.format(max_pressure) + " PSI")
    dpg.set_value("burn_time", "Burn Time: " + '{0:.2f}'.format(burn_time) + " s")
    dpg.set_value("total_impulse", "Total Impulse: " + '{0:.2f}'.format(total_impulse) + " Ns")
    dpg.set_value("motor_desig", "Motor Designation: " + motor_class + ' ' + '{0:.0f}'.format(avg_thrust))

    # Resize plot axes to fit new data
    dpg.fit_axis_data("y_axis_thrust")
    dpg.fit_axis_data("y_axis_pressure")
    dpg.fit_axis_data("x_axis_thrust")
    dpg.fit_axis_data("x_axis_pressure")

def exit_callback():
    """Called when 'Exit' is clicked."""
    dpg.stop_dearpygui()

def resize_callback(sender, app_data, user_data):
    """Adjust UI elements dynamically when the viewport is resized."""
    width, height = dpg.get_viewport_width(), dpg.get_viewport_height()
    if dpg.does_item_exist("Primary Window"):
        dpg.set_item_width("Primary Window", width)
        dpg.set_item_height("Primary Window", height)
    if dpg.does_item_exist("left_panel"):
        dpg.set_item_width("left_panel", width * 0.3)
    if dpg.does_item_exist("right_panel"):
        dpg.set_item_width("right_panel", width * 0.7)
    if dpg.does_item_exist("thrust_plot"):
        dpg.set_item_width("thrust_plot", width * 0.68)
    if dpg.does_item_exist("pressure_plot"):
        dpg.set_item_width("pressure_plot", width * 0.68)

# -------------------------
# Video Playback Functions
# -------------------------

def play_video_callback(sender, app_data):
    """
    Callback to start or stop video playback.
    If a video file was specified in the JSON, this function opens the video
    and starts a background thread to update the video frame.
    """
    global video_playing, video_capture, video_file
    if video_file == '':
        dpg.set_value("video_status", "No video file specified in JSON.")
        return
    if not video_playing:
        video_capture = cv2.VideoCapture(video_file)
        if not video_capture.isOpened():
            dpg.set_value("video_status", f"Failed to open video: {video_file}")
            return
        video_playing = True
        threading.Thread(target=video_loop, daemon=True).start()
        dpg.set_value("video_status", "Playing video...")
    else:
        video_playing = False
        if video_capture:
            video_capture.release()
        dpg.set_value("video_status", "Video stopped.")

def video_loop():
    """
    Loop that reads video frames and updates the dynamic texture.
    """
    global video_playing, video_capture
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25
    frame_duration = 1.0 / fps
    while video_playing:
        ret, frame = video_capture.read()
        if not ret:
            break
        # Convert frame from BGR to RGBA and resize to texture dimensions (640x480)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        frame = cv2.resize(frame, (640, 480))
        # Normalize pixel values and flatten the frame for Dear PyGui
        frame = frame.astype(np.float32) / 255.0
        frame_data = frame.flatten().tolist()
        # Use invoke to update the texture from the main thread
        dpg.invoke(lambda: dpg.set_value("video_texture", frame_data))
        time.sleep(frame_duration)
    video_playing = False
    if video_capture:
        video_capture.release()
    dpg.invoke(lambda: dpg.set_value("video_status", "Video playback ended."))

# -------------------------
# Building the UI
# -------------------------

def build_ui():
    """
    Build the entire UI layout.
    """
    # Main menu bar across the top
    with dpg.menu_bar():
        dpg.add_menu_item(label="File Upload", callback=lambda: dpg.configure_item("file_dialog_id", show=True))
        dpg.add_menu_item(label="Download")
        dpg.add_menu_item(label="About")
        dpg.add_menu_item(label="Help")
        dpg.add_menu_item(label="Exit", callback=exit_callback)
    
    # Title banner
    dpg.add_text("FreakAlyze")
    dpg.add_spacer(height=5)
    
    # Main horizontal layout: left panel and right panel
    with dpg.group(horizontal=True):
        # Left Panel
        with dpg.child_window(width=300, autosize_y=True):
            dpg.add_text("Choose a file or drag it here", wrap=250)
            dpg.add_text("", tag="file_label")
            dpg.add_button(label="Populate Graphs and Load Camera Feed", callback=populate_graphs_callback)
        
        # Right Panel (plots and key stats)
        with dpg.group():
            with dpg.child_window(width=-1, height=350):
                # Thrust Plot
                with dpg.plot(label="Thrust Data", height=160, width=-1):
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_thrust")
                    with dpg.plot_axis(dpg.mvYAxis, label="Thrust (N)", tag="y_axis_thrust"):
                        dpg.add_line_series([], [], label="Thrust Data", tag="thrust_series")
                # Pressure Plot
                with dpg.plot(label="Pressure Data", height=160, width=-1):
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_pressure")
                    with dpg.plot_axis(dpg.mvYAxis, label="Pressure (PSI)", tag="y_axis_pressure"):
                        dpg.add_line_series([], [], label="Pressure Data", tag="pressure_series")
            
            # Key stats at the bottom
            with dpg.child_window(width=-1, height=180):
                dpg.add_text("Average Thrust: N", tag="avg_thrust")
                dpg.add_text("Max Thrust: N", tag="max_thrust")
                dpg.add_text("Average Pressure: PSI", tag="avg_pressure")
                dpg.add_text("Max Pressure: PSI", tag="max_pressure")
                dpg.add_text("Burn Time: s", tag="burn_time")
                dpg.add_text("Total Impulse: Ns", tag="total_impulse")
                dpg.add_text("Motor Designation:", tag="motor_desig")
    
    dpg.add_spacer(height=10)
    
    # "Rocket Test Video" section
    dpg.add_separator()
    dpg.add_text("Rocket Test Video", color=(255, 140, 0))
    
    # Video display area with an image widget, a play/pause button, and a status text
    with dpg.child_window(width=-1, height=300):
        dpg.add_image("video_texture")
        dpg.add_button(label="Play/Pause Video", callback=play_video_callback)
        dpg.add_text("", tag="video_status")

# -------------------------
# Graphing/crunching imported data
# -------------------------

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
    Parse JSON for graph data and (if available) video information.
    """
    f = open(file_path, 'r')
    data = json.load(f)

    # If the JSON contains a video file, store its path globally.
    if "video_file" in data:
        global video_file
        video_file = data["video_file"]

    loads = []
    pressures = []
    time_list = []

    # Convert load cell voltages to force (N)
    for lv in data['load_cell_voltages_mv']:
        loadVoltage = lv
        loadAdjVoltage = (loadVoltage - 1.25) / 201
        calibratedLoad = 100387.5 * loadAdjVoltage - 3.8069375
        calibratedLoad = calibratedLoad * 9.81
        loads.append(calibratedLoad)

    # Convert pressure transducer voltages to PSI
    for pv in data['pressure_transducer_voltages_v']:
        pressVoltage = pv
        pressAdjVoltage = pressVoltage - TRANSDUCERMINVOLTAGE
        pressure = pressAdjVoltage * TRANSDUCERSCALINGFACTOR
        pressures.append(pressure)
       
    n_press_samples = len(pressures)
    n_ld_samples = len(loads)
    n_samples = min(n_ld_samples, n_press_samples)
    sample_rate = data['sample_rate']

    for i in range(n_samples):
        time_list.append(round((i + 1) * (1 / sample_rate), 3))

    return (time_list, pressures, loads)

# -------------------------
# Main script
# -------------------------

if __name__ == "__main__":
    dpg.create_context()
    
    # Create a texture registry and register the dynamic texture inside it
    with dpg.texture_registry():
        default_texture_data = [0.0] * (640 * 480 * 4)
        dpg.add_dynamic_texture(640, 480, default_texture_data, tag="video_texture")
    
    dpg.create_viewport(title="FreakAlyze", width=1000, height=700, resizable=True)
    dpg.setup_dearpygui()
    dpg.set_viewport_resize_callback(resize_callback)
    
    with dpg.window(tag="Primary Window", label="", no_title_bar=True, width=1000, height=700, pos=(0, 0)):
        build_ui()
    
    with dpg.file_dialog(directory_selector=False, show=False, callback=upload_file_callback, tag="file_dialog_id"):
        dpg.add_file_extension(".json")
    
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
