#pragma once
#include "esphome/components/it8951/it8951.h"
namespace esphome::epaper_refresh {
class DisplayAccess : public it8951::IT8951Display {
 public:
  using IT8951Display::queue_;
  using IT8951Display::enqueue_;
  using IT8951Display::update_started_at_;
  using IT8951Display::partial_update_count_;
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
  using display::Display::writer_;
};
}
