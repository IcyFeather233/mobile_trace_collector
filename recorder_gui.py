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
        self.root.title("Android操作记录器")
        
        # 设置窗口大小和位置
        self.root.geometry("1000x1000")  # 调整为更大的尺寸
        
        # 添加定期更新的功能
        self.pending_screenshot = None
        self.root.after(100, self.check_pending_updates)
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="20")  # 增加内边距
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 路径目标输入框
        self.target_frame = ttk.LabelFrame(self.main_frame, text="路径目标", padding="10")
        self.target_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.target_entry = ttk.Entry(self.target_frame, width=80)  # 加宽输入框
        self.target_entry.grid(row=0, column=0, padx=10, pady=10)
        
        self.target_button = ttk.Button(self.target_frame, text="设置目标", command=self.set_target)
        self.target_button.grid(row=0, column=1, padx=10, pady=10)
        
        # 当前步骤显示
        self.step_label = ttk.Label(self.main_frame, text="当前步骤: 0", font=('Arial', 12))  # 增大字体
        self.step_label.grid(row=1, column=0, columnspan=2, pady=10)
        
        # 上一步操作信息
        self.last_action_frame = ttk.LabelFrame(self.main_frame, text="上一步操作", padding="10")
        self.last_action_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.last_action_text = tk.Text(self.last_action_frame, height=8, width=80)  # 增加高度和宽度
        self.last_action_text.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)
        self.last_action_text.config(state='disabled')
        
        # 截图显示
        self.screenshot_label = ttk.Label(self.main_frame)
        self.screenshot_label.grid(row=3, column=0, columnspan=2, pady=20)
        
        # 按钮框架
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        # 删除上一步按钮
        self.delete_button = ttk.Button(self.button_frame, text="删除上一步", command=self.delete_last_step, width=20)  # 加宽按钮
        self.delete_button.grid(row=0, column=0, padx=20)
        
        # 结束当前路径按钮
        self.finish_button = ttk.Button(self.button_frame, text="结束当前路径", command=self.finish_current_path, width=20)  # 加宽按钮
        self.finish_button.grid(row=0, column=1, padx=20)
        
        # 初始化变量
        self.current_record = None
        self.monitor = None
        
        # 禁用其他按钮，直到设置了目标
        self.delete_button.config(state='disabled')
        self.finish_button.config(state='disabled')
    
    def set_monitor(self, monitor):
        """设置监视器实例"""
        self.monitor = monitor
        self.monitor.gui = self
    
    def update_step_display(self, step_id):
        """更新步骤显示"""
        self.step_label.config(text=f"当前步骤: {step_id}")
    
    def update_last_action(self, action_data):
        """更新上一步操作信息"""
        self.last_action_text.config(state='normal')
        self.last_action_text.delete(1.0, tk.END)
        self.last_action_text.insert(1.0, json.dumps(action_data, indent=2, ensure_ascii=False))
        self.last_action_text.config(state='disabled')
        
        # 设置待更新的截图路径
        if action_data and 'screen_shot' in action_data:
            self.pending_screenshot = os.path.join(
                self.monitor.record_dir,
                f"record_{self.monitor.record_timestamp}",
                "screenshots",
                action_data['screen_shot']
            )

    def check_pending_updates(self):
        """定期检查是否有待更新的截图"""
        if self.pending_screenshot:
            if os.path.exists(self.pending_screenshot):
                try:
                    image = Image.open(self.pending_screenshot)
                    # 调整图片大小以适应显示
                    image.thumbnail((400, 400))
                    photo = ImageTk.PhotoImage(image)
                    self.screenshot_label.config(image=photo)
                    self.screenshot_label.image = photo
                    self.pending_screenshot = None
                except Exception as e:
                    print(f"Error loading image: {e}")
        
        # 继续定期检查
        self.root.after(100, self.check_pending_updates)

    def delete_last_step(self):
        """删除上一步操作"""
        if self.monitor and self.monitor.actions:
            # 删除最后一个动作
            last_action = self.monitor.actions.pop()
            # 删除对应的截图
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
            
            # 更新step_id
            self.monitor.step_id -= 1
            # 保存更新后的记录
            self.monitor._save_actions()
            
            # 更新显示
            if self.monitor.actions:
                self.update_last_action(self.monitor.actions[-1])
            else:
                self.update_last_action(None)
            self.update_step_display(self.monitor.step_id)
    
    def set_target(self):
        """设置路径目标"""
        target = self.target_entry.get().strip()
        if target:
            # 设置目标并启用按钮
            self.monitor.set_path_target(target)
            self.target_entry.config(state='disabled')
            self.target_button.config(state='disabled')
            self.delete_button.config(state='normal')
            self.finish_button.config(state='normal')
    
    def finish_current_path(self):
        """结束当前路径记录"""
        if self.monitor:
            # 禁用记录
            self.monitor.recording_enabled = False
            
            # 保存当前记录
            self.monitor._save_actions()
            
            # 创建新的记录会话
            self.monitor.record_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.monitor.screenshots_dir = os.path.join(
                self.monitor.record_dir,
                f"record_{self.monitor.record_timestamp}",
                "screenshots"
            )
            os.makedirs(self.monitor.screenshots_dir, exist_ok=True)
            
            # 重置记录状态
            self.monitor.actions = []
            self.monitor.step_id = 0
            
            # 更新显示
            self.pending_screenshot = None  # 清除待更新的截图
            self.update_last_action(None)
            self.update_step_display(0)
            self.screenshot_label.config(image='')
            
            # 重新启用目标输入
            self.target_entry.config(state='normal')
            self.target_button.config(state='normal')
            self.target_entry.delete(0, tk.END)
            
            # 禁用操作按钮
            self.delete_button.config(state='disabled')
            self.finish_button.config(state='disabled')

    def update_initial_screenshot(self, image_path):
        """更新初始页面截图"""
        self.pending_screenshot = image_path
        # 清空上一步操作信息
        self.last_action_text.config(state='normal')
        self.last_action_text.delete(1.0, tk.END)
        self.last_action_text.insert(1.0, "初始页面")
        self.last_action_text.config(state='disabled') 