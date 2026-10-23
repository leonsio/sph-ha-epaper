"""Host regression for the actual SD PNG loader.

Requires Pillow, gcc/g++, and PNGLE_SOURCE_DIR pointing to pngle v1.1.0.
Optional SD_PNG_SAMPLE adds a real image (not stored in the repository).
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class SdPngDecoderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PIL import Image
        except ImportError:
            raise unittest.SkipTest("Pillow required")
        cls.Image = Image
        source = os.environ.get("PNGLE_SOURCE_DIR")
        if not source or not shutil.which("gcc") or not shutil.which("g++"):
            raise unittest.SkipTest("Set PNGLE_SOURCE_DIR to pngle v1.1.0; gcc/g++ required")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        root = Path(__file__).resolve().parents[1]
        code = (root / "components/sd_screensaver/sd_screensaver.cpp").read_text()
        code = code[code.index("// PNGLE expands"):code.index("bool SDScreensaver::load_gray4_")]
        prefix = r'''
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <chrono>
#include <pngle.h>
template<class T>struct RAMAllocator{enum{ALLOC_INTERNAL=2};RAMAllocator()=default;explicit RAMAllocator(int){} T* allocate(size_t n){if(n<8192 && getenv("SD_TEST_NO_ROW"))return nullptr;return (T*)malloc(n);}void deallocate(T*p,size_t){free(p);}};
static uint32_t micros(){return std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
struct {void feed_wdt(){}} App;
#define ESP_LOGW(tag,...) fprintf(stderr,__VA_ARGS__)
#define ESP_LOGI(tag,...) fprintf(stderr,__VA_ARGS__)
static uint8_t gray4(uint8_t v){return std::min(15,(int(v)+8)>>4);}
struct SDScreensaver{int width_,height_;bool load_png_(const std::string&,uint8_t*);};
'''
        main = r'''
int main(int argc,char**argv){
if(argc!=5)return 2;
SDScreensaver s{atoi(argv[2]),atoi(argv[3])};
std::vector<uint8_t> out((s.width_+1)/2*s.height_,255);
if(!s.load_png_(argv[1],out.data()))return 1;
FILE*f=fopen(argv[4],"wb");fwrite(out.data(),1,out.size(),f);fclose(f);
}
'''
        (cls.work / "loader.cpp").write_text(prefix + code + main)
        src = Path(source) / "src"
        for name in ("pngle", "miniz"):
            subprocess.run(["gcc", "-O2", "-c", str(src / (name + ".c")),
                            "-o", str(cls.work / (name + ".o"))], check=True)
        cls.binary = cls.work / "loader"
        subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-I" + str(src), str(cls.work / "loader.cpp"),
                        str(cls.work / "pngle.o"), str(cls.work / "miniz.o"),
                        "-o", str(cls.binary)], check=True)

    def decode(self, path, width, height):
        output = self.work / "out.gray4"
        result = subprocess.run([str(self.binary), str(path), str(width), str(height),
                                 str(output)], capture_output=True)
        return result, output

    def check_pixels(self, path, width, height):
        result, output = self.decode(path, width, height)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.Image.open(path) as source:
            image = source.convert("RGBA")
        iw, ih = image.size
        scale = min(width / iw, height / ih)
        dw, dh = max(1, int(iw * scale)), max(1, int(ih * scale))
        ox, oy = (width - dw) // 2, (height - dh) // 2
        expected = bytearray([255] * ((width + 1) // 2 * height))
        pixels = image.load()
        for y in range(dh):
            for x in range(dw):
                r, g, b, a = pixels[x * iw // dw, y * ih // dh]
                luminance = (77 * r + 150 * g + 29 * b + 128) >> 8
                luminance = (luminance * a + 255 * (255 - a) + 127) // 255
                value = min(15, (luminance + 8) >> 4)
                px = x + ox
                index = (y + oy) * ((width + 1) // 2) + px // 2
                expected[index] = ((expected[index] & 240) | value if px & 1
                                   else (expected[index] & 15) | (value << 4))
        self.assertEqual(output.read_bytes(), expected)

    def test_formats_scaling_alpha_and_interlace(self):
        image = self.Image.new("RGBA", (31, 19))
        image.putdata([((i * 37) % 256, (i * 19) % 256, (i * 53) % 256,
                        (i * 29) % 256) for i in range(31 * 19)])
        paths = []
        for mode in ("1", "L", "LA", "P", "RGB", "RGBA"):
            path = self.work / (mode + ".png")
            image.convert(mode).save(path)
            paths.append(path)
        if shutil.which("convert"):
            path = self.work / "interlaced.png"
            subprocess.run(["convert", str(paths[-1]), "-interlace", "PNG", str(path)], check=True)
            paths.append(path)
        for path in paths:
            for width, height in ((31, 19), (13, 11), (62, 41)):
                with self.subTest(path=path.name, width=width, height=height):
                    self.check_pixels(path, width, height)

    def test_row_buffer_fallback(self):
        image = self.Image.new("RGBA", (31, 19), (57, 57, 57, 255))
        path = self.work / "fallback.png"
        image.save(path)
        previous = os.environ.get("SD_TEST_NO_ROW")
        os.environ["SD_TEST_NO_ROW"] = "1"
        try:
            self.check_pixels(path, 31, 19)
        finally:
            if previous is None:
                del os.environ["SD_TEST_NO_ROW"]
            else:
                os.environ["SD_TEST_NO_ROW"] = previous

    def test_invalid_files(self):
        image = self.Image.new("RGBA", (31, 19), (20, 40, 60, 128))
        path = self.work / "invalid.png"
        image.save(path)
        data = path.read_bytes()
        for damaged in (data[:-20], data[:50] + bytes([data[50] ^ 1]) + data[51:], b"not PNG"):
            path.write_bytes(damaged)
            result, _ = self.decode(path, 31, 19)
            self.assertEqual(result.returncode, 1, result.stderr)

    @unittest.skipUnless(os.environ.get("SD_PNG_SAMPLE"), "No optional sample provided")
    def test_real_sample(self):
        self.check_pixels(Path(os.environ["SD_PNG_SAMPLE"]), 1872, 1404)


if __name__ == "__main__":
    unittest.main()

