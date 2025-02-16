# Android操作记录程序

这是一个记录Android设备操作的程序，能够自动捕获并记录用户的各种操作行为。

## 支持的操作类型

程序可以识别并记录以下类型的操作：

1. **点击操作 (click)**
   - 短按屏幕（小于0.6秒）
   - 记录点击的具体坐标

2. **长按操作 (press)**
   - 按住屏幕超过0.6秒
   - 记录长按的坐标和持续时间

3. **滑动操作 (swipe)**
   - 在屏幕上滑动
   - 记录起始和结束坐标
   - 记录滑动持续时间

4. **文本输入 (input)**
   - 记录键盘输入的文字
   - 连续的键盘输入会被合并为一个操作

5. **特殊事件 (special_event)**
   - 系统按键操作，包括：
     - KEY_BACK（返回键）
     - KEY_HOME（主页键）
     - KEY_APPSELECT（任务切换键）
     - KEY_ENTER（回车键）

## 记录的数据格式

每个操作都会生成一条记录，包含以下信息：

1. **点击操作**
```json
{
    "step_id": 1,
    "action_type": "click",
    "action_detail": {
        "x": 100,
        "y": 100
    },
    "activity_info": "com.example.app/com.example.app.MainActivity",
    "screen_shot": "step_1.png"
}
```

2. **长按操作**
```json
{
    "step_id": 2,
    "action_type": "press",
    "action_detail": {
        "x": 100,
        "y": 100,
        "duration": 1.5
    },
    "activity_info": "com.example.app/com.example.app.MainActivity",
    "screen_shot": "step_2.png"
}
```

3. **滑动操作**
```json
{
    "step_id": 3,
    "action_type": "swipe",
    "action_detail": {
        "start_x": 100,
        "start_y": 100,
        "end_x": 200,
        "end_y": 200,
        "duration": 0.5
    },
    "activity_info": "com.example.app/com.example.app.MainActivity",
    "screen_shot": "step_3.png"
}
```

4. **文本输入**
```json
{
    "step_id": 4,
    "action_type": "input",
    "action_detail": {
        "text": "KEY_H, KEY_E, KEY_L, KEY_L, KEY_O"
    },
    "activity_info": "com.example.app/com.example.app.MainActivity",
    "screen_shot": "step_4.png"
}
```

5. **特殊事件**
```json
{
    "step_id": 5,
    "action_type": "special_event",
    "action_detail": {
        "event": "KEY_BACK"
    },
    "activity_info": "com.example.app/com.example.app.MainActivity",
    "screen_shot": "step_5.png"
}
```

## 输出文件结构

程序会在 `records` 目录下创建以时间戳命名的文件夹，结构如下：

```
records/
  └── record_20240216_173023/
      ├── screenshots/
      │   ├── step_1.png
      │   ├── step_2.png
      │   └── ...
      └── record.json
```

## 特性

- 自动记录每个操作的当前Activity信息
- 每个操作后等待1秒确保页面加载完成再截图
- 自动合并连续的键盘输入操作
- 使用实际的事件时间戳判断操作类型（如长按）
- 支持设备分辨率自适应

## 使用方法

1. 确保已连接Android设备并启用ADB
2. 运行程序：
   ```
   python main.py
   ```
3. 程序会自动开始监听设备操作
4. 使用Ctrl+C终止程序
