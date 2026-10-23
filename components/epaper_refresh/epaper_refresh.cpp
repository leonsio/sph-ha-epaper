#include "epaper_refresh.h"
#include "esphome/core/log.h"
namespace esphome::epaper_refresh {
bool EpaperRefresh::panel_idle_() const {
  return display_ && !display_->is_failed() && display_->*(&DisplayAccess::initialised_) &&
    display_->*(&DisplayAccess::phase_) == it8951::Phase::IDLE &&
    !(display_->*(&DisplayAccess::update_pending_)) &&
    (display_->*(&DisplayAccess::queue_)).empty();
}
bool EpaperRefresh::synchronized_() const {
  return panel_idle_() && !barrier_pending_ &&
    synchronized_update_ == display_->*(&DisplayAccess::update_started_at_);
}
bool EpaperRefresh::idle() const { return !cleaning_ && synchronized_(); }
void EpaperRefresh::full_panel_() {
  display_->*(&DisplayAccess::x_low_) = 0;
  display_->*(&DisplayAccess::y_low_) = 0;
  display_->*(&DisplayAccess::x_high_) = display_->*(&DisplayAccess::width_);
  display_->*(&DisplayAccess::y_high_) = display_->*(&DisplayAccess::height_);
}
void EpaperRefresh::clean() {
  if (!idle()) return;
  saved_writer_ = display_->*(&DisplayAccess::writer_);
  cleaning_ = true;
  stage_ = 0;
  ESP_LOGI("epaper_refresh", "Panel reinigen: INIT weiss -> GC16 schwarz -> GC16 weiss");
}
void EpaperRefresh::loop() {
  if (!panel_idle_()) return;
  // IT8951's IDLE marks command submission, not physical waveform completion.
  // Poll LUTAFSR AFTER each update, before another transfer can overwrite the
  // controller image buffer. Use the driver's nonblocking operation queue.
  if (barrier_pending_) {
    barrier_pending_ = false;
    synchronized_update_ = display_->*(&DisplayAccess::update_started_at_);
  } else if (!synchronized_()) {
    auto enqueue = &DisplayAccess::enqueue_;
    (display_->*enqueue)(it8951::OpType::CMD, it8951::TCON_REG_RD, 0);
    (display_->*enqueue)(it8951::OpType::WRITE_W, it8951::LUTAFSR, 0);
    (display_->*enqueue)(it8951::OpType::READ_WORD, 0, 0);
    (display_->*enqueue)(it8951::OpType::CHECK_LUT_IDLE, 0, 0);
    barrier_pending_ = true;
    display_->enable_loop();
    return;
  }
  if (!cleaning_) return;
  if (stage_ == 3) {
    display_->set_writer(std::move(saved_writer_));
    saved_writer_ = {};
    cleaning_ = false;
    // The caller now redraws its complete UI, with its own invalidation flags.
    ESP_LOGI("epaper_refresh", "Reinigung abgeschlossen; Inhaltsaufbau freigegeben");
    return;
  }
  const Color color = stage_ == 1 ? Color::BLACK : Color::WHITE;
  display_->set_writer(display::display_writer_t([color](display::Display &it) { it.fill(color); }));
  full_panel_();
  const auto mode = stage_ == 0 ? it8951::UPDATE_MODE_INIT : it8951::UPDATE_MODE_GC16;
  // The driver may otherwise replace INIT with its count-triggered GC16.
  display_->*(&DisplayAccess::partial_update_count_) = 0;
  ++stage_;
  display_->update_mode(mode);
  // The next loop schedules a post-refresh barrier before the next stage.
}
}
