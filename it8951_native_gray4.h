#pragma once

#include <algorithm>
#include <cstdint>
#include <cstring>

#include "esphome/components/it8951/it8951.h"
#include "esphome/core/application.h"

// Native 4-bpp rectangle writer for ESPHome's IT8951 grayscale framebuffer.
//
// ESPHome's normal draw_pixels_at() accepts RGB888/RGB565/RGB332 and converts
// every source pixel to the native 4-bpp framebuffer. For solid grayscale
// rectangles that conversion is unnecessary. This helper packs two gray pixels
// into each framebuffer byte and uses memset() for the byte-aligned interior.
//
// It deliberately does not modify the IT8951 component itself. A tiny derived
// access shim promotes the protected members to public names; pointers-to-
// inherited-members still have IT8951Display as their owning type, so they can
// be applied safely to the real IT8951Display object.
namespace esphome::it8951_native {

class IT8951Access : public esphome::it8951::IT8951Display {
 public:
  using esphome::it8951::IT8951Display::apply_transform_;
  using esphome::it8951::IT8951Display::buffer_;
  using esphome::it8951::IT8951Display::effective_transform_;
  using esphome::it8951::IT8951Display::grayscale_;
  using esphome::it8951::IT8951Display::height_;
  using esphome::it8951::IT8951Display::invert_colors_;
  using esphome::it8951::IT8951Display::row_width_;
  using esphome::it8951::IT8951Display::width_;
  using esphome::it8951::IT8951Display::x_high_;
  using esphome::it8951::IT8951Display::x_low_;
  using esphome::it8951::IT8951Display::y_high_;
  using esphome::it8951::IT8951Display::y_low_;
};

inline uint8_t color_to_gray4(const esphome::Color &color) {
  uint8_t value;
  if (color.w == 0xFF && color.r == color.g && color.g == color.b) {
    value = color.r;
  } else if (color.raw_32 == 0) {
    value = 0;
  } else if (color.raw_32 == 0xFFFFFFFF) {
    value = 255;
  } else {
    value = static_cast<uint8_t>((77u * color.r + 150u * color.g + 29u * color.b + 128u) >> 8);
  }
  uint8_t nibble = static_cast<uint8_t>((static_cast<uint16_t>(value) + 8u) >> 4);
  return nibble > 0x0F ? 0x0F : nibble;
}

inline void fill_gray4_rect(esphome::it8951::IT8951Display *display_ptr, int x, int y, int w, int h,
                            const esphome::Color &color) {
  if (display_ptr == nullptr || w <= 0 || h <= 0)
    return;

  auto &display = *display_ptr;

  auto p_buffer = &IT8951Access::buffer_;
  auto p_row_width = &IT8951Access::row_width_;
  auto p_native_width = &IT8951Access::width_;
  auto p_native_height = &IT8951Access::height_;
  auto p_grayscale = &IT8951Access::grayscale_;
  auto p_invert = &IT8951Access::invert_colors_;
  auto p_x_low = &IT8951Access::x_low_;
  auto p_x_high = &IT8951Access::x_high_;
  auto p_y_low = &IT8951Access::y_low_;
  auto p_y_high = &IT8951Access::y_high_;
  auto p_apply_transform = &IT8951Access::apply_transform_;

  uint8_t *buffer = display.*p_buffer;
  if (buffer == nullptr)
    return;

  // This helper is optimized specifically for the native 4-bpp mode. The
  // fallback keeps behavior correct if the configuration is ever changed.
  if (!(display.*p_grayscale)) {
    const int logical_w = display.get_width();
    const int logical_h = display.get_height();
    const int x0 = std::max(0, x);
    const int y0 = std::max(0, y);
    const int x1 = std::min(logical_w, x + w);
    const int y1 = std::min(logical_h, y + h);
    for (int yy = y0; yy < y1; ++yy) {
      for (int xx = x0; xx < x1; ++xx)
        display.draw_pixel_at(xx, yy, color);
      if ((yy & 0x0F) == 0)
        App.feed_wdt();
    }
    return;
  }

  // Clip in logical coordinates first.
  const int logical_w = display.get_width();
  const int logical_h = display.get_height();
  int lx0 = std::max(0, x);
  int ly0 = std::max(0, y);
  int lx1 = std::min(logical_w, x + w);
  int ly1 = std::min(logical_h, y + h);
  if (lx1 <= lx0 || ly1 <= ly0)
    return;

  // Uniform rectangles remain axis-aligned under the IT8951 swap/mirror
  // transform. Transform opposite inclusive corners to find native bounds.
  int ax = lx0, ay = ly0;
  int bx = lx1 - 1, by = ly1 - 1;
  (display.*p_apply_transform)(ax, ay);
  (display.*p_apply_transform)(bx, by);

  const int native_w = display.*p_native_width;
  const int native_h = display.*p_native_height;
  int nx0 = std::max(0, std::min(ax, bx));
  int ny0 = std::max(0, std::min(ay, by));
  int nx1 = std::min(native_w, std::max(ax, bx) + 1);
  int ny1 = std::min(native_h, std::max(ay, by) + 1);
  if (nx1 <= nx0 || ny1 <= ny0)
    return;

  uint8_t nibble = color_to_gray4(color);
  if (display.*p_invert)
    nibble = static_cast<uint8_t>(0x0F - nibble);
  const uint8_t packed = static_cast<uint8_t>((nibble << 4) | nibble);
  const uint16_t stride = display.*p_row_width;

  for (int yy = ny0; yy < ny1; ++yy) {
    uint8_t *row = buffer + static_cast<size_t>(yy) * stride;
    int start = nx0;

    // Odd x: update only the low nibble of the first byte.
    if (start & 1) {
      const size_t idx = static_cast<size_t>(start >> 1);
      row[idx] = static_cast<uint8_t>((row[idx] & 0xF0) | nibble);
      ++start;
    }

    // Byte-aligned middle: two pixels per byte, filled natively.
    const int pair_pixels = ((nx1 - start) / 2) * 2;
    if (pair_pixels > 0) {
      std::memset(row + (start >> 1), packed, static_cast<size_t>(pair_pixels >> 1));
      start += pair_pixels;
    }

    // Remaining even x: update only the high nibble.
    if (start < nx1) {
      const size_t idx = static_cast<size_t>(start >> 1);
      row[idx] = static_cast<uint8_t>((row[idx] & 0x0F) | (nibble << 4));
    }

    if ((yy & 0x1F) == 0)
      App.feed_wdt();
  }

  // Mark one bounding dirty rectangle, matching the native driver's semantics.
  display.*p_x_low = std::min<uint16_t>(display.*p_x_low, static_cast<uint16_t>(nx0));
  display.*p_x_high = std::max<uint16_t>(display.*p_x_high, static_cast<uint16_t>(nx1));
  display.*p_y_low = std::min<uint16_t>(display.*p_y_low, static_cast<uint16_t>(ny0));
  display.*p_y_high = std::max<uint16_t>(display.*p_y_high, static_cast<uint16_t>(ny1));
}

}  // namespace esphome::it8951_native
