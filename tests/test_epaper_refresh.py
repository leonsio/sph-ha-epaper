"""Host regression test: command-IDLE must not release a running waveform.

Runs the production refresh state machine against a small IT8951 driver double.
No ESPHome installation, fonts, secrets or connected panel required.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = r'''
#pragma once
#include <cstdint>
#include <functional>
#include <utility>
#include <vector>
namespace esphome {
struct Color { int value; static const Color BLACK, WHITE; };
inline const Color Color::BLACK{0}, Color::WHITE{15};
namespace display {
class Display;
using display_writer_t = std::function<void(Display &)>;
class Display {
 public:
  virtual ~Display() = default;
  void set_writer(display_writer_t &&w) { writer_ = std::move(w); }
  void fill(Color c) { color = c.value; }
  int color = -1;
 protected: display_writer_t writer_;
};
}
namespace it8951 {
enum class Phase { IDLE, TRANSFER };
enum class OpType { CMD, WRITE_W, READ_WORD, CHECK_LUT_IDLE };
enum UpdateMode { UPDATE_MODE_INIT, UPDATE_MODE_GC16 };
constexpr uint16_t TCON_REG_RD = 16, LUTAFSR = 4644;
class IT8951Display : public display::Display {
 public:
  bool is_failed() const { return false; }
  void enable_loop() {}
  void update_mode(UpdateMode mode) {
    // The first driver update is normally count-forced to GC16.
    if (++partial_update_count_ >= 255) mode = UPDATE_MODE_GC16;
    modes.push_back(mode);
    if (x_low_ != 0 || y_low_ != 0 || x_high_ != width_ || y_high_ != height_) throw 1;
    ++update_started_at_; phase_ = Phase::TRANSFER;
    writer_(*this); colors.push_back(color);
  }
  void submit_finished() { phase_ = Phase::IDLE; }
  void finish_waveform() { queue_.clear(); }
  std::vector<UpdateMode> modes;
  std::vector<int> colors;
 protected:
  void enqueue_(OpType op, uint16_t, uint16_t) { queue_.push_back(op); }
  void apply_transform_(int &, int &) const {}
  std::vector<OpType> queue_;
  Phase phase_{Phase::IDLE};
  bool initialised_{true}, update_pending_{false}, invert_colors_{false};
  uint32_t update_started_at_{0}, partial_update_count_{255};
  uint8_t *buffer_{nullptr};
  uint16_t row_width_{936}, width_{1872}, height_{1404};
  uint16_t x_low_{1872}, x_high_{0}, y_low_{1404}, y_high_{0};
};
}
}
'''
HARNESS = r'''
#include "epaper_refresh.h"
#include <cassert>
using namespace esphome;
int main() {
  it8951::IT8951Display display;
  epaper_refresh::EpaperRefresh refresh;
  refresh.set_display(&display);
  int ui_calls = 0;
  display.set_writer([&](display::Display &) { ++ui_calls; });
  assert(refresh.idle());
  refresh.clean();
  assert(!refresh.idle());
  for (int stage = 0; stage < 3; ++stage) {
    refresh.loop();
    assert(display.modes.size() == unsigned(stage + 1));
    assert(ui_calls == 0);
    // The driver reports command-IDLE while the panel is still moving.
    display.submit_finished();
    refresh.loop();  // enqueue the post-update LUT barrier
    for (int tick = 0; tick < 10; ++tick) refresh.loop();
    assert(!refresh.idle());
    assert(display.modes.size() == unsigned(stage + 1));
    display.finish_waveform();
    // Completion is consumed on the next loop, which may start the next stage.
    if (stage == 2) refresh.loop();
  }
  assert(refresh.idle());
  assert((display.modes == std::vector<it8951::UpdateMode>{
    it8951::UPDATE_MODE_INIT, it8951::UPDATE_MODE_GC16, it8951::UPDATE_MODE_GC16}));
  assert((display.colors == std::vector<int>{15, 0, 15}));
  display.update_mode(it8951::UPDATE_MODE_GC16);
  assert(ui_calls == 1);  // original UI writer restored without an extra render
  assert(!refresh.idle());
  refresh.clean();       // a busy transaction cannot be hijacked by cleanup
  assert(!refresh.cleaning());
  display.submit_finished(); refresh.loop();
  assert(!refresh.idle());
  display.finish_waveform(); refresh.loop();
  assert(refresh.idle());
}
'''


class RefreshTest(unittest.TestCase):
    def test_physical_completion_and_writer_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for path, text in {
                "esphome/components/it8951/it8951.h": DRIVER,
                "esphome/core/component.h": "#pragma once\nnamespace esphome { class Component { public: virtual void loop() {} }; }\n",
                "esphome/core/log.h": "#define ESP_LOGI(...) ((void)0)\n",
                "test.cpp": HARNESS,
            }.items():
                target = work / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            source = ROOT / "components/epaper_refresh"
            binary = work / "test"
            subprocess.run([
                "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-I", str(work), "-I", str(source),
                str(work / "test.cpp"), str(source / "epaper_refresh.cpp"),
                "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
