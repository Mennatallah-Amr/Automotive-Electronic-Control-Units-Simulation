from ecu.car_control_ecu import CarControlECU

class L:
    def request(self, *a):
        pass

c = CarControlECU(None, L())
c.command_window(0, 2, 70)
assert c.windows["targets"][0] == 35, c.windows["targets"]
c.command_lights(15, 1)
assert c.lights["headlights"] == "ON"
c.command_door_lock(15, 0)
assert c.door_locks["FL"] is False
print("ok", c.update(0))
