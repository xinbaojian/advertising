import functools
import os
import time

import cv2
import numpy as np
import pyautogui

from applescript import call_iphone


@functools.lru_cache(maxsize=32)
def _load_template(template_path):
    """读取并缓存模板图片：同一文件在循环里不重复读盘/解码。"""
    return cv2.imread(template_path, cv2.IMREAD_COLOR)


def capture_screen_frame():
    """截取全屏并转换为 OpenCV BGR 帧。

    一轮 UI 判断只截一次屏，多个模板都在这同一帧上匹配：
    避免重复截图的开销，同时保证多个元素的状态判断基于同一时刻。

    Returns:
        tuple: (frame, scale_x, scale_y)
            frame: BGR numpy 数组（像素尺寸，Retina 下为逻辑尺寸的 2x）
            scale_x / scale_y: 像素 / 逻辑点 比例
    """
    screenshot = pyautogui.screenshot()
    shot_w, shot_h = screenshot.size
    screen_width, screen_height = pyautogui.size()

    scale_x = (shot_w / screen_width) if screen_width else 1.0
    scale_y = (shot_h / screen_height) if screen_height else 1.0

    frame = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    return frame, scale_x, scale_y


def find_image_in_frame(frame, template_path, scale_x=1.0, scale_y=1.0,
                        threshold=0.8, window_bounds=None):
    """
    在已截取的帧上查找图片模板的位置（不重复截图）

    Args:
        frame: capture_screen_frame() 返回的 BGR 帧
        template_path: 模板图片路径
        scale_x / scale_y: capture_screen_frame() 返回的缩放比例
        threshold: 匹配阈值，范围0-1，值越高表示匹配要求越严格
        window_bounds: 可选，(x1, y1, x2, y2) 屏幕逻辑坐标，用于限定在该窗口内匹配

    Returns:
        tuple: (x, y) 逻辑坐标，如果未找到返回 None
    """
    # 检查图片文件是否存在
    if not os.path.exists(template_path):
        print(f"错误：图片文件不存在 - {template_path}")
        return None

    # 读模板（命中缓存），模板异常时就不必白匹配一次
    template = _load_template(template_path)
    if template is None:
        print(f"错误：无法读取模板图片 - {template_path}")
        return None
    template_h, template_w = template.shape[:2]

    shot_h, shot_w = frame.shape[:2]

    # 计算匹配用的图像与坐标偏移
    use_roi = False
    rx1 = ry1 = 0
    match_img = frame

    if window_bounds and isinstance(window_bounds, tuple) and len(window_bounds) == 4:
        x1, y1, x2, y2 = window_bounds
        if x2 > x1 and y2 > y1:
            # 将窗口逻辑边界映射到截图像素坐标
            rx1 = max(0, int(round(x1 * scale_x)))
            ry1 = max(0, int(round(y1 * scale_y)))
            rx2 = min(shot_w, int(round(x2 * scale_x)))
            ry2 = min(shot_h, int(round(y2 * scale_y)))
            if rx2 > rx1 and ry2 > ry1:
                match_img = frame[ry1:ry2, rx1:rx2]
                use_roi = True

    # 使用模板匹配（在 ROI 或全帧上）
    result = cv2.matchTemplate(match_img, template, cv2.TM_CCOEFF_NORMED)

    # 找到最大匹配值的位置
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # 检查最大匹配值是否超过阈值
    if max_val >= threshold:
        # 计算匹配区域的中心像素坐标（相对全帧像素）
        center_x_px = max_loc[0] + template_w // 2 + (rx1 if use_roi else 0)
        center_y_px = max_loc[1] + template_h // 2 + (ry1 if use_roi else 0)

        # 转换为屏幕逻辑坐标
        logical_x = int(round(center_x_px / scale_x))
        logical_y = int(round(center_y_px / scale_y))

        # 返回逻辑坐标，便于后续用 pyautogui.click
        return (logical_x, logical_y)
    else:
        return None


def find_images_in_frame(frame, template_paths, scale_x=1.0, scale_y=1.0,
                         threshold=0.8, window_bounds=None):
    """
    在帧上按顺序查找多个模板，返回第一个命中的结果

    适用于同一按钮的多张截图变体（如 success.png / success1.png），
    多个模板共享同一次截图，按顺序取第一个超过阈值的。

    Args:
        frame: capture_screen_frame() 返回的 BGR 帧
        template_paths: 模板图片路径列表（按优先级排序）
        scale_x / scale_y: capture_screen_frame() 返回的缩放比例
        threshold: 匹配阈值，范围0-1
        window_bounds: 可选，(x1, y1, x2, y2) 屏幕逻辑坐标

    Returns:
        tuple: (template_path, position)，均未命中返回 (None, None)
    """
    for template_path in template_paths:
        position = find_image_in_frame(frame, template_path, scale_x, scale_y,
                                       threshold, window_bounds)
        if position:
            return template_path, position
    return None, None


def find_image_on_screen(template_path, threshold=0.8, window_bounds=None):
    """
    在屏幕上查找图片模板的位置（单次截图，供低频调用方使用）

    需要在一帧上匹配多个模板时，请改用 capture_screen_frame()
    + find_image_in_frame() / find_images_in_frame() 组合，避免重复截图。

    Args:
        template_path: 模板图片路径
        threshold: 匹配阈值，范围0-1，值越高表示匹配要求越严格
        window_bounds: 可选，(x1, y1, x2, y2) 屏幕逻辑坐标，用于限定在该窗口内匹配

    Returns:
        tuple: (x, y) 逻辑坐标，如果未找到返回 None
    """
    frame, scale_x, scale_y = capture_screen_frame()
    return find_image_in_frame(frame, template_path, scale_x, scale_y,
                               threshold, window_bounds)


def find_qi_shui_icon():
    """
    查找汽水音乐App图标位置
    """
    return find_image_on_screen("images/icon/qishui.png")

def click_qi_shui_icon():
    """
    点击汽水音乐App图标
    """
    icon_pos = find_qi_shui_icon()
    if icon_pos:
        pyautogui.click(icon_pos)
        print(f"已点击汽水音乐图标 {icon_pos}")
    else:
        print("未找到汽水音乐图标")


def countdown(times=1):
    """
    倒计时
    times: 倒计时秒数，默认1秒
    """
    for i in range(times, 0, -1):
        print(f"{i}...")
        time.sleep(1)


def un_lock():
    print("正在启动iPhone镜像应用...")
    call_iphone()
    time.sleep(3)

    while True :
        # 输入密码
        typepwd_pos = find_image_on_screen("images/typepwd.png")
        if not typepwd_pos:
            typepwd_pos = find_image_on_screen("images/typepwd1.png")
        if not typepwd_pos:
            print("未找到输入密码界面")
            time.sleep(3)
        else:
            pyautogui.click(typepwd_pos)
            pyautogui.typewrite('xinbj')
            pyautogui.press('enter')
            print("已输入密码，等待解锁")
            countdown(5)

        if find_image_on_screen("images/safari.png"):
            print("屏幕已解锁，开始执行任务")
            break
