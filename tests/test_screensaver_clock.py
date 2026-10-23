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
#include "screensaver_ui.h"
#define ESP_LOGI(...) ((void)0)
struct Color {int value; static const Color BLACK,WHITE;};
const Color Color::BLACK{0},Color::WHITE{15};
enum class TextAlign {CENTER,TOP_LEFT,TOP_CENTER};
struct Time {
  int hour=10,minute=21,day_of_week=6,day_of_month=23,month=10,year=2026;
  bool valid=true;
  bool is_valid() const {return valid;}
  static Time from_epoch_local(int64_t);
};
struct {Time value; Time now()const{return value;}} ha_time;
Time Time::from_epoch_local(int64_t){return ha_time.value;}
namespace esphome {using ESPTime=Time;}
struct {bool active()const{return true;} void render(){}} sd_photos;
struct {std::string mode="Analoge Uhr"; std::string current_option()const{return mode;}} screensaver_source;
struct {std::string state="cloudy";} epaper_weather_condition;
struct {std::string state="14.0";} weather_outdoor_temperature;
bool screensaver_clock_full=true;
int screensaver_clock_part=0;
int font_screensaver_clock=1,font_weather_condition=2,font_start_weather=3,font_small=4,ui_small=5,mdi_start_appliance=6;
int waste_rest_value=1,waste_bio_value=2,waste_papier_value=3,waste_gelb_value=4,waste_gruen_value=5;
auto *waste_rest=&waste_rest_value,*waste_bio=&waste_bio_value,*waste_papier=&waste_papier_value,*waste_gelb=&waste_gelb_value,*waste_gruen=&waste_gruen_value;
struct Display {
  int xlow=1872,ylow=1404,xhigh=0,yhigh=0;
  std::vector<int> appliance_centers;
  std::vector<int> waste_centers, waste_icons;
  int fills=0,circles=0,lines=0,hubs=0,triangles=0,prints=0,digits=0,clears=0;
  int get_width()const{return 1872;} int get_height()const{return 1404;}
  void rect(int x,int y,int w,int h){xlow=std::min(xlow,x);ylow=std::min(ylow,y);xhigh=std::max(xhigh,x+w);yhigh=std::max(yhigh,y+h);}
  void fill(Color){++fills;rect(0,0,1872,1404);}
  void print(int x,int y,int font,Color,TextAlign align,const char* text){
    if(font==6)appliance_centers.push_back(x);
    ++prints;int bx,by,w,h;get_text_bounds(x,y,text,font,align,&bx,&by,&w,&h);rect(bx,by,w,h);
  }
  template<class... Args> void printf(int x,int y,int font,Color c,TextAlign align,const char* fmt,Args...args){
    char out[256];snprintf(out,sizeof(out),fmt,args...);print(x,y,font,c,align,out);--prints;++digits;
  }
  void rectangle(int x,int y,int w,int h,Color){rect(x,y,w,h);}
  void filled_rectangle(int x,int y,int w,int h,Color){rect(x,y,w,h);}
  void image(int x,int y,int *icon,Color){waste_centers.push_back(x+32);waste_icons.push_back(*icon);rect(x,y,64,70);}
  void circle(int,int,int,Color){++circles;}
  void line(int,int,int,int,Color){++lines;}
  void filled_circle(int,int,int,Color){++hubs;}
  void filled_triangle(int,int,int,int,int,int,Color){++triangles;}
  void get_text_bounds(int x,int y,const char* text,int font,TextAlign align,
                       int *bx,int *by,int *w,int *h){
    *w=int(std::string(text).size())*(font==1?300:font==3?48:14);
    *h=font==1?500:font==3?89:font==6?60:30;
    *bx=x-(align!=TextAlign::TOP_LEFT?*w/2:0);
    *by=y-(align==TextAlign::CENTER?*h/2:0);
  }
  void reset(){appliance_centers.clear();waste_centers.clear();waste_icons.clear();fills=circles=lines=hubs=triangles=prints=digits=clears=0;xlow=1872;ylow=1404;xhigh=yhigh=0;}
} it;
Display *epaper=&it;
namespace esphome::it8951_native {
void fill_gray4_rect(Display *d,int x,int y,int w,int h,Color){++d->clears;d->rect(x,y,w,h);}
}
void render(){
RENDERER
}
int main(){
  auto &p=screensaver_ui::plan;p.condition="cloudy";p.temperature="14.0";
  render(); assert(it.fills==1 && it.circles==1 && it.lines==180);
  it.reset(); ++ha_time.value.minute; screensaver_clock_part=5;render();
  assert(!screensaver_clock_full);
  assert(it.fills==0 && it.circles==0 && it.lines==0 && it.prints==0);
  assert(it.triangles==4 && it.hubs==1); // old hand silhouettes + new hands
  it.reset(); render(); assert(it.triangles==0 && it.prints==0 && it.fills==0);
  screensaver_clock_part=7;p.temperature="15.0";
  render(); assert(it.prints==1 && it.clears==1 && it.triangles==0);
  screensaver_source.mode="Digitale Uhr"; screensaver_clock_full=true;
  it.reset();screensaver_clock_part=0; render(); assert(it.fills==1 && it.digits==4);
  it.reset(); ++ha_time.value.minute; screensaver_clock_part=4;render();
  assert(it.fills==0 && it.digits==1 && it.clears==1 && it.prints==0);
  assert(it.xhigh-it.xlow<=324 && it.ylow>240 && it.yhigh<1200);
  // Footer and hints are separate transmissions, never joined to this digit.
  p.waste={"Bioabfall","Papiertonne"};it.reset();screensaver_clock_part=8;render();
  assert(it.digits==0 && it.prints==6 && it.xhigh<936 && it.yhigh<=220);
  assert((it.waste_centers==std::vector<int>{164,444}));
  assert((it.waste_icons==std::vector<int>{2,3}));
  p.appliances={{"Geschirrspüler","Ein","22:52",40}};
  it.reset();screensaver_clock_part=9;render();
  assert(it.prints==4 && it.yhigh<=220);
  // A single device stays in the rightmost 280-pixel cell.
  // Ignore the clear region and inspect the same layout on a full paint.
  assert((it.appliance_centers==std::vector<int>{1708}));
  p.appliances.push_back({"Waschmaschine","Läuft","23:10",65});
  p.appliances.push_back({"Trockner","Läuft","23:20",25});
  it.reset();screensaver_clock_part=9;render();assert(it.prints==12 && it.xlow>=948 && it.yhigh<=220);
  assert((it.appliance_centers==std::vector<int>{1708,1428,1148}));
  p.appliances.clear();it.reset();render();assert(it.prints==0 && it.clears==1); // hide stopped/stale
  screensaver_clock_full=true;ha_time.value.hour=23;ha_time.value.minute=59; render();
  it.reset();ha_time.value.hour=0;ha_time.value.minute=0;++ha_time.value.day_of_month;
  screensaver_clock_part=6;render();assert(it.fills==0 && it.digits==0 && it.prints==1);
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
                            "-I",str(ROOT),str(work / "clock.cpp"), "-o", str(work / "clock")], check=True)
            subprocess.run([str(work / "clock")], check=True)


if __name__ == "__main__":
    unittest.main()
