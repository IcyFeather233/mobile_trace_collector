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
        self.record_timestamp = None  # 初始化为None
        self.record_dir = "records"
        self.screenshots_dir = None  # 初始化为None
        self.ui_trees_dir = None  # 初始化为None
        self.processed_screenshots_dir = None  # 初始化为None

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
                        
                        # 先截图
                        self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{self.step_id}"))

                        print(f"这是一个special event，当前的step_id是：{self.step_id}，截图路径是：{screenshot_name}")
                        
                        # 再记录步骤
                        self._record_step({
                            "step_id": self.step_id,
                            "action_type": "special_event",
                            "action_detail": {
                                "event": self.current_key
                            },
                            "screen_shot": f"{screenshot_name}"
                        })
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
            
            # 先截图
            self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{self.step_id}"))
            
            # 再记录步骤
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
        """解析bounds字符串为坐标值"""
        try:
            # 从形如 "[x1,y1][x2,y2]" 的字符串中提取坐标
            coords = bounds_str.strip('[]').split('][')
            x1, y1 = map(int, coords[0].split(','))
            x2, y2 = map(int, coords[1].split(','))
            return x1, y1, x2, y2
        except:
            return None

    def _calculate_area(self, bounds):
        """计算bounds的面积"""
        x1, y1, x2, y2 = bounds
        return (x2 - x1) * (y2 - y1)

    def _find_smallest_containing_bounds(self, xml_path, x, y):
        """找到包含指定坐标的最小bounds"""
        try:
            if not os.path.exists(xml_path):
                return None
                
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # 找到所有bounds属性
            bounds_pattern = r'bounds="(\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\])"'
            matches = re.finditer(bounds_pattern, xml_content)
            
            smallest_area = float('inf')
            smallest_bounds = None
            
            # 检查每个bounds
            for match in matches:
                bounds_str = match.group(1)
                bounds = self._parse_bounds(bounds_str)
                if bounds:
                    x1, y1, x2, y2 = bounds
                    # 检查坐标是否在bounds内
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
        """处理截图，添加操作标记"""
        try:
            # 打开原始截图
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)
            
            # 设置颜色和字体
            red_color = (255, 0, 0)
            blue_color = (0, 0, 255)
            circle_radius = 10
            try:
                font = ImageFont.truetype("arial.ttf", 24)  # Windows字体
            except:
                font = ImageFont.load_default()
            
            action_type = step_data["action_type"]
            
            if action_type in ["click", "press"]:
                # 绘制操作点和bounds
                x = step_data["action_detail"]["x"]
                y = step_data["action_detail"]["y"]
                
                # 画蓝色圆点
                draw.ellipse([x-circle_radius, y-circle_radius, x+circle_radius, y+circle_radius], 
                           outline=blue_color, width=2)
                
                # 如果有bounds，画红色边框
                if "operated_bounds" in step_data:
                    bounds = self._parse_bounds(step_data["operated_bounds"])
                    if bounds:
                        x1, y1, x2, y2 = bounds
                        draw.rectangle([x1, y1, x2, y2], outline=red_color, width=2)
            
            elif action_type == "swipe":
                # 绘制滑动起点、终点和箭头
                start_x = step_data["action_detail"]["start_x"]
                start_y = step_data["action_detail"]["start_y"]
                end_x = step_data["action_detail"]["end_x"]
                end_y = step_data["action_detail"]["end_y"]
                
                # 画起点和终点的圆
                draw.ellipse([start_x-circle_radius, start_y-circle_radius, 
                            start_x+circle_radius, start_y+circle_radius], 
                           outline=blue_color, width=2)
                draw.ellipse([end_x-circle_radius, end_y-circle_radius, 
                            end_x+circle_radius, end_y+circle_radius], 
                           outline=blue_color, width=2)
                
                # 画箭头
                draw.line([start_x, start_y, end_x, end_y], fill=blue_color, width=2)
                # 画箭头头部
                arrow_length = 20
                angle = math.atan2(end_y - start_y, end_x - start_x)
                arrow_angle = math.pi / 6  # 30度
                draw.line([end_x, end_y,
                          end_x - arrow_length * math.cos(angle + arrow_angle),
                          end_y - arrow_length * math.sin(angle + arrow_angle)], 
                         fill=blue_color, width=2)
                draw.line([end_x, end_y,
                          end_x - arrow_length * math.cos(angle - arrow_angle),
                          end_y - arrow_length * math.sin(angle - arrow_angle)], 
                         fill=blue_color, width=2)
            
            elif action_type == "input":
                # 在顶部绘制输入文本
                text = f"Input: {step_data['action_detail']['text']}"
                draw.text((10, 10), text, fill=red_color, font=font)
            
            elif action_type == "special_event":
                # 在顶部绘制特殊事件
                text = f"Special Event: {step_data['action_detail']['event']}"
                draw.text((10, 10), text, fill=red_color, font=font)
            
            # 保存处理后的图片
            processed_filename = f"step_{step_data['step_id']}_processed.png"
            processed_path = os.path.join(self.processed_screenshots_dir, processed_filename)
            img.save(processed_path)
            
            # 返回相对路径
            return f"processed_screenshots/{processed_filename}"
            
        except Exception as e:
            print(f"Error processing screenshot: {e}")
            return None

    def _record_step(self, step_data):
        """记录单个步骤"""
        if not self.recording_enabled:
            return
            
        # 等待1秒，确保页面跳转完成
        time.sleep(1)
        
        # 获取当前activity信息
        activity_info = self.get_current_activity()
        if activity_info:
            step_data["activity_info"] = activity_info
            
        # 获取UI层次结构
        ui_tree = self.get_ui_hierarchy()
        if ui_tree:
            ui_tree_filename = f"step_{step_data['step_id']}_ui.xml"
            ui_tree_path = os.path.join(self.ui_trees_dir, ui_tree_filename)
            with open(ui_tree_path, 'w', encoding='utf-8') as f:
                f.write(ui_tree)
            step_data["ui_tree"] = f"{ui_tree_filename}"
            
            # 对于点击和长按操作，查找对应的bounds
            if step_data["action_type"] in ["click", "press"]:
                x = step_data["action_detail"]["x"]
                y = step_data["action_detail"]["y"]
                bounds = self._find_smallest_containing_bounds(ui_tree_path, x, y)
                if bounds:
                    step_data["operated_bounds"] = bounds
        
        # 先处理上一步的截图（如果存在）
        prev_step_id = step_data['step_id'] - 1
        if prev_step_id >= 0:
            prev_screenshot = os.path.join(self.screenshots_dir, f"step_{prev_step_id}.png")
            if os.path.exists(prev_screenshot):
                processed_path = self.process_screenshot(prev_screenshot, step_data)
                if processed_path:
                    step_data["processed_screenshot"] = processed_path.replace("processed_screenshots/", "")
        
        # 保存当前步骤的原始截图
        self.take_screenshot(os.path.join(self.screenshots_dir, f"step_{step_data['step_id']}"))
            
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
        try:
            # 使用临时文件名
            temp_file = f"{filename}_temp.png"
            # 使用 -o 参数直接输出到文件，而不是使用重定向
            cmd = f"adb {self.device_id} exec-out screencap -p > \"{temp_file}\""
            subprocess.run(cmd, shell=True, check=True)
            
            # 确保文件写入完成
            time.sleep(0.5)
            
            # 如果文件存在且大小正常，则重命名为最终文件名
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                final_file = f"{filename}.png"
                # 如果目标文件已存在，先删除
                if os.path.exists(final_file):
                    os.remove(final_file)
                os.rename(temp_file, final_file)
            else:
                print(f"Screenshot failed: {temp_file} not created or empty")
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            # 清理可能的临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)

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

    def get_ui_hierarchy(self):
        """获取当前界面的UI层次结构"""
        try:
            # 导出UI层次结构到设备
            dump_cmd = f"adb {self.device_id} shell uiautomator dump"
            subprocess.run(dump_cmd, shell=True, check=True)
            
            # 创建临时文件名
            temp_xml = os.path.join(self.screenshots_dir, "temp_ui_dump.xml")
            
            # 从设备拉取文件
            pull_cmd = f"adb {self.device_id} pull /sdcard/window_dump.xml \"{temp_xml}\""
            subprocess.run(pull_cmd, shell=True, check=True)
            
            # 读取XML内容
            if os.path.exists(temp_xml):
                with open(temp_xml, 'r', encoding='utf-8') as f:
                    ui_tree = f.read()
                # 删除临时文件
                os.remove(temp_xml)
                return ui_tree
            return None
        except Exception as e:
            print(f"Error getting UI hierarchy: {e}")
            return None

    def _setup_record_dirs(self):
        """设置记录目录结构"""
        if not self.record_timestamp:
            self.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        record_path = os.path.join(self.record_dir, f"record_{self.record_timestamp}")
        self.screenshots_dir = os.path.join(record_path, "screenshots")
        self.ui_trees_dir = os.path.join(record_path, "ui_trees")
        self.processed_screenshots_dir = os.path.join(record_path, "processed_screenshots")
        
        # 确保所有目录存在
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.ui_trees_dir, exist_ok=True)
        os.makedirs(self.processed_screenshots_dir, exist_ok=True)

    def set_path_target(self, target):
        """设置路径目标"""
        self.path_target = target
        
        # 创建新的记录时间戳和目录
        self.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._setup_record_dirs()
        
        # 初始化记录
        self.actions = []
        self.step_id = 0
        
        # 先截取初始页面和UI层次结构
        self.take_screenshot(os.path.join(self.screenshots_dir, "step_0"))
        initial_ui = self.get_ui_hierarchy()
        if initial_ui:
            # 保存初始UI层次结构
            ui_file = os.path.join(self.ui_trees_dir, "step_0_ui.xml")
            with open(ui_file, 'w', encoding='utf-8') as f:
                f.write(initial_ui)
        
        # 启用记录并保存初始json
        self.recording_enabled = True
        self._save_actions()
        
        # 更新GUI显示初始截图
        if self.gui:
            self.gui.update_initial_screenshot(os.path.join(self.screenshots_dir, "step_0.png"))

    def finish_current_path(self):
        """结束当前路径记录"""
        self.recording_enabled = False  # 禁用记录
        self._save_actions()

    def finish_current_input(self):
        """手动结束当前输入并记录"""
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