import numpy as np
import motor_controller
import hall_probe

mc = motor_controller.MotorController()
axis = mc.axis['x']

hp = hall_probe.MetrolabProbe()
hp.setAverages(100)
hp.setRange(0.1)

start, stop, step = -10, 10, 0.5
x_values = np.linspace(start, stop, (stop - start) / step + 1)
field_values = np.zeros((len(x_values), 3))
for i, x in enumerate(x_values):
    # axis.move(x, wait=True)
    field_values[i] = hp.getField()

print(field_values)