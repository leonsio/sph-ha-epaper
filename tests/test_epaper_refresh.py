"""Host regression test: command-IDLE must not release a running waveform.

Runs the production refresh state machine against a small IT8951 driver double.
No ESPHome installation, fonts, secrets or connected panel required.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
DRIVER = r'''
#pragma once
#include <cstdint>
#include <cassert>
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
constexpr uint16_t TCON_REG_RD = 16, LUTAFSR = 4644, TCON_STANDBY = 2;
class IT8951Display : public display::Display {
 public:
  bool is_failed() const { return false; }
  void enable_loop() {}
  void update_mode(UpdateMode mode) {
    asleep_ = false;  // production driver wakes with SYS_RUN before transfer
    // The first driver update is normally count-forced to GC16.
    if (++partial_update_count_ >= 255) mode = UPDATE_MODE_GC16;
    modes.push_back(mode);
    if (x_low_ != 0 || y_low_ != 0 || x_high_ != width_ || y_high_ != height_) throw 1;
    ++update_started_at_; phase_ = Phase::TRANSFER;
    writer_(*this); colors.push_back(color);
  }
  void submit_finished() { phase_ = Phase::IDLE; }
  void finish_waveform() { queue_.clear(); }
  void finish_standby() {
    assert(queue_.size() == 1 && queue_[0] == OpType::CMD && asleep_);
    queue_.clear(); ++standby_count;
  }
  unsigned standby_count = 0;
  void seed_count(uint32_t value) { partial_update_count_ = value; }
  uint32_t count() const { return partial_update_count_; }
  std::vector<UpdateMode> modes;
  std::vector<int> colors;
 protected:
  void enqueue_(OpType op, uint16_t arg, uint16_t) {
    if (asleep_) throw 2;  // no register polls against a gated controller
    if (arg == TCON_STANDBY) assert(queue_.empty());
    queue_.push_back(op);
  }
  void apply_transform_(int &, int &) const {}
  std::vector<OpType> queue_;
  Phase phase_{Phase::IDLE};
  bool initialised_{true}, update_pending_{false}, invert_colors_{false};
  bool asleep_{false};
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
  assert(!refresh.idle());
  refresh.loop(); display.finish_standby();
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
    if (stage == 2) {
      refresh.loop();
      assert(!refresh.idle());  // standby must finish before caller can render
      display.finish_standby();
    }
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
  assert(!refresh.idle());
  display.finish_standby();
  assert(refresh.idle());
  assert(display.standby_count == 3); // boot, completed cleanup, normal UI frame
  for (int tick=0; tick<20; ++tick) refresh.loop(); // no polling while parked
  assert(refresh.idle());
  display.seed_count(254);
  refresh.preserve_partial();
  assert(display.count() == 0);
  // Repeated minute ticks must each wake, synchronize and park the controller.
  for (int minute=0; minute<60; ++minute) {
    display.update_mode(it8951::UPDATE_MODE_GC16);
    const auto count_before = display.count();
    refresh.preserve_partial(); // busy refresh cannot mutate the counter
    assert(display.count() == count_before);
    display.submit_finished(); refresh.loop();
    assert(!refresh.idle());
    display.finish_waveform(); refresh.loop();
    assert(!refresh.idle());
    display.finish_standby();
    assert(refresh.idle());
  }
  assert(display.standby_count == 63);
  // Picture path: one INIT white, then directly the normal picture writer.
  for(int picture=0;picture<2;++picture){
    const size_t before=display.modes.size();
    const int calls_before=ui_calls;
    refresh.clean(true);
    assert(!refresh.idle());
    refresh.loop();
    assert(display.modes.size()==before+1);
    assert(display.modes.back()==it8951::UPDATE_MODE_INIT);
    assert(display.colors.back()==15);
    assert(ui_calls==calls_before);
    display.submit_finished();refresh.loop();
    for(int tick=0;tick<10;++tick)refresh.loop();
    assert(!refresh.idle());
    assert(display.modes.size()==before+1);
    display.finish_waveform();refresh.loop();
    assert(!refresh.idle());
    display.finish_standby();
    assert(refresh.idle());
    assert(display.modes.size()==before+1); // no second cleaning waveform
    display.update_mode(it8951::UPDATE_MODE_GC16);
    assert(ui_calls==calls_before+1);
    display.submit_finished();refresh.loop();
    display.finish_waveform();refresh.loop();
    display.finish_standby();
    assert(refresh.idle());
  }
}
'''


class RefreshTest(unittest.TestCase):
    def test_cleanup_policy(self):
        runtime = yaml.load((ROOT / "packages/e1003/runtime.yaml").read_text(), Loader=yaml.BaseLoader)
        policy = next(s for s in runtime["script"] if s["id"] == "cleanup_if_due")
        expression = policy["then"][0]["if"]["condition"]["lambda"]
        expression = re.sub(r"id\((\w+)\)", r"\1", expression)
        maintenance = re.sub(r"id\((\w+)\)", r"\1", policy["then"][1]["lambda"])
        harness = r'''
#include <cassert>
#include <cstdint>
#include <string>
#define ESP_LOGI(...) ((void)0)
constexpr int ESP_SLEEP_WAKEUP_UNDEFINED=0;
int wake_cause_code=0;
struct { bool value=false; bool active()const{return value;} } sd_photos;
struct Switch { bool state; } cleanup_on_boot{true}, cleanup_on_page_change{false};
struct { std::string value="Aus"; std::string current_option()const{return value;} } cleanup_interval;
bool cleanup_boot_pending=true;
bool force_content=false, full_refresh_due=false, screensaver_clock_full=false;
int current_page=0, displayed_page=-1;
uint32_t tick=1000, cleanup_last_ms=0;
uint32_t millis(){return tick;}
bool due(){
POLICY
}
void maintain(){
MAINTENANCE
}
void reset_flags(){force_content=full_refresh_due=screensaver_clock_full=false;}
int main(){
  assert(due()); // default boot
  cleanup_on_boot.state=false; assert(!due());
  cleanup_on_boot.state=true; wake_cause_code=3; assert(!due()); // timer wake
  wake_cause_code=0;
  cleanup_boot_pending=false; cleanup_on_boot.state=true;
  displayed_page=0; assert(!due());
  current_page=2; assert(!due()); // default navigation: no cleanup
  cleanup_on_page_change.state=true; assert(!due()); maintain();
  assert(force_content && full_refresh_due && screensaver_clock_full); reset_flags();
  displayed_page=2; assert(!due()); // minute/forced redraw: no cleanup
  sd_photos.value=true; assert(!due()); maintain(); assert(full_refresh_due); reset_flags();
  displayed_page=-2; assert(!due()); // next clock tick/image
  maintain(); assert(!full_refresh_due);
  sd_photos.value=false; assert(!due()); maintain(); assert(full_refresh_due); reset_flags();
  cleanup_on_page_change.state=false;
  cleanup_interval.value="15 Minuten";
  cleanup_last_ms=0;
  tick=899999; maintain(); assert(!full_refresh_due);
  tick=900000; assert(!due()); maintain(); assert(full_refresh_due); reset_flags();
  cleanup_last_ms=tick; assert(!due());
  tick+=900000; maintain(); assert(full_refresh_due); reset_flags();
  cleanup_interval.value="Aus"; maintain(); assert(!full_refresh_due);
  cleanup_interval.value="15 Minuten";
  cleanup_last_ms=0xFFFF0000U; tick=cleanup_last_ms+900000U;
  assert(!due()); maintain(); assert(full_refresh_due); // uint32 rollover
}
'''.replace("POLICY", expression).replace("MAINTENANCE", maintenance)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "policy.cpp").write_text(harness)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(work / "policy.cpp"), "-o", str(work / "policy")], check=True)
            subprocess.run([str(work / "policy")], check=True)
        settings = yaml.load((ROOT / "packages/e1003/settings.yaml").read_text(), Loader=yaml.BaseLoader)
        switches = {s["id"]: s for s in settings["switch"]}
        self.assertEqual(switches["cleanup_on_boot"]["restore_mode"], "RESTORE_DEFAULT_ON")
        self.assertEqual(switches["cleanup_on_page_change"]["restore_mode"], "RESTORE_DEFAULT_OFF")
        self.assertEqual(next(s for s in settings["select"] if s["id"] == "cleanup_interval")["initial_option"], "Aus")

    def test_picture_cleanup_precedes_image_transfer(self):
        screensaver = yaml.load((ROOT / "packages/e1003/screensaver.yaml").read_text(),
                                Loader=yaml.BaseLoader)
        show = next(s for s in screensaver["script"] if s["id"] == "screensaver_show")
        # Every image enters the cleaning branch; it is not tied to the boot,
        # hourly interval, or page-change preferences.
        branch = show["then"][0]["if"]
        self.assertEqual(branch["condition"]["lambda"],
                         'return id(screensaver_source).current_option()=="Bild";')
        cleaning = branch["then"]
        self.assertIn("id(panel_refresh).clean(true);", cleaning[0]["lambda"])
        self.assertEqual(cleaning[1]["wait_until"]["condition"]["lambda"],
                         "return id(panel_refresh).idle();")
        self.assertIn("id(full_refresh_due)=true;", cleaning[2]["lambda"])
        self.assertIn("id(cleanup_boot_pending)=false;", cleaning[2]["lambda"])
        self.assertEqual(branch["else"], [
            {"script.execute": "cleanup_if_due"}, {"script.wait": "cleanup_if_due"}])
        image = show["then"][1]["if"]["then"]
        self.assertEqual(image[1]["it8951.update"]["mode"], "GC16")
        # The physical state machine verifies a single INIT for quick cleanup,
        # writer restore and physical completion before idle().
        self.assertEqual(image[2]["wait_until"]["condition"]["lambda"],
                         "return id(panel_refresh).idle();")

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

