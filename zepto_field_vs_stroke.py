import motor_controller
import hall_probe
import numpy as np

dipole_ctrl = motor_controller.ZeptoDipoleController()
dipole_axis = dipole_ctrl.axis
probe = hall_probe.MetrolabProbe()
probe.setAverages(100)

filename = r'\\fed.cclrc.ac.uk\Org\NLab\ASTeC\Apsv4\Astec\IDs and Magnets\Data\ZEPTO dipole\01 field vs stroke.csv'
file = open(filename, 'a')

# dipole_axis.stop()
for stroke in np.arange(0, 400.5, 0.5):
    dipole_axis.move(stroke, wait=True, timeout=1000)
    field = probe.getField()
    print(stroke, field)
    file.writelines(f'{stroke:.1f},' + ','.join(['{:.5f}'.format(b) for b in field[0]]) + '\n')
    file.flush()

file.close()
