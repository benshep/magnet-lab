import numpy as np
import motor_controller
import hall_probe
import adlink_card


class InputError(Exception):
    """Raise when a class method has been given incorrect input."""


class MissedTriggerError(Exception):
    """Raise when a trigger has been missed (by moving too fast)."""


def arange(start, stop=None, step=1.0):
    """Use numpy's arange with a slightly higher stop value to ensure the specified stop value is included.
    If no stop value is specified, just return a length-1 array containing only the start value."""
    return np.array([start]) if stop is None else np.arange(start, stop + 0.002, step)


class LineScan:
    """Class to enable scanning a Hall probe along a line in a given direction."""

    def __init__(self, axis_name, start, stop, step, hp_avgs=100, hp_range=0.1, mc=None, min_trigger_time=0.2):
        # usually would provide a motor controller instance to avoid permission errors
        self.mc = motor_controller.MotorController() if mc is None else mc
        if axis_name not in ('x', 'y', 'z'):
            raise InputError(f"can't scan along axis '{axis_name}'")
        self.axis_name = axis_name
        self.axis = self.mc.axis[axis_name]
        self.hp = hall_probe.MetrolabProbe()
        self.hp.setAverages(hp_avgs)
        self.hp.setRange(hp_range)
        self.start = start
        self.stop = stop
        self.step = step
        self.pos_values = arange(start, stop, step)
        self.n_steps = len(self.pos_values)
        self.field_values = np.zeros((len(self.pos_values), 3))
        if axis_name in ('x', 'z'):
            self.on_the_fly = True
            ad8102 = adlink_card.AdlinkCard()
            self.enc_axis = ad8102.axis['z']#axis_name]
            speed = min(self.step / min_trigger_time, self.axis.max_speed)  # set time longer if get MissedTriggerErrors
            print(f'speed = {speed:.3f} mm/s')
            self.speed = speed
            self.axis.setSpeed()  # max speed to get to start position
        else:
            self.on_the_fly = False
            self.enc_axis = None

    def run(self):
        """Move to the start position, set up triggers if necessary, and run the scan."""
        # Move to start
        self.axis.move(self.start, wait=True, tolerance=0.001)

        # Set up triggers
        self.hp.abortTrigger()
        self.hp.setTriggerSource(hall_probe.TriggerSource.BUS)
        self.hp.setTriggerCount(self.n_steps)
        self.hp.armTrigger()

        # Get the first field reading
        self.hp.probe.assert_trigger()

        if self.on_the_fly:
            self.axis.setSpeed(self.speed)
            # Set Adlink encoder position equal to that read by the McLennan motor controller
            mc_encoder_pos = self.axis.get_position(set_value=False) * self.axis.scale_factor
            # print('Z encoder position (from MC):', mc_encoder_pos)
            self.enc_axis.setPosition(mc_encoder_pos)
            # print('Encoder position (from Adlink):', self.enc_axis.getPosition())
            self.scanOnTheFly()
        else:
            self.scanPointByPoint()

        self.field_values = self.hp.getField(count=self.n_steps, fetch=True)

    def scanOnTheFly(self):
        """Run an on-the-fly scan."""
        direction_sign = np.copysign(1, self.stop - self.start)
        print('Moving to:', self.stop)
        self.axis.move(self.stop + direction_sign * 0.1)  # move a tiny bit further so we definitely hit the last trigger point

        for i, pos in enumerate(self.pos_values[1:]):
            trigger_at = pos * self.axis.scale_factor
            pos_now = self.enc_axis.getPosition()
            print(f'Waiting for position {trigger_at}, now at {pos_now}')
            if np.copysign(1, trigger_at - pos_now) != direction_sign:  # already passed the trigger!
                raise MissedTriggerError(f'Missed trigger at {trigger_at}, already at {pos_now}')
            self.enc_axis.waitForPosition(trigger_at)
            self.hp.probe.assert_trigger()

        self.axis.setSpeed()  # set back to max speed

    def scanPointByPoint(self):
        """Run a point-by-point scan."""
        for i, pos in enumerate(self.pos_values[1:]):
            print(pos)
            self.axis.move(pos, wait=True)
            self.hp.probe.assert_trigger()


if __name__ == '__main__':
    scan = LineScan('x', -10, 0, 0.5)
    scan.run()
    print(scan.field_values)
