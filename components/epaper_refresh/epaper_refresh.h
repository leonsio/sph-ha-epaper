#pragma once
#include "display_access.h"
#include "esphome/core/component.h"
namespace esphome::epaper_refresh {
// Owns panel transactions only. No SD, clock, UI or power-management state.
class EpaperRefresh : public Component {
 public:
  void set_display(it8951::IT8951Display *display) { display_ = display; }
  bool idle() const;
  bool cleaning() const { return cleaning_; }
  void clean();
  // Local UI updates must not be promoted to whole-panel updates by the
  // driver's count threshold. Hourly UI redraws still provide maintenance.
  void preserve_partial();
  void loop() override;
 private:
  bool panel_idle_() const;
  bool synchronized_() const;
  bool barrier_pending_{false};
  uint32_t synchronized_update_{0};
  void full_panel_();
  void standby_();
  it8951::IT8951Display *display_{nullptr};
  display::display_writer_t saved_writer_{};
  bool cleaning_{false};
  uint8_t stage_{0};
};
}
