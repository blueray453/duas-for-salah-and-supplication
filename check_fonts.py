import os
from fontTools.ttLib import TTFont

def check_fonts(folder_path, target_char):
    print(f"Checking fonts in '{folder_path}' for U+FDFA...")
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.ttf', '.otf')):
            font_path = os.path.join(folder_path, filename)
            try:
                font = TTFont(font_path)
                found = False
                for cmap in font['cmap'].tables:
                    if cmap.isUnicode() and target_char in cmap.cmap:
                        found = True
                        break
                if found:
                    print(f"[YES] {filename}")
                else:
                    print(f"[NO]  {filename}")
            except Exception as e:
                print(f"[ERROR] {filename}: {e}")

check_fonts('./fonts', 0xFDFA)
