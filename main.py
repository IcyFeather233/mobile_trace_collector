import subprocess
import threading
import time
from datetime import datetime
import json
import os
import re
import tkinter as tk
from recorder_gui import RecorderGUI
from PIL import Image, ImageDraw, ImageFont
import math

def print_with_timestamp(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    print(f'[{timestamp}] {message}')

class AndroidEventMonitor:
    def __init__(self, device_id=""):
        self.device_id = device_id
        self.process = None
        self.running = False
        
        # Initialize device information
        self.screen_width, self.screen_height = self.get_screen_resolution()
        self.max_x, self.max_y = self.get_touch_range()

        # Add new member variables to track touch events
        self.current_x = None
        self.current_y = None
        self.last_event_time = None
        self.touch_start_time = None  # Add: record touch start time
        self.is_continuous = False
        self.start_point = None
        self.time_threshold = 0.1  # 100ms threshold for continuous events
        self.press_threshold = 0.6  # 600ms threshold for long press events

        # Modify key-related member variables
        self.current_key = None
        self.pending_keys = []  # New: store pending key events
        # Define special key list
        self.special_keys = {'KEY_BACK', 'KEY_HOME', 'KEY_APPSELECT', 'KEY_ENTER'}

        # Modify action recording related member variables
        self.actions = []
        self.step_id = 0
        self.record_timestamp = None  # Initialize as None
        self.record_dir = "records"
        self.screenshots_dir = None  # Initialize as None
        self.ui_trees_dir = None  # Initialize as None
        self.processed_screenshots_dir = None  # Initialize as None

        self.gui = None  # Add GUI reference
        self.path_target = None  # Add path target variable
        self.recording_enabled = False  # Add flag to control recording

    def get_screen_resolution(self):
        """Get device screen resolution"""
        cmd = f"adb {self.device_id} shell wm size"
        output = subprocess.check_output(cmd, shell=True).decode()
        resolution = output.split()[-1].split('x')
        return int(resolution[0]), int(resolution[1])

    def get_touch_range(self):
        """Get touch screen coordinate range"""
        cmd = f"adb {self.device_id} shell getevent -p"
        output = subprocess.check_output(cmd, shell=True).decode()
        max_x = max_y = 32767  # Default value (some devices)
        for line in output.split('\n'):
            if 'ABS_MT_POSITION_X' in line:
                max_x = int(line.split('max ')[1])
            elif 'ABS_MT_POSITION_Y' in line:
                max_y = int(line.split('max ')[1])
        return max_x, max_y

    def start_monitoring(self):
        """Start event monitoring thread"""
        self.running = True
        cmd = f"adb {self.device_id} shell getevent -lt"
        self.process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        threading.Thread(target=self._read_output).start()

    def _read_output(self):
        """Continuously read event stream"""
        while self.running:
            line = self.process.stdout.readline().decode().strip()
            if line:
                self.parse_event(line)

    def parse_event(self, line):
        """Parse single line event"""
        # Parse event timestamp
        try:
            timestamp = float(line.split('[')[1].split(']')[0].strip())
        except:
            return
        
        if 'EV_KEY' in line:
            parts = line.split()
            key_parts = [part for part in parts if part.startswith('KEY_')]
            if key_parts:
                key = key_parts[0]
                action = parts[-1]
                
                if action == 'DOWN':
                    self.current_key = key
                elif action == 'UP' and self.current_key:
                    if self.current_key in self.special_keys:
                        self._output_pending_keys()
                        print_with_timestamp(f"[processed] {self.current_key}")
                        
                        self.step_id += 1
                        screenshot_name = f"step_{self.step_id}.png"
                        
                        # Take screenshot first
                        self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{self.step_id}"))

                        print(f"This is a special event, current step_id is: {self.step_id}, screenshot path is: {screenshot_name}")
                        
                        # Then record the step
                        self._record_step({
                            "step_id": self.step_id,
                            "action_type": "special_event",
                            "action_detail": {
                                "event": self.current_key
                            },
                            "screen_shot": f"{screenshot_name}"
                        })
                    else:
                        # Normal key, add to pending list
                        self.pending_keys.append(self.current_key)
                    self.current_key = None
        
        elif 'ABS_MT_POSITION_X' in line:
            self._output_pending_keys()
            hex_value = line.split()[-1]
            self.current_x = self._convert_coord(hex_value, self.max_x, self.screen_width)
            
        elif 'ABS_MT_POSITION_Y' in line:
            hex_value = line.split()[-1]
            self.current_y = self._convert_coord(hex_value, self.max_y, self.screen_height)
            
            # If both X and Y coordinates are present, process
            if self.current_x is not None:
                if not self.is_continuous:
                    # New touch sequence starts
                    self.start_point = (self.current_x, self.current_y)
                    self.is_continuous = True
                    self.last_event_time = timestamp
                    self.touch_start_time = timestamp  # Record touch start time
                else:
                    # Check if it is a continuous event
                    time_diff = timestamp - self.last_event_time
                    if time_diff > self.time_threshold:
                        # Time interval too large
                        self._process_touch_sequence(timestamp)
                        self.start_point = (self.current_x, self.current_y)
                        self.touch_start_time = timestamp
                    
                    self.last_event_time = timestamp

        elif 'ABS_MT_TRACKING_ID' in line:
            tracking_id = line.split()[-1]
            if tracking_id == 'ffffffff':  # ACTION_UP
                if self.is_continuous:
                    self._process_touch_sequence(timestamp)
                self.is_continuous = False
                self.current_x = None
                self.current_y = None
                self.last_event_time = None
                self.touch_start_time = None
                self.start_point = None
                print_with_timestamp("ACTION_UP")
            else:  # ACTION_DOWN
                print_with_timestamp("ACTION_DOWN")

    def _convert_coord(self, hex_str, max_raw, screen_size):
        """Convert coordinates to actual screen pixels"""
        raw_value = int(hex_str, 16)
        return int(raw_value * screen_size / max_raw)
    
    def _process_touch_sequence(self, current_timestamp):
        """Process touch sequence, distinguish between click, long press and swipe"""
        self._output_pending_keys()
        
        if not self.start_point or not self.current_x or not self.current_y or not self.touch_start_time:
            return
            
        start_x, start_y = self.start_point
        end_x, end_y = self.current_x, self.current_y
        
        # Calculate movement distance and duration
        distance = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5
        duration = current_timestamp - self.touch_start_time
        
        self.step_id += 1
        screenshot_name = f"step_{self.step_id}.png"
        
        if distance < 10:  # Stationary click
            if duration >= self.press_threshold:
                # Long press event
                print_with_timestamp(f"[processed] Press at ({start_x}, {start_y})")
                self._record_step({
                    "step_id": self.step_id,
                    "action_type": "press",
                    "action_detail": {
                        "x": start_x,
                        "y": start_y,
                        "duration": duration
                    },
                    "screen_shot": screenshot_name
                })
            else:
                # Normal click
                print_with_timestamp(f"[processed] Click at ({start_x}, {start_y})")
                self._record_step({
                    "step_id": self.step_id,
                    "action_type": "click",
                    "action_detail": {
                        "x": start_x,
                        "y": start_y
                    },
                    "screen_shot": screenshot_name
                })
        else:
            # Swipe event
            print_with_timestamp(f"[processed] Swipe from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            self._record_step({
                "step_id": self.step_id,
                "action_type": "swipe",
                "action_detail": {
                    "start_x": start_x,
                    "start_y": start_y,
                    "end_x": end_x,
                    "end_y": end_y,
                    "duration": duration
                },
                "screen_shot": screenshot_name
            })
        
        self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{self.step_id}"))

    def _output_pending_keys(self):
        """Output all pending key events"""
        if self.pending_keys:
            keys_str = ", ".join(self.pending_keys)
            print_with_timestamp(f"[processed input keyevent] {keys_str}")
            
            self.step_id += 1
            screenshot_name = f"step_{self.step_id}.png"
            
            # Take screenshot first
            self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{self.step_id}"))
            
            # Record step
            self._record_step({
                "step_id": self.step_id,
                "action_type": "input",
                "action_detail": {
                    "text": keys_str
                },
                "screen_shot": f"screenshots/{screenshot_name}"
            })
            
            self.pending_keys = []

    def _parse_bounds(self, bounds_str):
        """Parse bounds string to coordinate values"""
        try:
            # Extract coordinates from string like "[x1,y1][x2,y2]"
            coords = bounds_str.strip('[]').split('][')
            x1, y1 = map(int, coords[0].split(','))
            x2, y2 = map(int, coords[1].split(','))
            return x1, y1, x2, y2
        except:
            return None

    def _calculate_area(self, bounds):
        """Calculate bounds area"""
        x1, y1, x2, y2 = bounds
        return (x2 - x1) * (y2 - y1)

    def _find_smallest_containing_bounds(self, xml_path, x, y):
        """Find smallest bounds containing specified coordinates"""
        try:
            if not os.path.exists(xml_path):
                return None
                
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Find all bounds attributes
            bounds_pattern = r'bounds="(\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\])"'
            matches = re.finditer(bounds_pattern, xml_content)
            
            smallest_area = float('inf')
            smallest_bounds = None
            
            # Check each bounds
            for match in matches:
                bounds_str = match.group(1)
                bounds = self._parse_bounds(bounds_str)
                if bounds:
                    x1, y1, x2, y2 = bounds
                    # Check if coordinates are within bounds
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        area = self._calculate_area(bounds)
                        if area < smallest_area:
                            smallest_area = area
                            smallest_bounds = bounds_str
            
            return smallest_bounds
        except Exception as e:
            print(f"Error finding bounds: {e}")
            return None

    def process_screenshot(self, screenshot_path, step_data):
        """Process screenshot, add operation markers"""
        try:
            # Open original screenshot
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)
            
            # Set colors and font
            red_color = (255, 0, 0)
            blue_color = (0, 0, 255)
            circle_radius = 10
            try:
                font = ImageFont.truetype("arial.ttf", 24)  # Windows font
            except:
                font = ImageFont.load_default()
            
            action_type = step_data["action_type"]
            
            if action_type in ["click", "press"]:
                # Draw operation point and bounds
                x = step_data["action_detail"]["x"]
                y = step_data["action_detail"]["y"]
                
                # Draw blue circle
                draw.ellipse([x-circle_radius, y-circle_radius, x+circle_radius, y+circle_radius], 
                           outline=blue_color, width=2)
                
                # If bounds exist, draw red border
                if "operated_bounds" in step_data:
                    bounds = self._parse_bounds(step_data["operated_bounds"])
                    if bounds:
                        x1, y1, x2, y2 = bounds
                        draw.rectangle([x1, y1, x2, y2], outline=red_color, width=2)
            
            elif action_type == "swipe":
                # Draw swipe start point, end point and arrow
                start_x = step_data["action_detail"]["start_x"]
                start_y = step_data["action_detail"]["start_y"]
                end_x = step_data["action_detail"]["end_x"]
                end_y = step_data["action_detail"]["end_y"]
                
                # Draw start point and end point circles
                draw.ellipse([start_x-circle_radius, start_y-circle_radius, 
                            start_x+circle_radius, start_y+circle_radius], 
                           outline=blue_color, width=2)
                draw.ellipse([end_x-circle_radius, end_y-circle_radius, 
                            end_x+circle_radius, end_y+circle_radius], 
                           outline=blue_color, width=2)
                
                # Draw arrow
                draw.line([start_x, start_y, end_x, end_y], fill=blue_color, width=2)
                # Draw arrow head
                arrow_length = 20
                angle = math.atan2(end_y - start_y, end_x - start_x)
                arrow_angle = math.pi / 6  # 30 degrees
                draw.line([end_x, end_y,
                          end_x - arrow_length * math.cos(angle + arrow_angle),
                          end_y - arrow_length * math.sin(angle + arrow_angle)], 
                         fill=blue_color, width=2)
                draw.line([end_x, end_y,
                          end_x - arrow_length * math.cos(angle - arrow_angle),
                          end_y - arrow_length * math.sin(angle - arrow_angle)], 
                         fill=blue_color, width=2)
            
            elif action_type == "input":
                # Draw input text at top
                text = f"Input: {step_data['action_detail']['text']}"
                draw.text((10, 10), text, fill=red_color, font=font)
            
            elif action_type == "special_event":
                # Draw special event at top
                text = f"Special Event: {step_data['action_detail']['event']}"
                draw.text((10, 10), text, fill=red_color, font=font)
            
            # Save processed image
            processed_filename = f"step_{step_data['step_id']}_processed.png"
            processed_path = os.path.join(self.processed_screenshots_dir, processed_filename)
            img.save(processed_path)
            
            # Return relative path
            return f"processed_screenshots/{processed_filename}"
            
        except Exception as e:
            print(f"Error processing screenshot: {e}")
            return None

    def _record_step(self, step_data):
        """Record single step"""
        if not self.recording_enabled:
            return
            
        # Wait 1 second to ensure page transition is complete
        time.sleep(1)
        
        # Get current activity information
        activity_info = self.get_current_activity()
        if activity_info:
            step_data["activity_info"] = activity_info
            
        # Get UI hierarchy
        ui_tree = self.get_ui_hierarchy()
        if ui_tree:
            ui_tree_filename = f"step_{step_data['step_id']}_ui.xml"
            ui_tree_path = os.path.join(self.ui_trees_dir, ui_tree_filename)
            with open(ui_tree_path, 'w', encoding='utf-8') as f:
                f.write(ui_tree)
            step_data["ui_tree"] = f"{ui_tree_filename}"
            
            # For click and long press operations, find corresponding bounds
            if step_data["action_type"] in ["click", "press"]:
                x = step_data["action_detail"]["x"]
                y = step_data["action_detail"]["y"]
                bounds = self._find_smallest_containing_bounds(ui_tree_path, x, y)
                if bounds:
                    step_data["operated_bounds"] = bounds
        
        # Process previous step's screenshot (if exists)
        prev_step_id = step_data['step_id'] - 1
        if prev_step_id >= 0:
            prev_screenshot = os.path.join(self.screenshots_dir, f"step_{prev_step_id}.png")
            if os.path.exists(prev_screenshot):
                processed_path = self.process_screenshot(prev_screenshot, step_data)
                if processed_path:
                    step_data["processed_screenshot"] = processed_path.replace("processed_screenshots/", "")
        
        # Save current step's original screenshot
        self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{step_data['step_id']}"))
            
        self.actions.append(step_data)
        self._save_actions()
        
        # Update GUI display
        if self.gui:
            self.gui.update_last_action(step_data)
            self.gui.update_step_display(self.step_id)

    def _save_actions(self):
        """Save all actions to JSON file"""
        record_data = {
            "target": self.path_target,
            "screen_size": {
                "width": self.screen_width,
                "height": self.screen_height
            },
            "steps": self.actions
        }
        
        filename = os.path.join(self.record_dir, f"record_{self.record_timestamp}", "record.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(record_data, f, indent=4, ensure_ascii=False)

    def take_screenshot(self, filename):
        """Take screenshot"""
        try:
            # Use temporary file name
            temp_file = f"{filename}_temp.png"
            # Use -o parameter to output directly to file, not using redirection
            cmd = f"adb {self.device_id} exec-out screencap -p > \"{temp_file}\""
            subprocess.run(cmd, shell=True, check=True)
            
            # Ensure file writing is complete
            time.sleep(0.5)
            
            # If file exists and size is normal, rename it to final file name
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                final_file = f"{filename}.png"
                # If target file exists, delete it first
                if os.path.exists(final_file):
                    os.remove(final_file)
                os.rename(temp_file, final_file)
                return True
            else:
                print(f"Screenshot failed: {temp_file} not created or empty")
                return False
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            # Clean up possible temporary files
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def get_current_activity(self):
        """Get current Activity information"""
        try:
            cmd = f"adb {self.device_id} shell dumpsys activity activities | findstr topResumedActivity"
            output = subprocess.check_output(cmd, shell=True).decode()
            # Use regex to extract activity information
            match = re.search(r'com\.[^/]+/[^\s}]+', output)
            if match:
                return match.group(0)
            return None
        except:
            return None

    def get_ui_hierarchy(self):
        """Get current UI hierarchy"""
        try:
            # Export UI hierarchy to device
            dump_cmd = f"adb {self.device_id} shell uiautomator dump"
            subprocess.run(dump_cmd, shell=True, check=True)
            
            # Create temporary file name
            temp_xml = os.path.join(self.screenshots_dir, "temp_ui_dump.xml")
            
            # Pull file from device
            pull_cmd = f"adb {self.device_id} pull /sdcard/window_dump.xml \"{temp_xml}\""
            subprocess.run(pull_cmd, shell=True, check=True)
            
            # Read XML content
            if os.path.exists(temp_xml):
                with open(temp_xml, 'r', encoding='utf-8') as f:
                    ui_tree = f.read()
                # Delete temporary file
                os.remove(temp_xml)
                return ui_tree
            return None
        except Exception as e:
            print(f"Error getting UI hierarchy: {e}")
            return None

    def _setup_record_dirs(self):
        """Set record directory structure"""
        if not self.record_timestamp:
            self.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        record_path = os.path.join(self.record_dir, f"record_{self.record_timestamp}")
        self.screenshots_dir = os.path.join(record_path, "screenshots")
        self.ui_trees_dir = os.path.join(record_path, "ui_trees")
        self.processed_screenshots_dir = os.path.join(record_path, "processed_screenshots")
        
        # Ensure all directories exist
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.ui_trees_dir, exist_ok=True)
        os.makedirs(self.processed_screenshots_dir, exist_ok=True)

    def set_path_target(self, target):
        """Set path target"""
        self.path_target = target
        
        self.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._setup_record_dirs()
        
        # Initialize recording
        self.actions = []
        self.step_id = 0
        
        # Take initial page and UI hierarchy
        self.take_screenshot(os.path.join(self.screenshots_dir, "step_0"))
        initial_ui = self.get_ui_hierarchy()
        if initial_ui:
            # Save initial UI hierarchy
            ui_file = os.path.join(self.ui_trees_dir, "step_0_ui.xml")
            with open(ui_file, 'w', encoding='utf-8') as f:
                f.write(initial_ui)
        
        self.recording_enabled = True
        self._save_actions()
        
        if self.gui:
            self.gui.update_initial_screenshot(os.path.join(self.screenshots_dir, "step_0.png"))

    def finish_current_path(self):
        self.recording_enabled = False
        self._save_actions()

    def finish_current_input(self):
        if self.pending_keys:
            self._output_pending_keys()
            print_with_timestamp("[manual] Finish input")

if __name__ == "__main__":
    root = tk.Tk()
    gui = RecorderGUI(root)
    monitor = AndroidEventMonitor()
    gui.set_monitor(monitor)
    
    try:
        monitor.start_monitoring()
        root.mainloop()
    except KeyboardInterrupt:
        monitor.running = False
    finally:
        root.destroy()