import serial
from time import sleep, time
import re
from typing import Union

qa_pair = re.compile(r' {2,}(?![= \-\d])')
pair_split = re.compile('[:=]')
query_params = re.compile(r'\s+([\w\s]+?) *?[=:]\s*([\w\d-]+)')
truthy_dict = {'enabled': True, 'disabled': False, 'on': True, 'off': False}
name_map = {'actual pos': 'actual position', 'command pos': 'command position', 'autoexec': 'auto execute',
            'fast jog': 'fast jog speed', 'lower limit': 'lower soft limit', 'upper limit': 'upper soft limit',
            'settling': 'settling time', 'settle time': 'settling time', 'tracking': 'tracking window'}


class OutOfRangeException(Exception):
    """Raise when the user tries to set a parameter out of range."""


class Axis:
    def __init__(self, serial_port, axis_id, scale_factor, max_speed, acceleration,
                 axis_type='linear', version='PM341'):
        """Initialise axis with some parameters."""
        self.serial_port = serial_port
        self.id = axis_id  # axis id number starting with 1
        self.scale_factor = scale_factor  # steps per mm or steps per degree
        self.max_speed = max_speed  # mm/s or deg/s
        self.acceleration = acceleration  # mm/s/s or deg/s/s
        self.type = axis_type  # 'linear' or 'rotation'
        self.units = 'mm' if type == 'linear' else 'degrees'
        self.version = version  # motor controller version
        # What prefix do we expect to see on responses? PM341: 01# etc. PM600: 10: etc. PM304: nothing
        if version == 'PM304':
            self.prefix = ''
        else:
            self.prefix = '{:02d}{}'.format(self.id, '#' if version == 'PM341' else ':')

    def talk(self, command: str, parameter: Union[str, int, float] = '',
             multi_line: bool = False, check_ok: bool = False):
        """Send a command to the motor controller and wait for a response."""
        command = command.lower()
        # Coerce floats to ints (assuming there aren't any float-type commands!)
        if isinstance(parameter, float):
            parameter = round(parameter)
        send = '{}{}{}'.format(self.id, command, parameter)
        self.serial_port.write(send.encode('utf-8') + b'\r\n')
        reply = ''
        while reply.count('\r\n') < 2:
            sleep(2 if command.lower() in ('qa', 'he', 'hc') else 0.2)  # longer for certain commands
            reply += self.serial_port.read_all().decode("utf-8")
        lines = reply.splitlines()
        if not lines[0] == send:  # check the command echo
            # maybe retry?
            raise ValueError('Incorrect command echo: sent "{}", received "{}"'.format(send, lines[0]))
        if check_ok and not lines[1] == self.prefix + 'OK':
            raise ValueError('Error response on command "{}": received "{}"'.format(send, lines[1]))
        return lines[1:] if multi_line else lines[1]

    def get_position(self, set_value=True):  # ask for the set value by default, otherwise the read value
        """Query the motor controller for the axis position (set or read)."""
        reply = self.talk('oc' if set_value else 'oa')  # "output command", "output actual"
        # reply should begin either CP=, AP= or 01#, 02#, ...
        if self.version == 'PM304':
            prefix = 'CP=' if set_value else 'AP='
        else:
            prefix = self.prefix
        if not reply[:3] == prefix:
            raise ValueError('Bad reply from axis {}: "{}" does not begin "{}"'.format(self.id, reply, prefix))
        return int(reply[3:]) / self.scale_factor

    def move(self, position, relative=False, wait=False, tolerance=0.01, timeout=60):
        """Instruct the motor controller to move the axis by the specified amount."""
        final_pos = position + (self.get_position() if relative else 0)
        steps = int(position * self.scale_factor)
        self.talk('mr' if relative else 'ma', steps, check_ok=True)  # "move relative", "move absolute"
        if wait:
            start = time()
            sleep(0.1)
            while abs(self.get_position() - final_pos) > tolerance:
                sleep(0.1)
                if time() - start > timeout:
                    raise TimeoutError('Timed out waiting for axis {} to reach position {}'.format(self.id, final_pos))
            # sleep(0.2)  # extra delay so we don't confuse the controller

    def stop(self):
        self.talk('st')  # "stop"

    def resetPosition(self, position=0):
        """Reset the command and actual positions to the value specified."""
        steps = int(position * self.scale_factor)
        self.talk('cp', steps, check_ok=True)  # "command position"
        self.talk('ap', steps, check_ok=True)  # "actual position"

    def setLimits(self, limits=None):
        """Set soft limits, or instruct the controller to ignore them."""
        if limits is None:  # turn limits off
            if self.version == 'PM600':  # can't disable limits - just set them really big
                limits = (-9999999, 9999999)
            else:
                self.talk('il', check_ok=True)  # "inhibit limits"
                return
        lower_limit = min(limits) * self.scale_factor
        upper_limit = max(limits) * self.scale_factor
        if not self.version == 'PM600':
            self.talk('al', check_ok=True)  # "allow limits"
        self.talk('ll', lower_limit, check_ok=True)  # "lower limit"
        self.talk('ul', upper_limit, check_ok=True)  # "upper limit"

    def getSpeed(self):
        """Return the slew speed."""
        return self.queryAll()['slew speed'] / self.scale_factor

    def setSpeed(self, speed=None):
        """Set the slew speed; the default None sets the maximum speed."""
        if speed is None:
            speed = self.max_speed
        elif speed > self.max_speed:
            raise OutOfRangeException(f'Requested speed {speed} mm/s is higher than maximum {self.max_speed} mm/s.')
        self.talk('sv', speed * self.scale_factor, check_ok=True)

    def queryAll(self):
        """Query all axis parameters and return the result as a dict."""
        reply = self.talk('qa', multi_line=True)  # "query all"
        output_dict = {}
        for line in reply[1:]:  # skip the first line
            pairs = qa_pair.split(line.strip())  # split the line into pairs of params (usu 2 but can be more)
            for pair in pairs:
                pair_array = pair_split.split(pair)
                if len(pair_array) < 2:  # no "=" or ":" found
                    pair_array = pair.rsplit(' ', maxsplit=1)  # Use only the last word as the value, and the rest as the name
                name = pair_array[0].strip().lower()  # use lowercase names in the dict
                try:
                    name = name_map[name]  # try to standardise names across MC versions
                except KeyError:
                    pass  # no translation? just use the name as provided
                value = pair_array[1].strip()
                try:
                    base = 2 if name in ('read port', 'last write') else 10  # these two are binary values
                    out_value = int(value, base)  # try to interpret as an integer
                except ValueError:
                    try:
                        out_value = truthy_dict[value.lower()]  # try to interpret Enabled/Disabled/On/Off as True/False
                    except KeyError:
                        out_value = value.lower()  # just use the string value
                output_dict[name] = out_value
        return output_dict

    def getLimits(self):
        """Return the soft limits, or None if they are off."""
        qa = self.queryAll()
        # can't turn limits off on PM600
        if self.version == 'PM600' or qa['soft limits']:
            return qa['lower soft limit'] / self.scale_factor, qa['upper soft limit'] / self.scale_factor
        else:
            return None

# Define the interface to the McLennan motor controller


class MotorController:
    def __init__(self):
        serial_port = serial.Serial()
        self.serial_port = serial_port
        serial_port.port = 'COM1'
        serial_port.bytesize = 7
        serial_port.parity = serial.PARITY_EVEN
        serial_port.open()

        hpx = Axis(serial_port, 2, 2000, 2, 0.5)
        hpy = Axis(serial_port, 1, 2000, 6, 0.75)
        hpz = Axis(serial_port, 3, 1000, 30, 10, version='PM304')

        # all lowercase
        self.axis = {'hp y': hpy, 'hp x': hpx, 'hp z': hpz, 'y': hpy, 'x': hpx, 'z': hpz,  # allow aliases for HP axes
                     'fc x2': Axis(serial_port, 4, 2000, 5, 2.5),
                     'fc y2': Axis(serial_port, 5, 2000, 3, 1.5),
                     'fc x1': Axis(serial_port, 6, 2000, 5, 2.5),
                     'fc y1': Axis(serial_port, 7, 2000, 3, 1.5),
                     'fc theta 2': Axis(serial_port, 8, 5000, 12, 30, axis_type='rotation', version='PM304'),
                     'fc theta 1': Axis(serial_port, 9, 5000, 12, 30, axis_type='rotation', version='PM304'),
                     'py': Axis(serial_port, 10, 1000, 6, 6, version='PM600'),
                     'px': Axis(serial_port, 11, 1000, 6, 6, version='PM600'),
                     'fc z2': Axis(serial_port, 12, 1000, 6, 2, version='PM600')}

    def close(self):
        """Close the serial port - we're finished with it."""
        self.serial_port.close()

    def __del__(self):
        self.close()
