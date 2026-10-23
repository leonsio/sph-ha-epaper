"""Compile the production Maxim partial-render branch with drawing recorders.

Tests the rectangles actually requested by the renderer, rather than a copy of
its condition logic. Requires PyYAML and a C++17 host compiler, no panel/assets.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>
#define ESP_LOGI(...) ((void)0)
namespace esphome {
struct ESPTime {
  int hour=9, minute=12;
  static ESPTime from_epoch_local(time_t) { return {}; }
};
}
int maxim_time_part=1, maxim_clock_hours_value=8, maxim_clock_minutes_value=11;
int maxim_school_hours_value=2, maxim_school_minutes_value=1;
int64_t maxim_tick_epoch=10000, maxim_target_epoch=10000+3660;
int font_maxim_clock=1, font_lesson=2;
bool maxim_partial=true;
struct Rect { int x,y,w,h; };
std::vector<Rect> rectangles;
void render() {
  // Representative full-render cell positions: clock on the right, countdown left.
  const int maxim_clock_hour_x=1000, maxim_clock_minute_x=1400;
  const int maxim_clock_digit_y=250, maxim_clock_digit_w=300, maxim_clock_digit_h=250;
  const int maxim_clock_text_y=250;
  const int maxim_count_hour_x=300, maxim_count_minute_x=500, maxim_count_digit_y=210;
  const int maxim_count_hour_w=60, maxim_count_minute_w=60, maxim_count_digit_h=40;
  const int PAPER=15, INK=0;
  auto fast_rect=[](int x,int y,int w,int h,int){rectangles.push_back({x,y,w,h});};
  auto text=[](int,int,const std::string&,int,int,int){};
  auto width=[](const std::string&,int){return 40;};
BRANCH
}
int main() {
  render();
  assert(rectangles.size()==2);
  for(auto r:rectangles)assert(r.x>=1000 && r.y==250);
  assert(maxim_school_hours_value==2 && maxim_school_minutes_value==1);
  assert(maxim_time_part==0);
  rectangles.clear(); maxim_time_part=2; render();
  // Countdown hours changed, minutes did not. No clock or connecting rectangle.
  assert(rectangles.size()==1 && rectangles[0].x==300 && rectangles[0].y==210);
  assert(maxim_school_hours_value==1 && maxim_clock_minutes_value==12);
  rectangles.clear(); maxim_time_part=1; render();
  assert(rectangles.empty()); // unchanged digits cause no erase
}
'''


class PartialRegionsTest(unittest.TestCase):
    def test_clock_and_countdown_are_separate(self):
        source = yaml.load((ROOT / "packages/e1003/render/common.yaml").read_text(), Loader=yaml.BaseLoader)
        branch = source[source.index("if(maxim_partial){"):source.index("// Main navigation")]
        branch = re.sub(r"id\((\w+)\)", r"\1", branch)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "regions.cpp").write_text(HARNESS.replace("BRANCH", branch))
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(work / "regions.cpp"), "-o", str(work / "regions")], check=True)
            subprocess.run([str(work / "regions")], check=True)

    def test_home_partials_exclude_header(self):
        source = yaml.load((ROOT / "packages/e1003/render/common.yaml").read_text(), Loader=yaml.BaseLoader)
        # Compile and exercise the exact header guards with changed status values.
        guards = re.findall(r"if\((!home_partial && .*?)\)\{", source)
        self.assertEqual(len(guards), 3)
        harness = '''#include <cassert>
int main(){
bool home_partial=true, repaint_nav=false;
int sleep_state=1, painted_sleep=0, level=4, painted_wifi=3;
int battery_pixels=40, painted_battery=39, usb_power=1, painted_usb=0;
'''
        for guard in guards:
            harness += f"assert(!({guard}));\n"
        harness += "home_partial=false;\n"
        for guard in guards:
            harness += f"assert({guard});\n"
        harness += "}"
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "header.cpp").write_text(harness)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(work / "header.cpp"), "-o", str(work / "header")], check=True)
            subprocess.run([str(work / "header")], check=True)


if __name__ == "__main__":
    unittest.main()
