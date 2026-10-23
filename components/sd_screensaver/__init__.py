import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import esp32
from esphome.components.it8951.display import IT8951Display
from esphome.const import CONF_ID
from esphome.components.epaper_refresh import EpaperRefresh
# IT8951 is configured as a display platform, not a top-level YAML component.
# display_id still validates that the selected display is an IT8951Display.
DEPENDENCIES = ["esp32", "spi", "display", "epaper_refresh"]
ns = cg.esphome_ns.namespace("sd_screensaver")
SDScreensaver = ns.class_("SDScreensaver", cg.Component)
CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(SDScreensaver),
    cv.Required("refresh_id"): cv.use_id(EpaperRefresh),
    cv.Required("display_id"): cv.use_id(IT8951Display),
}).extend(cv.COMPONENT_SCHEMA)
async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_display(await cg.get_variable(config["display_id"])))
    esp32.require_fatfs()
    for name in ("fatfs", "sdmmc", "esp_driver_sdspi"):
        esp32.include_builtin_idf_component(name)


    cg.add(var.set_refresh(await cg.get_variable(config["refresh_id"])))
