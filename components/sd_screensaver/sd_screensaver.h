#pragma once
#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "esphome/components/it8951/it8951.h"
#include "sdmmc_cmd.h"
#include <string>
#include <vector>

namespace esphome::sd_screensaver {
// Retained only across deep sleep. Other resets deliberately restore the UI.
bool sleeping_screensaver_input_wake();
struct SleepState { uint32_t magic; bool active; char last_file[256]; };
class DisplayAccess : public it8951::IT8951Display {
 public:
  using IT8951Display::phase_;
  using IT8951Display::initialised_;
  using IT8951Display::update_pending_;
  using IT8951Display::buffer_;
  using IT8951Display::row_width_;
  using IT8951Display::apply_transform_;
  using IT8951Display::x_low_;
  using IT8951Display::x_high_;
  using IT8951Display::y_low_;
  using IT8951Display::y_high_;
  using IT8951Display::width_;
  using IT8951Display::height_;
  using IT8951Display::invert_colors_;
};
class SDScreensaver : public Component {
 public:
  void set_display(it8951::IT8951Display *p) { display_=p; }
  float get_setup_priority() const override { return 500.0f; } // after SPI, before display
  void setup() override;
  void on_safe_shutdown() override;
  bool display_idle() const;
  bool poll_card();
  bool card_present() const;
  bool ready() const { return mounted_; }
  size_t count() const { return files_.size(); }
  const std::string &filename() const { return filename_; }
  bool active() const { return active_; }
  bool resume_requested() const { return resume_; }
  void activity();
  void stop();
  bool next();
  bool next_clock(uint32_t minute);
  uint32_t clock_minute() const { return clock_minute_; }
  void render();
  bool due(uint32_t idle_min, uint32_t interval_min) const;
  bool hourly_due() const;
  void prepare_sleep();
  uint32_t remaining_ms(uint32_t minutes) const {
    uint32_t elapsed=millis()-last_change_;
    return elapsed>=minutes*60000UL?1000UL:minutes*60000UL-elapsed;
  }
 private:
  bool mount_();
  void unmount_();
  void scan_();
  bool load_bmp_(const std::string &path, uint8_t *out);
  bool load_gray4_(const std::string &path, uint8_t *out);
  void set_pixel_(uint8_t *out,int x,int y,uint8_t gray);
  sdmmc_card_t *card_{nullptr};
  it8951::IT8951Display *display_{nullptr};
  uint32_t clock_minute_{0};
  std::vector<std::string> files_;
  std::string filename_;
  uint8_t *pixels_{nullptr};
  bool mounted_{false}, active_{false}, resume_{false};
  uint32_t last_activity_{0}, last_change_{0}, last_full_{0};
  int width_{0}, height_{0};
};
} // namespace

