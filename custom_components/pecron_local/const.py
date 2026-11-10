from __future__ import annotations

DOMAIN = "pecron_local"

PLATFORMS = ["sensor", "binary_sensor", "switch", "select"]

CONF_AUTH_KEY = "auth_key"
CONF_MAC = "mac"
CONF_POLL_INTERVAL = "poll_interval"
CONF_PREFERRED_TRANSPORT = "preferred_transport"
CONF_REGION = "region"
CONF_DEVICE_KEY = "device_key"
CONF_PRODUCT_KEY = "product_key"
CONF_CONTROLS = "controls"

DEFAULT_POLL_INTERVAL = 30
DEFAULT_FAILURE_GRACE_POLLS = 3
DEFAULT_PORT = 6607
TRANSPORT_TCP = "tcp"
TRANSPORT_BLE = "ble"

# TSL numeric ID → TSL code (from pecron-monitor local_transport.TSL_TOP)
TSL_TOP: dict[int, str] = {
    1: "battery_percentage",
    2: "remain_time",
    3: "remain_charging_time",
    4: "total_input_power",
    5: "total_output_power",
    27: "ups_status_hm",
    28: "dc_data_input_hm",
    29: "ac_data_input_hm",
    30: "dc_data_output_hm",
    31: "ac_data_output_hm",
    32: "ac_output_voltage_io",
    33: "ac_output_frequency_io",
    34: "noastime_io",
    35: "host_packet_data_jdb",
    36: "charging_pack_data_jdb",
    37: "device_status_hm",
    38: "dc_switch_hm",
    39: "add_bat_status_hm",
    40: "ac_switch_hm",
    41: "device_mode_info",
    42: "device_touch_locking_as",
    43: "auto_light_flag_as",
    44: "eco_quite_mode_as",
    45: "machine_screen_light_as",
    46: "ups_start_charge_value_as",
    47: "battery_temp",
    48: "charging_plate_temp",
    49: "inverter_temp",
    50: "ac_charging_power_ios",
    51: "device_standy_times_as",
    52: "device_manual",
    55: "dc_charging_power_enable",
    56: "bypass_enable",
    86: "battery_coding_us",
    87: "beep_voice_us",
    89: "battery_indicator_us",
    90: "FAULT_ALARM_ENUM",
    91: "battery_heating_mode",
    92: "charging_limit_voltage",
    93: "discharge_limiting_voltage",
    94: "charging_current_limit",
    95: "discharge_limiting_current",
    100: "high_frequency_reporting",
}

TSL_STRUCT: dict[str, dict[int, str]] = {
    "host_packet_data_jdb": {
        1: "host_packet_electric_percentage",
        2: "host_packet_voltage",
        3: "host_packet_current",
        4: "host_packet_temp",
        5: "host_packet_status",
    },
    "ac_data_output_hm": {
        1: "ac_output_hz",
        2: "ac_output_voltage",
        3: "ac_output_pf",
        4: "ac_output_power",
    },
    "dc_data_output_hm": {1: "dc_output_power"},
    "ac_data_input_hm": {1: "ac_power"},
    # Solar port sub-field IDs are unknown for local transport — only dc_input_power
    # (ID 1) is confirmed. Per-port detail fields come from cloud MQTT only.
    "dc_data_input_hm": {1: "dc_input_power"},
    "charging_pack_data_jdb": {
        1: "charging_pack_num",
        2: "charging_pack_battery",
        3: "charging_pack_voltage",
        4: "charging_pack_current",
        5: "charging_pack_temp",
        6: "charging_pack_status",
    },
}

# Sensor field lookup: logical name → list of (key path) to try in kv dict
SENSOR_FIELDS: dict[str, list[tuple]] = {
    "battery_percent": [
        ("host_packet_data_jdb", "host_packet_electric_percentage"),
        ("battery_percentage",),
    ],
    "voltage": [("host_packet_data_jdb", "host_packet_voltage")],
    "current": [("host_packet_data_jdb", "host_packet_current")],
    "temperature": [
        ("host_packet_data_jdb", "host_packet_temp"),
        ("battery_temp",),
    ],
    "battery_temp": [("battery_temp",)],
    "charging_plate_temp": [("charging_plate_temp",)],
    "inverter_temp": [("inverter_temp",)],
    "charge_status": [("host_packet_data_jdb", "host_packet_status")],
    "total_input_power": [("total_input_power",)],
    "total_output_power": [("total_output_power",)],
    "ac_output_power": [("ac_data_output_hm", "ac_output_power")],
    "ac_output_voltage": [("ac_data_output_hm", "ac_output_voltage")],
    "ac_output_hz": [("ac_data_output_hm", "ac_output_hz")],
    "ac_output_pf": [("ac_data_output_hm", "ac_output_pf")],
    "ac_input_power": [("ac_data_input_hm", "ac_power")],
    "dc_output_power": [("dc_data_output_hm", "dc_output_power")],
    "dc_input_power": [("dc_data_input_hm", "dc_input_power")],
    "dc5521_input_voltage": [("dc_data_input_hm", "dc5521_input_voltage")],
    "dc5521_input_current": [("dc_data_input_hm", "dc5521_input_current")],
    "dc5521_input_power": [("dc_data_input_hm", "dc5521_input_power")],
    "gx16mf1_input_voltage": [("dc_data_input_hm", "gx16mf1_input_voltage")],
    "gx16mf1_input_current": [("dc_data_input_hm", "gx16mf1_input_current")],
    "gx16mf1_input_power": [("dc_data_input_hm", "gx16mf1_input_power")],
    "gx16mf2_input_voltage": [("dc_data_input_hm", "gx16mf2_input_voltage")],
    "gx16mf2_input_current": [("dc_data_input_hm", "gx16mf2_input_current")],
    "gx16mf2_input_power": [("dc_data_input_hm", "gx16mf2_input_power")],
    "remain_time": [("remain_time",)],
    "remain_charging_time": [("remain_charging_time",)],
    "ac_charging_power": [("ac_charging_power_ios",)],
    "ac_switch": [
        ("ac_switch_hm",),
        ("host_packet_data_jdb", "host_packet_ac_switch"),
    ],
    "dc_switch": [
        ("dc_switch_hm",),
        ("host_packet_data_jdb", "host_packet_dc_switch"),
    ],
    "ups_mode": [
        ("ups_status_hm",),
        ("host_packet_data_jdb", "host_packet_ups_status"),
    ],
    "device_status_hm": [("device_status_hm",)],
    # Energy counters (cloud TSL ids 70-77 on e.g. p11wPr). "Session" values
    # are "this time" in the Pecron app.
    "pv_energy_session": [("solar_panel_power_generation",)],
    "pv_energy_total": [("total_energy",)],
    "ac_charge_energy_session": [("ac_charge_energy",)],
    "ac_charge_energy_total": [("total_ac_charge_energy",)],
    "dc_output_energy_session": [("dc_output_energy",)],
    "dc_output_energy_total": [("total_dc_output_energy",)],
    "ac_output_energy_session": [("ac_output_energy",)],
    "ac_output_energy_total": [("total_ac_output_energy",)],
    "power_pack_attached": [("add_bat_status_hm",)],
    "alarm": [("FAULT_ALARM_ENUM",)],
    "alarm_active": [("FAULT_ALARM_ENUM",)],
    # Derived from power flow; gated on the device reporting input power.
    "activity": [("total_input_power",)],
}

# Remaining-time value the device sends when nothing is drawing power.
REMAIN_TIME_NO_LOAD = 6000

# Labels as printed in the user manual / shown on the unit's screen.
KEY_BRIGHTNESS_OPTIONS: list[str] = ["Off", "L1", "L2", "L3"]

SCREEN_ENERGY_DISPLAY_OPTIONS: list[str] = [
    "Solar Input", "AC Input", "DC Output", "AC Output", "Battery Output",
]

# Alarm codes as listed in the Pecron user manual (shown as e.g. "E02" on the
# unit). The cloud TSL enum for FAULT_ALARM_ENUM uses a different numbering
# and starts at 0 = "Battery Pack Low Temperature", while devices send 0 with
# no alarm active, so the manual's codes are used. Not yet confirmed against a
# live alarm.
ALARM_CODES: dict[int, str] = {
    2: "Battery pack undervoltage",
    3: "Battery discharge overcurrent",
    4: "Battery charge overcurrent",
    5: "Battery short circuit",
    6: "Battery disconnection",
    7: "Battery low voltage, charging prohibited",
    8: "Low charging temperature",
    9: "High charging temperature",
    10: "Low discharging temperature",
    11: "High discharging temperature",
    12: "Charging tube abnormal during discharging",
    20: "Inverter overload",
    21: "Inverter overtemperature",
    22: "Busbar overvoltage/undervoltage",
    35: "DC charging overtemperature",
    40: "DC output short circuit/overload",
    41: "DC output overvoltage",
    42: "DC output overcurrent",
    43: "DC output overtemperature",
    51: "Expansion battery undervoltage",
    52: "Expansion battery discharge overcurrent",
    53: "Expansion battery charging overcurrent",
    54: "Expansion battery short circuit",
    55: "Expansion battery disconnection",
    57: "Expansion battery low charging temperature",
    58: "Expansion battery high charging temperature",
    59: "Expansion battery low discharging temperature",
    60: "Expansion battery high discharging temperature",
}
ALARM_NONE = "None"

# Enum decode tables
DEVICE_STATUS_LABELS: dict[int, str] = {
    0: "Shut Down", 1: "Charging", 2: "DC Discharge",
    3: "AC Discharge", 4: "Standby", 5: "Conservation",
}

CHARGE_STATUS_LABELS: dict[int, str] = {
    0: "No Charge", 1: "Cascade Charging",
    2: "Balance No Charge", 3: "Balanced Charging", 4: "No Connection",
}

AC_CHARGING_POWER_OPTIONS: list[str] = [
    "0%", "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"
]

SCREEN_BRIGHTNESS_OPTIONS: list[str] = ["5%", "20%", "50%", "80%", "100%"]

STANDBY_TIMEOUT_OPTIONS: list[str] = ["24 Hours", "48 Hours", "7 Days", "14 Days", "Always On"]

AC_VOLTAGE_OPTIONS: list[str] = ["100V", "110V", "120V", "220V", "230V", "240V"]

AC_FREQUENCY_OPTIONS: list[str] = ["50Hz", "60Hz"]

AUTO_OFF_OPTIONS: list[str] = ["Off", "1 Hour", "2 Hours", "3 Hours", "4 Hours"]

# Control definitions: TSL code → {id, type, desc}
CONTROLS: dict[str, dict] = {
    "ac_switch_hm": {"id": 40, "type": "BOOL", "desc": "AC output"},
    "dc_switch_hm": {"id": 38, "type": "BOOL", "desc": "DC output"},
    "ups_status_hm": {"id": 27, "type": "BOOL", "desc": "UPS mode"},
    "device_touch_locking_as": {"id": 42, "type": "BOOL", "desc": "Touch lock"},
    "auto_light_flag_as": {"id": 43, "type": "BOOL", "desc": "Auto screen light"},
    "eco_quite_mode_as": {"id": 44, "type": "BOOL", "desc": "Eco/quiet mode"},
    "machine_screen_light_as": {"id": 45, "type": "ENUM", "desc": "Screen brightness"},
    "ac_charging_power_ios": {"id": 50, "type": "ENUM", "desc": "AC charging power"},
    "device_standy_times_as": {"id": 51, "type": "ENUM", "desc": "Standby timeout"},
    "ac_output_voltage_io": {"id": 32, "type": "ENUM", "desc": "AC output voltage"},
    "ac_output_frequency_io": {"id": 33, "type": "ENUM", "desc": "AC output frequency"},
    "noastime_io": {"id": 34, "type": "ENUM", "desc": "Auto-off time"},
    "beep_voice_us": {"id": 87, "type": "BOOL", "desc": "Buzzer"},
    "key_light_us": {"id": 88, "type": "ENUM", "desc": "Key brightness"},
    "screen_power_statistics_mode_us": {"id": 85, "type": "ENUM", "desc": "Screen energy display"},
}


def _enum_sort_key(item: tuple[object, str]) -> tuple[int, object]:
    value, _ = item
    if isinstance(value, int):
        return (0, value)
    return (1, str(value))


def _normalize_enum_labels(raw: dict | None) -> dict:
    labels = {}
    if not isinstance(raw, dict):
        return labels
    for key, label in raw.items():
        try:
            value = int(key)
        except (TypeError, ValueError):
            value = key
        labels[value] = str(label)
    return labels


def enum_labels_from_specs(specs) -> dict:
    """Extract enum value labels from a cloud TSL property `specs` list."""
    labels = {}
    if not isinstance(specs, list):
        return labels
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        if "value" not in spec or "name" not in spec:
            continue
        try:
            value = int(spec["value"])
        except (TypeError, ValueError):
            value = spec["value"]
        labels[value] = str(spec["name"])
    return labels


def enum_labels_for(
    code: str,
    info: dict | None = None,
    fallback_options: list[str] | None = None,
) -> dict:
    """Return model-specific enum labels when available, else explicit fallbacks."""
    if isinstance(info, dict):
        labels = _normalize_enum_labels(info.get("enum_labels"))
        if labels:
            return labels
        labels = _normalize_enum_labels(info.get("labels"))
        if labels:
            return labels
        labels = enum_labels_from_specs(info.get("specs"))
        if labels:
            return labels

    if fallback_options:
        return dict(enumerate(fallback_options))
    return {}


def enum_options(labels: dict) -> list[str]:
    return [label for _, label in sorted(labels.items(), key=_enum_sort_key)]

# Cloud API regions
REGIONS: dict[str, dict] = {
    "na": {
        "name": "North America",
        "base_url": "https://iot-api.landecia.com",
        "user_domain": "C.DM.10351.1",
        "user_domain_secret": "FA5ZHXSka8y9GHvU91Hz1vWvaDSHE2mGW5B7bpn3fXTW",
        "user_domain_fallback": "U.DM.10351.1",
        "user_domain_secret_fallback": "HARsQXfeex8vxyaPRAM8fyjqqVuH2uxAGQ3inJ8XxTiB",
    },
    "eu": {
        "name": "Europe",
        "base_url": "https://iot-api.acceleronix.io",
        "user_domain": "C.DM.10351.1",
        "user_domain_secret": "FA5ZHXSka8y9GHvU91Hz1vWvaDSHE2mGW5B7bpn3fXTW",
    },
    "cn": {
        "name": "China",
        "base_url": "https://iot-api.quectelcn.com",
        "user_domain": "C.DM.5903.1",
        "user_domain_secret": "EufftRJSuWuVY7c6txzGifV9bJcfXHAFa7hXY5doXSn7",
    },
}

BLE_CHAR_UUID = "00009c40-0000-1000-8000-00805f9b34fb"
BLE_DEVICE_PREFIX = "QUEC_BLE"
