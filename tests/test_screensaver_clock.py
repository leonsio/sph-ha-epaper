"""Run the complete production clock renderer with a recording display."""
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
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#define ESP_LOGI(...) ((void)0)
struct Color {int value; static const Color BLACK,WHITE;};
const Color Color::BLACK{0},Color::WHITE{15};
enum class TextAlign {CENTER,TOP_LEFT};
struct Time {
  int hour=10,minute=21,day_of_week=6,day_of_month=23,month=10,year=2026;
  bool valid=true;
  bool is_valid() const {return valid;}
};
struct {Time value; Time now()const{return value;}} ha_time;
struct {bool active()const{return true;} void render(){}} sd_photos;
struct {std::string mode="Analoge Uhr"; std::string current_option()const{return mode;}} screensaver_source;
struct {std::string state="cloudy";} epaper_weather_condition;
struct {std::string state="14.0";} weather_outdoor_temperature;
bool screensaver_clock_full=true;
int font_screensaver_clock=1,font_weather_condition=2,font_start_weather=3;
struct Display {
  int fills=0,circles=0,lines=0,hubs=0,triangles=0,prints=0,digits=0,clears=0;
  int get_width()const{return 1872;} int get_height()const{return 1404;}
  void fill(Color){++fills;}
  void print(int,int,int,Color,TextAlign,const char*){++prints;}
  template<class... Args> void printf(int,int,int,Color,TextAlign,const char*,Args...){++digits;}
  void circle(int,int,int,Color){++circles;}
  void line(int,int,int,int,Color){++lines;}
  void filled_circle(int,int,int,Color){++hubs;}
  void filled_triangle(int,int,int,int,int,int,Color){++triangles;}
  void get_text_bounds(int x,int y,const char* text,int font,TextAlign align,
                       int *bx,int *by,int *w,int *h){
    *w=int(std::string(text).size())*(font==1?300:font==3?48:30);
    *h=font==1?500:font==3?89:56;
    *bx=x-(align==TextAlign::CENTER?*w/2:0);
    *by=y-(align==TextAlign::CENTER?*h/2:0);
  }
  void reset(){fills=circles=lines=hubs=triangles=prints=digits=clears=0;}
} it;
Display *epaper=&it;
namespace esphome::it8951_native {
void fill_gray4_rect(Display *d,int,int,int,int,Color){++d->clears;}
}
void render(){
RENDERER
}
int main(){
  render(); assert(it.fills==1 && it.circles==1 && it.lines==180);
  it.reset(); ++ha_time.value.minute; render();
  assert(!screensaver_clock_full);
  assert(it.fills==0 && it.circles==0 && it.lines==0 && it.prints==0);
  assert(it.triangles==4 && it.hubs==1); // old hand silhouettes + new hands
  it.reset(); render(); assert(it.triangles==0 && it.prints==0 && it.fills==0);
  weather_outdoor_temperature.state="15.0";
  render(); assert(it.prints==1 && it.clears==1 && it.triangles==0);
  screensaver_source.mode="Digitale Uhr"; screensaver_clock_full=true;
  it.reset(); render(); assert(it.fills==1 && it.digits==4);
  it.reset(); ++ha_time.value.minute; render();
  assert(it.fills==0 && it.digits==1 && it.clears==1 && it.prints==0);
  ha_time.value.hour=23;ha_time.value.minute=59; render();
  it.reset();ha_time.value.hour=0;ha_time.value.minute=0;++ha_time.value.day_of_month;
  render();assert(it.fills==0 && it.digits==4 && it.prints==1); // midnight/date
  it.reset();screensaver_clock_full=true;render();assert(it.fills==1); // explicit full
  it.reset();ha_time.value.valid=false;render();assert(it.fills==1);
  it.reset();ha_time.value.valid=true;render();assert(it.fills==1); // sync message replaced
}
'''


class ScreensaverClockTest(unittest.TestCase):
    def test_partial_analog_digital_and_footer(self):
        source = yaml.load((ROOT / "packages/e1003/render/clock.yaml").read_text(), Loader=yaml.BaseLoader)
        source = re.sub(r"id\((\w+)\)", r"\1", source)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "clock.cpp").write_text(HARNESS.replace("RENDERER", source))
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(work / "clock.cpp"), "-o", str(work / "clock")], check=True)
            subprocess.run([str(work / "clock")], check=True)


if __name__ == "__main__":
    unittest.main()
