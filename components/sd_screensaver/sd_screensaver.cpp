#include "sd_screensaver.h"
#include "esphome/core/application.h"
#include "esphome/core/log.h"
#include "driver/gpio.h"
#include "driver/sdspi_host.h"
#include "esp_vfs_fat.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "esp_random.h"
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <sys/stat.h>

namespace esphome::sd_screensaver {
static constexpr const char *TAG="sd_screensaver";
static constexpr uint32_t MAGIC=0xE1003A01;
static constexpr uint32_t BOOT_CLEANUP_PAUSE_MS=1600UL;
static constexpr uint32_t BOOT_COLD_START_WAIT_MS=2500UL;
static constexpr uint32_t BOOT_WARM_START_WAIT_MS=500UL;
static constexpr uint32_t USER_FULL_REFRESH_WINDOW_MS=2500UL;
static RTC_DATA_ATTR SleepState retained;
bool sleeping_screensaver_input_wake(){
  auto cause=esp_sleep_get_wakeup_cause();
  return retained.magic==MAGIC && retained.active &&
    (cause==ESP_SLEEP_WAKEUP_EXT0 || cause==ESP_SLEEP_WAKEUP_EXT1);
}
static uint16_t le16(const uint8_t *p){return p[0]|uint16_t(p[1])<<8;}
static uint32_t le32(const uint8_t *p){return le16(p)|uint32_t(le16(p+2))<<16;}
static uint8_t gray4(uint8_t v){return std::min(15, (int(v)+8)>>4);}
static const char *reset_reason_name(esp_reset_reason_t reason){
  switch(reason){
    case ESP_RST_POWERON:return "POWERON";
    case ESP_RST_EXT:return "EXT";
    case ESP_RST_SW:return "SW";
    case ESP_RST_PANIC:return "PANIC";
    case ESP_RST_INT_WDT:return "INT_WDT";
    case ESP_RST_TASK_WDT:return "TASK_WDT";
    case ESP_RST_WDT:return "WDT";
    case ESP_RST_DEEPSLEEP:return "DEEPSLEEP";
    case ESP_RST_BROWNOUT:return "BROWNOUT";
    case ESP_RST_SDIO:return "SDIO";
    default:return "UNKNOWN";
  }
}

void SDScreensaver::setup(){
  last_activity_=millis();
  const auto cause=esp_sleep_get_wakeup_cause();
  const auto reset_reason=esp_reset_reason();
  const bool retained_valid=retained.magic==MAGIC;
  resume_=retained_valid && retained.active && cause==ESP_SLEEP_WAKEUP_TIMER;
  if(resume_){
    clock_active_=retained.clock_active;
    if(clock_active_)clock_minute_=retained.clock_minute;
  }else retained={MAGIC,false,false,0,{0}};

  // A real battery power-cycle loses RTC_DATA_ATTR. This is a more robust cold
  // boot signal than relying only on esp_reset_reason(), which can differ with
  // board/power-path behaviour. Genuine deep-sleep wakes retain the marker and
  // keep their fast path. OTA/software resets still receive the cleanup.
  boot_cleanup_cold_start_=!retained_valid;
  const bool genuine_deep_sleep_wake=retained_valid && reset_reason==ESP_RST_DEEPSLEEP &&
      (cause==ESP_SLEEP_WAKEUP_TIMER || cause==ESP_SLEEP_WAKEUP_EXT0 || cause==ESP_SLEEP_WAKEUP_EXT1);
  boot_cleanup_active_=boot_cleanup_cold_start_ || !genuine_deep_sleep_wake;
  boot_cleanup_stage_=0;
  boot_cleanup_pause_pending_=false;
  boot_cleanup_pause_until_=0;
  boot_cleanup_start_after_=0;
  user_full_refresh_until_=0;
  ESP_LOGI(TAG,"Reset-Ursache: %s (%d), Wakeup-Ursache: %d, RTC-Marker: %s",
           reset_reason_name(reset_reason),(int)reset_reason,(int)cause,
           retained_valid?"erhalten":"KALTSTART");
  if(boot_cleanup_active_)
    ESP_LOGI(TAG,"Boot-Cleanup vorgemerkt: WEISS -> SCHWARZ -> WEISS -> SCHWARZ -> WEISS (GC16, %u ms Pause)",
             (unsigned)BOOT_CLEANUP_PAUSE_MS);
  else
    ESP_LOGI(TAG,"Boot-Cleanup uebersprungen: bestaetigter Deep-Sleep-Wakeup");

  // Display CS must stay deasserted while the SD card enters SPI mode.
  gpio_set_direction(GPIO_NUM_10,GPIO_MODE_OUTPUT);gpio_set_level(GPIO_NUM_10,1);
  gpio_set_direction(GPIO_NUM_14,GPIO_MODE_OUTPUT);gpio_set_level(GPIO_NUM_14,1);
  gpio_set_direction(GPIO_NUM_39,GPIO_MODE_OUTPUT);gpio_set_level(GPIO_NUM_39,0);
  gpio_set_direction(GPIO_NUM_15,GPIO_MODE_INPUT);gpio_set_pull_mode(GPIO_NUM_15,GPIO_PULLUP_ONLY);
  if(gpio_get_level(GPIO_NUM_15)==0)mount_();
}
void SDScreensaver::loop(){
  if(!boot_cleanup_active_ || !panel_idle_())return;

  // Cold power-on needs a little settling time after the IT8951 reports IDLE.
  // OTA/software resets use the shorter warm-start delay.
  if(boot_cleanup_stage_==0){
    if(boot_cleanup_start_after_==0){
      const uint32_t wait=boot_cleanup_cold_start_?BOOT_COLD_START_WAIT_MS:BOOT_WARM_START_WAIT_MS;
      boot_cleanup_start_after_=millis()+wait;
      ESP_LOGI(TAG,"Boot-Cleanup startet nach %u ms Panel-Stabilisierungszeit",(unsigned)wait);
      return;
    }
    if((int32_t)(millis()-boot_cleanup_start_after_)<0)return;
  }

  // Start the inter-stage pause only after the preceding physical GC16 update
  // has actually completed. This makes the cleanup visibly slower without
  // blocking the ESPHome scheduler or watchdog.
  if(boot_cleanup_pause_pending_){
    if(boot_cleanup_pause_until_==0){
      boot_cleanup_pause_until_=millis()+BOOT_CLEANUP_PAUSE_MS;
      return;
    }
    if((int32_t)(millis()-boot_cleanup_pause_until_)<0)return;
    boot_cleanup_pause_pending_=false;
    boot_cleanup_pause_until_=0;
  }

  auto writer=&DisplayAccess::writer_;
  auto force_full_panel=[&](){
    display_->*(&DisplayAccess::x_low_)=0;
    display_->*(&DisplayAccess::y_low_)=0;
    display_->*(&DisplayAccess::x_high_)=display_->*(&DisplayAccess::width_);
    display_->*(&DisplayAccess::y_high_)=display_->*(&DisplayAccess::height_);
  };
  auto paint=[&](Color color,const char *name,uint8_t step,uint8_t next){
    display_->set_writer(display::display_writer_t([color](display::Display &it){it.fill(color);}));
    // On a cold boot the software framebuffer may already contain white while
    // the physical ePaper still retains the previous image. Explicitly forcing
    // the complete dirty region guarantees a real full-panel transaction.
    force_full_panel();
    ESP_LOGI(TAG,"Boot-Cleanup %u/5: %s (FULL PANEL)",(unsigned)step,name);
    display_->update_mode(it8951::UPDATE_MODE_GC16);
    boot_cleanup_stage_=next;
    boot_cleanup_pause_pending_=true;
  };

  switch(boot_cleanup_stage_){
    case 0:
      // Save the normal YAML writer only after the IT8951 display is initialized.
      // Normal YAML updates see display_idle()==false until the cleanup is done.
      boot_writer_=display_->*writer;
      paint(Color::WHITE,"WEISS",1,1);
      return;
    case 1:
      paint(Color::BLACK,"SCHWARZ",2,2);
      return;
    case 2:
      paint(Color::WHITE,"WEISS",3,3);
      return;
    case 3:
      paint(Color::BLACK,"SCHWARZ",4,4);
      return;
    case 4:
      paint(Color::WHITE,"WEISS",5,5);
      return;
    case 5:
      // Restore the original renderer and paint the actual UI immediately.
      display_->set_writer(display::display_writer_t(boot_writer_));
      force_full_panel();
      ESP_LOGI(TAG,"Boot-Cleanup: normaler Renderer wiederhergestellt (FULL PANEL)");
      display_->update_mode(it8951::UPDATE_MODE_GC16);
      boot_cleanup_stage_=6;
      return;
    default:
      boot_cleanup_active_=false;
      ESP_LOGI(TAG,"Boot-Cleanup abgeschlossen; normale Displayupdates wieder freigegeben");
      return;
  }
}
bool SDScreensaver::panel_idle_() const {
  if(!display_ || display_->is_failed())return false;
  auto p=&DisplayAccess::phase_;auto i=&DisplayAccess::initialised_;auto u=&DisplayAccess::update_pending_;
  return display_->*i && display_->*p==it8951::Phase::IDLE && !(display_->*u);
}
bool SDScreensaver::display_idle() const {
  // Keep every YAML/screensaver update out of the way until the boot cleanup
  // owns the display no longer. loop() uses panel_idle_() directly.
  const bool idle=!boot_cleanup_active_ && panel_idle_();
  if(!idle)return false;

  // Touch and the three physical buttons all call activity() before their
  // navigation/action logic. During this short window force the next normal UI
  // GC16 transaction to cover the whole panel. This removes remnants from the
  // previous page while leaving autonomous minute-level updates partial.
  if(!active_ && user_full_refresh_until_!=0 &&
     (int32_t)(user_full_refresh_until_-millis())>0){
    display_->*(&DisplayAccess::x_low_)=0;
    display_->*(&DisplayAccess::y_low_)=0;
    display_->*(&DisplayAccess::x_high_)=display_->*(&DisplayAccess::width_);
    display_->*(&DisplayAccess::y_high_)=display_->*(&DisplayAccess::height_);
  }
  return true;
}
bool SDScreensaver::mount_(){
  gpio_set_level(GPIO_NUM_39,1);delay(200);
  // ESPHome owns SPI2_HOST (interface: spi2); never initialise/free that bus here.
  sdmmc_host_t host=SDSPI_HOST_DEFAULT();host.slot=SPI2_HOST;host.max_freq_khz=4000;
  sdspi_device_config_t dev=SDSPI_DEVICE_CONFIG_DEFAULT();
  dev.host_id=SPI2_HOST;dev.gpio_cs=GPIO_NUM_14;
  esp_vfs_fat_sdmmc_mount_config_t cfg={};
  cfg.format_if_mount_failed=false;cfg.max_files=3;cfg.allocation_unit_size=0;
  esp_err_t err=esp_vfs_fat_sdspi_mount("/sdcard",&host,&dev,&cfg,&card_);
  if(err!=ESP_OK){
    ESP_LOGW(TAG,"SD nicht lesbar: %s (kein Formatieren)",esp_err_to_name(err));
    card_=nullptr;gpio_set_level(GPIO_NUM_39,0);return false;
  }
  mounted_=true;scan_();ESP_LOGI(TAG,"SD bereit: %u BMP/Gray4-Dateien",unsigned(files_.size()));return true;
}
void SDScreensaver::unmount_(){
  if(mounted_)esp_vfs_fat_sdcard_unmount("/sdcard",card_);
  mounted_=false;card_=nullptr;files_.clear();gpio_set_level(GPIO_NUM_14,1);gpio_set_level(GPIO_NUM_39,0);
}
void SDScreensaver::on_safe_shutdown(){unmount_();}
bool SDScreensaver::card_present() const{return gpio_get_level(GPIO_NUM_15)==0;}
bool SDScreensaver::poll_card(){
  if(!display_idle())return mounted_;
  if(gpio_get_level(GPIO_NUM_15)!=0){if(mounted_)unmount_();return false;}
  if(!mounted_) {
    mount_();
  }
  return mounted_;
}
void SDScreensaver::scan_(){
  files_.clear();DIR *dir=opendir("/sdcard/screensaver");if(!dir)return;
  while(auto *e=readdir(dir)){
    std::string name=e->d_name;if(name.empty()||name[0]=='.')continue;
    auto dot=name.find_last_of('.');if(dot==std::string::npos)continue;
    std::string ext=name.substr(dot);for(auto &c:ext)c=std::tolower(static_cast<unsigned char>(c));
    if(ext!=".bmp"&&ext!=".gray4")continue;
    std::string path="/sdcard/screensaver/"+name;struct stat st;
    if(path.size()<sizeof(retained.last_file)&&stat(path.c_str(),&st)==0&&S_ISREG(st.st_mode))files_.push_back(path);
    if(files_.size()>=1024)break;
  }closedir(dir);
}
void SDScreensaver::activity(){
  last_activity_=millis();
  user_full_refresh_until_=last_activity_+USER_FULL_REFRESH_WINDOW_MS;
  stop();
}
void SDScreensaver::stop(){
  active_=false;resume_=false;clock_active_=false;retained.active=false;
  if(pixels_){RAMAllocator<uint8_t> a; a.deallocate(pixels_,size_t((width_+1)/2)*height_);pixels_=nullptr;}
}
bool SDScreensaver::due(uint32_t idle_min,uint32_t interval_min) const{
  if(resume_)return true;
  return active_?uint32_t(millis()-last_change_)>=interval_min*60000UL:
                 uint32_t(millis()-last_activity_)>=idle_min*60000UL;
}
bool SDScreensaver::hourly_due() const{return active_&&uint32_t(millis()-last_full_)>=3600000UL;}
void SDScreensaver::prepare_sleep(){
  retained.magic=MAGIC;retained.active=active_;
  retained.clock_active=clock_active_;retained.clock_minute=clock_minute_;
  std::snprintf(retained.last_file,sizeof(retained.last_file),"%s",filename_.c_str());
}
void SDScreensaver::set_pixel_(uint8_t *out,int x,int y,uint8_t v){
  size_t i=size_t(y)*((width_+1)/2)+x/2;
  if(x&1)out[i]=(out[i]&0xf0)|v;else out[i]=(out[i]&0x0f)|(v<<4);
}
bool SDScreensaver::load_bmp_(const std::string &path,uint8_t *out){
  FILE *f=fopen(path.c_str(),"rb");if(!f)return false;
  auto fail=[&](){fclose(f);return false;};
  uint8_t hdr[54];if(fread(hdr,1,54,f)!=54||hdr[0]!='B'||hdr[1]!='M'||le32(hdr+14)<40)return fail();
  uint32_t offset=le32(hdr+10),dib=le32(hdr+14);
  int32_t iw=int32_t(le32(hdr+18)),ih=int32_t(le32(hdr+22));
  uint16_t bpp=le16(hdr+28);
  if(iw<=0||iw>8192||ih==0||ih < -8192||ih>8192||le16(hdr+26)!=1||le32(hdr+30)!=0||
     (bpp!=1&&bpp!=4&&bpp!=8&&bpp!=24&&bpp!=32))return fail();
  bool top=ih<0;int h=top?-ih:ih;size_t stride=((size_t(iw)*bpp+31)/32)*4;
  struct stat st;if(fstat(fileno(f),&st)!=0||uint64_t(offset)+uint64_t(stride)*h>uint64_t(st.st_size))return fail();
  uint8_t palette[256]={};
  if(bpp<=8){
    uint32_t n=le32(hdr+46);if(n==0)n=1U<<bpp;
    if(n>(1U<<bpp)||uint64_t(14)+dib+n*4>offset||fseek(f,14+dib,SEEK_SET)!=0)return fail();
    for(unsigned j=0;j<n;j++){uint8_t c[4];if(fread(c,1,4,f)!=4)return fail();
      palette[j]=gray4(uint8_t((77U*c[2]+150U*c[1]+29U*c[0]+128)>>8));}
  }
  RAMAllocator<uint8_t> allocator;uint8_t *row=allocator.allocate(stride);if(!row)return fail();
  double scale=std::min(double(width_)/iw,double(height_)/h);
  int dw=std::max(1,int(iw*scale)),dh=std::max(1,int(h*scale)),ox=(width_-dw)/2,oy=(height_-dh)/2;
  int prev=-1;bool ok=true;
  for(int y=0;y<dh;y++){
    int sy=std::min(h-1,int(y/scale));
    if(sy!=prev){
      if(fseek(f,offset+size_t(top?sy:h-1-sy)*stride,SEEK_SET)!=0||fread(row,1,stride,f)!=stride){ok=false;break;}
      prev=sy;
    }
    for(int x=0;x<dw;x++){
      int sx=std::min(static_cast<int>(iw)-1,int(x/scale));uint8_t v;
      if(bpp==1)v=palette[(row[sx/8]>>(7-(sx&7)))&1];
      else if(bpp==4)v=palette[(row[sx/2]>>((sx&1)?0:4))&15];
      else if(bpp==8)v=palette[row[sx]];
      else {auto *c=row+sx*(bpp/8);v=gray4(uint8_t((77U*c[2]+150U*c[1]+29U*c[0]+128)>>8));}
      set_pixel_(out,x+ox,y+oy,v);
    }App.feed_wdt();
  }
  allocator.deallocate(row,stride);fclose(f);return ok;
}
bool SDScreensaver::load_gray4_(const std::string &path,uint8_t *out){
  FILE *f=fopen(path.c_str(),"rb");if(!f)return false;
  // G4E1, uint16 LE logical width/height, then row-major high nibble first.
  uint8_t hdr[8];size_t n=size_t((width_+1)/2)*height_;
  bool ok=fread(hdr,1,8,f)==8&&!memcmp(hdr,"G4E1",4)&&le16(hdr+4)==width_&&le16(hdr+6)==height_;
  if(ok){for(size_t p=0;p<n;p+=4096){size_t chunk=std::min(size_t(4096),n-p);
    if(fread(out+p,1,chunk,f)!=chunk){ok=false;break;}App.feed_wdt();}}
  fclose(f);return ok;
}
bool SDScreensaver::next(){
  if(!mounted_||!display_idle())return false;
  width_=display_->get_width();height_=display_->get_height();
  size_t n=size_t((width_+1)/2)*height_;RAMAllocator<uint8_t> allocator;
  uint8_t *candidate=allocator.allocate(n);if(!candidate){ESP_LOGE(TAG,"Kein RAM fuer Gray4-Bild");return false;}
  bool ok=false;std::string chosen;
  {
    scan_();const std::string previous=resume_?std::string(retained.last_file):filename_;
    auto candidates=files_;
    if(candidates.size()>1)candidates.erase(std::remove(candidates.begin(),candidates.end(),previous),candidates.end());
    while(!candidates.empty()){
      size_t i=esp_random()%candidates.size();chosen=candidates[i];memset(candidate,0xff,n);
      auto dot=chosen.find_last_of('.');std::string ext=chosen.substr(dot);
      for(auto &c:ext)c=std::tolower(static_cast<unsigned char>(c));
      ok=ext==".gray4"?load_gray4_(chosen,candidate):load_bmp_(chosen,candidate);
      if(ok)break;
      ESP_LOGW(TAG,"Ungueltiges/nicht unterstuetztes Bild: %s",chosen.c_str());candidates.erase(candidates.begin()+i);
    }
  }
  if(!ok){allocator.deallocate(candidate,n);ESP_LOGW(TAG,"Kein lesbares Bild; normale UI bleibt verfuegbar");return false;}
  if(pixels_) {
    allocator.deallocate(pixels_,n);
  }
  pixels_=candidate;
  filename_=chosen;active_=true;resume_=false;clock_active_=false;last_change_=millis();
  ESP_LOGI(TAG,"Bild bereit: %s (%dx%d)",filename_.c_str(),width_,height_);return true;
}
bool SDScreensaver::next_clock(uint32_t minute){
  if(!display_idle())return false;
  const bool first_clock=!active_ || !clock_active_;
  previous_clock_minute_=clock_minute_;
  active_=true;resume_=false;clock_active_=true;last_change_=millis();
  clock_minute_=minute;filename_.clear();

  // The framebuffer retains the complete clock because auto_clear is disabled.
  // Every five minutes force the dirty rectangle to the complete panel. The
  // existing YAML clock renderer may still redraw only the changed digit/hand,
  // but GC16 then transfers and drives every pixel, including static digits.
  const bool five_minute_clean=minute>0 && (minute%5U)==0U;
  if(first_clock || five_minute_clean)last_full_=millis();
  if(five_minute_clean){
    display_->*(&DisplayAccess::x_low_)=0;
    display_->*(&DisplayAccess::y_low_)=0;
    display_->*(&DisplayAccess::x_high_)=display_->*(&DisplayAccess::width_);
    display_->*(&DisplayAccess::y_high_)=display_->*(&DisplayAccess::height_);
    ESP_LOGI(TAG,"Uhr: 5-Minuten-Cleanup -> kompletter GC16-Panelrefresh");
  }
  return true;
}
void SDScreensaver::render(){
  if(!active_||!pixels_)return;
  // Logical coordinates -> native framebuffer. Match existing driver mirror/rotation.
  auto b=&DisplayAccess::buffer_;auto s=&DisplayAccess::row_width_;
  auto t=&DisplayAccess::apply_transform_;auto inv=&DisplayAccess::invert_colors_;
  uint8_t *dst=display_->*b;if(!dst)return;
  for(int y=0;y<height_;y++){
    for(int x=0;x<width_;x++){
      uint8_t v=(pixels_[size_t(y)*((width_+1)/2)+x/2]>>((x&1)?0:4))&15;
      if(display_->*inv)v=15-v;
      int nx=x,ny=y;(display_->*t)(nx,ny);size_t idx=size_t(ny)*(display_->*s)+nx/2;
      dst[idx]=(nx&1)?((dst[idx]&0xf0)|v):((dst[idx]&0x0f)|(v<<4));
    }App.feed_wdt();
  }
  display_->*(&DisplayAccess::x_low_)=0;display_->*(&DisplayAccess::y_low_)=0;
  display_->*(&DisplayAccess::x_high_)=display_->*(&DisplayAccess::width_);
  display_->*(&DisplayAccess::y_high_)=display_->*(&DisplayAccess::height_);
  last_full_=millis();
}
} // namespace
