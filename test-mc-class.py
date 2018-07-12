import motor_controller
mc = motor_controller.MotorController()
za = mc.axis['px']
# qa = za.queryAll()
# qa_list = sorted([(k, v) for k, v in qa.items()])
# for k, v in qa_list:
#     print(k, '\t', v)
za.setLimits(None)
print(za.getLimits())
# pos = za.get_position()
# print('Axis {}: {} {}'.format(za.id, pos, za.units))
# za.move(10, relative=False, wait=True)
# za.resetPosition()
# za.setLimits((-10, 10))
# za.move(11, relative=False, wait=True)
# pos = za.get_position()
# print('Axis {}: {} {}'.format(za.id, pos, za.units))

