#pragma once
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>
#include "esphome/components/json/json_util.h"

namespace epaper_home {
struct Layout {
  int w, h;
  int sidebar = 430, top = 205, room_h = 54, card_h = 210;
  int room_rows() const { return std::max(1, (h - top - 95) / room_h); }
  int device_rows() const { return std::max(1, (h - top - 95) / card_h); }
  int right() const { return sidebar + 24; }
  int card_width() const { return w - right() - 24; }
};
struct Button { std::string label, icon, operation, value; bool enabled; };
inline std::string number(float n) { char b[32]; snprintf(b,sizeof(b),"%.1f",n); return b; }
inline bool has(JsonArray a, const char *v) {
  for (JsonVariant x : a) if (x.as<std::string>() == v) return true;
  return false;
}
inline std::vector<Button> buttons(JsonObject e) {
  std::vector<Button> out;
  std::string domain=e["d"] | "", state=e["s"] | "";
  bool available=!state.empty() && state!="unknown" && state!="unavailable";
  int features=e["f"] | 0;
  auto add=[&](const char *label,const char *icon,const char *op,std::string val,bool enabled=true){
    out.push_back({label,icon,op,val,available && enabled});
  };
  if(domain=="light") {
    add(state=="on"?"Aus":"Ein","\U000F0425",state=="on"?"off":"on","");
    if(e["dim"] | false) {
      bool known=state=="off" || e["b"].is<float>() || e["b"].is<int>();
      float b=state=="off"?0.0f:e["b"].as<float>();
      add("-10 %","\U000F0374","brightness",number(std::max(0.0f,b-10)),known && b>0);
      add("+10 %","\U000F0415","brightness",number(std::min(100.0f,b+10)),known && b<100);
    }
  } else if(domain=="cover") {
    add("Auf","\U000F005D","open","",features&1);
    add("Stopp","\U000F04DB","stop","",features&8);
    add("Zu","\U000F0045","close","",features&2);
  } else if(domain=="climate") {
    bool known=!e["t"].isNull() && (features&1);
    float t=e["t"].as<float>(), step=e["step"] | 0.5f;
    if(!std::isfinite(step)||step<=0)step=0.5f;
    float lo=e["min"] | 5.0f, hi=e["max"] | 30.0f;
    add("Kälter","\U000F0374","temperature",number(std::max(lo,t-step)),known && t>lo);
    add("Wärmer","\U000F0415","temperature",number(std::min(hi,t+step)),known && t<hi);
    JsonArray modes=e["m"].as<JsonArray>();
    if(has(modes,"auto"))add("Auto","\U000F06A9","mode","auto");
    if(has(modes,"heat"))add("Heizen","\U000F0438","mode","heat");
    if(has(modes,"off"))add("Aus","\U000F0425","mode","off");
  }
  return out;
}
} // namespace epaper_home
