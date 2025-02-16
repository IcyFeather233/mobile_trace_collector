import subprocess
import threading
import time
from datetime import datetime
import json
import os
import re
import tkinter as tk
from recorder_gui import RecorderGUI

def print_with_timestamp(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    print(f'[{timestamp}] {message}')

class AndroidEventMonitor:
    def __init__(self, device_id=""):
        self.device_id = device_id
        self.process = None
        self.running = False
        
        # 初始化设备信息
        self.screen_width, self.screen_height = self.get_screen_resolution()
        self.max_x, self.max_y = self.get_touch_range()

        # 添加新的成员变量用于跟踪触摸事件
        self.current_x = None
        self.current_y = None
        self.last_event_time = None
        self.touch_start_time = None  # 添加：记录触摸开始的时间
        self.is_continuous = False
        self.start_point = None
        self.time_threshold = 0.1  # 100ms阈值判断连续事件
        self.press_threshold = 0.6  # 600ms阈值判断长按事件

        # 修改按键相关的成员变量
        self.current_key = None
        self.pending_keys = []  # 新增：存储待处理的按键事件
        # 定义特殊按键列表
        self.special_keys = {'KEY_BACK', 'KEY_HOME', 'KEY_APPSELECT', 'KEY_ENTER'}

        # 修改动作记录相关的成员变量
        self.actions = []
        self.step_id = 0
        self.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.record_dir = "records"
        self.screenshots_dir = os.path.join(self.record_dir, f"record_{self.record_timestamp}", "screenshots")
        # 确保记录目录存在
        os.makedirs(self.screenshots_dir, exist_ok=True)

        self.gui = None  # 添加GUI引用
        self.path_target = None  # 添加路径目标变量
        self.recording_enabled = False  # 添加标志控制是否记录

    def get_screen_resolution(self):
        """获取设备屏幕分辨率"""
        cmd = f"adb {self.device_id} shell wm size"
        output = subprocess.check_output(cmd, shell=True).decode()
        resolution = output.split()[-1].split('x')
        return int(resolution[0]), int(resolution[1])

    def get_touch_range(self):
        """获取触摸屏坐标范围"""
        cmd = f"adb {self.device_id} shell getevent -p"
        output = subprocess.check_output(cmd, shell=True).decode()
        max_x = max_y = 32767  # 默认值（部分设备）
        for line in output.split('\n'):
            if 'ABS_MT_POSITION_X' in line:
                max_x = int(line.split('max ')[1])
            elif 'ABS_MT_POSITION_Y' in line:
                max_y = int(line.split('max ')[1])
        return max_x, max_y

    def start_monitoring(self):
        """启动事件监听线程"""
        self.running = True
        cmd = f"adb {self.device_id} shell getevent -lt"
        self.process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        threading.Thread(target=self._read_output).start()

    def _read_output(self):
        """持续读取事件流"""
        while self.running:
            line = self.process.stdout.readline().decode().strip()
            if line:
                self.parse_event(line)

    def parse_event(self, line):
        """解析单行事件"""
        # 解析事件时间戳
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
                        
                        self._record_step({
                            "step_id": self.step_id,
                            "action_type": "special_event",
                            "action_detail": {
                                "event": self.current_key
                            },
                            "screen_shot": screenshot_name
                        })
                        
                        self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{self.step_id}"))
                    else:
                        # 普通按键，加入待处理列表
                        self.pending_keys.append(self.current_key)
                    self.current_key = None
        
        elif 'ABS_MT_POSITION_X' in line:
            self._output_pending_keys()
            hex_value = line.split()[-1]
            self.current_x = self._convert_coord(hex_value, self.max_x, self.screen_width)
            
        elif 'ABS_MT_POSITION_Y' in line:
            hex_value = line.split()[-1]
            self.current_y = self._convert_coord(hex_value, self.max_y, self.screen_height)
            
            # 如果同时有X和Y坐标，进行处理
            if self.current_x is not None:
                if not self.is_continuous:
                    # 新的触摸序列开始
                    self.start_point = (self.current_x, self.current_y)
                    self.is_continuous = True
                    self.last_event_time = timestamp
                    self.touch_start_time = timestamp  # 记录触摸开始时间
                else:
                    # 检查是否为连续事件
                    time_diff = timestamp - self.last_event_time
                    if time_diff > self.time_threshold:
                        # 时间间隔过大，视为新的触摸序列
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
        """转换坐标到屏幕实际像素"""
        raw_value = int(hex_str, 16)
        return int(raw_value * screen_size / max_raw)
    
    def _process_touch_sequence(self, current_timestamp):
        """处理触摸序列，区分点击、长按和滑动"""
        self._output_pending_keys()
        
        if not self.start_point or not self.current_x or not self.current_y or not self.touch_start_time:
            return
            
        start_x, start_y = self.start_point
        end_x, end_y = self.current_x, self.current_y
        
        # 计算移动距离和持续时间
        distance = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5
        duration = current_timestamp - self.touch_start_time
        
        self.step_id += 1
        screenshot_name = f"step_{self.step_id}.png"
        
        if distance < 10:  # 静止点击
            if duration >= self.press_threshold:
                # 长按事件
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
                # 普通点击
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
            # 滑动事件
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
        """输出所有待处理的按键事件"""
        if self.pending_keys:
            keys_str = ", ".join(self.pending_keys)
            print_with_timestamp(f"[processed input keyevent] {keys_str}")
            
            self.step_id += 1
            screenshot_name = f"step_{self.step_id}.png"
            
            self._record_step({
                "step_id": self.step_id,
                "action_type": "input",
                "action_detail": {
                    "text": keys_str
                },
                "screen_shot": screenshot_name
            })
            
            self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{self.step_id}"))
            self.pending_keys = []

    def _record_step(self, step_data):
        """记录单个步骤"""
        if not self.recording_enabled:  # 如果未启用记录，直接返回
            return
            
        # 等待1秒，确保页面跳转完成
        time.sleep(1)
        
        # 获取当前activity信息
        activity_info = self.get_current_activity()
        if activity_info:
            step_data["activity_info"] = activity_info
        self.actions.append(step_data)
        self._save_actions()
        
        # 更新GUI显示
        if self.gui:
            self.gui.update_last_action(step_data)
            self.gui.update_step_display(self.step_id)

    def _save_actions(self):
        """保存所有动作到JSON文件"""
        record_data = {
            "target": self.path_target,
            # "timestamp": self.record_timestamp,
            "steps": self.actions
        }
        
        filename = os.path.join(self.record_dir, f"record_{self.record_timestamp}", "record.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(record_data, f, indent=4, ensure_ascii=False)

    def take_screenshot(self, filename):
        """截取屏幕"""
        cmd = f"adb {self.device_id} exec-out screencap -p > {filename}.png"
        subprocess.run(cmd, shell=True)

    def get_current_activity(self):
        """获取当前Activity信息"""
        try:
            cmd = f"adb {self.device_id} shell dumpsys activity activities | findstr topResumedActivity"
            output = subprocess.check_output(cmd, shell=True).decode()
            # 使用正则表达式提取activity信息
            match = re.search(r'com\.[^/]+/[^\s}]+', output)
            if match:
                return match.group(0)
            return None
        except:
            return None

    def set_path_target(self, target):
        """设置路径目标"""
        self.path_target = target
        # 创建新的记录
        self.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshots_dir = os.path.join(
            self.record_dir,
            f"record_{self.record_timestamp}",
            "screenshots"
        )
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # 初始化记录
        self.actions = []
        self.step_id = 0
        self.recording_enabled = True  # 启用记录
        self._save_actions()

    def finish_current_path(self):
        """结束当前路径记录"""
        self.recording_enabled = False  # 禁用记录
        self._save_actions()

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