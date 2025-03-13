import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import json
import os
from datetime import datetime
import time

class RecorderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Android Operation Recorder")
        
        # Set window size and position
        self.root.geometry("1000x1000")  # Adjust to larger size
        
        # Add periodic update functionality
        self.pending_screenshot = None
        self.root.after(100, self.check_pending_updates)
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="20")  # Add inner padding
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Path target input frame
        self.target_frame = ttk.LabelFrame(self.main_frame, text="Path Target", padding="10")
        self.target_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.target_entry = ttk.Entry(self.target_frame, width=80)  # Widen input box
        self.target_entry.grid(row=0, column=0, padx=10, pady=10)
        
        self.target_button = ttk.Button(self.target_frame, text="Set Target", command=self.set_target)
        self.target_button.grid(row=0, column=1, padx=10, pady=10)
        
        # Current step display
        self.step_label = ttk.Label(self.main_frame, text="Current Step: 0", font=('Arial', 12))  # Increase font size
        self.step_label.grid(row=1, column=0, columnspan=2, pady=10)
        
        # Last action information
        self.last_action_frame = ttk.LabelFrame(self.main_frame, text="Last Action", padding="10")
        self.last_action_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.last_action_text = tk.Text(self.last_action_frame, height=8, width=80)  # Increase height and width
        self.last_action_text.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)
        self.last_action_text.config(state='disabled')
        
        # Screenshot display
        self.screenshot_label = ttk.Label(self.main_frame)
        self.screenshot_label.grid(row=3, column=0, columnspan=2, pady=20)
        
        # Button frame
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        # Delete last step button
        self.delete_button = ttk.Button(self.button_frame, text="Delete Last Step", command=self.delete_last_step, width=20)
        self.delete_button.grid(row=0, column=0, padx=20)
        
        # Retake screenshot button
        self.retake_button = ttk.Button(self.button_frame, text="Retake Screenshot", command=self.retake_screenshot, width=20)
        self.retake_button.grid(row=0, column=1, padx=20)
        
        # Finish input button
        self.finish_input_button = ttk.Button(self.button_frame, text="Finish Input and Record", command=self.finish_input, width=20)
        self.finish_input_button.grid(row=0, column=2, padx=20)
        
        # Finish current path button
        self.finish_button = ttk.Button(self.button_frame, text="Finish Current Path", command=self.finish_current_path, width=20)
        self.finish_button.grid(row=0, column=3, padx=20)
        
        # Initialize variables
        self.current_record = None
        self.monitor = None
        
        # Disable other buttons until target is set
        self.delete_button.config(state='disabled')
        self.finish_button.config(state='disabled')
        self.finish_input_button.config(state='disabled')
        self.retake_button.config(state='disabled')
    
    def set_monitor(self, monitor):
        """Set monitor instance"""
        self.monitor = monitor
        self.monitor.gui = self
    
    def update_step_display(self, step_id):
        """Update step display"""
        self.step_label.config(text=f"Current Step: {step_id}")
    
    def update_last_action(self, action_data):
        """Update last action information"""
        self.last_action_text.config(state='normal')
        self.last_action_text.delete(1.0, tk.END)
        self.last_action_text.insert(1.0, json.dumps(action_data, indent=2, ensure_ascii=False))
        self.last_action_text.config(state='disabled')
        
        # Set pending screenshot path
        if action_data and 'screen_shot' in action_data:
            if "screenshots" in action_data['screen_shot']:
                self.pending_screenshot = os.path.join(
                    self.monitor.record_dir,
                    f"record_{self.monitor.record_timestamp}",
                    action_data['screen_shot']
                )
            else:
                self.pending_screenshot = os.path.join(
                    self.monitor.record_dir,
                    f"record_{self.monitor.record_timestamp}",
                    "screenshots",
                    action_data['screen_shot']
                )

    def check_pending_updates(self):
        """Periodically check for pending screenshot updates"""
        if self.pending_screenshot:
            print(self.pending_screenshot)
            if os.path.exists(self.pending_screenshot):
                try:
                    image = Image.open(self.pending_screenshot)
                    # Adjust image size to fit display
                    image.thumbnail((400, 400))
                    photo = ImageTk.PhotoImage(image)
                    self.screenshot_label.config(image=photo)
                    self.screenshot_label.image = photo
                    self.pending_screenshot = None
                except Exception as e:
                    print(f"Error loading image: {e}")
        
        # Continue periodic checking
        self.root.after(100, self.check_pending_updates)

    def delete_last_step(self):
        """Delete last action"""
        if self.monitor and self.monitor.actions:
            # Delete last action
            last_action = self.monitor.actions.pop()
            # Delete corresponding screenshot
            screenshot_path = os.path.join(
                self.monitor.record_dir,
                f"record_{self.monitor.record_timestamp}",
                "screenshots",
                last_action['screen_shot']
            )
            try:
                os.remove(screenshot_path)
            except:
                pass
            
            # Update step_id
            self.monitor.step_id -= 1
            # Save updated record
            self.monitor._save_actions()
            
            # Update display
            if self.monitor.actions:
                self.update_last_action(self.monitor.actions[-1])
            else:
                self.update_last_action(None)
            self.update_step_display(self.monitor.step_id)
    
    def set_target(self):
        """Set path target"""
        target = self.target_entry.get().strip()
        if target:
            # Set target and enable buttons
            self.monitor.set_path_target(target)
            self.target_entry.config(state='disabled')
            self.target_button.config(state='disabled')
            self.delete_button.config(state='normal')
            self.finish_button.config(state='normal')
            self.finish_input_button.config(state='normal')
            self.retake_button.config(state='normal')
    
    def finish_current_path(self):
        """End current path recording"""
        if self.monitor:
            # Disable recording
            self.monitor.recording_enabled = False
            
            # Save current record
            self.monitor._save_actions()
            
            # Create new recording session
            self.monitor.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.monitor.screenshots_dir = os.path.join(
                self.monitor.record_dir,
                f"record_{self.monitor.record_timestamp}",
                "screenshots"
            )
            os.makedirs(self.monitor.screenshots_dir, exist_ok=True)
            
            # Reset recording state
            self.monitor.actions = []
            self.monitor.step_id = 0
            
            # Update display
            self.pending_screenshot = None  # Clear pending screenshot
            self.update_last_action(None)
            self.update_step_display(0)
            self.screenshot_label.config(image='')
            
            # Re-enable target input
            self.target_entry.config(state='normal')
            self.target_button.config(state='normal')
            self.target_entry.delete(0, tk.END)
            
            # Disable operation buttons
            self.delete_button.config(state='disabled')
            self.finish_button.config(state='disabled')
            self.finish_input_button.config(state='disabled')
            self.retake_button.config(state='disabled')

    def update_initial_screenshot(self, image_path):
        """Update initial page screenshot"""
        self.pending_screenshot = image_path
        # Clear last action information
        self.last_action_text.config(state='normal')
        self.last_action_text.delete(1.0, tk.END)
        self.last_action_text.insert(1.0, "Initial Page")
        self.last_action_text.config(state='disabled')

    def finish_input(self):
        """Manually finish current input and record"""
        if self.monitor:
            self.monitor.finish_current_input()

    def retake_screenshot(self):
        """Retake screenshot for current step"""
        if self.monitor and self.monitor.actions:
            current_step = self.monitor.actions[-1]
            step_id = current_step['step_id']
            
            # Retake screenshot
            screenshot_success = self.monitor.take_screenshot(os.path.join(self.monitor.screenshots_dir, f"step_{step_id}"))
            
            if screenshot_success:
                # Process screenshot if needed (for non-initial steps)
                if step_id > 0:
                    # Get previous screenshot
                    prev_screenshot = os.path.join(self.monitor.screenshots_dir, f"step_{step_id-1}.png")
                    if os.path.exists(prev_screenshot):
                        # Generate processed screenshot based on previous screenshot
                        processed_path = self.monitor.process_screenshot(prev_screenshot, current_step)
                        if processed_path:
                            current_step["processed_screenshot"] = processed_path.replace("processed_screenshots/", "")
                
                # Save updated record
                self.monitor._save_actions()
                
                # Update display
                self.update_last_action(current_step) 