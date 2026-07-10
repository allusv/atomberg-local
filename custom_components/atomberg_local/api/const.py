"""Protocol constants for local Atomberg fan control.

Two transports reach the same fan:

* Wi-Fi  - JSON command datagram to UDP :5600; the fan broadcasts a presence
           beacon and full state on UDP :5625.
* BLE    - the same JSON commands written to the command characteristic; state
           read from the state characteristic. Works with no Wi-Fi at all.

The fan is identified by its stable ``device_id`` (its Wi-Fi MAC, e.g.
``a1b2c3d4e5f6``). Both transports expose it, so a fan seen over BLE and later
over Wi-Fi is the same logical device.
"""

# --- Wi-Fi (UDP) ---
CMD_PORT = 5600          # fan listens here for JSON command datagrams
BROADCAST_PORT = 5625    # fan broadcasts presence beacons + state here

# --- BLE (GATT) ---
BLE_SERVICE_UUID = "9256cc8a-85b3-46a6-a4a4-9b6a2e1248be"
BLE_CMD_CHAR = "e29ee02c-af3d-11ec-b909-0242ac120002"    # write JSON cmd / notify+read 4B state
BLE_STATE_CHAR = "9fa1610e-e6fc-11ec-8fea-0242ac120002"  # read full state_string
BLE_APLIST_CHAR = "36684e6a-df79-4e4b-b031-0620ecf10cae"  # read scanned Wi-Fi AP list
BLE_WIFI_CHAR = "f1bd396f-8a7a-43a9-a112-777eb60db2aa"   # encrypted provisioning (not used)
BLE_NAME_PREFIXES = ("atomberg_", "Atomberg_")           # advertised local-name prefix

# BLE MAC = Wi-Fi MAC + 2 (empirically); device_id is the stable key regardless.
BLE_MAC_OFFSET = 2

# --- command / state field keys ---
ATTR_POWER = "power"
ATTR_SPEED = "speed"
ATTR_SLEEP = "sleep"
ATTR_LED = "led"
ATTR_BRIGHTNESS = "brightness"
ATTR_TIMER = "timer"
ATTR_BOOST = "boost"
ATTR_LIGHT_MODE = "light_mode"

READ_COMMAND = {"read": 1}   # no-op query: fan replies with current state

MIN_SPEED = 1
MAX_SPEED = 6
MAX_TIMER_HOURS = 4          # 0-4 hours

LIGHT_MODE_COOL = "cool"
LIGHT_MODE_WARM = "warm"
LIGHT_MODE_DAYLIGHT = "daylight"

# how stale a Wi-Fi beacon may be before we treat Wi-Fi as down (seconds)
WIFI_STALE_AFTER = 12.0
