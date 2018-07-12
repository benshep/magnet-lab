import os
import numpy as np
import hp_line_scan
import motor_controller
from datetime import datetime

x, y = 0, 0

mc = motor_controller.MotorController()
mc.axis['x'].move(x, wait=True)
mc.axis['y'].move(y, wait=True)

start, stop, step = 0, 40, 0.5
line_scan = hp_line_scan.LineScan('z', start, stop, step, mc=mc)

magnet = 'PITZ Compensation Solenoid'
current = 30
comment = 'Z scan to find peak'

path = r'\\fed.cclrc.ac.uk\Org\NLab\ASTeC\Apsv4\Astec\IDs and Magnets\Data\PITZ solenoids\Compensation solenoid 15050'
filename = os.path.join(path, '07 z scan.csv')
file = open(filename, 'a')
scan_time = datetime.now()

line_scan.run()
# fit 2nd-order poly to Bz values
fit_coeffs = np.polyfit(line_scan.pos_values, line_scan.field_values[:, 2], deg=2)
peak_pos = -fit_coeffs[1] / (2 * fit_coeffs[0])
print(f'Found peak at {peak_pos:.3f} mm')

hp = line_scan.hp
header = ['Date/time,' + scan_time.strftime('%d/%m/%y %H:%M:%S'),
          f'Magnet under test,{magnet}',
          f'Magnet current [A],{current}',
          f'Probe,{hp.probe.manufacturer_name} {hp.probe.model_name} S/N {hp.probe.serial_number}',
          f'Averages,{hp.getAverages()}',
          f'Probe range,{hp.getRange()[1]}',
          f'Comment,{comment}',
          f'X position [mm],{x}',
          f'Y position [mm],{y}',
          'Polynomial fit coefficients,' + ','.join([f'{c:.3g}' for c in fit_coeffs]),
          f'Peak position [mm],{peak_pos:.3f}',
          'Z [mm],Bx [mT],By [mT],Bz [mT]',
          ]
file.writelines('%s\n' % l for l in header)
for position, field in zip(line_scan.pos_values, line_scan.field_values):
    file.write(','.join([f'{p:.3f}' for p in np.insert(field, 0, position)]) + '\n')
file.close()
