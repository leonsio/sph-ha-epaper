import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.it8951.display import IT8951Display
from esphome.const import CONF_ID
DEPENDENCIES = ["display"]
ns = cg.esphome_ns.namespace("epaper_refresh")
EpaperRefresh = ns.class_("EpaperRefresh", cg.Component)
CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(EpaperRefresh),
    cv.Required("display_id"): cv.use_id(IT8951Display),
}).extend(cv.COMPONENT_SCHEMA)
async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_display(await cg.get_variable(config["display_id"])))
