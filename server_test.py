import struct
import numpy as np
import cv2
import threading

from config import (
    HEADER_FORMAT,
    HEADER_SIZE,
    CRC_SIZE,
    TCP_PORT,
    PIXEL_FORMAT_BGR24,
    PIXEL_FORMAT_RGB24,
)

from protocol import parse_packet
from transport import TCPTransport


# ============================================================
# Server Settings
# ============================================================

# 使用 0.0.0.0 才能同時接收來自 Wi-Fi 或有線網路的兩台電腦
HOST = "0.0.0.0"


# ============================================================
# Client Connection Handler
# ============================================================

def handle_client(client_transport, client_id):
    """
    專門處理個別客戶端（文字端或影片端）持續傳輸的執行緒
    """
    print(f"[Server] Client #{client_id} 開始通訊...")
    try:
        while True:
            # 1. 接收 Header
            header = client_transport.receive_exactly(HEADER_SIZE)
            if not header:
                print(f"[Server] Client #{client_id} 已斷開連線")
                break

            # 2. 解析 Header
            (
                magic,
                version,
                packet_type,
                frame_id,
                width,
                height,
                pixel_format,
                payload_size,
            ) = struct.unpack(HEADER_FORMAT, header)

            # 3. 接收 Payload + CRC
            remaining = client_transport.receive_exactly(payload_size + CRC_SIZE)
            if not remaining:
                print(f"[Server] Client #{client_id} 封包接收不完整，已中斷")
                break

            # 4. 組回完整 Packet 並通用解析
            packet = header + remaining
            result = parse_packet(packet)

            # 5. 根據封包類型分別處理
            if result["type_name"] == "TEXT":
                print()
                print(f"================ [收到文字訊息 #{result['frame_id']}] ================")
                print(f"內容: {result['message']}")
                print("=========================================================")

            elif result["type_name"] == "FRAME":
                print()
                print(f"================ [收到影像幀 #{result['frame_id']}] ================")
                print(f"Image Size   : {result['width']} × {result['height']}")
                print(f"Payload Size : {result['payload_size']} bytes")
                print("=========================================================")

                # 依據格式還原影像並存檔
                if result["pixel_format"] in (PIXEL_FORMAT_BGR24, PIXEL_FORMAT_RGB24):
                    image = np.frombuffer(result["payload"], dtype=np.uint8).reshape(
                        result["height"], result["width"], 3
                    )
                    if result["pixel_format"] == PIXEL_FORMAT_RGB24:
                        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                else:
                    # 預設 GRAY8
                    image = np.frombuffer(result["payload"], dtype=np.uint8).reshape(
                        result["height"], result["width"]
                    )

                filename = f"received_frame_{result['frame_id']}.png"
                cv2.imwrite(filename, image)
                print(f"[Server] 影像已存為 {filename}")

    except Exception as e:
        print(f"[Server] Client #{client_id} 處理異常: {e}")
    finally:
        client_transport.close()


# ============================================================
# Main Server Loop
# ============================================================

def main():
    print("========================================")
    print("   Frame & Text Unified Server")
    print("========================================")

    server_transport = TCPTransport(HOST, TCP_PORT)
    print(f"[Server] 伺服端監聽中 (Port: {TCP_PORT})，等待連線...")

    client_count = 0
    try:
        while True:
            # 等待任一台電腦連入
            client_transport = server_transport.listen()
            client_count += 1
            print(f"[Server] 偵測到新連線，指派為 Client #{client_count}")

            # 開啟獨立執行緒處理該連線，避免文字端與影片端互相卡住
            t = threading.Thread(
                target=handle_client,
                args=(client_transport, client_count),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        print("\n[Server] 正在停止伺服端...")
    finally:
        server_transport.close()


if __name__ == "__main__":
    main()