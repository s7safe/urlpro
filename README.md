# URL Filter Tool

A Python application with a PyQt5 GUI that filters URLs based on static resource extensions and groups similar URLs.
![图片](https://github.com/user-attachments/assets/01e8ceab-14e0-41ea-98be-1d95421cf13a)

## Features

- Filter out URLs with specific static resource extensions (.jpg, .png, .css, etc.)
- Group similar URLs and keep only the top 3 from each group
- User-friendly GUI interface
- Customizable extension filters

## Installation

1. Install Python 3.7 or higher
2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python url_filter.py
   ```
2. Enter URLs in the input text area (one URL per line)
3. Click "Filter URLs" to process the input
4. View filtered results in the results area
5. Add custom extensions using the settings panel on the right

## Customization

- Add new extensions to filter through the settings panel
- Default extensions include: .jpg, .jpeg, .png, .gif, .css, .js
