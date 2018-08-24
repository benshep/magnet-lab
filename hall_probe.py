import visa
from enum import Enum
from typing import Union
import numpy as np


class TriggerSource(Enum):
    BUS = 'BUS'
    TIMER = 'TIM'  # TODO: add support for a timed trigger
    IMMEDIATE = 'IMM'


class OnState(Enum):
    ON = True
    OFF = False


class CommunicationError(Exception):
    """Raise upon communication failure with the probe."""


class InputError(Exception):
    """Raise when a class method has been given incorrect input."""


class MetrolabProbe:
    """This class allows communication with a Metrolab Hall probe attached to the USB port."""

    def __init__(self, resource_name='USB0::0x1BFA::0x0498::0000155::INSTR'):
        rm = visa.ResourceManager()
        self.probe = rm.open_resource(resource_name, read_termination='\n')

        # check that we are indeed talking to a Metrolab probe
        if not self.probe.manufacturer_name == 'Metrolab Technology SA':
            raise CommunicationError(f'resource at address {resource_name} is not a Metrolab probe - manufacturer is "{self.probe.manufacturer_name}"')

        # set longer timeout (default is 2s)
        self.probe.timeout = 10000

        # get range information
        ranges = self.probe.query(':SENS:ALL?;').split(',')  # ['0.1 T', '0.5 T', ... ]
        range_list, unit_list = list(zip(*[rt.split(' ') for rt in ranges]))  # separate out numbers and units
        assert len(set(unit_list)) == 1  # all units returned by this query are the same
        self.range_units = unit_list[0]
        self.ranges = sorted(tuple(float(r) for r in range_list))  # ranges is a tuple of float values

        # get unit information - what units can be used?
        unit_list = self.probe.query(':UNIT:ALL?').split(',')  # 'T,1000000,MT,1000, ...'
        self.unit_dict = dict(zip(unit_list[0::2], unit_list[1::2]))  # change to dict {'T': 1000000, 'MT': 1000, ... }

        self.getUnits()
        self.getAverages()
        self.getRange()

    def send(self, message):
        """Wrapper for sending a message to the probe when we don't expect an answer."""
        ret_bytes, ret_value = self.probe.write(message)
        if not ret_value.value == 0:
            raise CommunicationError(f'failed sending "{message}" to probe')

    def getUnits(self):
        """Find what units the probe will return."""
        self.units = self.probe.query(':UNIT?')

    def setUnits(self, unit_name: str):
        """Set the units to be used by the probe."""
        unit_name = unit_name.upper()
        if unit_name not in self.unit_dict.keys():
            raise InputError(f'bad unit: "{unit_name}"')
        self.send(':UNIT ' + unit_name)
        self.units = unit_name
        return self.units

    def getAverages(self) -> int:
        """Find out how many averages the probe will take for each reading."""
        self.averages = int(self.probe.query(':AVER:COUN?'))
        return self.averages

    def setAverages(self, averages: int):
        """Set the number of averages taken by the probe for each reading."""
        if not (isinstance(averages, int) and averages > 0):
            raise InputError(f'bad number of averages: {averages}')
        self.send(f':AVER:COUN {averages}')
        self.averages = averages

    def getRange(self):
        """Find out the sensing range of the probe."""
        on_off = self.probe.query(':SENS:AUTO?')
        if on_off not in OnState.__members__:
            raise CommunicationError(f'bad reply to auto-range query: "{on_off}"')
        self.auto_range = OnState[on_off].value  # True or False
        # this query returns (e.g.) "0.100000 T"
        range_str, units = self.probe.query(':SENS?').split(' ')
        assert units == self.range_units
        self.range = float(range_str)
        return self.auto_range, self.range

    def setRange(self, r=None):
        """Set the range used by the probe - set None for automatic ranging."""
        self.auto_range = r is None
        self.send(':SENS:AUTO ' + OnState(self.auto_range).name)
        if not self.auto_range:
            r = float(r)
            if r not in self.ranges:
                # Find the next-highest range
                try:
                    new_r = next(x for x in self.ranges if r < x)
                    print(f'Range {r} is not in allowed ranges. Using {new_r} instead.')
                    r = new_r
                except StopIteration:
                    raise InputError(f'range {r} is above maximum range {self.ranges[-1]} of probe')
            self.send(f':SENS {r:.2g}')  # ensures correct text format: 0.1, 0.5, 3, 20
            self.range = r

    def getField(self, direction='all', digits=5, count=1, fetch=False):
        """Read the field measured by the probe."""
        directions = ('X', 'Y', 'Z')
        if direction.lower() == 'all':
            return np.transpose([self.getField(d, digits, count, fetch) for d in directions])
        assert direction.upper() in directions
        assert digits in (1, 2, 3, 4, 5)
        assert isinstance(count, int) and 1 <= count <= 2048
        if fetch:  # fetch previously-gathered values
            values = self.probe.query(f':FETC:ARR:{direction}? {count},{digits}').split(',')
        else:  # just do a measurement now
            values = self.probe.query(f':READ:ARR:{direction}? {count},,{digits}').split(',')  # extra omitted argument is <expected_value>
        return [float(value.split(' ')[0]) for value in values]

    def abortTrigger(self):
        """Abort all pending triggers."""
        self.send(':ABOR')

    def setTriggerSource(self, source: Union[TriggerSource, str]):
        """Determine what the probe will trigger from."""
        if isinstance(source, str):  # IMM, TIM, or BUS
            source = TriggerSource[source]
        self.send(f':TRIG:SOUR {source.value}')

    def setTriggerCount(self, count: int):
        """Set the number of triggers expected by the probe."""
        if not (isinstance(count, int) and count > 0):
            raise InputError(f'bad trigger count: {count}')
        self.send(f':TRIG:COUN {count}')

    def armTrigger(self):
        """Start triggering the probe."""
        self.send(':INIT')  # initiate
