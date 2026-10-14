import random
import time
from typing import Optional

import pyautogui

from applescript import get_window_bounds
from screen import (
    call_iphone,
    capture_screen_frame,
    countdown,
    find_image_in_frame,
    find_images_in_frame,
)

# 图片路径前缀
IMAGE_PREFIX = "images/qishui/"

# 固定坐标
LIVESTREAM_CLOSE_FALLBACK = (295, 143)

# 循环与延迟配置
MAX_LOOP_COUNT = 90
AD_WAIT_INTERVAL = 5
POST_CLICK_DELAY = 1
REWARD_CLICK_DELAY = 2
REWARD_POLL_TIMEOUT = 3      # 点击成功后轮询奖励弹窗的最长时间（秒）
REWARD_POLL_INTERVAL = 0.5   # 奖励弹窗轮询间隔（秒）
MEMBER_UNLOCK_INTERVAL = 3
INIT_COUNTDOWN = 5

# 全局坐标缓存：只缓存喇叭图标这类位置固定、且漏点会导致流程卡住的按钮
_coordinates_cache: dict = {}


def _get_cached(*image_names: str) -> Optional[tuple]:
    """按顺序查找缓存坐标，命中即返回。"""
    for image_name in image_names:
        cached = _coordinates_cache.get(IMAGE_PREFIX + image_name)
        if cached:
            print(f"使用缓存坐标: {image_name} -> {cached}")
            return cached
    return None


def _set_cache(image_name: str, position: tuple) -> None:
    """缓存静态按钮坐标。"""
    _coordinates_cache[IMAGE_PREFIX + image_name] = position
    print(f"缓存坐标: {image_name} -> {position}")


def _find(frame, scale_x, scale_y, image_name, window_bounds=None) -> Optional[tuple]:
    """在当前帧上查找单个图片（自动补路径前缀）。"""
    return find_image_in_frame(
        frame, IMAGE_PREFIX + image_name, scale_x, scale_y, window_bounds=window_bounds
    )


def _find_any(frame, scale_x, scale_y, image_names, window_bounds=None) -> Optional[tuple]:
    """在当前帧上按顺序查找多个图片，返回第一个命中的坐标。

    用于同一按钮的多张截图变体（如 success.png / success1.png）。
    """
    paths = [IMAGE_PREFIX + name for name in image_names]
    _, position = find_images_in_frame(
        frame, paths, scale_x, scale_y, window_bounds=window_bounds
    )
    return position


def qishui_ad() -> None:
    """主流程：启动 iPhone 镜像应用并查找目标图片。"""
    call_iphone()
    countdown(INIT_COUNTDOWN)


def _poll_for_reward(window_bounds=None) -> Optional[tuple]:
    """查找领取奖励按钮。

    reward1.png / reward2.png 是同一按钮的不同配色变体，按顺序取第一个命中。
    在超时时间内轮询屏幕而不直接信任缓存坐标：
    既避免奖励弹窗出现慢于固定等待时间而导致漏领，
    也避免点到已失效的旧坐标却误判为领取成功。
    """
    deadline = time.monotonic() + REWARD_POLL_TIMEOUT
    while True:
        frame, scale_x, scale_y = capture_screen_frame()
        position = _find_any(
            frame, scale_x, scale_y, ("reward1.png", "reward2.png"), window_bounds
        )
        if position:
            return position
        if time.monotonic() >= deadline:
            return None
        time.sleep(REWARD_POLL_INTERVAL)


def _click_speaker(window_bounds=None) -> None:
    """点击喇叭图标继续任务。

    优先用当前帧实测到的位置；识别不到时回退到缓存坐标——
    喇叭图标位置固定，盲点一次也比漏点导致流程卡住要好
    （不点喇叭就无法进入下一个广告）。
    """
    frame, scale_x, scale_y = capture_screen_frame()
    horn_pos = _find(frame, scale_x, scale_y, "speaker.png", window_bounds)
    if horn_pos:
        _set_cache("speaker.png", horn_pos)
    else:
        horn_pos = _get_cached("speaker.png")
        if horn_pos:
            print("未识别到喇叭图标，回退缓存坐标")

    if horn_pos:
        print(f"点击喇叭图标(逻辑坐标): {horn_pos}")
        pyautogui.click(horn_pos)
    else:
        print("未找到喇叭图标")


def _try_claim_reward(window_bounds=None) -> bool:
    """尝试领取奖励并点击喇叭。返回 True 表示成功领取奖励。"""
    reward_pos = _poll_for_reward(window_bounds)
    if not reward_pos:
        print("未找到领取奖励按钮")
        return False

    print(f"领取奖励位置(逻辑坐标): {reward_pos}")
    pyautogui.click(reward_pos)
    time.sleep(REWARD_CLICK_DELAY)

    _click_speaker(window_bounds)
    return True


def loop_process() -> None:
    """主循环：自动点击广告并领取奖励。"""
    count = 0
    day = 0

    while count < MAX_LOOP_COUNT:
        # 每轮只截一次屏，所有判断基于同一帧：
        # 既避免重复截图的开销，也消除多次截图之间的状态竞态
        frame, scale_x, scale_y = capture_screen_frame()

        # 每轮刷新窗口边界，把匹配限制在 iPhone 镜像窗口内
        # （窗口约占全屏 12% 面积，实测匹配提速约 10 倍）；
        # 查询失败返回 None 时自动回退到全屏匹配
        window_bounds = get_window_bounds()

        # finished.png / finished1.png：任务完成后的终态提示（如「第30日畅听」弹窗），
        # 出现即表示已无可领取的奖励，直接结束
        if _find_any(
            frame, scale_x, scale_y, ("finished.png", "finished1.png"), window_bounds
        ):
            print("任务完成")
            break

        success_pos = _find_any(
            frame, scale_x, scale_y, ("success.png", "success1.png"), window_bounds
        )
        if success_pos:
            print(f"成功图片位置(逻辑坐标): {success_pos}，随机延迟1-5秒")
            countdown(random.randint(1, 5))
            pyautogui.click(success_pos)
            time.sleep(POST_CLICK_DELAY)

            if _try_claim_reward(window_bounds):
                count += 1
                print(f"第{count}次循环")
                if count % MEMBER_UNLOCK_INTERVAL == 0:
                    day += 1
                    print(f"已解锁{day}天会员")
                    time.sleep(1)
            continue

        retry_pos = _find(frame, scale_x, scale_y, "retry.png", window_bounds)
        if retry_pos:
            print("广告未加载完成")
            pyautogui.click(retry_pos)
            continue

        if _find(frame, scale_x, scale_y, "guan-zhu.png", window_bounds):
            print("进入了直播界面")
            close_pos = _find(frame, scale_x, scale_y, "gz-close.png", window_bounds)
            if close_pos:
                pyautogui.click(close_pos)
                print(f"已关闭直播 {close_pos}")
            else:
                print("未找到关闭按钮,尝试点击固定位置")
                pyautogui.click(LIVESTREAM_CLOSE_FALLBACK)
            continue

        print("广告未播放完毕，继续等待ing")
        time.sleep(AD_WAIT_INTERVAL)
