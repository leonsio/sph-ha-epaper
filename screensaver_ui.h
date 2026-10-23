#pragma once
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace screensaver_ui {
inline std::string tomorrow(int year, int month, int day) {
  const int lengths[]={31,28,31,30,31,30,31,31,30,31,30,31};
  const int length=lengths[month-1]+(month==2 && year%4==0 && (year%100!=0 || year%400==0));
  if(++day>length){day=1;if(++month>12){month=1;++year;}}
  char out[24];std::snprintf(out,sizeof(out),"%04d-%02d-%02d",year,month,day);return out;
}
inline bool fresh(int64_t now, int64_t timestamp) {
  return timestamp>0 && now-timestamp>=-60 && now-timestamp<=180;
}
inline bool pickup_due(const std::string &date, int days, const std::string &next_day, bool same_day) {
  return date.empty() ? same_day && days==1 : date==next_day;
}
inline std::string lower(std::string value) {
  for(char &c:value)c=std::tolower(static_cast<unsigned char>(c));
  return value;
}
inline bool running(const std::string &state) {
  const auto s=lower(state);
  return s=="running" || s=="run" || s=="starting" || s=="ending" || s=="rinse" ||
      s=="läuft" || s=="ein" || s=="startet" || s=="wird fertig" || s=="spülen";
}
inline bool appliance(const std::string &name) {
  const auto s=lower(name);
  return s.find("geschirr")!=std::string::npos || s.find("wasch")!=std::string::npos ||
      s.find("trockner")!=std::string::npos || s.find("dishwasher")!=std::string::npos ||
      s.find("washing")!=std::string::npos || s.find("dryer")!=std::string::npos;
}
inline std::string signature(const std::vector<std::string> &rows) {
  std::string out;for(const auto &row:rows){out+=row;out+='\n';}return out;
}
struct Plan {
  // Parts 1..4: individual digits; 5: analog hands; 6/7: date/weather;
  // 8/9: left/right hints. Never combine distant parts in one driver update.
  std::array<std::string,9> desired{},painted{};
  std::vector<std::string> waste,devices;
  std::string condition,temperature;
  int64_t epoch{0};
  uint16_t pending{0};
  void prepare(bool full) {
    pending=0;
    for(unsigned i=0;i<desired.size();++i)
      if(full || desired[i]!=painted[i])pending|=1U<<i;
  }
  bool has(unsigned part) const {return part>=1 && part<=9 && (pending&(1U<<(part-1)));}
  void commit(unsigned part) {
    if(part>=1 && part<=9){painted[part-1]=desired[part-1];pending&=~(1U<<(part-1));}
  }
  void commit_all(){painted=desired;pending=0;}
};
inline Plan plan;
}  // namespace screensaver_ui
