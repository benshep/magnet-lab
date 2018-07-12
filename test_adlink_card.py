import adlink_card
import motor_controller
from time import sleep
import numpy as np

mc = motor_controller.MotorController()
z_axis = mc.axis['z']
start_pos = -10
z_axis.move(start_pos, wait=True)
# sleep(2)
z_encoder_pos = z_axis.get_position(set_value=False) * z_axis.scale_factor
print('Z encoder position (from MC):', z_encoder_pos)

ad8102 = adlink_card.AdlinkCard()
enc_axis = ad8102.axis['z']
enc_axis.setPosition(z_encoder_pos)
print('Encoder position (from Adlink):', enc_axis.getPosition())

move_to = 20
step = 1
steps = np.linspace(start_pos, move_to, abs((move_to - start_pos) / step) + 1)
print('Moving to:', move_to)
z_axis.move(move_to)
for z in steps[1:]:  # skip first one
    trigger_at = z * z_axis.scale_factor
    print('Trigger at encoder position:', trigger_at)
    enc_axis.waitForPosition(trigger_at)
    print('Triggered')

z_encoder_pos = z_axis.get_position(set_value=False) * z_axis.scale_factor
print('Z encoder position (from MC):', z_encoder_pos)
print('Encoder position (from Adlink):', enc_axis.getPosition())
