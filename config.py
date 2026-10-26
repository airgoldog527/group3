import struct

# ============================================================
# Protocol Settings
# ============================================================

MAGIC = 0x4652414D   # ASCII: "FRAM"

VERSION = 1

TYPE_FRAME = 0x01
TYPE_TEXT = 0x02

# 像素格式定義 (與傳送端協議一致即可)
PIXEL_FORMAT_GRAY8 = 0x01
PIXEL_FORMAT_BGR24 = 0x02   # OpenCV 預設色彩排列 (Blue, Green, Red)
PIXEL_FORMAT_RGB24 = 0x03   # 標準 RGB 排列

# ============================================================
# Packet Structure
# ============================================================

HEADER_FORMAT = "<IBBIHHBI"
# Header 格式
#
# <    = Little Endian
# I    = uint32  MAGIC
# B    = uint8   VERSION
# B    = uint8   TYPE
# I    = uint32  FRAME_ID
# H    = uint16  WIDTH
# H    = uint16  HEIGHT
# B    = uint8   PIXEL_FORMAT
# I    = uint32  PAYLOAD_SIZE
#
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

CRC_SIZE = 4

# ============================================================
# TCP Settings
# ============================================================

# 手繪圖中標示 Port 為 5000
TCP_PORT = 5000

# ============================================================
# Frame Settings
# ============================================================

MAX_FRAME_ID = 0xFFFFFFFF
MAX_WIDTH = 0xFFFF
MAX_HEIGHT = 0xFFFF
MAX_PAYLOAD_SIZE = 0xFFFFFFFF