import hall_probe

hp = hall_probe.MetrolabProbe()
hp.setAverages(100)
print('Averages:', hp.averages)
hp.setRange(0.1)
print('Auto range: ', hp.auto_range)
print('Range:', hp.range, hp.range_units)
hp.setUnits('MT')
print('Field:', hp.getField(), hp.units)