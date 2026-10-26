# ---------- Packet Header ----------
import struct
import zlib


# ============================================================
# Protocol Configuration & Imports
# ============================================================

from config import (
    MAGIC,
    VERSION,
    TYPE_FRAME,
    TYPE_TEXT,
    PIXEL_FORMAT_GRAY8,
    PIXEL_FORMAT_BGR24,
    PIXEL_FORMAT_RGB24,
    HEADER_FORMAT,
    HEADER_SIZE,
    CRC_SIZE,
    MAX_FRAME_ID,
    MAX_WIDTH,
    MAX_HEIGHT,
    MAX_PAYLOAD_SIZE,
)


# ============================================================
# Create Packet (Frame / Text)
# ============================================================

def create_frame_packet(frame_id, width, height, payload, pixel_format=PIXEL_FORMAT_GRAY8):
    """建立影像 Frame 封包。"""
    if not (0 <= width <= MAX_WIDTH):
        raise ValueError(f"Width 超出範圍：{width}")

    if not (0 <= height <= MAX_HEIGHT):
        raise ValueError(f"Height 超出範圍：{height}")

    if not (0 <= frame_id <= MAX_FRAME_ID):
        raise ValueError(f"Frame ID 超出範圍：{frame_id}")

    if pixel_format not in (PIXEL_FORMAT_GRAY8, PIXEL_FORMAT_BGR24, PIXEL_FORMAT_RGB24):
        raise ValueError(f"不支援的 Pixel Format：{pixel_format}")

    payload_size = len(payload)
    if payload_size > MAX_PAYLOAD_SIZE:
        raise ValueError(f"Payload 太大：{payload_size} bytes")

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        TYPE_FRAME,
        frame_id,
        width,
        height,
        pixel_format,
        payload_size,
    )

    crc = zlib.crc32(payload)
    crc_bytes = struct.pack("<I", crc)

    return header + payload + crc_bytes


def create_text_packet(message, frame_id=0):
    """建立 UTF-8 純文字封包。"""
    if not isinstance(message, str):
        raise TypeError("message 必須是 str")

    if not isinstance(frame_id, int) or isinstance(frame_id, bool):
        raise TypeError("frame_id 必須是整數")

    if not (0 <= frame_id <= MAX_FRAME_ID):
        raise ValueError(f"Frame ID 超出範圍：{frame_id}")

    payload = message.encode("utf-8")
    payload_size = len(payload)

    if payload_size > MAX_PAYLOAD_SIZE:
        raise ValueError(f"Payload 太大：{payload_size} bytes")

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        TYPE_TEXT,
        frame_id,
        0,  # width
        0,  # height
        0,  # pixel_format
        payload_size,
    )

    crc = zlib.crc32(payload)
    crc_bytes = struct.pack("<I", crc)

    return header + payload + crc_bytes


# ============================================================
# Parse Single Packet (Unified Dispatcher)
# ============================================================

def parse_packet(packet: bytes) -> dict:
    """
    通用單一完整封包解析進入點。
    會自動驗證 Header、CRC32，並根據 TYPE_FRAME 或 TYPE_TEXT 解析出對應格式。
    """
    if len(packet) < HEADER_SIZE + CRC_SIZE:
        raise ValueError("Packet 太短")

    header_data = packet[:HEADER_SIZE]
    (
        magic,
        version,
        packet_type,
        frame_id,
        width,
        height,
        pixel_format,
        payload_size,
    ) = struct.unpack(HEADER_FORMAT, header_data)

    if magic != MAGIC:
        raise ValueError(f"MAGIC 錯誤：0x{magic:X}，預期 0x{MAGIC:X}")

    if version != VERSION:
        raise ValueError(f"VERSION 不支援：{version}")

    expected_size = HEADER_SIZE + payload_size + CRC_SIZE
    if len(packet) != expected_size:
        raise ValueError(
            f"Packet 長度錯誤：實際 {len(packet)} bytes，預期 {expected_size} bytes"
        )

    payload_start = HEADER_SIZE
    payload_end = payload_start + payload_size
    payload = packet[payload_start:payload_end]

    received_crc = struct.unpack("<I", packet[payload_end:expected_size])[0]
    calculated_crc = zlib.crc32(payload)

    if received_crc != calculated_crc:
        raise ValueError("CRC32 檢查失敗")

    base_result = {
        "version": version,
        "packet_type": packet_type,
        "frame_id": frame_id,
        "payload_size": payload_size,
        "payload": payload,
    }

    if packet_type == TYPE_FRAME:
        if pixel_format not in (PIXEL_FORMAT_GRAY8, PIXEL_FORMAT_BGR24, PIXEL_FORMAT_RGB24):
            raise ValueError(f"Pixel Format 不支援：{pixel_format}")

        base_result.update({
            "type_name": "FRAME",
            "width": width,
            "height": height,
            "pixel_format": pixel_format,
        })
        return base_result

    elif packet_type == TYPE_TEXT:
        try:
            message = payload.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ValueError("文字封包無法以 UTF-8 解碼") from err

        base_result.update({
            "type_name": "TEXT",
            "message": message,
        })
        return base_result

    else:
        raise ValueError(f"未知的封包類型 (packet_type={packet_type})")


def parse_frame_packet(packet: bytes) -> dict:
    """專門解析 Frame Packet（向後相容舊介面）。"""
    result = parse_packet(packet)
    if result["packet_type"] != TYPE_FRAME:
        raise ValueError("Packet TYPE 不是 FRAME")
    return result


def parse_text_packet(packet: bytes) -> dict:
    """專門解析 Text Packet。"""
    result = parse_packet(packet)
    if result["packet_type"] != TYPE_TEXT:
        raise ValueError("Packet TYPE 不是 TEXT")
    return result


# ============================================================
# Stream Receiver / Buffer Manager
# ============================================================

class StreamReceiver:
    """
    接收端緩衝區管理器。
    為每一台連進來的電腦（無論是傳送文字或影像串流）各自建立一個實例，
    負責處理網路傳輸產生的「黏包」、「斷包/分包」與「雜訊對齊」。
    """

    def __init__(self):
        self._buffer = bytearray()
        # 取得 MAGIC 對應的 bytes 格式
        self._magic_bytes = struct.pack(HEADER_FORMAT[0] + "I" if HEADER_FORMAT[0] in "<>!=" else "<I", MAGIC)

    def feed(self, data: bytes):
        """將 socket.recv() 收到的位元組資料塞入暫存區"""
        if data:
            self._buffer.extend(data)

    def extract_packets(self):
        """
        嘗試從緩衝區切出所有已收齊的封包。
        以 Generator 依序 yield 解析後的封包 dict。
        """
        while True:
            # 1. 緩衝區長度不足以容納 Header 則跳出等待更多資料
            if len(self._buffer) < HEADER_SIZE:
                break

            # 2. 同步 MAGIC，防止封包前面夾帶雜訊或損毀位元
            idx = self._buffer.find(self._magic_bytes)
            if idx == -1:
                # 完全找不到 MAGIC，保留末端長度避免 MAGIC 被跨包切斷
                keep_len = len(self._magic_bytes) - 1
                del self._buffer[:-keep_len]
                break
            elif idx > 0:
                # 丟棄 MAGIC 之前的雜訊
                del self._buffer[:idx]
                if len(self._buffer) < HEADER_SIZE:
                    break

            # 3. 預讀 Payload Size
            header_data = bytes(self._buffer[:HEADER_SIZE])
            (
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                payload_size,
            ) = struct.unpack(HEADER_FORMAT, header_data)

            total_packet_size = HEADER_SIZE + payload_size + CRC_SIZE

            # 4. 檢查整個封包是否已經接收完整
            if len(self._buffer) < total_packet_size:
                break

            # 5. 擷取完整封包並移出緩衝區
            raw_packet = bytes(self._buffer[:total_packet_size])
            del self._buffer[:total_packet_size]

            # 6. 解析並回傳
            try:
                yield parse_packet(raw_packet)
            except ValueError as err:
                # 遇 CRC 錯誤或未知格式時丟棄，繼續嘗試下一筆
                print(f"[StreamReceiver Warning] 無效封包已略過: {err}")