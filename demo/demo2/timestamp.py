import time

# 获取当前时间（单位：秒）并转换为毫秒级时间戳
timestamp_ms = int(time.time() * 1000)

print("当前毫秒级时间戳：", timestamp_ms)