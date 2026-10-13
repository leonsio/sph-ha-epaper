#!/usr/bin/env python3
"""Prepare PNG/BMP/JPEG as BMP or packed Gray4; do not dither again."""
import argparse
from pathlib import Path
import struct
from PIL import Image, ImageOps

def prepare(source, destination, width=1872, height=1404, fit='contain'):
    with Image.open(source) as src:
        image = ImageOps.exif_transpose(src).convert('L')
        if image.size != (width, height):
            size = (width, height)
            if fit == 'cover':
                image = ImageOps.fit(image, size, method=Image.Resampling.NEAREST)
            else:
                inner = ImageOps.contain(image, size, method=Image.Resampling.NEAREST)
                image = Image.new('L', size, 255)
                image.paste(inner, ((width-inner.width)//2, (height-inner.height)//2))
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix.lower() == '.bmp':
            image.save(destination, 'BMP')
        elif destination.suffix.lower() == '.gray4':
            data = image.tobytes()
            with destination.open('wb') as f:
                f.write(struct.pack('<4sHH', b'G4E1', width, height))
                for y in range(height):
                    row = data[y*width:(y+1)*width]
                    q = [min(15, (v+8)//16) for v in row]
                    f.write(bytes((q[x]<<4)|(q[x+1] if x+1<width else 15)
                                  for x in range(0,width,2)))
        else:
            raise ValueError('Ausgabe muss .bmp oder .gray4 sein')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--width', type=int, default=1872)
    parser.add_argument('--height', type=int, default=1404)
    parser.add_argument('--fit', choices=['contain','cover'], default='contain')
    args = parser.parse_args()
    if not (1 <= args.width <= 8192 and 1 <= args.height <= 8192):
        parser.error('Abmessungen muessen zwischen 1 und 8192 liegen')
    prepare(args.source, args.destination, args.width, args.height, args.fit)
