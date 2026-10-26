from protocol import (
    create_frame_packet,
    parse_frame_packet,
    HEADER_SIZE,
    CRC_SIZE,
)


def main():

    print("========== Protocol Test ==========")

    # 建立測試資料
    frame_id = 123
    width = 640
    height = 480

    # 假裝這是一張 640x480 的 GRAY8 影像
    payload = bytes(width * height)

    print(f"Frame ID      : {frame_id}")
    print(f"Width         : {width}")
    print(f"Height        : {height}")
    print(f"Payload Size  : {len(payload)} bytes")

    # 建立封包
    packet = create_frame_packet(
        frame_id,
        width,
        height,
        payload
    )

    print(f"Header Size   : {HEADER_SIZE} bytes")
    print(f"CRC Size      : {CRC_SIZE} bytes")
    print(f"Packet Size   : {len(packet)} bytes")

    # 解析封包
    result = parse_frame_packet(packet)

    print()
    print("========== Parse Result ==========")

    print(f"Frame ID      : {result['frame_id']}")
    print(f"Width         : {result['width']}")
    print(f"Height        : {result['height']}")
    print(f"Pixel Format  : {result['pixel_format']}")
    print(f"Payload Size  : {result['payload_size']} bytes")

    # 確認資料是否完全一致
    assert result["frame_id"] == frame_id
    assert result["width"] == width
    assert result["height"] == height
    assert result["payload"] == payload

    print()
    print("===================================")
    print("Protocol Test PASSED!")
    print("===================================")


if __name__ == "__main__":
    main()