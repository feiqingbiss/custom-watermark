# -*- coding: utf-8 -*-
"""
从一张大尺寸 PNG 生成多尺寸 ICO，以及按命名规则输出多尺寸 PNG。
用法：
    python make_icon.py icon\icon_source.png
或放到项目根目录直接双击运行（需把 source_png 改好）。
生成：
    icon/icon.ico
    icon/icon_16.png, icon_32.png, icon_48.png, icon_64.png, icon_128.png, icon_256.png
"""
import os
import sys
from PIL import Image

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon')

# ICO 里包含的尺寸（Windows 推荐）
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# 单张 PNG 导出尺寸（给 tk iconphoto 多尺寸用）
PNG_SIZES = [16, 32, 48, 64, 128, 256]


def main():
    if len(sys.argv) >= 2:
        src = sys.argv[1]
    else:
        # 默认查找 icon 目录下常见命名
        candidates = ['icon_source.png', 'icon.png', 'icon_512.png', 'icon_1024.png']
        src = None
        for c in candidates:
            p = os.path.join(ICON_DIR, c)
            if os.path.exists(p):
                src = p
                break
        if src is None:
            print("未找到源 PNG。请把一张大尺寸 PNG 放到 icon/ 下，或运行：")
            print("    python make_icon.py icon\\你的图.png")
            input("按回车退出...")
            return

    if not os.path.exists(src):
        print(f"源文件不存在: {src}")
        input("按回车退出...")
        return

    os.makedirs(ICON_DIR, exist_ok=True)

    print(f"源图片: {src}")
    img = Image.open(src).convert('RGBA')
    print(f"原始尺寸: {img.size[0]}x{img.size[1]}")

    # 1) 生成多尺寸 ICO
    ico_path = os.path.join(ICON_DIR, 'icon.ico')
    img.save(ico_path, format='ICO', sizes=ICO_SIZES)
    print(f"[OK] 生成 {ico_path}  (尺寸: {ICO_SIZES})")

    # 2) 生成多尺寸 PNG
    for size in PNG_SIZES:
        out = os.path.join(ICON_DIR, f'icon_{size}.png')
        im2 = img.copy()
        im2.thumbnail((size, size), Image.LANCZOS)
        im2.save(out, format='PNG', optimize=True)
        print(f"[OK] 生成 {out}")

    print()
    print("完成！请把 icon/icon_source.png 删掉或保留均可，不影响打包。")
    print("接下来直接运行 打包成exe.bat 即可。")
    input("按回车退出...")


if __name__ == '__main__':
    main()