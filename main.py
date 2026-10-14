import sys
from qishui import qishui_ad,loop_process
from screen import find_image_on_screen
import pyautogui

if __name__ == '__main__':
    # un_lock()
    if len(sys.argv) > 1:
        if sys.argv[1] == 'qishui':
            qishui_ad()
            loop_process()
        elif sys.argv[1] == 'xima':
            print("xiaomi ad")
        elif sys.argv[1] == 'test':
            position = find_image_on_screen("images/qishui/gz-close.png")
            if position:
                print(position)
                # pyautogui.moveTo(position)
                pyautogui.click(position)
            else:
                print("未找到目标图片")
    else:
        print("使用方法: python3 main.py qishui")