# Android操作记录器

一个用于记录Android设备操作的工具，可以记录用户的点击、滑动、输入等操作，并生成详细的操作记录。

## 功能特点

1. 图形界面操作
   - 设置操作路径目标
   - 实时显示当前步骤
   - 显示上一步操作的详细信息
   - 显示操作截图
   - 支持删除上一步操作
   - 支持手动结束输入操作
   - 支持结束当前路径记录

2. 支持的操作类型
   - 点击（Click）
   - 长按（Press）
   - 滑动（Swipe）
   - 文本输入（Input）
   - 特殊事件（Special Event，如返回键、Home键等）

3. 自动记录信息
   - 操作类型和详细参数
   - 操作时的Activity信息
   - 操作前的页面截图
   - UI层次结构（XML格式）
   - 点击操作的目标元素边界（Bounds）

4. 可视化处理
   - 为每个操作生成带标记的处理后截图：
     - 点击/长按：蓝色圆点标记点击位置，红色边框标记操作元素
     - 滑动：蓝色圆点标记起点和终点，带箭头的线条表示滑动方向
     - 输入：在顶部显示输入的文本内容
     - 特殊事件：在顶部显示事件类型

## 目录结构

```
records/
  └── record_YYYYMMDD_HHMMSS/
      ├── screenshots/          # 原始截图
      │   ├── step_0.png
      │   ├── step_1.png
      │   └── ...
      ├── processed_screenshots/  # 处理后的截图
      │   ├── step_1_processed.png
      │   └── ...
      ├── ui_trees/            # UI层次结构
      │   ├── step_0_ui.xml
      │   ├── step_1_ui.xml
      │   └── ...
      └── record.json          # 操作记录文件
```

## 记录格式

```json
{
    "target": "操作路径的目标描述",
    "steps": [
        {
            "step_id": 1,
            "action_type": "click",
            "action_detail": {
                "x": 100,
                "y": 200
            },
            "activity_info": "com.example.app/com.example.app.MainActivity",
            "screen_shot": "step_1.png",
            "processed_screenshot": "step_1_processed.png",
            "ui_tree": "step_1_ui.xml",
            "operated_bounds": "[90,190][110,210]"
        }
    ]
}
```

## 使用方法

1. 启动程序
2. 在输入框中设置操作路径的目标
3. 开始在Android设备上进行操作
4. 可以随时：
   - 点击"删除上一步"删除错误的操作
   - 点击"结束输入并记录"手动结束当前的输入操作
   - 点击"结束当前路径"完成当前路径的记录
5. 所有操作都会自动记录并保存

## 依赖要求

- Python 3.x
- PIL (Pillow)
- tkinter
- ADB工具
- 已连接的Android设备

## 注意事项

- 使用前请确保Android设备已通过ADB连接
- 设备需要开启开发者选项和USB调试
- 建议在操作期间保持设备屏幕常亮
