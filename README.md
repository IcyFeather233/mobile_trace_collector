# Android Operation Recorder

A tool for recording operations on Android devices, capable of logging user clicks, swipes, inputs, and other actions while generating detailed operation records.

## Features

1. Graphical Interface Operations
   - Set operation path target
   - Real-time display of current step
   - Show detailed information of previous operation
   - Display operation screenshots
   - Support deleting previous operation
   - Support manual input operation ending
   - Support ending current path recording

2. Supported Operation Types
   - Click
   - Press (Long Press)
   - Swipe
   - Text Input
   - Special Events (e.g., Back key, Home key)

3. Automatic Information Recording
   - Operation type and detailed parameters
   - Activity information during operation
   - Screenshot before operation
   - UI hierarchy (XML format)
   - Target element bounds for click operations

4. Visual Processing
   - Generates processed screenshots with markers for each operation:
     - Click/Press: Blue dot marks click position, red border marks operated element
     - Swipe: Blue dots mark start and end points, arrowed line shows swipe direction
     - Input: Displays input text content at the top
     - Special Events: Displays event type at the top

## Directory Structure

```
records/
  └── record_YYYYMMDD_HHMMSS/
      ├── screenshots/          # Original screenshots
      │   ├── step_0.png
      │   ├── step_1.png
      │   └── ...
      ├── processed_screenshots/  # Processed screenshots
      │   ├── step_1_processed.png
      │   └── ...
      ├── ui_trees/            # UI hierarchy
      │   ├── step_0_ui.xml
      │   ├── step_1_ui.xml
      │   └── ...
      └── record.json          # Operation record file
```

## Record Format

```json
{
    "target": "Description of operation path target",
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

## Usage

1. Start the program
2. Set the operation path target in the input field
3. Start performing operations on the Android device
4. At any time, you can:
   - Click "Delete Last Step" to remove incorrect operations
   - Click "End Input and Record" to manually end the current input operation
   - Click "End Current Path" to complete the current path recording
5. All operations are automatically recorded and saved

## Dependencies

- Python 3.x
- PIL (Pillow)
- tkinter
- ADB tools
- Connected Android device

## Notes

- Ensure Android device is connected via ADB before use
- Device must have Developer Options and USB Debugging enabled
- Recommended to keep device screen on during operations
