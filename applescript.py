import subprocess


def run_applescript(script: str) -> None:
    """
    执行AppleScript
    使用 stdin 传递脚本，避免 -e 多行/转义问题，并开启 check 以捕获非 0 退出码
    """
    try:
        completed = subprocess.run(
            ["osascript"],
            input=script.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        if completed.stdout:
            print(completed.stdout.decode("utf-8", errors="ignore").strip())
    except subprocess.CalledProcessError as e:
        err_out = e.stderr.decode("utf-8", errors="ignore").strip()
        print("AppleScript 执行失败:")
        print(err_out or str(e))
    except Exception as e:
        print(f"执行AppleScript时发生未知错误: {e}")


def get_window_bounds():
    """
    获取 iPhone 镜像窗口的逻辑坐标边界 (x1, y1, x2, y2)，失败返回 None

    用于把模板匹配限制在窗口 ROI 内：Retina 全屏下窗口通常只占约 12% 面积，
    匹配耗时约为全屏的 1/10。返回 None 时调用方应回退到全屏匹配。
    """
    apple_script = """
        -- 通过 Bundle ID 获取应用当前语言环境下的名称
        set appName to name of application id "com.apple.ScreenContinuity"
        tell application "System Events"
            tell process appName
                set p to position of window 1
                set s to size of window 1
                return {item 1 of p, item 2 of p, (item 1 of p) + (item 1 of s), (item 2 of p) + (item 2 of s)}
            end tell
        end tell
    """
    try:
        completed = subprocess.run(
            ["osascript"],
            input=apple_script.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        err_out = e.stderr.decode("utf-8", errors="ignore").strip()
        print("获取窗口边界失败:")
        print(err_out or str(e))
        return None
    except Exception as e:
        print(f"获取窗口边界时发生未知错误: {e}")
        return None

    output = completed.stdout.decode("utf-8", errors="ignore").strip()
    try:
        values = [int(round(float(v.strip()))) for v in output.split(",")]
    except ValueError:
        print(f"无法解析窗口边界: {output}")
        return None

    if len(values) != 4:
        print(f"窗口边界格式异常: {output}")
        return None

    x1, y1, x2, y2 = values
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def call_iphone():
    """
    通过 Bundle ID 获取应用名称，保证在不同语言环境下都能找到正确的进程名称
    然后激活应用，并将第一个窗口移动到指定位置
    """
    apple_script = """
        -- 通过 Bundle ID 获取应用当前语言环境下的名称
        set appName to name of application id "com.apple.ScreenContinuity"
        
        -- 激活应用（通过 Bundle ID，避免本地化名称差异）
        tell application id "com.apple.ScreenContinuity"
            activate
        end tell
        
        -- 使用 UI 脚本移动窗口位置
        tell application "System Events"
            tell process appName
                try
                    set position of window 1 to {1, 50}
                on error errMsg number errNum
                    -- 如果窗口不存在或无权限，输出更清晰的错误提示
                    error "无法设置窗口位置: " & errMsg & " (" & errNum & ")"
                end try
            end tell
        end tell
    """
    run_applescript(apple_script)
