import json
import dearpygui.dearpygui as dpg
from scipy import integrate
from filedialogs import open_file_dialog
import DearPyGui_DragAndDrop as dpg_dnd

# NAMED CONSTANTS FOR CONVERSIONS, maybe move in future?
TRANSDUCERMINVOLTAGE = 0.5
TRANSDUCERMAXVOLTAGE = 4.5
TRANSDUCERMAXPRESSURE = 1600 #In PSI
TRANSDUCERSCALINGFACTOR = TRANSDUCERMAXPRESSURE / (TRANSDUCERMAXVOLTAGE-TRANSDUCERMINVOLTAGE)
file_path = ''

#FILENAME = './mock_data.json' # TODO: Add dynamic file pathing for imported JSON files (see read_data() function)

# -------------------------
# Callback stubs
# -------------------------

def populate_graphs_callback():
    """
    Called when user clicks 'Populate Graphs and Load Camera Feed'.
    In a real app, you would load data from the uploaded file,
    parse it, and fill in the plot series and any camera/video feed.
    """

    # Our lists to be used in graphing UI and motor characteristics/key stats
    time, thrusts, pressures = read_data()

    # Calculate key stats/motor characteristics
    burn_time = time[len(time)-1]
    avg_thrust = sum(thrusts) / len(thrusts)
    avg_pressure = sum(pressures) / len(pressures)
    max_thrust = max(thrusts)
    max_pressure = max(pressures)
    total_impulse = integrate.simpson(thrusts,x=time)
    motor_class = determine_motor_class(total_impulse)

    # For demonstration, just show some dummy lines on the plots
    dpg.set_item_label("thrust_series", "Thrust Data")
    dpg.set_item_label("pressure_series", "Pressure Data")
    
    # Thrust data (time vs thrust)
    dpg.set_value("thrust_series", [time, thrusts])
    
    # Pressure data (time vs pressure)
    dpg.set_value("pressure_series", [time, pressures])
    
    # Update the “average thrust,” etc. labels here.
    dpg.set_value("avg_thrust", "Average Thrust: " + '{0:,.2f}'.format(avg_thrust) + " N")
    dpg.set_value("max_thrust", "Max Thrust: " + '{0:,.2f}'.format(max_thrust) + " N")
    dpg.set_value("avg_pressure", "Average Pressure: " + '{0:,.2f}'.format(avg_pressure) + " PSI")
    dpg.set_value("max_pressure", "Max Pressure: " + '{0:,.2f}'.format(max_pressure) + " PSI")
    dpg.set_value("burn_time", "Burn Time: " + '{0:.2f}'.format(burn_time) + " s")
    dpg.set_value("total_impulse", "Total Impulse: " + '{0:.2f}'.format(total_impulse) + " Ns")
    dpg.set_value("motor_desig", "Motor Designation: " + motor_class + '{0:.0f}'.format(avg_thrust))

    # Resize the axes to fit the file data
    dpg.fit_axis_data("y_axis_thrust")
    dpg.fit_axis_data("y_axis_pressure")

    dpg.fit_axis_data("x_axis_thrust")
    dpg.fit_axis_data("x_axis_pressure")

def exit_callback():
    """
    Called when 'Exit' is clicked in the top bar.
    """
    dpg.stop_dearpygui()

def resize_callback(sender, app_data, user_data):
   """Adjust UI elements dynamically when the viewport is resized."""
   width, height = dpg.get_viewport_width(), dpg.get_viewport_height()
  
   # Only update if items exist
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


def upload_callback():
   """
   This is the new and improved file upload callback which uses
   a deliciously aesthetic and intuitive windows file picker dialogue
   :)
   """
   global file_path
   file_path = open_file_dialog()
   dpg.set_value("file_label", f"File: {file_path} Successfully Uploaded")

def drop(data, _):
   """
   This is the drag and drop functionality
   """
   global file_path
   file_path = data[0]
   dpg.set_value("file_label", f"File: {file_path} Successfully Uploaded")

# -------------------------
# Building the UI
# -------------------------

def build_ui():
    """
    Build the entire UI layout inside the primary window.
    """

    # Main menu bar across the top
    with dpg.menu_bar():
        # Just top-level items for simplicity
        dpg.add_menu_item(label="File Upload", callback=upload_callback)
        dpg.add_menu_item(label="Download")
        dpg.add_menu_item(label="About")
        dpg.add_menu_item(label="Help")
        dpg.add_menu_item(label="Exit", callback=exit_callback)
    
    # Title banner
    dpg.add_text("FreakAlyze")
    dpg.add_spacer(height=5)
    
    # Separate into two main sections horizontally: left panel and right panel
    with dpg.group(horizontal=True):
        
        # Left Panel
        with dpg.child_window(width=300, autosize_y=True):
            # Placeholder for "Choose a file or drag it here"
            dpg.add_text("Choose a file or drag it here", wrap=250)
            
            # Show the name of the file once loaded
            dpg.add_text("", tag="file_label")
            
            # Button that triggers graph/camera loading
            dpg.add_button(label="Populate Graphs and Load Camera Feed", callback=populate_graphs_callback)
        
        # Right Panel
        with dpg.group():
            
            # Plots/Results section
            with dpg.child_window(width=-1, height=350):
                # Thrust Plot
                with dpg.plot(label="Thrust Data", height=160, width=-1):
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_thrust")
                    with dpg.plot_axis(dpg.mvYAxis, label="Thrust (N)", tag="y_axis_thrust"):
                        # We'll add an empty series here and populate it later
                        dpg.add_line_series([], [], label="Thrust Data", tag="thrust_series")
                
                # Pressure Plot
                with dpg.plot(label="Pressure Data", height=160, width=-1):
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_pressure")
                    with dpg.plot_axis(dpg.mvYAxis, label="Pressure (PSI)", tag="y_axis_pressure"):
                        # We'll add an empty series here and populate it later
                        dpg.add_line_series([], [], label="Pressure Data", tag="pressure_series")
            
            # Key stats at the bottom
            with dpg.child_window(width=-1, height=180):
                dpg.add_text("Average Thrust: " + " N", tag="avg_thrust")
                dpg.add_text("Max Thrust: " + " N", tag = "max_thrust")
                dpg.add_text("Average Pressure: " + " PSI", tag="avg_pressure")
                dpg.add_text("Max Pressure: " + " PSI", tag="max_pressure")
                dpg.add_text("Burn Time: " + " s", tag="burn_time")
                dpg.add_text("Total Impulse: " + " Ns", tag="total_impulse")
                dpg.add_text("Motor Designation: ", tag="motor_desig")
    
    dpg.add_spacer(height=10)
    
    # "Rocket Test Video" section
    dpg.add_separator()
    dpg.add_text("Rocket Test Video", color=(255, 140, 0))
    
    # A child window to hold a mock video thumbnail or camera feed
    with dpg.child_window(width=-1, height=200):
        # For demonstration, we just show a button with some text or a placeholder image
        dpg.add_button(label="Play Video (Placeholder)")


# -------------------------
# Graphing/crunching imported data
# -------------------------

# Determines the motor class dependent on the specified impulse
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

# Main function to parse JSON for graphing purposes, translates imported voltages into thrust/pressure values
def read_data():
    # Open/point to the JSON file (input file to generate data from)
    f = open(file_path, 'r')
    data = json.load(f)

    # Declare lists
    loads = []
    pressures = []
    time = []

    # NOTE: Instead of averaging every X samples into one data entry, this is treating each sample as its own entry

    # Read and convert load_cell data into N
    for lv in data['load_cell_voltages_mv']:
       loadVoltage = lv
       #1.25 and 201 taken from dip switches active on the LJ-Tick-InAmp. For more info see https://labjack.com/pages/support?doc=/datasheets/accessories/ljtick-inamp-datasheet/
       loadAdjVoltage = (loadVoltage - 1.25) / 201
       #our load cell's senitivity is 2 mV/V
       #found by calculating the slope and intercept between two known weights and the adjusted voltage
       calibratedLoad = 100387.5 * loadAdjVoltage - 3.8069375
       #calibration value is set in kg, to get the reading in N, need to multiply by 9.81
       calibratedLoad = calibratedLoad * 9.81
       loads.append(calibratedLoad)

    # Read and convert transducer data into psi
    for pv in data['pressure_transducer_voltages_v']:
       pressVoltage = pv #/ num_samples
       pressAdjVoltage = pressVoltage - TRANSDUCERMINVOLTAGE
       pressure = pressAdjVoltage * TRANSDUCERSCALINGFACTOR
       pressures.append(pressure)
       
    # REMOVE IF WE MOVE FORWARD WITH TIMESTAMPING LOGIC INSTEAD OF FREQ
    # Until we have a better input file format, this is the best way to get the number of samples taken
    # n_press_samples = len(pressures)
    # n_ld_samples = len(loads)
    # n_samples = min(n_ld_samples, n_press_samples) # OR take max()
    # sample_rate = data['sample_rate']

    for ts in data['time_stamps']:
       time.append(ts)

    # REMOVE IF WE MOVE FORWARD WITH TIMESTAMPING LOGIC INSTEAD OF FREQ
    # Gets time array to "sync" data entries to graphs dependent on sampling rate and samples relative to a second
    # for i in range(n_samples):
    #     time.append( round( (float) ((i+1) * (float) (1/sample_rate)), 3) )

    return (time, pressures, loads)

# -------------------------
# Main script
# -------------------------

if __name__ == "__main__":
    dpg.create_context()
    dpg_dnd.initialize()
    dpg.create_viewport(title="FreakAlyze", width=1000, height=700, resizable=True)
    dpg_dnd.set_drop(drop)
    dpg.setup_dearpygui()

    # Bind the resize callback
    dpg.set_viewport_resize_callback(resize_callback)
    
    # Primary Window (no title bar so we can simulate a “custom” top bar)
    with dpg.window(tag="Primary Window", label="", no_title_bar=True,
                    width=1000, height=700, pos=(0, 0)):
        build_ui()
    
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
