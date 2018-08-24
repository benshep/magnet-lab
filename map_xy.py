import sys
import os
import numpy as np
import motor_controller
import hp_line_scan
from adlink_card import EncoderException
from datetime import datetime
import argparse
from typing import List
from collections import OrderedDict


def scan_range(arg) -> List:
    l = [x if i == 0 else float(x) for i, x in enumerate(arg.replace('=', ',').split(','))]
    if len(l) not in (2, 3, 4) or l[0].lower() not in ('x', 'y', 'z', 's'):
        raise argparse.ArgumentTypeError(f"Can't interpret range specifier {arg}")
    return l


# Parse the input arguments
parser = argparse.ArgumentParser(description='Perform a 2D Hall probe scan.',
                                 epilog='Multiple scan ranges can be specified. The first one is the primary axis and will preferentially use an on-the-fly scan.')
parser.add_argument('scan', help="scan axis and range in the format X|Y|Z,start[,stop[,step]]", type=scan_range,
                    action='append', nargs='+')
parser.add_argument('-f', '--file', help="filename to save data - print data to console if not specified")
parser.add_argument('-c', '--comment', help="comment for the output file")
parser.add_argument('-m', '--magnet', help='name of magnet to be scanned')
parser.add_argument('-i', '--current', help="current in the magnet [Amps]", type=float)

args = parser.parse_args()
scans = args.scan[0]

# Ensure we are doing at least one scan!
# TODO: in the future, allow this
if all([len(scan) < 3 for scan in scans]):
    raise ValueError('No scans specified - only fixed positions.')

# Ensure first argument is a scan, not a fixed position
for i, scan in enumerate(scans):
    if len(scan) > 2:
        scans.insert(0, scans.pop(i))
        break

mc = motor_controller.MotorController()
line_scan = hp_line_scan.LineScan(*scans[0], mc=mc)
# Are the other axes specified? If not, add them as a 'scan' in a single position
scan_dirs = {scan[0] for scan in scans}
dirs = {'x', 'y', 'z'}
unlisted_dirs = dirs - scan_dirs
for direction in unlisted_dirs:
    scans.append([direction, mc.axis[direction].get_position()])

# Using the ZEPTO dipole with a 'stroke' axis?
if 's' in scan_dirs:
    dipole_ctrl = motor_controller.ZeptoDipoleController()
    mc.axis['s'] = dipole_ctrl.axis  # this is perhaps a little hacky, but should work

# Convert each remaining scan specification into a tuple of ('axis_name', array([val1, val2, ...]) )
scans = [(scan[0], hp_line_scan.arange(*scan[1:])) for scan in scans[1:]]

# Concatenate arrays together, so that "x=1,2,3 y=1 x=5,6,7" -> "x=1,2,3,5,6,7 y=1"
scan_dict = OrderedDict()
for axis_name, scan_array in scans:
    scan_dict[axis_name] = np.concatenate([scan_dict[axis_name], scan_array]) if axis_name in scan_dict.keys() else scan_array

# Metadata for the file
magnet = args.magnet
current = args.current
comment = args.comment

# magnet = 'PITZ Compensation Solenoid'
# current = 30
# comment = 'YZ scan at X centre +10mm'

# Where to save the file(s)?
# path = r'\\fed.cclrc.ac.uk\Org\NLab\ASTeC\Apsv4\Astec\IDs and Magnets\Data\PITZ solenoids\Compensation solenoid 15050'
# basename = '17 yz scan (x centre +10mm)'

# Set up the scan
hp = line_scan.hp
field_units = 'T'
hp.setUnits(field_units)
hp.setRange(3.0)  # TODO: add to options

# Produce a header for the file(s)
header = [('Date/time', datetime.now().strftime('%d/%m/%y %H:%M:%S')),
          ('Magnet under test', magnet) if magnet else (),
          ('Magnet current [A]', current) if current else (),
          ('Probe', f'{hp.probe.manufacturer_name} {hp.probe.model_name} S/N {hp.probe.serial_number}'),
          ('Averages', hp.getAverages()),
          ('Probe range', hp.getRange()[1]),
          ('Comment', comment) if comment else (),
          ]

columns = ''
for axis_name, scan_array in scan_dict.items():
    if len(scan_array) == 1:
        header.append((f'{axis_name} position [mm]', scan_array[0]))
    else:
        columns += f'{axis_name} [mm],'
columns += f'{line_scan.axis_name} [mm]'

# Write header and columns to CSV file
out_file = open(args.file, 'a') if args.file else sys.stdout
[print(*l, sep=',', file=out_file) for l in header if l]
print(f'{columns},Bx [{field_units}],By [{field_units}],Bz [{field_units}]', file=out_file)

# we should have two or three axes to scan over (e.g. X, Y, and stroke, with a LineScan in Z)
assert len(scan_dict) in (2, 3)
scan_index = 0
start = datetime.now()
eta = None

axis2 = list(scan_dict)[0]
ax2_values = scan_dict[axis2]
axis3 = list(scan_dict)[1]
ax3_values = scan_dict[axis3]
if len(scan_dict) >= 3:
    axis4 = list(scan_dict)[2]
    ax4_values = scan_dict[axis4]
else:
    axis4 = None
    ax4_values = [0]

n_line_scans = len(ax2_values) * len(ax3_values) * len(ax4_values)

for k, s in enumerate(ax4_values):
    if axis4 is not None:
        print(f'{axis4} = {s} mm')
        mc.axis[axis4].move(s, wait=True)

    for j, z in enumerate(ax3_values):
        print(f'{axis3} = {z} mm')
        mc.axis[axis3].move(z, wait=True)

        # Run the scan, invoking line_scan for each position along axis 2
        for i, y in enumerate(ax2_values):
            if i > 0:
                progress = i / n_line_scans
                elapsed = datetime.now() - start
                eta = start + elapsed / progress
            print(f'{axis2} = {y} mm' + (eta.strftime(', ETA %H:%M') if eta else ''))
            mc.axis[axis2].move(y, wait=True)
            tries = 0
            ok = False
            while not ok:
                try:
                    line_scan.run()
                    ok = True
                except (hp_line_scan.MissedTriggerError, EncoderException) as e:  # sometimes we get a little hiccup
                    line_scan.axis.stop()
                    tries += 1
                    print(e)
                    if tries % 5 == 0 and input(f'Scan failed after {tries} tries. Try again? [Y/n]').upper() not in ('', 'Y'):
                        raise  # break out
            # line_scan.field_values = np.random.rand(len(line_scan.pos_values), 3) - 0.5  # for testing!

            # Record the data in the file(s)
            pos_vector = [z] if len(ax3_values) > 1 else []
            if len(ax2_values) > 1:
                pos_vector.append([y])
            for column, (x, field) in enumerate(zip(line_scan.pos_values, line_scan.field_values)):
                print(','.join([f'{p:.5f}' for p in np.concatenate([[y, x], field])]), file=out_file, flush=True)

            # Save as we go along in case of unforeseen errors
            out_file.flush()

out_file.close()
